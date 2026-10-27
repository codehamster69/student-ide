"""One lab, one sitting: the student opens a lab once and moves between its
questions. Each question visited is still its own session (so the detector,
review timeline and competitions see what they always saw), linked by a
sitting id; code carries over to the next sitting; time spent on another
question is not a pause."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.detector.features import PAUSE_MS, streams, window_features

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}
SITTING = "a1b2c3d4e5f60718"


def ev(seq, type_, data, t):
    return {"seq": seq, "t": float(t), "type": type_, "data": data}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "s.sqlite3", admin_token=TOKEN, serve_frontend=False))


def open_lab(c):
    lab = c.post("/api/teach/labs", json={"title": "Strings"}, headers=ADMIN).json()
    for t in ("Armstrong", "Perfect", "Binary"):
        lab = c.post(f"/api/teach/labs/{lab['id']}/questions", headers=ADMIN,
                     json={"title": t, "prompt": t, "starter_code": "# start\n", "sample_input": ""}).json()
    c.put(f"/api/teach/labs/{lab['id']}/roster", json={"student_ids": ["S1"]}, headers=ADMIN)
    c.patch(f"/api/teach/labs/{lab['id']}", json={"status": "open"}, headers=ADMIN)
    c.post("/api/consent", json={"student_id": "S1"})
    return lab


def start(c, qid, sitting=SITTING):
    r = c.post("/api/sessions", json={"student_id": "S1", "question_id": qid, "sitting_id": sitting})
    assert r.status_code == 200, r.text
    return r.json()


def test_questions_of_one_sitting_are_linked_sessions(client):
    lab = open_lab(client)
    q1, q2 = (q["id"] for q in lab["questions"][:2])
    a, b = start(client, q1), start(client, q2)
    assert a["sitting_id"] == b["sitting_id"] == SITTING and a["session_id"] != b["session_id"]
    assert a["resume_code"] is None  # first visit: the starter code
    rows = {r["id"]: r for r in client.get("/api/sessions", headers=ADMIN).json()}
    assert rows[a["session_id"]]["sitting_id"] == SITTING and rows[b["session_id"]]["task_id"] == q2
    assert client.get(f"/api/review/sessions/{a['session_id']}", headers=ADMIN).status_code == 200
    summary = client.get("/api/review/sessions", headers=ADMIN).json()
    assert {s["sitting_id"] for s in summary} == {SITTING}


def test_bad_sitting_id_is_refused(client):
    lab = open_lab(client)
    r = client.post("/api/sessions", json={"student_id": "S1", "question_id": lab["questions"][0]["id"],
                                           "sitting_id": "x; drop"})
    assert r.status_code == 422


def test_code_carries_over_to_the_next_sitting(client):
    lab = open_lab(client)
    qid = lab["questions"][0]["id"]
    sid = start(client, qid)["session_id"]
    client.post(f"/api/sessions/{sid}/events", json={"schema_version": 1, "events": [
        ev(0, "snapshot", {"reason": "start", "text": "# start\n"}, 0),
        ev(1, "edit", {"origin": "input.type", "changes": [[8, 8, "n = 153\n"]], "len_before": 8, "len_after": 16}, 500),
        ev(2, "focus", {"target": "question", "state": "out"}, 900),
        ev(3, "session_end", {"wall_clock_ms": 1, "reason": "pagehide"}, 1000),
    ]})
    again = start(client, qid, "fffeeedddccc0001")
    assert again["resume_code"] == "# start\nn = 153\n"
    # another question, never typed in, still starts from its starter code
    assert start(client, lab["questions"][1]["id"], "fffeeedddccc0001")["resume_code"] is None


def test_question_switch_is_not_a_pause():
    def keys(ts):
        out, seq = [], 0
        for t in ts:
            out.append(ev(seq, "key", {"action": "down", "code": "KeyA", "cls": "letter", "shift": False}, t))
            seq += 1
        return out, seq
    ts = list(np.arange(0, 6000, 150)) + list(np.arange(20000, 26000, 150))  # 14 s gap in the middle
    base, seq = keys(ts)
    end = [ev(seq + 2, "session_end", {"wall_clock_ms": 1, "reason": "submit"}, 30000)]

    def features(extra):
        evs = sorted([ev(0, "snapshot", {"reason": "start", "text": ""}, 0)] + base + extra + end, key=lambda e: e["t"])
        return window_features(streams(evs), 30)
    plain = features([])
    switched = features([ev(seq, "focus", {"target": "question", "state": "out"}, 6500),
                         ev(seq + 1, "focus", {"target": "question", "state": "in"}, 19000)])
    assert plain[0]["pause_per_100"] > 0  # the gap counts as a pause when the student just sat there
    assert switched[0]["pause_per_100"] == 0  # but not when they were working on another question
    assert switched[0]["focus_out_rate"] == 0  # and switching is not looking away
    assert PAUSE_MS < 14000


def test_live_class_view_follows_the_question_on_screen(client):
    lab = open_lab(client)
    q1, q2 = (q["id"] for q in lab["questions"][:2])
    a = start(client, q1)["session_id"]
    b = start(client, q2)["session_id"]  # newest session
    client.post(f"/api/sessions/{b}/events", json={"schema_version": 1, "events": [
        ev(0, "focus", {"target": "question", "state": "out"}, 100)]})
    client.get(f"/api/sessions/{b}/viewers")
    client.get(f"/api/sessions/{a}/viewers")  # back on question 1: only the question on screen polls
    row = client.get(f"/api/live/labs/{lab['id']}", headers=ADMIN).json()["students"][0]
    assert row["question_id"] == q1 and row["session_id"] == a
    # leaving question 2 for question 1 is not "away from the IDE"
    client.get(f"/api/sessions/{b}/viewers")
    row = client.get(f"/api/live/labs/{lab['id']}", headers=ADMIN).json()["students"][0]
    assert row["session_id"] == b and row["tab_away"] is False

"""Conversation outcomes: staff note what came of talking about a review moment.

Staff-only, never shown to students, never read by the detector, and counted
for the thesis only as aggregates on the dev split."""

import pytest
from fastapi.testclient import TestClient

from studentide import pilot
from studentide.app import create_app
from studentide.db import Database
from studentide.retention import erase_student
from studentide.review import OUTCOMES, attach_outcomes
from studentide.seed import seed

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    path = tmp_path_factory.mktemp("outcomes") / "demo.sqlite3"
    seed(Database(path), n_students=4, minutes=20, log=lambda *_: None)
    return path


@pytest.fixture(scope="module")
def client(seeded):
    c = TestClient(create_app(seeded, admin_token=TOKEN, serve_frontend=False))
    c.app.state.reviewer.fresh_s = 0
    return c


def _with_moment(client) -> tuple[str, dict]:
    rows = client.get("/api/review/sessions", headers=ADMIN).json()
    r = next(r for r in rows if r["episodes"])
    return r["id"], r["episodes"][0]


def test_note_shows_on_its_moment_and_clears(client):
    sid, ep = _with_moment(client)
    before = client.get(f"/api/review/sessions/{sid}", headers=ADMIN).json()
    assert before["episodes"][0]["outcome"] is None and before["other_outcomes"] == []
    body = {"channel": ep["channel"], "start_s": ep["switch_est"], "outcome": "had_help"}
    assert client.put(f"/api/review/sessions/{sid}/outcome", json=body, headers=ADMIN).status_code == 200
    after = client.get(f"/api/review/sessions/{sid}", headers=ADMIN).json()
    assert after["episodes"][0]["outcome"] == "had_help"
    # the summary list carries it too, and a second tap replaces the first
    body["outcome"] = "own_work"
    client.put(f"/api/review/sessions/{sid}/outcome", json=body, headers=ADMIN)
    summ = next(r for r in client.get("/api/review/sessions", headers=ADMIN).json() if r["id"] == sid)
    assert summ["episodes"][0]["outcome"] == "own_work"
    body["outcome"] = None
    client.put(f"/api/review/sessions/{sid}/outcome", json=body, headers=ADMIN)
    assert client.get(f"/api/review/sessions/{sid}", headers=ADMIN).json()["episodes"][0]["outcome"] is None


def test_the_detector_never_reads_a_note(client):
    sid, ep = _with_moment(client)
    strip = lambda r: {k: v for k, v in r.items() if k != "other_outcomes"} | {  # noqa: E731
        "episodes": [{k: v for k, v in e.items() if k != "outcome"} for e in r["episodes"]]}
    before = strip(client.get(f"/api/review/sessions/{sid}", headers=ADMIN).json())
    client.put(f"/api/review/sessions/{sid}/outcome", headers=ADMIN,
               json={"channel": ep["channel"], "start_s": ep["switch_est"], "outcome": "copied"})
    after = strip(client.get(f"/api/review/sessions/{sid}", headers=ADMIN).json())
    assert after == before


def test_bad_values_and_access(client, seeded):
    sid, ep = _with_moment(client)
    url = f"/api/review/sessions/{sid}/outcome"
    ok = {"channel": ep["channel"], "start_s": ep["switch_est"], "outcome": "own_work"}
    assert client.put(url, json={**ok, "outcome": "cheated"}, headers=ADMIN).status_code == 422
    assert client.put(url, json={**ok, "channel": "nope"}, headers=ADMIN).status_code == 422
    assert client.put(url, json=ok).status_code == 401  # no staff token: students cannot write or read notes
    assert client.put("/api/review/sessions/nope/outcome", json=ok, headers=ADMIN).status_code == 404


def test_note_on_a_moment_no_longer_shown_is_kept():
    eps = [{"channel": "identity", "switch_est": 120.04}]
    notes = [{"channel": "identity", "start_s": 120.0, "outcome": "own_work"},
             {"channel": "process", "start_s": 400.0, "outcome": "not_discussed"}]
    other = attach_outcomes(eps, notes)
    assert eps[0]["outcome"] == "own_work" and [n["channel"] for n in other] == ["process"]
    assert list(OUTCOMES) == ["own_work", "had_help", "copied", "not_discussed"]


def test_erasing_a_student_erases_their_notes(tmp_path):
    path = tmp_path / "e.sqlite3"
    db = Database(path)
    seed(db, n_students=2, minutes=2, log=lambda *_: None)
    with db.connect() as conn:
        sid = conn.execute("SELECT id FROM sessions WHERE student_id = 'DEMO01'").fetchone()[0]
    db.set_moment_outcome(sid, "identity", 60.0, "had_help")
    n = erase_student(db, "DEMO01")
    assert n["moment_outcomes"] == 1 and db.moment_outcomes(sid) == []


def test_pilot_counts_outcomes_on_the_dev_split_only(tmp_path):
    path = tmp_path / "p.sqlite3"
    db = Database(path)
    seed(db, n_students=4, minutes=2, log=lambda *_: None)
    with db.connect() as conn:
        rows = conn.execute("SELECT id, student_id, started_at FROM sessions ORDER BY started_at").fetchall()
    cut = rows[len(rows) // 2]["started_at"]  # everything from here on is held out, as from 24 Nov on the pilot
    want = {"identity": {o: 0 for o in OUTCOMES}, "process": {o: 0 for o in OUTCOMES}}
    for i, r in enumerate(rows):
        ch, oc = ("identity", "process")[i % 2], list(OUTCOMES)[i % 4]
        db.set_moment_outcome(r["id"], ch, 30.0 * i, oc)
        if r["started_at"] < cut and pilot.pilot_split(r["student_id"], 0.0) == "dev":
            want[ch][oc] += 1
    c = pilot.outcome_counts(str(path), test_from=cut)
    n = sum(sum(v.values()) for v in want.values())
    assert 0 < n < len(rows) and c["n_notes"] == n and c["held_out"] == len(rows) - n
    assert {ch: c["by_channel"].get(ch, {o: 0 for o in OUTCOMES}) for ch in want} == want
    assert sum(c["by_outcome"].values()) == n and set(c["by_outcome"]) == set(OUTCOMES)
    assert "DEMO0" not in str(c)  # numbers only
    assert "Had help" in pilot.outcome_summary(c) and "\\begin{tabular}" in pilot.outcome_table(c)
    assert pilot.OUTCOME_ORDER == tuple(OUTCOMES)

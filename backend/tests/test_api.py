import pytest
from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.replay import ReplayError, final_text, replay

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "t.sqlite3", admin_token=TOKEN, serve_frontend=False)
    return TestClient(app)


def start(client, student="PG25CS07", task="free"):
    client.post("/api/consent", json={"student_id": student})
    r = client.post("/api/sessions", json={"student_id": student, "task_id": task, "client_meta": {"ua": "pytest"}})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def edit(seq, t, changes, before, after, origin="input.type"):
    return {"seq": seq, "t": t, "type": "edit",
            "data": {"origin": origin, "changes": changes, "len_before": before, "len_after": after}}


def key(seq, t, action, code="KeyA", cls="letter"):
    return {"seq": seq, "t": t, "type": "key", "data": {"action": action, "code": code, "cls": cls}}


def test_consent_is_required(client):
    assert client.post("/api/login", json={"student_id": "s1"}).json() == {"student_id": "s1", "consented": False}
    r = client.post("/api/sessions", json={"student_id": "s1", "task_id": "free"})
    assert r.status_code == 403
    client.post("/api/consent", json={"student_id": "s1"})
    assert client.post("/api/login", json={"student_id": "s1"}).json()["consented"] is True


def test_bad_student_id(client):
    assert client.post("/api/login", json={"student_id": "../etc"}).status_code == 400


def test_ingest_is_idempotent_and_ordered(client):
    sid = start(client)
    url = f"/api/sessions/{sid}/events"
    batch = [key(0, 1.5, "down"), key(1, 80.25, "up"), key(2, 120.0, "down", "KeyB")]
    r = client.post(url, json={"schema_version": 1, "events": batch})
    assert r.json()["inserted"] == 3
    # retry of an overlapping batch only adds the new event
    r = client.post(url, json={"schema_version": 1, "events": batch[1:] + [key(3, 190.0, "up", "KeyB")]})
    assert r.json()["inserted"] == 1 and r.json()["max_seq"] == 3
    events = client.get(url, headers=ADMIN).json()
    assert [e["seq"] for e in events] == [0, 1, 2, 3]
    assert events[1]["t"] == 80.25 and events[1]["data"]["shift"] is False


def test_bad_events_rejected_individually(client):
    sid = start(client)
    batch = [
        key(0, 1.0, "down"),
        {"seq": 1, "t": 2.0, "type": "key", "data": {"action": "sideways", "code": "KeyA", "cls": "letter"}},
        edit(2, 3.0, [[0, 5, "x"]], 2, 1),  # range past end of document
        {"seq": 3, "t": 4.0, "type": "nonsense", "data": {}},
    ]
    r = client.post(f"/api/sessions/{sid}/events", json={"events": batch}).json()
    assert r["inserted"] == 1
    assert [x["seq"] for x in r["rejected"]] == [1, 2, 3]


def test_beacon_text_plain_body(client):
    sid = start(client)
    body = '{"schema_version":1,"events":[{"seq":0,"t":0,"type":"session_end","data":{"wall_clock_ms":1,"reason":"pagehide"}}]}'
    r = client.post(f"/api/sessions/{sid}/events", content=body, headers={"Content-Type": "text/plain"})
    assert r.json()["inserted"] == 1
    s = client.get("/api/sessions", headers=ADMIN).json()[0]
    assert s["end_reason"] == "pagehide" and s["ended_at"] is not None


def test_unknown_session(client):
    assert client.post("/api/sessions/nope/events", json={"events": []}).status_code == 404


def test_research_endpoints_need_token(client, tmp_path):
    assert client.get("/api/sessions").status_code == 401
    closed = TestClient(create_app(tmp_path / "c.sqlite3", admin_token="", serve_frontend=False))
    assert closed.get("/api/sessions", headers=ADMIN).status_code == 403


def test_run_records_result(client):
    sid = start(client)
    r = client.post(f"/api/sessions/{sid}/run", json={"code": "n = int(input())\nprint(n * 2)\n", "stdin": "21"}).json()
    assert r["stdout"] == "42\n" and r["exit_code"] == 0 and r["error_type"] is None
    r = client.post(f"/api/sessions/{sid}/run", json={"code": "print(1/0)"}).json()
    assert r["error_type"] == "ZeroDivisionError"
    runs = client.get(f"/api/sessions/{sid}/runs", headers=ADMIN).json()
    assert len(runs) == 2 and runs[0]["stdin"] == "21"


def test_replay_matches_snapshots():
    events = [
        {"seq": 0, "t": 0, "type": "snapshot", "data": {"reason": "start", "text": "x = 1\n"}},
        edit(1, 10, [[6, 6, "print(x)"]], 6, 14),
        edit(2, 20, [[0, 1, "y"], [12, 13, "y"]], 14, 14, "input.replace"),  # two ranges in one edit
        edit(3, 30, [[6, 14, ""]], 14, 6, "delete.backward"),
        edit(4, 40, [[6, 6, "print(y)\nprint('é✓')"]], 6, 26, "input.paste"),
        {"seq": 5, "t": 50, "type": "snapshot", "data": {"reason": "end", "text": "y = 1\nprint(y)\nprint('é✓')"}},
    ]
    assert final_text(events) == "y = 1\nprint(y)\nprint('é✓')"
    # emoji take two UTF-16 units, like CodeMirror offsets
    emoji = [events[0], edit(1, 1, [[0, 0, "🙂"]], 6, 8), edit(2, 2, [[2, 3, "z"]], 8, 8)]
    assert final_text(emoji) == "🙂z = 1\n"

    events[-1]["data"]["text"] = "something else"
    with pytest.raises(ReplayError):
        list(replay(events))

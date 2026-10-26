"""Raw keystrokes are deleted once due, and the review screen still works
from the stored window summaries."""

import time

from studentide import retention
from studentide.db import Database
from studentide.review import Reviewer, load_settings
from studentide.seed import WEEK, seed


def _n_keys(db, sid):
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM events WHERE session_id = ? AND type = 'key'", (sid,)).fetchone()[0]


def test_purge_keeps_scores_and_deletes_keys(tmp_path):
    db = Database(tmp_path / "r.sqlite3")
    retention.ensure_schema(db)
    t0 = (time.time() - 6 * WEEK) // 86400 * 86400
    seed(db, n_students=3, minutes=12, log=lambda *_: None, start=t0)
    sessions = db.list_sessions()
    lengths = list(load_settings().window_s.values())

    # in week 6 the baseline weeks (1-4) are due, weeks 5-6 are not yet 28 days old
    due = {d["id"]: d["reason"] for d in retention.due(db)}
    by_week = {s["id"]: int((s["started_at"] - t0) // WEEK) for s in sessions}
    assert due and all(by_week[i] < 4 and r == "baseline built" for i, r in due.items())
    assert all(by_week[s["id"]] >= 4 for s in sessions if s["id"] not in due)

    before = {s["id"]: Reviewer(db).summary(s["id"]) for s in sessions}
    done = retention.purge(db, lengths)
    assert {d["session_id"] for d in done} == set(due) and all(d["deleted_keys"] > 0 for d in done)
    assert all(_n_keys(db, i) == 0 for i in due)
    assert retention.due(db) == []  # nothing left to do

    after = {s["id"]: Reviewer(db).summary(s["id"]) for s in db.list_sessions()}
    for sid, b in before.items():
        a = after[sid]
        assert a["baseline"] == b["baseline"] and a["peak"] == b["peak"] and a["episodes"] == b["episodes"], sid

    # later, every session is past the retention period
    later = retention.purge(db, lengths, now=time.time() + 60 * 86400)
    assert {d["session_id"] for d in later} == {s["id"] for s in sessions} - set(due)


def test_open_sessions_are_left_alone(tmp_path):
    db = Database(tmp_path / "o.sqlite3")
    retention.ensure_schema(db)
    db.get_or_create_student("S1")
    db.create_session("live", "S1", "free", 1, {})
    db.insert_events("live", [{"seq": 0, "t": 1.0, "type": "key", "data": {"action": "down", "code": "KeyA", "cls": "letter"}}])
    assert retention.due(db, now=time.time() + 3600, days=0) == []
    assert [d["id"] for d in retention.due(db, now=time.time() + 2 * 86400, days=0)] == ["live"]


def test_enabled_by_mode(monkeypatch):
    monkeypatch.delenv("STUDENTIDE_PURGE", raising=False)
    monkeypatch.delenv("STUDENTIDE_GOOGLE_CLIENT_ID", raising=False)
    assert not retention.enabled()
    monkeypatch.setenv("STUDENTIDE_GOOGLE_CLIENT_ID", "x")
    assert retention.enabled()
    monkeypatch.setenv("STUDENTIDE_PURGE", "off")
    assert not retention.enabled()


def test_erase_student(tmp_path):
    from fastapi.testclient import TestClient
    from studentide.app import create_app
    from studentide.auth import Config

    path = tmp_path / "e.sqlite3"
    cfg = Config(client_id="x", secure_cookie=False)
    verify = lambda c: {"email": c, "email_verified": True, "hd": "iiitsurat.ac.in"}
    c = TestClient(create_app(path, serve_frontend=False, auth_config=cfg, verify_google=verify))
    for who in ("PG25CS07", "PG25CS08"):
        c.post("/api/auth/google", json={"credential": f"{who.lower()}@iiitsurat.ac.in"})
        c.post("/api/consent", json={"student_id": who})
        sid = c.post("/api/sessions", json={"student_id": who, "task_id": "free"}).json()["session_id"]
        c.post(f"/api/sessions/{sid}/events", json={"schema_version": 1, "events": [
            {"seq": 0, "t": 1.0, "type": "key", "data": {"action": "down", "code": "KeyA", "cls": "letter"}}]})
        c.post(f"/api/sessions/{sid}/run", json={"code": "print(1)"})
    db = Database(path)
    n = retention.erase_student(db, "PG25CS07")
    assert n["sessions"] == 1 and n["events"] == 1 and n["runs"] == 1 and n["users"] == 1 and n["students"] == 1
    assert [s["student_id"] for s in db.list_sessions()] == ["PG25CS08"]
    assert [s["id"] for s in db.list_students()] == ["PG25CS08"]

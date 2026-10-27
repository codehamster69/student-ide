"""Live classroom view: the class grid, the read-only editor view, and that
students are always told when a teacher is watching."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.auth import Config
from studentide.live import VIEW_TTL_S

from test_auth import DOMAIN, fake_google, sign_in

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}


def ev(seq, type_, data, t=None):
    return {"seq": seq, "t": float(t if t is not None else seq * 100), "type": type_, "data": data}


def open_lab(c, headers=None, roster=("S1", "S2", "S3")):
    h = headers or {}
    lab = c.post("/api/teach/labs", json={"title": "Lab 4: loops"}, headers=h).json()
    lab = c.post(f"/api/teach/labs/{lab['id']}/questions", headers=h,
                 json={"title": "Sum to n", "prompt": "Print 1+...+n", "starter_code": "", "sample_input": "3"}).json()
    c.put(f"/api/teach/labs/{lab['id']}/roster", json={"student_ids": list(roster)}, headers=h)
    c.patch(f"/api/teach/labs/{lab['id']}", json={"status": "open"}, headers=h)
    return lab


def start(c, sid, question_id):
    c.post("/api/consent", json={"student_id": sid})
    return c.post("/api/sessions", json={"student_id": sid, "question_id": question_id}).json()["session_id"]


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "l.sqlite3", admin_token=TOKEN, serve_frontend=False))


def test_class_view_and_editor_view(client):
    lab = open_lab(client, ADMIN)
    qid = lab["questions"][0]["id"]
    s1 = start(client, "S1", qid)
    events = [ev(0, "snapshot", {"reason": "start", "text": ""}),
              ev(1, "edit", {"origin": "input.type", "changes": [[0, 0, "n = int(input())\n"]], "len_before": 0, "len_after": 17}),
              ev(2, "edit", {"origin": "input.paste", "changes": [[17, 17, "print(n * (n + 1) // 2)\n"]],
                             "len_before": 17, "len_after": 41}),
              ev(3, "clipboard", {"action": "paste", "length": 24, "lines": 1, "text": "print(n * (n + 1) // 2)\n"}),
              ev(4, "focus", {"target": "window", "state": "out"})]
    assert client.post(f"/api/sessions/{s1}/events", json={"schema_version": 1, "events": events}).json()["rejected"] == []
    client.post(f"/api/sessions/{s1}/run", json={"code": "n = int(input())\nprint(n)\n", "stdin": "3"})

    # teacher endpoints need the teacher's credentials
    assert client.get(f"/api/live/labs/{lab['id']}").status_code == 401
    assert [l["id"] for l in client.get("/api/live/labs", headers=ADMIN).json()] == [lab["id"]]

    # the IDE has not polled yet, so S1 is not connected
    view = client.get(f"/api/live/labs/{lab['id']}", headers=ADMIN).json()
    rows = {r["student_id"]: r for r in view["students"]}
    assert set(rows) == {"S1", "S2", "S3"}
    assert rows["S2"]["state"] == "not_started" and rows["S2"]["session_id"] is None
    assert rows["S1"]["state"] == "offline"
    assert rows["S1"]["question_title"] == "Sum to n" and rows["S1"]["pastes"] == 1 and rows["S1"]["runs"] == 1
    assert rows["S1"]["last_run"]["ok"] is True and sum(rows["S1"]["activity"]) == 2

    # once the IDE polls it is online; the window is in the background, so "away"
    seen = client.get(f"/api/sessions/{s1}/viewers").json()
    assert seen["class_view"] is True and seen["editor"] == []  # the class view above is still open
    rows = {r["student_id"]: r for r in client.get(f"/api/live/labs/{lab['id']}", headers=ADMIN).json()["students"]}
    assert rows["S1"]["state"] == "away"
    client.post(f"/api/sessions/{s1}/events", json={"schema_version": 1, "events": [ev(5, "focus", {"target": "window", "state": "in"})]})
    rows = {r["student_id"]: r for r in client.get(f"/api/live/labs/{lab['id']}", headers=ADMIN).json()["students"]}
    assert rows["S1"]["state"] == "typing"

    # the editor view rebuilds the code from the edits, and the student is told
    ed = client.get(f"/api/live/sessions/{s1}", headers=ADMIN).json()
    assert ed["text"] == "n = int(input())\nprint(n * (n + 1) // 2)\n" and ed["caret"] == 41
    assert ed["runs"][0]["stdout"] == "3\n" and ed["session"]["question_title"] == "Sum to n"
    assert client.get(f"/api/sessions/{s1}/viewers").json()["editor"] == [{"name": "Your teacher"}]

    # new edits arrive incrementally
    client.post(f"/api/sessions/{s1}/events", json={"schema_version": 1, "events": [
        ev(6, "edit", {"origin": "delete.backward", "changes": [[40, 41, ""]], "len_before": 41, "len_after": 40})]})
    assert client.get(f"/api/live/sessions/{s1}", headers=ADMIN).json()["text"] == "n = int(input())\nprint(n * (n + 1) // 2)"

    # leaving ends the banner at once, and every view stays in the log
    client.delete(f"/api/live/views?session_id={s1}", headers=ADMIN)
    client.delete(f"/api/live/views?lab_id={lab['id']}", headers=ADMIN)
    assert client.get(f"/api/sessions/{s1}/viewers").json() | {"live": None} == {"class_view": False, "editor": [], "live": None}
    with sqlite3.connect(client.app.state.db.path) as conn:
        log = conn.execute("SELECT viewer, lab_id, session_id, student_id, last_seen - started_at FROM live_views").fetchall()
    assert {(v, l, s, st) for v, l, s, st, _ in log} == {("admin-token", lab["id"], None, None), ("admin-token", lab["id"], s1, "S1")}


def test_view_spans_merge_and_time_out(client):
    lab = open_lab(client, ADMIN)
    db = client.app.state.db
    for _ in range(3):
        client.get(f"/api/live/labs/{lab['id']}", headers=ADMIN)
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM live_views").fetchone()[0] == 1
        conn.execute("UPDATE live_views SET last_seen = last_seen - ?", (VIEW_TTL_S + 1,))
    client.get(f"/api/live/labs/{lab['id']}", headers=ADMIN)
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM live_views").fetchone()[0] == 2  # a new span after a gap


def test_live_modes(tmp_path):
    c = TestClient(create_app(tmp_path / "m.sqlite3", admin_token=TOKEN, serve_frontend=False, live_mode="class"))
    lab = open_lab(c, ADMIN)
    s1 = start(c, "S1", lab["questions"][0]["id"])
    assert c.get(f"/api/live/labs/{lab['id']}", headers=ADMIN).json()["editor_view"] is False
    assert c.get(f"/api/live/sessions/{s1}", headers=ADMIN).status_code == 403
    assert c.get(f"/api/sessions/{s1}/viewers").json()["live"] == "class"

    off = TestClient(create_app(tmp_path / "o.sqlite3", admin_token=TOKEN, serve_frontend=False, live_mode="off"))
    assert off.get("/api/live/labs", headers=ADMIN).status_code == 403


def test_old_consent_must_be_renewed(client):
    db = client.app.state.db
    db.get_or_create_student("S9")
    with db.connect() as conn:  # agreed before live viewing existed
        conn.execute("UPDATE students SET consented_at = 1, consent_version = NULL WHERE id = 'S9'")
    assert client.post("/api/login", json={"student_id": "S9"}).json()["consented"] is False
    assert client.post("/api/sessions", json={"student_id": "S9", "task_id": "free"}).status_code == 403
    client.post("/api/consent", json={"student_id": "S9"})
    row = db.get_or_create_student("S9")
    assert row["consent_version"] == 2 and row["consented_at"] > 1
    assert client.post("/api/login", json={"student_id": "S9"}).json()["consented"] is True


def test_google_mode_names_the_teacher_and_guards_students(tmp_path):
    cfg = Config(client_id="test-client", secure_cookie=False)
    app = create_app(tmp_path / "g.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google)
    teacher = sign_in(app, "meera.shah@" + DOMAIN)
    lab = open_lab(teacher, roster=("PG25CS07",))
    student = sign_in(app, "pg25cs07@" + DOMAIN)
    s1 = start(student, "PG25CS07", lab["questions"][0]["id"])

    assert student.get(f"/api/live/sessions/{s1}").status_code == 403       # students never watch
    assert sign_in(app, "pg25cs08@" + DOMAIN).get(f"/api/sessions/{s1}/viewers").status_code == 403
    assert teacher.get(f"/api/live/sessions/{s1}").status_code == 200
    assert student.get(f"/api/sessions/{s1}/viewers").json()["editor"] == [{"name": "meera.shah"}]

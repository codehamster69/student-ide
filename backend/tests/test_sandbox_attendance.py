"""Sandbox Labs attendance and consent v3: terminal typing counts toward the typed-characters rule,
desktop Run/Check presses count as runs, closing a sandbox lab sends attendance, and Sandbox Labs need
the v3 consent while web labs keep v2. Also: attendance tables accept Sandbox Lab ids on old databases."""

import sqlite3
import uuid

from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.db import has_consent, has_sandbox_consent

from test_attendance import ADMIN, KEY_A, TOKEN, FakeRollCall, today
from test_live import ev


def sandbox_lab(c):
    s = c.post("/api/sandbox/subjects", json={"title": "Operating Systems", "code": "CS301", "recipe": {"base": "linux"}}, headers=ADMIN).json()
    lab = c.post(f"/api/sandbox/subjects/{s['id']}/labs", json={"title": "Shell basics"}, headers=ADMIN).json()
    lab = c.post(f"/api/sandbox/labs/{lab['id']}/assignments", headers=ADMIN, json={
        "title": "Part 1", "statement": "Do it.", "files": [{"path": "main.c", "content": "int main(void){return 0;}\n"}],
        "open": ["main.c"], "run": "cc main.c && ./a.out"}).json()
    return lab


def sandbox_session(app, student, lab):
    """A recorded sandbox session, as the student app's POST /api/sessions makes it (lab_id = sbx lab, question = assignment)."""
    sid = uuid.uuid4().hex
    a = lab["definition"]["assignments"][0]
    app.state.db.get_or_create_student(student)
    app.state.db.create_session(sid, student, a["id"], 3, {"client": {"kind": "desktop"}},
                                {"kind": "sandbox", "id": a["id"], "lab_id": lab["id"], "title": a["title"]}, "sit1")
    return sid


def terminal_work(c, sid, minutes, keys_per_minute=8):
    events, seq = [ev(0, "session_start", {"wall_clock_ms": 0}, t=0)], 1
    for m in range(minutes):
        t = m * 60_000 + 1000
        events.append(ev(seq, "term_cmd", {"term_id": "t1", "phase": "start", "command": "vim main.c", "cwd": "/home/student"}, t=t)); seq += 1
        for k in range(keys_per_minute):
            events.append(ev(seq, "key", {"action": "down", "code": "KeyA", "cls": "letter", "surface": "terminal-editor",
                                          "path": "/home/student/labs/x/main.c"}, t=t + 10 + k)); seq += 1
    events.append(ev(seq, "run", {"run_id": "t-1", "code_sha256": "a" * 64, "source": "terminal", "command": "./a.out"}, t=1500))
    r = c.post(f"/api/sessions/{sid}/events", json={"schema_version": 3, "events": events})
    assert r.json()["rejected"] == [], r.text


def test_terminal_typing_counts_and_closing_sends(tmp_path):
    rc = FakeRollCall()
    app = create_app(tmp_path / "a.sqlite3", admin_token=TOKEN, serve_frontend=False, attendance_transport=rc)
    c = TestClient(app)
    c.put("/api/teach/attendance", json={"sync_key": KEY_A}, headers=ADMIN)
    g = rc.add_class(KEY_A, "CSE", "A", "", "UG23CS", 1, 3)
    lab = sandbox_lab(c)
    r = c.put(f"/api/teach/labs/{lab['id']}/classes", json={"class_ids": [g], "add_to_roster": True}, headers=ADMIN)
    assert r.status_code == 200, r.text
    terminal_work(c, sandbox_session(app, "UG23CS001", lab), minutes=11)                  # vim only: present
    terminal_work(c, sandbox_session(app, "UG23CS002", lab), minutes=11, keys_per_minute=3)  # 33 keys: absent
    p = c.get(f"/api/teach/labs/{lab['id']}/attendance", headers=ADMIN).json()
    by = {s["student_id"]: s for cl in p["classes"] for s in cl["students"]}
    assert by["UG23CS001"]["present"] and by["UG23CS001"]["typed"] == 88 and by["UG23CS001"]["runs"] == 1
    assert by["UG23CS001"]["active_minutes"] == 11
    assert not by["UG23CS002"]["present"] and "33 of 40 typed characters" in by["UG23CS002"]["reason"]
    # closing the sandbox lab sends the day, with a link back to the sandbox lab
    c.patch(f"/api/sandbox/labs/{lab['id']}", json={"status": "published"}, headers=ADMIN)
    out = c.patch(f"/api/sandbox/labs/{lab['id']}", json={"status": "closed"}, headers=ADMIN).json()
    assert out["attendance_sent"][0]["day"] == today()
    sent = list(rc.ws[KEY_A]["sessions"].values())[0]
    assert sent["marks"] == {"UG23CS001": "P", "UG23CS002": "A", "UG23CS003": "A"}
    assert sent["source"]["url"].endswith(f"#/sandbox/labs/{lab['id']}") and sent["subject"] == "CS301 Operating Systems"


def test_old_databases_lose_the_labs_foreign_key(tmp_path):
    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE labs (id TEXT PRIMARY KEY);
        CREATE TABLE lab_attendance (lab_id TEXT PRIMARY KEY REFERENCES labs(id) ON DELETE CASCADE, rule_json TEXT NOT NULL,
                                     auto_send INTEGER NOT NULL DEFAULT 1);
        INSERT INTO labs VALUES ('L1');
        INSERT INTO lab_attendance VALUES ('L1', '{}', 1);
    """)
    conn.commit()
    conn.close()
    app = create_app(path, admin_token=TOKEN, serve_frontend=False, attendance_transport=FakeRollCall())
    with app.state.db.connect() as c:
        sql = c.execute("SELECT sql FROM sqlite_master WHERE name = 'lab_attendance'").fetchone()[0]
        assert "REFERENCES" not in sql
        assert c.execute("SELECT lab_id FROM lab_attendance").fetchall()[0][0] == "L1"
        c.execute("INSERT INTO lab_attendance VALUES ('sbx_lab', '{}', 1)")  # a Sandbox Lab id is fine now


def test_consent_v3_is_separate_from_web_consent(tmp_path):
    app = create_app(tmp_path / "c.sqlite3", admin_token=TOKEN, serve_frontend=False)
    c = TestClient(app)
    r = c.post("/api/consent", json={"student_id": "S1"}).json()
    assert r["consented"] and not r["sandbox_consented"]
    row = app.state.db.get_or_create_student("S1")
    assert has_consent(row) and not has_sandbox_consent(row)
    assert c.post("/api/consent", json={"student_id": "S1", "scope": "sandbox"}).json()["sandbox_consented"]
    # signing the web text again never takes v3 away
    c.post("/api/consent", json={"student_id": "S1"})
    assert c.post("/api/login", json={"student_id": "S1"}).json() == {"student_id": "S1", "consented": True, "sandbox_consented": True}
    assert c.post("/api/consent", json={"student_id": "S1", "scope": "other"}).status_code == 422

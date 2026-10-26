import sqlite3

import pytest
from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.db import Database

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "t.sqlite3", admin_token=TOKEN, serve_frontend=False))


def make_lab(client, title="Lab 3: strings", questions=("Reverse words",)):
    lab = client.post("/api/teach/labs", json={"title": title, "description": "week 3"}, headers=ADMIN).json()
    for t in questions:
        lab = client.post(f"/api/teach/labs/{lab['id']}/questions", headers=ADMIN,
                          json={"title": t, "prompt": f"Do {t}", "starter_code": "s = input()\n", "sample_input": "a b"}).json()
    return lab


def consent(client, sid):
    client.post("/api/consent", json={"student_id": sid})


def test_teacher_routes_need_token(client):
    assert client.get("/api/teach/labs").status_code == 401
    assert client.post("/api/teach/labs", json={"title": "x"}).status_code == 401


def test_teacher_builds_a_lab(client):
    lab = make_lab(client, questions=("One", "Two", "Three"))
    assert [q["title"] for q in lab["questions"]] == ["One", "Two", "Three"]
    assert lab["status"] == "draft" and lab["roster"] == [] and lab["everyone"] is False

    ids = [q["id"] for q in lab["questions"]]
    lab = client.put(f"/api/teach/labs/{lab['id']}/order", json={"question_ids": ids[::-1]}, headers=ADMIN).json()
    assert [q["title"] for q in lab["questions"]] == ["Three", "Two", "One"]
    assert client.put(f"/api/teach/labs/{lab['id']}/order", json={"question_ids": ids[:2]}, headers=ADMIN).status_code == 400

    lab = client.patch(f"/api/teach/questions/{ids[0]}", json={"title": "One, renamed"}, headers=ADMIN).json()
    assert lab["questions"][-1]["title"] == "One, renamed"
    lab = client.delete(f"/api/teach/questions/{ids[1]}", headers=ADMIN).json()
    assert len(lab["questions"]) == 2

    listed = client.get("/api/teach/labs", headers=ADMIN).json()
    assert listed[0]["n_questions"] == 2 and listed[0]["n_sessions"] == 0


def test_cannot_open_an_empty_lab(client):
    lab = make_lab(client, questions=())
    r = client.patch(f"/api/teach/labs/{lab['id']}", json={"status": "open"}, headers=ADMIN)
    assert r.status_code == 409


def test_students_see_only_open_assigned_labs(client):
    lab = make_lab(client)
    client.put(f"/api/teach/labs/{lab['id']}/roster", json={"student_ids": ["S1", " S2 ", "S1"]}, headers=ADMIN)
    assert client.get("/api/students/S1/labs").json() == []  # still a draft

    client.patch(f"/api/teach/labs/{lab['id']}", json={"status": "open"}, headers=ADMIN)
    mine = client.get("/api/students/S1/labs").json()
    assert [l["title"] for l in mine] == ["Lab 3: strings"]
    q = mine[0]["questions"][0]
    assert q["starter_code"] == "s = input()\n" and q["lab_title"] == "Lab 3: strings" and q["sessions"] == 0
    assert client.get("/api/students/S3/labs").json() == []

    client.put(f"/api/teach/labs/{lab['id']}/roster", json={"everyone": True}, headers=ADMIN)
    assert len(client.get("/api/students/S3/labs").json()) == 1

    client.patch(f"/api/teach/labs/{lab['id']}", json={"status": "closed"}, headers=ADMIN)
    assert client.get("/api/students/S1/labs").json() == []


def test_bad_roster_ids(client):
    lab = make_lab(client)
    r = client.put(f"/api/teach/labs/{lab['id']}/roster", json={"student_ids": ["ok", "../x"]}, headers=ADMIN)
    assert r.status_code == 400


def test_session_links_to_lab_and_question(client):
    lab = make_lab(client)
    qid = lab["questions"][0]["id"]
    client.put(f"/api/teach/labs/{lab['id']}/roster", json={"student_ids": ["S1"]}, headers=ADMIN)
    consent(client, "S1"), consent(client, "S9")

    # draft lab: not startable
    assert client.post("/api/sessions", json={"student_id": "S1", "question_id": qid}).status_code == 403
    client.patch(f"/api/teach/labs/{lab['id']}", json={"status": "open"}, headers=ADMIN)
    # not on the roster
    assert client.post("/api/sessions", json={"student_id": "S9", "question_id": qid}).status_code == 403

    r = client.post("/api/sessions", json={"student_id": "S1", "question_id": qid}).json()
    assert r["lab_id"] == lab["id"] and r["question_id"] == qid
    sid = r["session_id"]
    client.post(f"/api/sessions/{sid}/events", json={"schema_version": 1, "events": [
        {"seq": 0, "t": 0, "type": "session_start", "data": {"wall_clock_ms": 1}},
        {"seq": 1, "t": 9, "type": "session_end", "data": {"wall_clock_ms": 2, "reason": "submit"}}]})

    # the teacher edits the question afterwards; the session keeps what the student saw
    client.patch(f"/api/teach/questions/{qid}", json={"prompt": "changed"}, headers=ADMIN)
    rows = client.get(f"/api/sessions?lab_id={lab['id']}", headers=ADMIN).json()
    assert len(rows) == 1 and rows[0]["question_id"] == qid and rows[0]["task_id"] == qid
    assert rows[0]["question_json"]["prompt"] == "Do Reverse words"

    q = client.get("/api/students/S1/labs").json()[0]["questions"][0]
    assert q["sessions"] == 1 and q["submitted"] is True
    detail = client.get(f"/api/teach/labs/{lab['id']}", headers=ADMIN).json()
    assert detail["n_sessions"] == 1 and detail["progress"][0]["submitted"] is True
    assert detail["questions"][0]["n_sessions"] == 1

    # recorded work protects the lab and question from deletion
    assert client.delete(f"/api/teach/questions/{qid}", headers=ADMIN).status_code == 409
    assert client.delete(f"/api/teach/labs/{lab['id']}", headers=ADMIN).status_code == 409


def test_practice_tasks_still_work(client):
    consent(client, "S1")
    r = client.post("/api/sessions", json={"student_id": "S1", "task_id": "free"})
    assert r.status_code == 200 and r.json()["lab_id"] is None
    assert client.post("/api/sessions", json={"student_id": "S1"}).status_code == 400


def test_old_database_files_are_migrated(tmp_path):
    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript("""CREATE TABLE sessions (id TEXT PRIMARY KEY, student_id TEXT NOT NULL, task_id TEXT NOT NULL,
        started_at REAL NOT NULL, ended_at REAL, end_reason TEXT, schema_version INTEGER NOT NULL, client_meta TEXT NOT NULL);
        INSERT INTO sessions VALUES ('a', 's', 'free', 1, NULL, NULL, 1, '{}');""")
    conn.commit()
    conn.close()
    db = Database(path)
    row = db.get_session("a")
    assert row["lab_id"] is None and row["question_json"] is None

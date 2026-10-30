""""View as student": a teacher or admin opens the student side under their
own staff id. They see their own and shared labs (drafts too) and the
learning lab, and can run and check code, but nothing they do is study data:
it never reaches baselines, review, the live view, lab progress, the export
or a competition board, and it never blocks deleting a lab."""

import pytest

from studentide import export
from studentide.app import create_app
from studentide.auth import Config

from test_auth import DOMAIN, fake_google, sign_in
from test_live import ev, open_lab, start

PRIYA, MEERA, ADMIN = (f"{n}@{DOMAIN}" for n in ("priya.shah", "meera.rao", "rohan.admin"))


@pytest.fixture
def app(tmp_path):
    cfg = Config(client_id="test-client", admins=frozenset({ADMIN}), secure_cookie=False)
    return create_app(tmp_path / "p.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google)


@pytest.fixture
def world(app):
    priya, meera, admin = sign_in(app, PRIYA), sign_in(app, MEERA), sign_in(app, ADMIN)
    lab = open_lab(priya, roster=("PG25CS07",))
    draft = priya.post("/api/teach/labs", json={"title": "Next week"}).json()
    draft = priya.post(f"/api/teach/labs/{draft['id']}/questions",
                       json={"title": "Echo", "prompt": "Print the input", "starter_code": "", "sample_input": "hi",
                             "tests": [{"stdin": "hi", "expected": "hi"}]}).json()
    return priya, meera, admin, lab, draft


def me(c):
    return c.get("/api/me").json()["student_id"]


def preview_session(c, question_id=None, lesson_id=None):
    body = {"student_id": me(c)} | ({"question_id": question_id} if question_id else {"lesson_id": lesson_id})
    r = c.post("/api/sessions", json=body)
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    c.post(f"/api/sessions/{sid}/events", json={"schema_version": 1, "events": [
        ev(0, "snapshot", {"reason": "start", "text": ""}), ev(1, "edit", {"changes": [[0, 0, "print(input())"]]})]})
    return sid


def test_teacher_sees_own_labs_with_drafts_without_consent(world):
    priya, meera, admin, lab, draft = world
    assert me(priya) == "PRIYA_SHAH"
    labs = priya.get(f"/api/students/{me(priya)}/labs").json()
    assert {l["id"] for l in labs} == {lab["id"], draft["id"]}
    assert [l.get("draft", False) for l in labs if l["id"] == draft["id"]] == [True]
    assert meera.get(f"/api/students/{me(meera)}/labs").json() == []          # not her labs
    assert {l["id"] for l in admin.get(f"/api/students/{me(admin)}/labs").json()} == {lab["id"], draft["id"]}
    # no consent screen for staff, and the session runs and checks like a student's
    sid = preview_session(priya, draft["questions"][0]["id"])
    assert priya.post(f"/api/sessions/{sid}/check", json={"code": "print(input())"}).json()["passed"] == 1
    assert meera.post("/api/sessions", json={"student_id": me(meera), "question_id": lab["questions"][0]["id"]}).status_code == 403
    # still only as themselves
    assert priya.post("/api/sessions", json={"student_id": "PG25CS07", "task_id": "free"}).status_code == 403


def test_preview_sessions_are_not_study_data(world, app, tmp_path):
    priya, meera, admin, lab, draft = world
    qid = lab["questions"][0]["id"]
    sid = preview_session(priya, qid)
    lesson = preview_session(priya, lesson_id="learn:python/01-print")
    db = app.state.db
    assert {r["context"] for r in db.list_sessions(include_learn=True)} == set()
    assert db.list_sessions() == []
    for c in (priya, admin):
        assert c.get("/api/sessions").json() == [] and c.get("/api/review/sessions").json() == []
        assert c.get("/api/review/students").json() == []
        live = c.get(f"/api/live/labs/{lab['id']}").json()["students"]
        assert [s["student_id"] for s in live] == ["PG25CS07"] and live[0]["session_id"] is None
    detail = priya.get(f"/api/teach/labs/{lab['id']}").json()
    assert detail["progress"] == [] and detail["n_sessions"] == 0
    assert export.export_all(db, tmp_path / "out") == 0
    # the learning lab still marks the teacher's own progress
    learn = {l["id"]: l for t in priya.get(f"/api/learn?student_id={me(priya)}").json() for l in t["lessons"]}
    assert learn["learn:python/01-print"]["sessions"] == 1
    # previewing never blocks deleting the lab, and the preview data goes with it
    assert priya.delete(f"/api/teach/labs/{lab['id']}").status_code == 200
    assert db.get_session(sid) is None and db.get_session(lesson) is not None


def test_students_cannot_hide_their_sessions(world, app):
    priya, meera, admin, lab, draft = world
    student = sign_in(app, "pg25cs07@" + DOMAIN)
    sid = start(student, "PG25CS07", lab["questions"][0]["id"])
    assert app.state.db.get_session(sid)["context"] is None
    # a draft is never open to students
    assert student.post("/api/sessions", json={"student_id": "PG25CS07", "question_id": draft["questions"][0]["id"]}).status_code == 403


def test_competitions_stay_off_limits(world, app):
    priya, meera, admin, lab, draft = world
    comp = admin.post("/api/teach/competitions", json={"title": "Sprint", "description": "", "duration_min": 30}).json()
    lab_id = comp["lab_id"]
    q = admin.post(f"/api/teach/labs/{lab_id}/questions",
                   json={"title": "Add", "prompt": "a+b", "starter_code": "", "sample_input": "1 2",
                         "tests": [{"stdin": "1 2", "expected": "3"}]}).json()["questions"][0]
    admin.post(f"/api/teach/competitions/{lab_id}/start")
    r = admin.post(f"/api/competitions/{lab_id}/join", json={"student_id": me(admin), "handle": "rohan"})
    assert r.status_code == 403 and "class board" in r.json()["detail"]
    r = admin.post("/api/sessions", json={"student_id": me(admin), "question_id": q["id"]})
    assert r.status_code == 403 and "class board" in r.json()["detail"]

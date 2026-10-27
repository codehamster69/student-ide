"""Lab ownership: a teacher sees and manages only their own and shared labs,
and only the sessions, reviews, live views and results recorded in them.
Admins see everything; labs from before ownership belong to admins."""

import pytest

from studentide.app import create_app
from studentide.auth import Config

from test_auth import DOMAIN, fake_google, sign_in
from test_live import ev, open_lab, start

PRIYA, MEERA, ADMIN = (f"{n}@{DOMAIN}" for n in ("priya.shah", "meera.rao", "rohan.admin"))


@pytest.fixture
def app(tmp_path):
    cfg = Config(client_id="test-client", admins=frozenset({ADMIN}), secure_cookie=False)
    return create_app(tmp_path / "o.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google)


@pytest.fixture
def world(app):
    priya, meera, admin = sign_in(app, PRIYA), sign_in(app, MEERA), sign_in(app, ADMIN)
    lab = open_lab(priya, roster=("PG25CS07",))
    student = sign_in(app, "pg25cs07@" + DOMAIN)
    sid = start(student, "PG25CS07", lab["questions"][0]["id"])
    student.post(f"/api/sessions/{sid}/events", json={"schema_version": 1, "events": [
        ev(0, "session_start", {}), ev(1, "edit", {"changes": [[0, 0, "x"]]})]})
    return priya, meera, admin, lab, sid


def test_teacher_sees_only_own_labs(world):
    priya, meera, admin, lab, sid = world
    lab_id, qid = lab["id"], lab["questions"][0]["id"]
    mine = priya.get("/api/teach/labs").json()
    assert [l["id"] for l in mine] == [lab_id] and mine[0]["owner_email"] == PRIYA and mine[0]["access"] == "owner"
    assert meera.get("/api/teach/labs").json() == []
    assert admin.get("/api/teach/labs").json()[0]["access"] == "admin"

    for path in (f"/api/teach/labs/{lab_id}", f"/api/live/labs/{lab_id}", f"/api/live/sessions/{sid}",
                 f"/api/review/sessions/{sid}", f"/api/review/sessions/{sid}/replay", f"/api/sessions/{sid}/events",
                 f"/api/sessions?lab_id={lab_id}"):
        assert meera.get(path).status_code == 403, path
        assert priya.get(path).status_code == 200, path
        assert admin.get(path).status_code == 200, path
    assert meera.patch(f"/api/teach/labs/{lab_id}", json={"status": "closed"}).status_code == 403
    assert meera.patch(f"/api/teach/questions/{qid}", json={"title": "mine now"}).status_code == 403
    assert meera.post(f"/api/teach/questions/{qid}/check", json={"code": ""}).status_code == 403
    assert meera.delete(f"/api/teach/labs/{lab_id}").status_code == 403

    # lists are filtered rather than refused
    assert meera.get("/api/sessions").json() == [] and meera.get("/api/review/sessions").json() == []
    assert meera.get("/api/review/students").json() == [] and meera.get("/api/live/labs").json() == []
    assert meera.get("/api/review/labs").json() == []
    assert [s["id"] for s in priya.get("/api/review/sessions").json()] == [sid]
    assert [l["id"] for l in priya.get("/api/live/labs").json()] == [lab_id]


def test_review_tab_lists_lab_sessions(world, app):
    priya, meera, admin, lab, sid = world
    # a practice-task session sits outside every lab: admins only
    student = sign_in(app, "pg25cs07@" + DOMAIN)
    student.post("/api/sessions", json={"student_id": "PG25CS07", "task_id": "free"})
    rows = priya.get("/api/review/labs").json()
    assert [r["id"] for r in rows] == [lab["id"]]
    assert rows[0]["n_students"] == 1 and rows[0]["n_sessions"] == 1 and len(rows[0]["sittings_at"]) == 1
    assert {r["id"] for r in admin.get("/api/review/labs").json()} == {lab["id"], "practice"}
    assert len(admin.get("/api/review/sessions?lab_id=practice").json()) == 1
    assert priya.get("/api/review/sessions?lab_id=practice").status_code == 403
    assert [s["id"] for s in priya.get(f"/api/review/sessions?lab_id={lab['id']}").json()] == [sid]


def test_sharing_with_a_co_teacher(world):
    priya, meera, admin, lab, sid = world
    lab_id = lab["id"]
    r = priya.put(f"/api/teach/labs/{lab_id}/teachers", json={"co_teachers": [" Meera.Rao@" + DOMAIN]})
    assert r.status_code == 200 and r.json()["co_teachers"] == [MEERA]
    assert meera.get("/api/teach/labs").json()[0]["access"] == "co_teacher"
    assert meera.get(f"/api/review/sessions/{sid}").status_code == 200
    # a co-teacher can teach the lab but not reshare it or take it over
    assert meera.patch(f"/api/teach/labs/{lab_id}", json={"title": "Lab 4b"}).status_code == 200
    assert meera.put(f"/api/teach/labs/{lab_id}/teachers", json={"co_teachers": []}).status_code == 403
    assert priya.put(f"/api/teach/labs/{lab_id}/teachers", json={"co_teachers": [], "owner_email": MEERA}).status_code == 403
    # students and outside addresses cannot be co-teachers
    assert priya.put(f"/api/teach/labs/{lab_id}/teachers", json={"co_teachers": ["pg25cs07@" + DOMAIN]}).status_code == 400
    assert priya.put(f"/api/teach/labs/{lab_id}/teachers", json={"co_teachers": ["x@gmail.com"]}).status_code == 400
    # unsharing takes access away again
    priya.put(f"/api/teach/labs/{lab_id}/teachers", json={"co_teachers": []})
    assert meera.get(f"/api/teach/labs/{lab_id}").status_code == 403


def test_unowned_labs_go_to_admins_until_handed_over(app):
    db = app.state.db
    db.create_lab("lab_old", "Lab from before ownership", "")  # owner_email NULL, as after the migration
    priya, admin = sign_in(app, PRIYA), sign_in(app, ADMIN)
    assert priya.get("/api/teach/labs").json() == []
    assert admin.get("/api/teach/labs/lab_old").json()["owner_email"] is None
    r = admin.put("/api/teach/labs/lab_old/teachers", json={"co_teachers": [], "owner_email": PRIYA})
    assert r.status_code == 200 and r.json()["owner_email"] == PRIYA
    assert priya.get("/api/teach/labs").json()[0]["access"] == "owner"


def test_competitions_are_owned_too(world):
    priya, meera, admin, lab, sid = world
    comp = priya.post("/api/teach/competitions", json={"title": "Friday sprint", "duration_min": 10}).json()
    cid = comp["lab_id"]
    assert priya.get(f"/api/teach/competitions/{cid}").status_code == 200
    assert meera.get(f"/api/teach/competitions/{cid}").status_code == 403
    assert meera.post(f"/api/teach/competitions/{cid}/start").status_code == 403
    assert admin.get(f"/api/teach/competitions/{cid}").status_code == 200
    assert cid in {l["id"] for l in priya.get("/api/teach/labs").json()}
    # a co-teacher sees the leaderboard too, with the same detail as the owner
    priya.put(f"/api/teach/labs/{cid}/teachers", json={"co_teachers": [MEERA]})
    board = meera.get(f"/api/teach/competitions/{cid}")
    assert board.status_code == 200 and "board" in board.json()
    assert admin.get(f"/api/teach/competitions/{cid}").json()["board"] == board.json()["board"]

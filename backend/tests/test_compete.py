import pytest
from fastapi.testclient import TestClient

from studentide import compete
from studentide.app import create_app

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}
SOLUTION = "a, b = map(int, input().split())\nprint(a + b)\n"
TESTS = [{"name": "small", "stdin": "1 2", "expected": "3", "hidden": False},
         {"name": "big", "stdin": "40 2", "expected": "42", "hidden": True}]


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "t.sqlite3", admin_token=TOKEN, serve_frontend=False)


@pytest.fixture
def client(app):
    return TestClient(app)


def make_comp(client, app, tests=TESTS, duration_min=30, board="top"):
    c = client.post("/api/teach/competitions", headers=ADMIN,
                    json={"title": "Friday sprint", "description": "", "duration_min": duration_min, "board": board}).json()
    lab_id = c["lab_id"]
    lab = client.post(f"/api/teach/labs/{lab_id}/questions", headers=ADMIN,
                      json={"title": "Add two", "prompt": "Print a + b", "starter_code": "", "sample_input": "1 2",
                            "tests": tests}).json()
    qid = lab["questions"][0]["id"]
    client.put(f"/api/teach/labs/{lab_id}/roster", headers=ADMIN, json={"student_ids": ["S1", "S2", "S3"], "everyone": False})
    return lab_id, qid


def enter(client, sid):
    client.post("/api/consent", json={"student_id": sid})


def session(client, sid, qid):
    r = client.post("/api/sessions", json={"student_id": sid, "question_id": qid, "client_meta": {}})
    return r


def test_competition_needs_tests_to_start(client, app):
    lab_id, qid = make_comp(client, app, tests=[])
    r = client.post(f"/api/teach/competitions/{lab_id}/start", headers=ADMIN)
    assert r.status_code == 409 and "test case" in r.json()["detail"]
    client.patch(f"/api/teach/questions/{qid}", headers=ADMIN, json={"tests": TESTS})
    assert client.post(f"/api/teach/competitions/{lab_id}/start", headers=ADMIN).status_code == 200
    # the last test of a competition question cannot be removed
    assert client.patch(f"/api/teach/questions/{qid}", headers=ADMIN, json={"tests": []}).status_code == 409


def test_lobby_then_live_then_scored(client, app):
    lab_id, qid = make_comp(client, app)
    for s in ("S1", "S2"):
        enter(client, s)
    client.patch(f"/api/teach/labs/{lab_id}", headers=ADMIN, json={"status": "open"})

    # lobby: listed as a competition, questions hidden, cannot start a session yet
    labs = client.get("/api/students/S1/labs").json()
    assert labs[0]["kind"] == "competition" and labs[0]["state"] == "waiting" and labs[0]["questions"] == []
    assert session(client, "S1", qid).status_code == 403
    v = client.post(f"/api/competitions/{lab_id}/join", json={"student_id": "S1", "handle": "Ada"}).json()
    assert v["state"] == "waiting" and v["questions"] == [] and v["lobby"] == ["Ada"]
    assert client.post(f"/api/competitions/{lab_id}/join", json={"student_id": "S2", "handle": "ada"}).status_code == 409

    client.post(f"/api/teach/competitions/{lab_id}/start", headers=ADMIN)
    v = client.get(f"/api/competitions/{lab_id}", params={"student_id": "S1"}).json()
    assert v["state"] == "live" and v["questions"][0]["title"] == "Add two"
    assert [t["name"] for t in v["questions"][0]["tests"]] == ["small"]  # the hidden test stays on the server
    assert v["questions"][0]["n_hidden_tests"] == 1

    s1 = session(client, "S1", qid).json()["session_id"]
    s2 = session(client, "S2", qid).json()["session_id"]  # joins the board under the roll number
    wrong = client.post(f"/api/sessions/{s2}/submit", json={"code": "print(3)\n"}).json()
    assert (wrong["passed"], wrong["total"]) == (1, 2)
    assert [r["name"] for r in wrong["results"]] == ["small", "big"]
    assert wrong["results"][0]["expected"] == "3" and wrong["results"][1].get("expected") is None
    right = client.post(f"/api/sessions/{s1}/submit", json={"code": SOLUTION}).json()
    assert right["passed"] == 2 and right["standing"]["rank"] == 1 and right["standing"]["points"] > 100

    board = client.get(f"/api/teach/competitions/{lab_id}", headers=ADMIN).json()["board"]
    assert [b["handle"] for b in board] == ["Ada", "S2"]
    assert board[0]["solved"] == 1 and board[1]["points"] == 50 and board[1]["solved"] == 0
    assert {"id": "first_solve", "label": "First to solve"} in board[0]["badges"]

    client.post(f"/api/teach/competitions/{lab_id}/end", headers=ADMIN)
    assert client.post(f"/api/sessions/{s1}/submit", json={"code": SOLUTION}).status_code == 409
    assert session(client, "S1", qid).status_code == 403


def test_student_board_respects_mode(client, app):
    lab_id, qid = make_comp(client, app, board="hidden")
    enter(client, "S1")
    client.post(f"/api/teach/competitions/{lab_id}/start", headers=ADMIN)
    s1 = session(client, "S1", qid).json()["session_id"]
    client.post(f"/api/sessions/{s1}/submit", json={"code": SOLUTION})
    v = client.get(f"/api/competitions/{lab_id}", params={"student_id": "S1"}).json()
    assert v["board"] == [] and v["me"]["rank"] == 1  # own standing only while hidden
    client.post(f"/api/teach/competitions/{lab_id}/end", headers=ADMIN)
    v = client.get(f"/api/competitions/{lab_id}", params={"student_id": "S1"}).json()
    assert v["state"] == "ended" and v["board"][0]["me"] is True
    assert "student_id" not in v["board"][0]  # other students' roll numbers never reach the browser


def test_not_on_roster(client, app):
    lab_id, _ = make_comp(client, app)
    client.post(f"/api/teach/competitions/{lab_id}/start", headers=ADMIN)
    assert client.get(f"/api/competitions/{lab_id}", params={"student_id": "X9"}).status_code == 403
    assert client.post(f"/api/competitions/{lab_id}/join", json={"student_id": "X9"}).status_code == 403


# pure scoring --------------------------------------------------------------

def test_score_partial_credit_speed_and_ties():
    comp = {"started_at": 0.0, "ends_at": 600.0, "duration_s": 600}
    players = {"a": "A", "b": "B", "c": "C", "d": "D"}
    subs = [
        {"student_id": "a", "question_id": "q1", "created_at": 300.0, "passed": 4, "total": 4},  # solved half-way
        {"student_id": "b", "question_id": "q1", "created_at": 100.0, "passed": 2, "total": 4},  # partial: no speed
        {"student_id": "b", "question_id": "q1", "created_at": 200.0, "passed": 1, "total": 4},  # worse: ignored
        {"student_id": "c", "question_id": "q1", "created_at": 400.0, "passed": 2, "total": 4},  # ties b, later
        {"student_id": "d", "question_id": "q1", "created_at": 700.0, "passed": 4, "total": 4},  # after the end
    ]
    ranked = compete.score(comp, ["q1"], players, [], subs)
    pts = {p.student_id: p.points for p in ranked}
    assert pts == {"a": 125, "b": 50, "c": 50, "d": 0}
    assert [p.student_id for p in ranked] == ["a", "b", "c", "d"]
    assert ranked[1].questions["q1"].tries == 2
    # the teacher ending early does not change bonuses already earned
    early = compete.score(comp | {"ends_at": 400.0}, ["q1"], players, [], subs)
    assert next(p.points for p in early if p.student_id == "a") == 125


def test_runs_never_score_but_earn_a_badge():
    comp = {"started_at": 0.0, "ends_at": None, "duration_s": None}
    runs = [{"student_id": "a", "question_id": "q", "created_at": t, "error_type": e}
            for t, e in [(1, "SyntaxError"), (2, None), (3, "NameError"), (4, None)]]
    ranked = compete.score(comp, ["q"], {"a": "A", "b": "B"}, runs, [])
    a = next(p for p in ranked if p.student_id == "a")
    assert a.points == 0 and a.fixes == 2 and {"id": "comeback", "label": "Most bugs fixed"} in a.badges


def test_board_reads_nothing_from_the_detector():
    imports = [l for l in open(compete.__file__, encoding="utf-8") if l.lstrip().startswith(("from ", "import "))]
    assert not [l for l in imports if "review" in l or "detector" in l or "harness" in l]

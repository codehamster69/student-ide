"""Any-language competitions: each student picks the language per question."""

import json

import pytest

from studentide import compete
from studentide.grading import LANGUAGES

from test_compete import ADMIN, client, app, edits, enter, rewind, sync_hand_in  # noqa: F401  (fixtures)

PY = "a, b = map(int, input().split())\nprint(a + b)\n"
C = '#include <stdio.h>\nint main(void) {\n    int a, b;\n    scanf("%d %d", &a, &b);\n    printf("%d\\n", a + b);\n    return 0;\n}\n'
TESTS = [{"name": "small", "stdin": "1 2", "expected": "3"}, {"name": "big", "stdin": "40 2", "expected": "42", "hidden": True}]
C_STARTER = "#include <stdio.h>\n\nint main(void) {\n    return 0;\n}\n"


def make_any(client, variants=None, tests=TESTS):
    c = client.post("/api/teach/competitions", headers=ADMIN,
                    json={"title": "Open contest", "language": "any", "duration_min": 30}).json()
    lab_id = c["lab_id"]
    assert c["language"] == "any"
    lab = client.post(f"/api/teach/labs/{lab_id}/questions", headers=ADMIN, json={
        "title": "Add two", "prompt": "Print a + b", "sample_input": "1 2", "tests": tests,
        "variants": variants if variants is not None else {"c": {"starter_code": C_STARTER}}}).json()
    client.put(f"/api/teach/labs/{lab_id}/roster", headers=ADMIN, json={"student_ids": ["S1", "S2"], "everyone": False})
    for s in ("S1", "S2"):
        enter(client, s)
    return lab_id, lab["questions"][0]["id"]


def start(client, sid, qid, language=None):
    return client.post("/api/sessions", json={"student_id": sid, "question_id": qid, "client_meta": {},
                                              **({"language": language} if language else {})})


def test_students_pick_a_language_per_question(client, app):
    lab_id, qid = make_any(client)
    client.post(f"/api/teach/competitions/{lab_id}/start", headers=ADMIN)

    q = client.get(f"/api/competitions/{lab_id}", params={"student_id": "S1"}).json()["questions"][0]
    assert q["language"] == "any" and q["languages"] == list(LANGUAGES)
    assert q["variants"]["c"]["starter_code"] == C_STARTER

    assert start(client, "S1", qid).status_code == 400            # must say which language
    assert start(client, "S1", qid, "cobol").status_code == 400
    s_c = start(client, "S1", qid, "c").json()["session_id"]
    s_py = start(client, "S2", qid, "python").json()["session_id"]
    snap = json.loads(app.state.db.get_session(s_c)["question_json"])
    assert snap["language"] == "c" and snap["starter_code"] == C_STARTER

    # runs and submissions use the session's language, whatever the code looks like
    assert client.post(f"/api/sessions/{s_c}/run", json={"code": C, "stdin": "2 3"}).json()["stdout"] == "5\n"
    assert client.post(f"/api/sessions/{s_c}/submit", json={"code": PY}).json()["passed"] == 0
    r = client.post(f"/api/sessions/{s_c}/submit", json={"code": C}).json()
    assert (r["passed"], r["total"]) == (2, 2)
    assert client.post(f"/api/sessions/{s_py}/submit", json={"code": PY}).json()["passed"] == 2

    v = client.get(f"/api/teach/competitions/{lab_id}", headers=ADMIN).json()
    by = {b["student_id"]: b for b in v["board"]}
    assert by["S1"]["languages"] == ["c"] and by["S1"]["questions"][0]["language"] == "c"
    assert by["S2"]["languages"] == ["python"]
    assert v["questions"][0]["languages"] == list(LANGUAGES)


def test_function_style_questions_only_open_in_languages_with_a_driver(client, app):
    lab_id, qid = make_any(client, variants={
        "python": {"starter_code": "def add(a, b):\n    pass\n", "harness": "import json\nprint(add(*json.loads(input())))\n"}},
        tests=[{"name": "t", "stdin": "[1, 2]", "expected": "3"}])
    client.post(f"/api/teach/competitions/{lab_id}/start", headers=ADMIN)
    q = client.get(f"/api/competitions/{lab_id}", params={"student_id": "S1"}).json()["questions"][0]
    assert q["languages"] == ["python"]
    assert start(client, "S1", qid, "c").status_code == 400
    s = start(client, "S1", qid, "python").json()["session_id"]
    assert client.post(f"/api/sessions/{s}/submit", json={"code": "def add(a, b):\n    return a + b\n"}).json()["passed"] == 1
    # the teacher's try-an-answer box grades in the language asked for
    r = client.post(f"/api/teach/questions/{qid}/check", headers=ADMIN,
                    json={"code": "def add(a, b):\n    return a + b\n", "language": "python"})
    assert r.json()["passed"] == 1
    assert client.post(f"/api/teach/questions/{qid}/check", headers=ADMIN, json={"code": C, "language": "c"}).status_code == 400


def test_switching_to_and_from_any_keeps_starter_code(client, app):
    c = client.post("/api/teach/competitions", headers=ADMIN, json={"title": "C contest", "language": "c"}).json()
    lab_id = c["lab_id"]
    client.post(f"/api/teach/labs/{lab_id}/questions", headers=ADMIN,
                json={"title": "Q", "starter_code": C_STARTER, "tests": TESTS})
    lab = client.patch(f"/api/teach/labs/{lab_id}", headers=ADMIN, json={"language": "any"}).json()
    q = lab["questions"][0]
    assert lab["language"] == "any" and q["starter_code"] == "" and q["variants"]["c"]["starter_code"] == C_STARTER
    lab = client.patch(f"/api/teach/labs/{lab_id}", headers=ADMIN, json={"language": "c"}).json()
    assert lab["questions"][0]["starter_code"] == C_STARTER

    plain = client.post("/api/teach/labs", headers=ADMIN, json={"title": "Lab"}).json()
    assert client.patch(f"/api/teach/labs/{plain['id']}", headers=ADMIN, json={"language": "any"}).status_code == 400


def test_hand_in_takes_the_language_edited_last(client, app, sync_hand_in):
    lab_id, qid = make_any(client)
    client.post(f"/api/teach/competitions/{lab_id}/start", headers=ADMIN)
    s_py = start(client, "S1", qid, "python").json()["session_id"]
    edits(client, s_py, "print(3)\n")
    s_c = start(client, "S1", qid, "c").json()["session_id"]
    edits(client, s_c, C)                                   # switched to C and solved it there, last
    with app.state.db.connect() as conn:                    # the Python edit is older
        conn.execute("UPDATE events SET received_at = received_at - 30 WHERE session_id = ?", (s_py,))
    client.post(f"/api/teach/competitions/{lab_id}/end", headers=ADMIN)
    rewind(app, lab_id, compete.GRACE_S + 5)
    v = client.get(f"/api/teach/competitions/{lab_id}", headers=ADMIN).json()
    me = next(b for b in v["board"] if b["student_id"] == "S1")
    assert me["solved"] == 1 and me["questions"][0]["auto"] is True and me["questions"][0]["language"] == "c"


def test_import_into_an_any_language_competition(client, app, monkeypatch):
    from studentide.providers import PROVIDERS, ProviderError
    from studentide.providers.base import Imported

    class Fake:
        id, name, status = "fake", "Fake", "bundled"

        def fetch(self, language, ref):
            if language == "java":
                raise ProviderError("no Java", 404)
            tests = [{"name": "t", "stdin": "[1, 2]", "expected": "3", "hidden": False, "compare": "text"}]
            if language == "javascript":
                tests = tests[:0]  # e.g. a driver that had to drop a test
            return Imported(title="Add", prompt="add", starter_code=f"// {language}", tests=tests,
                            harness=f"driver for {language}", source={"provider": "fake", "ref": ref})
    monkeypatch.setitem(PROVIDERS, "fake", Fake())
    c = client.post("/api/teach/competitions", headers=ADMIN, json={"title": "Any", "language": "any"}).json()
    r = client.post(f"/api/teach/labs/{c['lab_id']}/import", headers=ADMIN, json={"provider": "fake", "ref": "add"}).json()
    q = r["questions"][0]
    assert sorted(q["variants"]) == ["c", "cpp", "python"] and q["variants"]["c"]["harness"] == "driver for c"
    assert q["starter_code"] == "" and q["harness"] == "" and len(q["tests"]) == 1
    assert any("Java" in n and "JavaScript" in n for n in r["notes"])


def test_competition_baseline_prefers_the_same_language(tmp_path):
    from studentide.db import Database
    from studentide.review import MIN_BASELINE, Reviewer

    rv = Reviewer(Database(tmp_path / "r.sqlite3"))
    mk = lambda i, lab, lang: {"id": f"s{i}", "lab_id": lab, "language": lang, "context": "competition",
                               "n_events": 10, "started_at": float(i)}
    few = [mk(1, "L1", "c"), mk(2, "L2", "python"), mk(3, "L2", "python")]
    assert rv.baseline_ids(few, "competition", "L9", "c") == ["s1", "s2", "s3"]  # too few in C: all of them
    many = few + [mk(10 + i, f"L{3 + i}", "c") for i in range(MIN_BASELINE)]
    got = rv.baseline_ids(many, "competition", "L9", "c")
    assert "s2" not in got and set(got) == {"s1", *(f"s{10 + i}" for i in range(MIN_BASELINE))}
    assert "s1" not in rv.baseline_ids(many, "competition", "L1", "c")  # still leaves its own competition out

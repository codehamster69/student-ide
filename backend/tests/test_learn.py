"""The learning lab: lessons parse, every model answer passes its exercise
and every starter does not, practice is recorded but kept away from the
detector, review and teachers, and a lesson opened again keeps its code."""

import shutil

import pytest
from fastapi.testclient import TestClient

from studentide import grading, learn, retention, runner
from studentide.app import create_app
from studentide.review import Reviewer

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}
LESSONS = [l for t in learn.tracks() for l in t["lessons"]]


@pytest.fixture
def client(tmp_path):
    c = TestClient(create_app(tmp_path / "l.sqlite3", admin_token=TOKEN, serve_frontend=False))
    c.post("/api/consent", json={"student_id": "S1"})
    return c


def typed(text):
    """The editor's opening snapshot, then `text` typed into the empty file."""
    return [{"seq": 0, "t": 0.0, "type": "snapshot", "data": {"reason": "start", "text": ""}},
            {"seq": 1, "t": 100.0, "type": "edit",
             "data": {"origin": "input.type", "changes": [[0, 0, text]], "len_before": 0, "len_after": len(text)}}]


def start(c, lesson_id="learn:c/06-loops"):
    r = c.post("/api/sessions", json={"student_id": "S1", "lesson_id": lesson_id})
    assert r.status_code == 200, r.text
    return r.json()


def test_tracks_parse_and_have_exercises():
    ids = {t["id"]: t for t in learn.tracks()}
    assert {"c", "c-advanced", "cpp", "cpp-intermediate", "cpp-advanced",
            "python", "python-intermediate", "python-advanced"} <= set(ids)
    assert len(ids["c"]["lessons"]) >= 12 and len(ids["c-advanced"]["lessons"]) >= 10
    for lang in ("python", "cpp"):  # listed beginner to advanced
        assert [t["level"] for t in learn.tracks() if t["language"] == lang] == ["beginner", "intermediate", "advanced"]
    for l in LESSONS:
        assert l["title"] and l["prompt"].strip() and l["starter_code"].strip(), l["id"]
        assert l["tests"] and l["solution"], f"{l['id']}: every lesson has an exercise with a model answer"
        assert "```tests" not in l["prompt"] and " solution" not in l["prompt"] and " starter" not in l["prompt"]


def test_parser_takes_out_starter_input_tests_and_solution():
    text = """---
title: T
summary: S
---
Intro

```c
int main(void) { return 0; }
```

```c starter
/* start */
```

```input
5
```

```c solution
/* answer */
```

```tests
{"stdin": "1", "expected": "2"}
{"stdin": "3", "expected": "4", "hidden": true}
```
"""
    l = learn.parse_lesson(text, "c")
    assert l["starter_code"] == "/* start */\n" and l["sample_input"] == "5\n" and l["solution"] == "/* answer */\n"
    assert [t["hidden"] for t in l["tests"]] == [False, True]
    assert "int main" in l["prompt"] and "start" not in l["prompt"] and "answer" not in l["prompt"]
    with pytest.raises(learn.LessonError):
        learn.parse_lesson("no front matter", "c")


@pytest.mark.parametrize("lesson", LESSONS, ids=[l["id"] for l in LESSONS])
def test_model_answer_passes_and_starter_fails(lesson):
    lang = lesson["language"]
    if lang != "python" and not shutil.which(runner.LANGUAGES[lang]["tool"]):
        pytest.skip(f"{lang} not installed")
    good = grading.grade(lesson, lesson["solution"], lang)
    assert good["passed"] == good["total"], [r for r in good["results"] if not r["passed"]]
    bad = grading.grade(lesson, lesson["starter_code"], lang)
    assert bad["passed"] < bad["total"], "the starter must not already solve the exercise"
    if lesson["sample_input"]:  # the example input is one the model answer handles
        assert runner.run(lesson["solution"], lesson["sample_input"], lang).error_type is None


def test_students_never_get_answers_or_hidden_tests(client):
    tracks = client.get("/api/learn").json()
    for t in tracks:
        for l in t["lessons"]:
            assert "solution" not in l and all(not x.get("hidden") for x in l["tests"])
            assert l["n_tests"] >= len(l["tests"]) and l["lesson"] is True
    one = client.get("/api/learn/lessons/c/03-reading-input").json()
    assert one["n_hidden_tests"] == 1 and "solution" not in one
    assert client.get("/api/learn/lessons/c/nope").status_code == 404


def test_lesson_session_runs_checks_and_tracks_progress(client):
    if not shutil.which("gcc"):
        pytest.skip("gcc not installed")
    s = start(client)["session_id"]
    lesson = learn.get_lesson("learn:c/06-loops")
    r = client.post(f"/api/sessions/{s}/run", json={"code": lesson["solution"], "stdin": "4729\n"}).json()
    assert r["stdout"].strip() == "22"  # runs in the lesson's language, C
    prog = {l["id"]: l for t in client.get("/api/learn?student_id=S1").json() for l in t["lessons"]}
    assert prog["learn:c/06-loops"]["sessions"] == 1 and not prog["learn:c/06-loops"]["submitted"]
    g = client.post(f"/api/sessions/{s}/check", json={"code": lesson["solution"]}).json()
    assert g["passed"] == g["total"]
    prog = {l["id"]: l for t in client.get("/api/learn?student_id=S1").json() for l in t["lessons"]}
    assert prog["learn:c/06-loops"]["submitted"]  # a lesson with tests is done once Check passes


def test_unknown_lesson_and_consent(client, tmp_path):
    assert client.post("/api/sessions", json={"student_id": "S1", "lesson_id": "learn:c/zz"}).status_code == 404
    assert client.post("/api/sessions", json={"student_id": "S2", "lesson_id": "learn:c/06-loops"}).status_code == 403


def test_opening_a_lesson_again_keeps_the_code(client):
    a = start(client)
    assert a["resume_code"] is None
    client.post(f"/api/sessions/{a['session_id']}/events",
                json={"schema_version": 1, "events": typed("int x;\n")})
    b = start(client)
    assert b["resume_code"] == "int x;\n"
    assert start(client, "learn:c/07-functions")["resume_code"] is None  # per lesson


def test_learn_sessions_stay_out_of_everything_the_detector_reads(client):
    s = start(client)["session_id"]
    client.post(f"/api/sessions/{s}/events", json={"schema_version": 1, "events": typed("x")})
    db = client.app.state.db
    assert db.list_sessions() == []                       # baselines, harness, live view
    assert [r["context"] for r in db.list_sessions(include_learn=True)] == ["learn"]  # export
    assert client.get("/api/sessions", headers=ADMIN).json() == []
    assert client.get("/api/review/sessions", headers=ADMIN).json() == []
    assert client.get("/api/review/labs", headers=ADMIN).json() == []
    assert client.get("/api/review/students", headers=ADMIN).json() == []
    assert Reviewer(db)._load_sessions() == []


def test_learning_practice_does_not_start_the_baseline_clock(client):
    """The four-week baseline starts at the first *lab* session; practising in
    the learning lab beforehand must not move it, and its raw keys still age out."""
    db = client.app.state.db
    s = start(client)["session_id"]
    client.post(f"/api/sessions/{s}/events", json={"schema_version": 1, "events": typed("x")})
    db.end_session(s, "end")
    with db.connect() as conn:
        conn.execute("UPDATE sessions SET started_at = started_at - 40 * 86400 WHERE id = ?", (s,))
    due = retention.due(db, days=28)
    assert [(d["id"], d["reason"]) for d in due] == [(s, "older than 28 days")]

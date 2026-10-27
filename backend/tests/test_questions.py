"""Optional test cases, lab language/subject, the multi-language runner and
question sources (platform providers)."""

import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studentide import grading, runner
from studentide.app import create_app
from studentide.providers import PROVIDERS
from studentide.providers.base import Cached
from studentide.providers.exercism import RAW, Exercism, excluded_uuids, snake

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}
FIX = Path(__file__).parent / "fixtures" / "exercism"
FILES = {
    f"{RAW}/python/main/config.json": "python-config.json",
    f"{RAW}/python/main/exercises/practice/isogram/.docs/instructions.md": "isogram-instructions.md",
    f"{RAW}/python/main/exercises/practice/isogram/.meta/config.json": "isogram-meta.json",
    f"{RAW}/python/main/exercises/practice/isogram/isogram.py": "isogram.py",
    f"{RAW}/python/main/exercises/practice/isogram/.meta/tests.toml": "isogram-tests.toml",
    f"{RAW}/problem-specifications/main/exercises/isogram/canonical-data.json": "isogram-canonical.json",
}
ISOGRAM = "def is_isogram(phrase):\n    s = [c.lower() for c in phrase if c.isalpha()]\n    return len(s) == len(set(s))\n"


def offline(url: str) -> bytes | None:
    name = FILES.get(url)
    return (FIX / name).read_bytes() if name else None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setitem(PROVIDERS, "exercism", Exercism(Cached(offline)))
    return TestClient(create_app(tmp_path / "t.sqlite3", admin_token=TOKEN, serve_frontend=False))


def open_lab(client, language="python", questions=()):
    lab = client.post("/api/teach/labs", headers=ADMIN,
                      json={"title": "Week 5", "subject": "Data Structures", "language": language}).json()
    for q in questions:
        lab = client.post(f"/api/teach/labs/{lab['id']}/questions", json=q, headers=ADMIN).json()
    client.put(f"/api/teach/labs/{lab['id']}/roster", json={"everyone": True}, headers=ADMIN)
    client.patch(f"/api/teach/labs/{lab['id']}", json={"status": "open"}, headers=ADMIN)
    client.post("/api/consent", json={"student_id": "S1"})
    return lab


def start(client, qid):
    return client.post("/api/sessions", json={"student_id": "S1", "question_id": qid}).json()["session_id"]


# grading -------------------------------------------------------------------

def test_text_comparison_ignores_trailing_whitespace_only():
    assert grading.outputs_match("YES  \n\n", "YES")
    assert grading.outputs_match("a\r\nb\n", "a\nb")
    assert not grading.outputs_match("yes", "YES")
    assert not grading.outputs_match(" YES", "YES")
    assert grading.outputs_match('{"b": 1, "a": [1, 2]}', '{"a":[1,2],"b":1}', "json")
    assert not grading.outputs_match("not json", "1", "json")


def test_no_tests_means_effort_only():
    assert grading.grade({"tests": []}, "print(1)") is None
    assert grading.grade({"tests_json": "[]"}, "print(1)") is None
    assert grading.competition_ready({"tests": []})
    assert grading.competition_ready({"tests": [{"stdin": "", "expected": "1"}]}) is None


def test_grade_hides_hidden_tests():
    q = {"tests": [{"name": "small", "stdin": "2 3", "expected": "5"},
                   {"stdin": "10 -4", "expected": "6", "hidden": True},
                   {"stdin": "1 1", "expected": "3", "hidden": True}]}
    g = grading.grade(q, "a, b = map(int, input().split())\nprint(a + b)\n")
    assert (g["passed"], g["total"]) == (2, 3)
    assert g["results"][0]["stdout"] == "5\n" and g["results"][0]["name"] == "small"
    assert "stdin" not in g["results"][1] and "expected" not in g["results"][2] and g["results"][2]["name"] == "Test 3"


def test_grade_with_harness_calls_a_function():
    q = {"tests": [{"stdin": '["abc"]', "expected": '"cba"', "compare": "json"}],
         "harness": "import json, sys\nprint(json.dumps(rev(*json.loads(sys.stdin.read()))))\n"}
    assert grading.grade(q, "def rev(s):\n    return s[::-1]")["passed"] == 1
    assert grading.grade(q, "def rev(s):\n    return s")["passed"] == 0


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not installed")
def test_compile_error_fails_every_test_once():
    q = {"tests": [{"stdin": "1", "expected": "1"}, {"stdin": "2", "expected": "2", "hidden": True}]}
    g = grading.grade(q, "int main() { return x; }", "c")
    assert g["passed"] == 0 and g["total"] == 2
    assert {r["error_type"] for r in g["results"]} == {"CompileError"} and "undeclared" in g["results"][0]["stderr"]


# runner ----------------------------------------------------------------------

ECHO_SUM = {
    "python": "a, b = map(int, input().split())\nprint(a + b)\n",
    "c": "#include <stdio.h>\nint main(void){int a,b;scanf(\"%d %d\",&a,&b);printf(\"%d\\n\",a+b);return 0;}\n",
    "cpp": "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b<<\"\\n\";}\n",
    "java": "import java.util.*;\npublic class Sum { public static void main(String[] x) { Scanner s = new Scanner(System.in);"
            " System.out.println(s.nextInt() + s.nextInt()); } }\n",
    "javascript": "const [a, b] = require('fs').readFileSync(0, 'utf8').split(/\\s+/).map(Number);\nconsole.log(a + b);\n",
}


@pytest.mark.parametrize("language", list(ECHO_SUM))
def test_runner_languages(language):
    if not next(l for l in runner.available_languages() if l["id"] == language)["available"]:
        pytest.skip(f"{language} toolchain not installed")
    r = runner.run(ECHO_SUM[language], "20 22", language)
    assert (r.stdout.strip(), r.error_type) == ("42", None)


def test_runner_rejects_unknown_language():
    with pytest.raises(ValueError):
        runner.run("x", "", "cobol")


# labs, sessions and checks -----------------------------------------------------

def test_lab_language_and_subject(client):
    lab = client.post("/api/teach/labs", json={"title": "L", "subject": " OOP ", "language": "java"}, headers=ADMIN).json()
    assert (lab["subject"], lab["language"]) == ("OOP", "java")
    lab = client.patch(f"/api/teach/labs/{lab['id']}", json={"language": "cpp"}, headers=ADMIN).json()
    assert lab["language"] == "cpp"
    assert client.patch(f"/api/teach/labs/{lab['id']}", json={"language": "cobol"}, headers=ADMIN).status_code == 422
    langs = {l["id"] for l in client.get("/api/teach/languages", headers=ADMIN).json()}
    assert langs == {"python", "c", "cpp", "java", "javascript"}


def test_student_sees_visible_tests_and_checks_against_snapshot(client):
    tests = [{"name": "sample", "stdin": "2 3", "expected": "5"}, {"stdin": "5 5", "expected": "10", "hidden": True}]
    lab = open_lab(client, questions=[{"title": "Sum", "prompt": "add", "tests": tests}])
    q = client.get("/api/students/S1/labs").json()[0]["questions"][0]
    assert q["tests"] == [{"name": "sample", "stdin": "2 3", "expected": "5", "hidden": False, "compare": "text"}]
    assert (q["n_hidden_tests"], q["n_tests"], q["language"]) == (1, 2, "python")
    assert "5 5" not in str(client.get("/api/students/S1/labs").json())

    sid = start(client, q["id"])
    # a later edit does not change what this open session is checked against
    client.patch(f"/api/teach/questions/{q['id']}", json={"tests": [{"stdin": "", "expected": "nope"}]}, headers=ADMIN)
    g = client.post(f"/api/sessions/{sid}/check", json={"code": ECHO_SUM["python"]}).json()
    assert (g["passed"], g["total"]) == (2, 2) and "stdin" not in g["results"][1]
    stored = client.get(f"/api/sessions/{sid}/checks", headers=ADMIN).json()
    assert len(stored) == 1 and stored[0]["passed"] == 2
    snap = client.get(f"/api/sessions?lab_id={lab['id']}", headers=ADMIN).json()[0]["question_json"]
    assert snap["tests"][1]["hidden"] is True and snap["language"] == "python" and snap["subject"] == "Data Structures"


def test_questions_without_tests_cannot_be_checked(client):
    open_lab(client, questions=[{"title": "Free"}])
    qid = client.get("/api/students/S1/labs").json()[0]["questions"][0]["id"]
    assert client.post(f"/api/sessions/{start(client, qid)}/check", json={"code": "print(1)"}).status_code == 409


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
def test_run_uses_the_lab_language(client):
    open_lab(client, language="cpp", questions=[{"title": "Sum"}])
    qid = client.get("/api/students/S1/labs").json()[0]["questions"][0]["id"]
    r = client.post(f"/api/sessions/{start(client, qid)}/run", json={"code": ECHO_SUM["cpp"], "stdin": "1 2"}).json()
    assert r["stdout"].strip() == "3" and r["error_type"] is None
    # practice tasks stay Python
    s = client.post("/api/sessions", json={"student_id": "S1", "task_id": "free"}).json()["session_id"]
    assert client.post(f"/api/sessions/{s}/run", json={"code": "print(7)"}).json()["stdout"] == "7\n"


def test_teacher_tries_a_model_answer(client):
    lab = open_lab(client, questions=[{"title": "Sum", "tests": [{"stdin": "1 2", "expected": "3"}]}])
    qid = lab["questions"][0]["id"]
    g = client.post(f"/api/teach/questions/{qid}/check", json={"code": ECHO_SUM["python"]}, headers=ADMIN).json()
    assert g["passed"] == 1


def test_competition_questions_keep_their_tests(client):
    lab = open_lab(client, questions=[{"title": "Sum", "tests": [{"stdin": "1 2", "expected": "3"}]}])
    qid = lab["questions"][0]["id"]
    db = client.app.state.db
    with db.connect() as conn:
        conn.execute("UPDATE labs SET kind = 'competition' WHERE id = ?", (lab["id"],))
    assert client.patch(f"/api/teach/questions/{qid}", json={"tests": []}, headers=ADMIN).status_code == 409
    assert client.patch(f"/api/teach/questions/{qid}", json={"title": "Add"}, headers=ADMIN).status_code == 200


def test_old_question_rows_are_migrated(tmp_path):
    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript("""CREATE TABLE labs (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft', everyone INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL);
        CREATE TABLE questions (id TEXT PRIMARY KEY, lab_id TEXT NOT NULL, position INTEGER NOT NULL, title TEXT NOT NULL,
        prompt TEXT NOT NULL DEFAULT '', starter_code TEXT NOT NULL DEFAULT '', sample_input TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL, updated_at REAL NOT NULL);
        INSERT INTO labs(id, title, created_at, updated_at) VALUES ('l', 'L', 1, 1);
        INSERT INTO questions(id, lab_id, position, title, created_at, updated_at) VALUES ('q', 'l', 0, 'Q', 1, 1);""")
    conn.commit()
    conn.close()
    from studentide.db import Database
    db = Database(path)
    assert db.get_lab("l")["language"] == "python" and db.get_question("q")["tests_json"] == "[]"


# question sources ---------------------------------------------------------------

def test_sources_say_what_each_platform_supports(client):
    s = {p["id"]: p for p in client.get("/api/teach/sources", headers=ADMIN).json()}
    assert s["exercism"]["status"] == "live"
    assert s["hackerrank"]["status"] == "link_only" and not s["hackerrank"]["can_browse"]
    assert s["codeforces"]["status"] == s["codechef"]["status"] == s["leetcode"]["status"] == "bundled"
    assert s["mbpp"]["status"] == "live"
    assert s["codechef"]["can_browse"] and s["codechef"]["can_link"] and s["leetcode"]["can_link"]
    assert client.get("/api/teach/sources/hackerrank/categories", headers=ADMIN).status_code == 409


def test_browse_and_import_from_exercism(client):
    cats = client.get("/api/teach/sources/exercism/categories?language=python", headers=ADMIN).json()
    assert cats[0]["id"] == "difficulty:easy" and cats[0]["count"] >= 1
    found = client.get("/api/teach/sources/exercism/questions?language=python&q=iso", headers=ADMIN).json()
    assert [f["ref"] for f in found] == ["isogram"]

    preview = client.get("/api/teach/sources/exercism/questions/isogram?language=python", headers=ADMIN).json()
    assert preview["title"] == "Isogram" and "isogram" in preview["prompt"].lower()
    assert preview["source"]["license"] == "MIT" and len(preview["tests"]) >= 10

    lab = client.post("/api/teach/labs", json={"title": "L"}, headers=ADMIN).json()
    lab = client.post(f"/api/teach/labs/{lab['id']}/import", json={"provider": "exercism", "ref": "isogram"}, headers=ADMIN).json()
    q = next(q for q in lab["questions"] if q["id"] == lab["imported"])
    assert q["starter_code"].startswith("def is_isogram") and "is_isogram(" in q["harness"]
    assert any(t["hidden"] for t in q["tests"]) and q["source"]["provider"] == "exercism"
    g = client.post(f"/api/teach/questions/{q['id']}/check", json={"code": ISOGRAM}, headers=ADMIN).json()
    assert g["passed"] == g["total"] == len(q["tests"])

    bad = client.post(f"/api/teach/labs/{lab['id']}/import", json={"provider": "exercism", "ref": "nope"}, headers=ADMIN)
    assert bad.status_code == 404
    assert client.post(f"/api/teach/labs/{lab['id']}/import", json={"provider": "exercism", "ref": "../x"}, headers=ADMIN).status_code == 400


def test_link_only_platforms(client):
    lab = client.post("/api/teach/labs", json={"title": "L"}, headers=ADMIN).json()
    ok = client.post(f"/api/teach/labs/{lab['id']}/link", headers=ADMIN,
                     json={"provider": "leetcode", "url": "https://leetcode.com/problems/two-sum/", "title": "Two sum"}).json()
    q = ok["questions"][0]
    assert q["source"] == {"provider": "leetcode", "url": "https://leetcode.com/problems/two-sum/", "linked_only": True}
    assert q["prompt"] == "" and q["tests"] == []
    for url in ("https://evil.example/leetcode.com", "http://leetcode.com/problems/x", "https://notleetcode.com/x"):
        r = client.post(f"/api/teach/labs/{lab['id']}/link", headers=ADMIN, json={"provider": "leetcode", "url": url, "title": "x"})
        assert r.status_code == 400, url
    r = client.post(f"/api/teach/labs/{lab['id']}/link", headers=ADMIN,
                    json={"provider": "codechef", "url": "https://www.codechef.com/problems/FLOW001", "title": "Add"})
    assert r.status_code == 200


def test_exercism_helpers():
    assert snake("isIsogram") == "is_isogram" and snake("reverse") == "reverse"
    toml = '[a0e97d2d-669e-47c7-8134-518a1e2c4555]\ndescription = "x"\ninclude = false\n\n[9a001b50-f194-4143-bc29-2af5ec1ef652]\n'
    assert excluded_uuids(toml) == {"a0e97d2d-669e-47c7-8134-518a1e2c4555"}


def test_exercism_without_tests_for_c_family():
    ex = Exercism(Cached(lambda url: offline(url.replace("/cpp/", "/python/"))))
    got = ex.fetch("cpp", "isogram")
    assert got.tests == [] and "int main()" in got.starter_code and got.notes


# Codeforces and CodeChef (CodeContests, bundled) and MBPP (live) -------------------

def test_codeforces_by_topic_and_rating(client):
    cats = client.get("/api/teach/sources/codeforces/categories?language=cpp", headers=ADMIN).json()
    ids = [c["id"] for c in cats]
    for topic in ("topic:dp", "topic:graphs", "topic:strings", "topic:sorting", "topic:trees", "topic:math"):
        assert topic in ids
    assert "level:beginner" in ids and sum(c["count"] for c in cats if c["id"].startswith("level:")) > 4000
    dp = client.get("/api/teach/sources/codeforces/questions?language=cpp&category=topic:dp", headers=ADMIN).json()
    assert dp and all("dp" in s["categories"] for s in dp)
    beginners = client.get("/api/teach/sources/codeforces/questions?language=cpp&category=level:beginner", headers=ADMIN).json()
    assert beginners and all(800 <= int(s["blurb"]) <= 1000 for s in beginners)

    lab = client.post("/api/teach/labs", json={"title": "L", "language": "python"}, headers=ADMIN).json()
    lab = client.post(f"/api/teach/labs/{lab['id']}/import", json={"provider": "codeforces", "ref": "cf-1003A"}, headers=ADMIN).json()
    q = next(q for q in lab["questions"] if q["id"] == lab["imported"])
    assert q["title"] == "Polycarp's Pockets" and q["source"]["url"].endswith("/1003/A") and q["source"]["license"] == "CC BY 4.0"
    assert "$$$" not in q["prompt"] and "≤" in q["prompt"] and q["sample_input"].startswith("6")
    assert len(q["tests"]) >= 3 and any(t["hidden"] for t in q["tests"])
    answer = "input()\nfrom collections import Counter\nprint(max(Counter(input().split()).values()))\n"
    g = client.post(f"/api/teach/questions/{q['id']}/check", json={"code": answer}, headers=ADMIN).json()
    assert g["passed"] == g["total"]


def test_codechef_from_codecontests(client):
    cats = client.get("/api/teach/sources/codechef/categories?language=c", headers=ADMIN).json()
    assert {c["id"] for c in cats} == {"level:easy", "level:medium"}
    easy = client.get("/api/teach/sources/codechef/questions?language=c&category=level:easy", headers=ADMIN).json()
    got = client.get(f"/api/teach/sources/codechef/questions/{easy[0]['ref']}?language=c", headers=ADMIN).json()
    assert got["source"]["provider"] == "codechef" and "CodeContests" in got["source"]["attribution"]
    assert client.get("/api/teach/sources/codechef/questions/cf-1003A?language=c", headers=ADMIN).status_code == 404


def test_real_number_answers_use_a_tolerance():
    assert grading.outputs_match("0.3333333\n", "0.333333333", "tokens")
    assert grading.outputs_match("YES 2.0000001", "YES 2", "tokens")
    assert not grading.outputs_match("0.34", "0.333333", "tokens")
    assert not grading.outputs_match("1 2", "1 2 3", "tokens")


def test_mbpp_offline(monkeypatch):
    from studentide.providers.mbpp import MBPP, URL, convert, guess_topics
    data = (Path(__file__).parent / "fixtures" / "mbpp" / "mbpp-head.jsonl").read_bytes()
    m = MBPP(Cached(lambda url: data if url == URL else None))
    assert any(c.id == "topic:strings" for c in m.categories("python"))
    with pytest.raises(Exception):
        m.categories("cpp")
    q = m.fetch("python", "2")
    assert q.starter_code == "def similar_elements(test_tup1, test_tup2):\n    pass\n" and "tc[" not in q.starter_code
    assert len(q.tests) == 3 and q.tests[1]["hidden"] and "similar_elements(" in q.harness
    g = grading.grade(q.as_dict(), "def similar_elements(a, b):\n    return tuple(sorted(set(a) & set(b)))\n")
    assert g["passed"] == 3
    assert guess_topics("Write a function to reverse words in a given string.") == ["strings"]
    fn, tests, skipped = convert({"test_list": ["assert f(1) == 2", "assert math.isclose(f(2), 3)", "assert g(1) == 1"]})
    assert (fn, len(tests), skipped) == ("f", 1, 2)


"""The original question sets (providers/originals.py): every reference
solution passes every test, the starter code does not, and a question
imports into a competition ready to start."""

import shutil

import pytest
from fastapi.testclient import TestClient

from studentide import grading
from studentide.app import create_app
from studentide.providers import PROVIDERS
from studentide.providers.originals import _sets

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}
QUESTIONS = [(s, x) for s in _sets() for x in s["questions"]]
needs_gcc = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not installed")


def test_sets_are_well_formed():
    assert {s["id"] for s in _sets()} >= {"c-fundamentals"}
    for _, x in QUESTIONS:
        tests = grading.parse_tests(x["tests"])
        assert any(not t["hidden"] for t in tests) and any(t["hidden"] for t in tests), x["ref"]
        assert x["sample_input"] == tests[0]["stdin"]


@needs_gcc
@pytest.mark.parametrize("s,x", QUESTIONS, ids=[x["ref"] for _, x in QUESTIONS])
def test_reference_solution_passes_and_starter_fails(s, x):
    got = grading.grade({"tests": x["tests"]}, x["solution"], s["language"])
    assert got["passed"] == got["total"], [r for r in got["results"] if not r["passed"]]
    starter = grading.grade({"tests": x["tests"]}, x["starter_code"], s["language"])
    assert starter["passed"] < starter["total"]


@needs_gcc
def test_hidden_tests_catch_a_common_slip():
    leap = next(x for _, x in QUESTIONS if x["ref"] == "c-leap")
    div4 = "#include <stdio.h>\nint main(void){int y;scanf(\"%d\",&y);puts(y%4==0?\"YES\":\"NO\");}\n"
    got = grading.grade({"tests": leap["tests"]}, div4, "c")
    shown = [r for r in got["results"] if not r["hidden"]]
    assert not all(r["passed"] for r in shown) or got["passed"] < got["total"]
    assert got["passed"] < got["total"]


def test_browse_and_import_into_a_competition(tmp_path):
    c = TestClient(create_app(tmp_path / "t.sqlite3", admin_token=TOKEN, serve_frontend=False))
    assert PROVIDERS["originals"].info()["status"] == "bundled"
    cats = c.get("/api/teach/sources/originals/categories?language=c", headers=ADMIN).json()
    assert [k["label"] for k in cats][:3] == ["Input and output", "Operators", "Conditionals"]
    assert c.get("/api/teach/sources/originals/questions?language=python", headers=ADMIN).json() == []
    lab = c.post("/api/teach/competitions", json={"title": "C sprint", "language": "c"}, headers=ADMIN).json()["lab_id"]
    r = c.post(f"/api/teach/labs/{lab}/import", json={"provider": "originals", "ref": "c-prime"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    q = next(q for q in c.get(f"/api/teach/labs/{lab}", headers=ADMIN).json()["questions"] if q["title"] == "Prime Time")
    assert "solution" not in q and "is_prime" in q["starter_code"]
    assert len(q["tests"]) == 6 and sum(t["hidden"] for t in q["tests"]) == 4
    assert grading.competition_ready(q) is None

"""Optional test cases on a question, and checking code against them.

Correctness is optional by design. A lab is about effort, so its tests (if a
teacher adds any) are only a self-check the student can press; nothing is
scored. Competitions are the one place correctness counts, so a competition
question must have at least one test (see competition_ready).

A test is stdin in, stdout out, which works the same in every language:

    {"name": "two words", "stdin": "listen\\nsilent\\n", "expected": "YES",
     "hidden": false, "compare": "text"}

compare "text" (default): trailing spaces on each line and trailing blank
lines are ignored. compare "json": both sides are parsed as JSON and compared
as values (used by imported function-style questions, whose harness prints
the function's return value as JSON).

A question's optional `harness` is code appended after the student's before
the tests run, e.g. a few lines that read a JSON argument list from stdin,
call the student's function and print the result. Students see that it
exists, and the tests call the function it names.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from . import runner

MAX_TESTS = 50
SHOWN_CHARS = 2000  # stdout/expected echoed back per test


class TestCase(BaseModel):
    name: str = Field(default="", max_length=120)
    stdin: str = Field(default="", max_length=100_000)
    expected: str = Field(default="", max_length=100_000)
    hidden: bool = False  # the student sees pass/fail only, never the input or expected output
    compare: Literal["text", "json"] = "text"


def parse_tests(raw: str | list | None) -> list[dict]:
    """tests_json column (or an already-parsed list) -> validated list of dicts."""
    if not raw:
        return []
    items = json.loads(raw) if isinstance(raw, str) else raw
    return [TestCase.model_validate(t).model_dump() for t in items]


def _text(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.replace("\r\n", "\n").split("\n")).rstrip("\n")


def outputs_match(got: str, expected: str, compare: str = "text") -> bool:
    if compare == "json":
        try:
            return json.loads(got) == json.loads(expected)
        except ValueError:
            return False
    return _text(got) == _text(expected)


def competition_ready(question: dict) -> str | None:
    """None when the question can be used in a competition, else why not."""
    if not parse_tests(question.get("tests") if "tests" in question else question.get("tests_json")):
        return "competition questions need at least one test case, since competitions are scored on correctness"
    return None


def grade(question: dict, code: str, language: str = "python") -> dict | None:
    """Run `code` (plus the question's harness) against every test.

    Returns None when the question has no tests (an effort-only question),
    otherwise {"passed", "total", "results": [...]}. Hidden tests report only
    whether they passed. The program is compiled once for all tests.
    """
    tests = parse_tests(question.get("tests") if "tests" in question else question.get("tests_json"))
    if not tests:
        return None
    harness = question.get("harness") or ""
    source = code if not harness else code.rstrip("\n") + "\n\n" + harness
    results = []
    failed, outs, _ = runner.run_many(source, language, [t["stdin"] for t in tests])
    for i, t in enumerate(tests):
        r = failed or outs[i]
        ok = r.error_type is None and outputs_match(r.stdout, t["expected"], t["compare"])
        res = {"name": t["name"] or f"Test {i + 1}", "passed": ok, "hidden": t["hidden"],
               "error_type": r.error_type, "duration_ms": round(r.duration_ms, 1)}
        if not t["hidden"]:
            res.update(stdin=t["stdin"][:SHOWN_CHARS], stdout=r.stdout[:SHOWN_CHARS],
                       expected=t["expected"][:SHOWN_CHARS], stderr=r.stderr[:SHOWN_CHARS])
        results.append(res)
        if failed:  # a compile error fails every test the same way; say it once
            res["stderr"] = r.stderr[:SHOWN_CHARS]
            results.extend({"name": u["name"] or f"Test {j + 1}", "passed": False, "hidden": u["hidden"],
                            "error_type": r.error_type, "duration_ms": 0.0}
                           for j, u in enumerate(tests[i + 1:], start=i + 1))
            break
    return {"passed": sum(r["passed"] for r in results), "total": len(results), "results": results}

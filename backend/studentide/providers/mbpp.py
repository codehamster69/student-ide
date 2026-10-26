"""MBPP (Mostly Basic Python Problems): about 1,000 short, entry-level Python
problems written for "Program Synthesis with Large Language Models" (Austin et
al., 2021), each with three test asserts. Published in the google-research
repository (Apache 2.0; the dataset card gives CC BY 4.0) and fetched live
from GitHub when the teacher browses.

Python only: the tests are asserts on a function, which become stdin/stdout
tests through the same JSON driver Exercism questions use. MBPP has no topic
labels of its own, so topics here are guessed from words in the question
(and say so); the reference solution is never shown, only its signature.
"""

from __future__ import annotations

import ast
import json
import re
import time

from .base import Cached, Category, Imported, Provider, ProviderError, Summary, topic_categories

URL = "https://raw.githubusercontent.com/google-research/google-research/master/mbpp/mbpp.jsonl"
HARNESS = ("# Student IDE test driver: reads the arguments as JSON, calls your function, prints the result.\n"
           "import json as _json, sys as _sys\n"
           "print(_json.dumps({fn}(*_json.loads(_sys.stdin.read())), "
           "default=lambda o: sorted(o) if isinstance(o, (set, frozenset)) else str(o)))\n")

# Keyword -> shared topic (base.TOPICS); first matching words decide.
KEYWORDS = [
    ("regex", r"\bregex|regular expression"),
    ("strings", r"\bstring|\bcharacter|\bword|\bvowel|substring|palindrome|uppercase|lowercase|\bletter"),
    ("dictionaries", r"\bdictionar|\bset\b|\bsets\b|frequency|\bcount the occurr"),
    ("tuples", r"\btuple"),
    ("arrays", r"\blist|\barray|\belement|\bmatrix"),
    ("sorting", r"\bsort|\bheap|\bsmallest|\blargest|\bk-th|kth"),
    ("searching", r"binary search|\bsearch"),
    ("bits", r"\bbit|binary|\bxor"),
    ("number-theory", r"\bprime|\bgcd|\blcm|divisor|divisible"),
    ("math", r"\bnumber|\bsum\b|\bsum of|\bdigit|factorial|\bsquare|\bcube|\barea|\bperimeter|\bvolume|fibonacci|power|average"),
    ("recursion", r"recurs"),
    ("dp", r"\bways\b|minimum cost|maximum sum|longest|subsequence"),
]


def guess_topics(text: str) -> list[str]:
    t = text.lower()
    return [topic for topic, pat in KEYWORDS if re.search(pat, t)][:3] or ["implementation"]


def _literal(node: ast.AST):
    v = ast.literal_eval(node)
    if isinstance(v, (set, frozenset)):
        return sorted(v)
    return v


def convert(row: dict) -> tuple[str, list[dict], int]:
    """(function name, tests, asserts skipped). Only `assert f(literals) == literal` is translated."""
    fn, tests, skipped = None, [], 0
    for line in row.get("test_list", []):
        try:
            node = ast.parse(line.strip()).body[0]
            ok = (isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare) and len(node.test.ops) == 1
                  and isinstance(node.test.ops[0], ast.Eq) and isinstance(node.test.left, ast.Call)
                  and isinstance(node.test.left.func, ast.Name) and not node.test.left.keywords)
            if not ok:
                raise ValueError
            call = node.test.left
            args = [_literal(a) for a in call.args]
            expected = _literal(node.test.comparators[0])
            json.dumps(args), json.dumps(expected)
        except (ValueError, SyntaxError, TypeError, IndexError):
            skipped += 1
            continue
        if fn not in (None, call.func.id):
            skipped += 1
            continue
        fn = call.func.id
        tests.append({"stdin": json.dumps(args), "expected": json.dumps(expected), "compare": "json"})
    return fn or "", tests, skipped


def signature(code: str, fn: str) -> str:
    """The reference solution's `def` line for `fn` (never its body)."""
    m = re.search(rf"^\s*def\s+{re.escape(fn)}\s*\(([^)]*)\)", code, re.M)
    return f"def {fn}({m.group(1).strip() if m else '*args'}):\n    pass\n"


class MBPP(Provider):
    id = "mbpp"
    name = "MBPP"
    status = "live"
    license = "Apache 2.0 / CC BY 4.0"
    about = ("About 1,000 short beginner Python problems (Google Research), each with three tests. "
             "Topics are guessed from the wording. Python labs only.")
    terms_url = "https://github.com/google-research/google-research/tree/master/mbpp"

    def __init__(self, http: Cached | None = None):
        self.http = http or Cached()

    def _rows(self, language: str, fresh: bool = False) -> list[dict]:
        if language != "python":
            raise ProviderError("MBPP questions are Python only; switch the lab to Python to use them", 400)
        text = self.http.text(URL, fresh)
        if text is None:
            raise ProviderError("MBPP is not available right now")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def categories(self, language: str) -> list[Category]:
        return topic_categories([guess_topics(r["text"]) for r in self._rows(language)], [])

    def search(self, language: str, category: str | None = None, query: str = "") -> list[Summary]:
        q = query.strip().lower()
        out = []
        for r in self._rows(language):
            tps = guess_topics(r["text"])
            if category and category.startswith("topic:") and category[6:] not in tps:
                continue
            if q and q not in r["text"].lower():
                continue
            out.append(Summary(str(r["task_id"]), _title(r["text"]), "beginner", tps))
        return out[:400]

    def fetch(self, language: str, ref: str) -> Imported:
        row = next((r for r in self._rows(language, fresh=True) if str(r["task_id"]) == ref), None)
        if row is None:
            raise ProviderError(f"MBPP has no problem {ref}", 404)
        fn, tests, skipped = convert(row)
        notes = [f"{skipped} of MBPP's asserts couldn't be turned into input/output tests and were left out."] if skipped else []
        for i, t in enumerate(tests):
            t.update(name=f"Test {i + 1}", hidden=i > 0)
        return Imported(
            title=_title(row["text"]), prompt=row["text"] + (f"\n\nWrite it as a function named `{fn}`." if fn else ""),
            starter_code=signature(row["code"], fn) if fn else "", tests=tests,
            harness=HARNESS.format(fn=fn) if tests else "",
            source={"provider": self.id, "ref": ref, "url": self.terms_url, "license": self.license,
                    "attribution": "MBPP, Austin et al. 2021 (Google Research)", "fetched_at": time.time()},
            notes=notes,
        )


def _title(text: str) -> str:
    t = re.sub(r"^write (a|an) (python )?(function|program) to ", "", text.strip(), flags=re.I).rstrip(".")
    t = t[0].upper() + t[1:] if t else text
    return t if len(t) <= 80 else t[:77].rstrip() + "..."

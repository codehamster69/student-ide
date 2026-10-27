"""MBPP (Mostly Basic Python Problems): about 1,000 short, entry-level Python
problems written for "Program Synthesis with Large Language Models" (Austin et
al., 2021), each with three test asserts. Published in the google-research
repository (Apache 2.0; the dataset card gives CC BY 4.0) and fetched live
from GitHub when the teacher browses.

The tests are asserts on a function, which become stdin/stdout tests: one
JSON value per argument per line, and the function's return value printed as
JSON. MBPP has no type hints, so for C, C++, Java and JavaScript the types
come from the test values (polyglot.py); a problem whose values have no
single type in those languages (a mixed tuple, a dict) stays Python only.
When a problem has types, every language gets the same tests. MBPP has no
topic labels of its own, so topics here are guessed from words in the
question (and say so); the reference solution is never shown, only its
signature.
"""

from __future__ import annotations

import ast
import json
import re
import time

from . import polyglot
from .base import Cached, Category, Imported, Provider, ProviderError, Summary, topic_categories

URL = "https://raw.githubusercontent.com/google-research/google-research/master/mbpp/mbpp.jsonl"
HARNESS = ("# Student IDE test driver: reads the arguments as JSON, calls your function, prints the result.\n"
           "import json as _json, sys as _sys\n"
           "print(_json.dumps({fn}(*_json.loads(_sys.stdin.read())), "
           "default=lambda o: sorted(o) if isinstance(o, (set, frozenset)) else str(o)))\n")
LINES_HARNESS = ("# Student IDE test driver: reads one JSON value per argument per line, calls your function, prints the result.\n"
                 "import json as _json, sys as _sys\n"
                 "print(_json.dumps({fn}(*[_json.loads(_l) for _l in _sys.stdin.read().splitlines() if _l.strip()]), "
                 "default=lambda o: sorted(o) if isinstance(o, (set, frozenset)) else str(o)))\n")
LABELS = {"python": "Python", "c": "C", "cpp": "C++", "java": "Java", "javascript": "JavaScript"}

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


def params(code: str, fn: str) -> list[str] | None:
    """The reference solution's parameter names (None if it takes *args or can't be found)."""
    m = re.search(rf"^\s*def\s+{re.escape(fn)}\s*\(([^)]*)\)", code, re.M)
    if not m or "*" in m.group(1):
        return None
    return [p.split("=")[0].split(":")[0].strip() for p in m.group(1).split(",") if p.strip()]


def typed(row: dict, language: str) -> tuple[polyglot.Signature, list[dict]] | None:
    """Signature and tests for a typed language (Python: the same tests), or None
    unless every test has types there, so a problem's tests are the same in every language."""
    fn, tests, _ = convert(row)
    names = params(row.get("code", ""), fn) if tests else None
    if names is None:
        return None
    cases = [(json.loads(t["stdin"]), json.loads(t["expected"])) for t in tests]
    built = polyglot.build(fn, names, None, None, cases)
    lang = "c" if language == "python" else language
    if built is None or len(built[1]) < len(cases) or not all(polyglot.in_range([a, e], lang) for a, e in cases):
        return None
    return built[0], [{"stdin": polyglot.stdin(a), "expected": t["expected"], "compare": "json"}
                      for (a, _), t in zip(cases, tests)]


def signature(code: str, fn: str) -> str:
    """The reference solution's `def` line for `fn` (never its body)."""
    m = re.search(rf"^\s*def\s+{re.escape(fn)}\s*\(([^)]*)\)", code, re.M)
    return f"def {fn}({m.group(1).strip() if m else '*args'}):\n    pass\n"


class MBPP(Provider):
    id = "mbpp"
    name = "MBPP"
    status = "live"
    license = "Apache 2.0 / CC BY 4.0"
    about = ("About 1,000 short beginner problems (Google Research), each with three tests. Topics are guessed "
             "from the wording. Written for Python; about 840 also work in C, C++, Java and JavaScript, with "
             "types taken from the tests.")
    terms_url = "https://github.com/google-research/google-research/tree/master/mbpp"

    def __init__(self, http: Cached | None = None):
        self.http = http or Cached()
        self._typed: tuple[int, dict[str, set[str]]] = (0, {})  # (hash of the fetched file, language -> task ids)

    def _rows(self, language: str, fresh: bool = False) -> list[dict]:
        if language != "python" and language not in polyglot.LANGUAGES:
            raise ProviderError(f"MBPP questions aren't available in {language}", 400)
        text = self.http.text(URL, fresh)
        if text is None:
            raise ProviderError("MBPP is not available right now")
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        if language == "python":
            return rows
        if self._typed[0] != hash(text):
            self._typed = (hash(text), {})
        ids = self._typed[1].get(language)
        if ids is None:
            ids = self._typed[1][language] = {str(r["task_id"]) for r in rows if typed(r, language)}
        return [r for r in rows if str(r["task_id"]) in ids]

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
        row = next((r for r in self._rows("python", fresh=True) if str(r["task_id"]) == ref), None)
        if row is None:
            raise ProviderError(f"MBPP has no problem {ref}", 404)
        fn, tests, skipped = convert(row)
        notes = [f"{skipped} of MBPP's asserts couldn't be turned into input/output tests and were left out."] if skipped else []
        got = typed(row, language)
        if got is None and language != "python":
            raise ProviderError(f"MBPP problem {ref} can't be set in {LABELS.get(language, language)}: its test values "
                                "don't have one type there (or don't fit). It works in Python.", 404)
        if got is None:
            code, driver = (signature(row["code"], fn) if fn else ""), (HARNESS.format(fn=fn) if tests else "")
        else:
            sig, tests = got
            code = signature(row["code"], fn) if language == "python" else polyglot.starter(sig, language)
            driver = LINES_HARNESS.format(fn=fn) if language == "python" else polyglot.harness(sig, language)
            if language != "python":
                notes.append(f"MBPP is written for Python: the {LABELS[language]} starter's types are taken from the "
                             "tests (tuples become arrays); the tests are the same in every language.")
        for i, t in enumerate(tests):
            t.update(name=f"Test {i + 1}", hidden=i > 0)
        name = polyglot.c_name(fn) if language == "c" else fn  # e.g. remove() is taken by C's stdio.h
        prompt = row["text"] + (f"\n\nWrite it as a function named `{name}`." if fn else "")
        if language != "python":
            prompt = re.sub(r"\b[Pp]ython ", "", prompt)
        return Imported(
            title=_title(row["text"]), prompt=prompt, starter_code=code, tests=tests, harness=driver,
            source={"provider": self.id, "ref": ref, "url": self.terms_url, "license": self.license,
                    "attribution": "MBPP, Austin et al. 2021 (Google Research)", "fetched_at": time.time()},
            notes=notes,
        )


def _title(text: str) -> str:
    t = re.sub(r"^write (a|an) (python )?(function|program) to ", "", text.strip(), flags=re.I).rstrip(".")
    t = t[0].upper() + t[1:] if t else text
    return t if len(t) <= 80 else t[:77].rstrip() + "..."

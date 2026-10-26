"""Exercism: openly licensed (MIT) exercises, fetched live from Exercism's
public GitHub repositories.

  index      exercism/<track>/config.json            practice exercises, difficulty, concepts
  statement  exercism/<track>/exercises/practice/<slug>/.docs/instructions.md
  starter    the track's solution stub (Python and JavaScript only, see below)
  tests      exercism/problem-specifications/exercises/<slug>/canonical-data.json

Exercism's own tests are unit tests that call a function. Student IDE tests
are stdin -> stdout, so for Python and JavaScript each canonical case becomes
a test whose stdin is the argument list as JSON, plus a short harness that
calls the student's function and prints the result as JSON. A case is only
kept when that translation is certain (the function exists in the stub with
the right number of parameters, the expected value is not an error). C, C++
and Java stubs have no main(), so for those languages the statement comes in
with a stdin/stdout starter and the teacher adds tests if they want them.
"""

from __future__ import annotations

import json
import re
import time

from .base import Cached, Category, Imported, Provider, ProviderError, Summary

RAW = "https://raw.githubusercontent.com/exercism"
TRACKS = {"python": "python", "javascript": "javascript", "java": "java", "c": "c", "cpp": "cpp"}
BANDS = (("easy", "Easy", 1, 3), ("medium", "Medium", 4, 6), ("hard", "Hard", 7, 10))
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_TESTS = 30

STARTERS = {
    "c": "#include <stdio.h>\n\nint main(void) {\n    \n    return 0;\n}\n",
    "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n",
    "java": "import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner in = new Scanner(System.in);\n        \n    }\n}\n",
}

HARNESS = {
    "python": ("# Student IDE test driver: reads the arguments as JSON, calls your function, prints the result.\n"
               "import json as _json, sys as _sys\n"
               "print(_json.dumps({fn}(*_json.loads(_sys.stdin.read()))))\n"),
    "javascript": ("// Student IDE test driver: reads the arguments as JSON, calls your function, prints the result.\n"
                   "import {{ readFileSync as __sidRead }} from \"node:fs\";\n"
                   "console.log(JSON.stringify({fn}(...JSON.parse(__sidRead(0, \"utf8\")))));\n"),
}


def snake(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def band(difficulty: int) -> str:
    return next((b for b, _, lo, hi in BANDS if lo <= difficulty <= hi), "hard")


def flatten(cases: list) -> list[dict]:
    out = []
    for c in cases:
        out.extend(flatten(c["cases"]) if "cases" in c else [c])
    return out


def excluded_uuids(tests_toml: str | None) -> set[str]:
    """Cases the track has switched off (include = false in .meta/tests.toml)."""
    if not tests_toml:
        return set()
    out, current = set(), None
    for line in tests_toml.splitlines():
        m = re.match(r"\s*\[([0-9a-f-]{36})\]", line)
        if m:
            current = m.group(1)
        elif current and re.match(r"\s*include\s*=\s*false", line):
            out.add(current)
    return out


class Exercism(Provider):
    id = "exercism"
    name = "Exercism"
    status = "live"
    about = ("Open-source practice exercises (MIT licence), fetched live from Exercism's public repositories, "
             "with test cases for Python and JavaScript.")
    terms_url = "https://github.com/exercism/problem-specifications/blob/main/LICENSE"

    def __init__(self, http: Cached | None = None):
        self.http = http or Cached()

    def _track(self, language: str) -> str:
        if language not in TRACKS:
            raise ProviderError(f"Exercism has no {language} track here", 400)
        return TRACKS[language]

    def _exercises(self, language: str) -> list[dict]:
        cfg = self.http.json(f"{RAW}/{self._track(language)}/main/config.json")
        if not cfg:
            raise ProviderError("Exercism's exercise list is not available right now")
        return [e for e in cfg["exercises"]["practice"] if e.get("status") != "deprecated"]

    def categories(self, language: str) -> list[Category]:
        ex = self._exercises(language)
        out = [Category(f"difficulty:{b}", label, sum(1 for e in ex if band(e.get("difficulty", 1)) == b))
               for b, label, _, _ in BANDS]
        concepts: dict[str, int] = {}
        for e in ex:
            for c in e.get("practices", []):
                concepts[c] = concepts.get(c, 0) + 1
        out += [Category(f"concept:{c}", c.replace("-", " ").capitalize(), n)
                for c, n in sorted(concepts.items(), key=lambda kv: (-kv[1], kv[0])) if n >= 2]
        return [c for c in out if c.count]

    def search(self, language: str, category: str | None = None, query: str = "") -> list[Summary]:
        q = query.strip().lower()
        out = []
        for e in self._exercises(language):
            b = band(e.get("difficulty", 1))
            if category and category.startswith("difficulty:") and category[11:] != b:
                continue
            if category and category.startswith("concept:") and category[8:] not in e.get("practices", []):
                continue
            if q and q not in e["name"].lower() and q not in e["slug"]:
                continue
            out.append(Summary(e["slug"], e["name"], b, e.get("practices", [])))
        return sorted(out, key=lambda s: ([b for b, *_ in BANDS].index(s.difficulty), s.title))

    def fetch(self, language: str, ref: str) -> Imported:
        if not SLUG.match(ref):
            raise ProviderError("not an Exercism exercise id", 400)
        track = self._track(language)
        entry = next((e for e in self._exercises(language) if e["slug"] == ref), None)
        if entry is None:
            raise ProviderError(f"Exercism's {language} track has no exercise '{ref}'", 404)
        base = f"{RAW}/{track}/main/exercises/practice/{ref}"
        # fresh=True: the statement is read at the moment the teacher picks it.
        instructions = self.http.text(f"{base}/.docs/instructions.md", fresh=True)
        if instructions is None:
            raise ProviderError("this exercise has no instructions to import", 404)
        extra = self.http.text(f"{base}/.docs/instructions.append.md", fresh=True) or ""
        meta = self.http.json(f"{base}/.meta/config.json", fresh=True) or {}
        prompt = re.sub(r"^# .*\n+", "", instructions.strip() + ("\n\n" + extra.strip() if extra.strip() else ""), count=1)

        result = Imported(
            title=entry["name"], prompt=prompt.strip(),
            source={"provider": self.id, "ref": ref, "language": language,
                    "url": f"https://exercism.org/tracks/{track}/exercises/{ref}",
                    "license": "MIT", "attribution": f"Exercism ({track} track and problem-specifications), MIT licence",
                    "blurb": meta.get("blurb", ""), "fetched_at": time.time()},
        )
        if language in HARNESS:
            stub_name = (meta.get("files", {}).get("solution") or [None])[0]
            stub = self.http.text(f"{base}/{stub_name}", fresh=True) if stub_name else None
            result.starter_code = stub or ""
            self._tests(language, ref, base, stub or "", result)
        else:
            result.starter_code = STARTERS[language]
            result.notes.append(f"Exercism's {language} exercises are unit-tested functions without main(), so no tests "
                                "were imported. Add stdin/stdout tests yourself if you want students to check their work.")
        return result

    def _tests(self, language: str, ref: str, base: str, stub: str, result: Imported) -> None:
        canonical = self.http.json(f"{RAW}/problem-specifications/main/exercises/{ref}/canonical-data.json", fresh=True)
        if not canonical:
            result.notes.append("Exercism has no shared test data for this exercise, so no tests were imported.")
            return
        off = excluded_uuids(self.http.text(f"{base}/.meta/tests.toml", fresh=True))
        cases = flatten(canonical.get("cases", []))
        replaced = {c["reimplements"] for c in cases if "reimplements" in c}
        fns = self._functions(language, stub)
        pairs, skipped = [], 0
        for c in cases:
            if c.get("uuid") in off or c.get("uuid") in replaced:
                continue
            expected, args = c.get("expected"), list((c.get("input") or {}).values())
            fn = snake(c.get("property", "")) if language == "python" else c.get("property", "")
            arity = fns.get(fn, -2)
            if (isinstance(expected, dict) and "error" in expected) or arity == -2 or (arity >= 0 and arity != len(args)):
                skipped += 1
                continue
            pairs.append((fn, {"name": c.get("description", "")[:120], "stdin": json.dumps(args, ensure_ascii=False),
                               "expected": json.dumps(expected, ensure_ascii=False), "hidden": False, "compare": "json"}))
        if not pairs:
            result.notes.append("None of Exercism's test cases could be turned into input/output tests for this exercise.")
            return
        # One harness calls one function: keep the function most cases test.
        counts: dict[str, int] = {}
        for fn, _ in pairs:
            counts[fn] = counts.get(fn, 0) + 1
        main = max(counts, key=counts.get)
        skipped += len(pairs) - counts[main]
        tests = [t for fn, t in pairs if fn == main][:MAX_TESTS]
        for i, t in enumerate(tests):  # later cases hidden, so the visible ones guide and the rest check
            t["hidden"] = i >= max(3, len(tests) // 2)
        result.tests = tests
        result.harness = HARNESS[language].format(fn=main)
        if skipped:
            result.notes.append(f"{skipped} of Exercism's cases test errors or other functions and were left out.")

    @staticmethod
    def _functions(language: str, stub: str) -> dict[str, int]:
        """Function name -> parameter count in the stub (-1 when it can't be told)."""
        if language == "python":
            out = {}
            for name, params in re.findall(r"^def\s+(\w+)\s*\(([^)]*)\)", stub, re.M):
                ps = [p for p in params.split(",") if p.strip() and not p.strip().startswith("*")]
                out[name] = -1 if "*" in params else len(ps)
            return out
        names = re.findall(r"^export\s+(?:const\s+(\w+)\s*=|function\s+(\w+))", stub, re.M)
        return {a or b: -1 for a, b in names}

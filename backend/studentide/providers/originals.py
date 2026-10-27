"""Question sets written for Student IDE itself (data/sets/*.json, built by
scripts/build_question_sets.py). They are original, so they can ship with
the app and carry the repository's own licence, and every question has
stdin/stdout tests checked against a reference solution, which makes them
ready for a competition as imported. The reference solution never leaves
the server: teachers import the statement, starter code and tests only.

Categories are the sets' own topics (Input and output, Loops, Arrays, ...)
in teaching order, then difficulty. A set lists only for its language.
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path

from .base import Category, Imported, Provider, ProviderError, Summary

DATA = Path(__file__).parent / "data" / "sets"
LEVELS = ("warm-up", "easy", "medium")


@lru_cache(maxsize=1)
def _sets() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DATA.glob("*.json"))]


def _questions(language: str) -> list[tuple[dict, dict]]:
    return [(s, x) for s in _sets() if s["language"] == language for x in s["questions"]]


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower())


class Originals(Provider):
    id = "originals"
    name = "Student IDE sets"
    status = "bundled"
    license = "Same as Student IDE"
    about = ("Original beginner questions written for this app (C fundamentals so far), each with visible "
             "examples and hidden tests checked against a reference solution: ready for a competition.")

    def categories(self, language: str) -> list[Category]:
        rows = [x for _, x in _questions(language)]
        topics: dict[str, int] = {}
        for x in rows:
            topics[x["topic"]] = topics.get(x["topic"], 0) + 1
        return ([Category(f"topic:{_slug(t)}", t, n) for t, n in topics.items()]
                + [Category(f"level:{lv}", lv.capitalize(), n) for lv in LEVELS
                   if (n := sum(x["level"] == lv for x in rows))])

    def search(self, language: str, category: str | None = None, query: str = "") -> list[Summary]:
        q = query.strip().lower()
        out = []
        for s, x in _questions(language):
            if category and category.startswith("topic:") and category[6:] != _slug(x["topic"]):
                continue
            if category and category.startswith("level:") and category[6:] != x["level"]:
                continue
            if q and q not in x["title"].lower() and q not in x["topic"].lower():
                continue
            out.append(Summary(x["ref"], x["title"], x["level"], [x["topic"]], s["title"]))
        return out  # set order is teaching order

    def fetch(self, language: str, ref: str) -> Imported:
        hit = next(((s, x) for s, x in _questions(language) if x["ref"] == ref), None)
        if hit is None:
            raise ProviderError(f"no {language} question '{ref}' in the Student IDE sets", 404)
        s, x = hit
        hidden = sum(t["hidden"] for t in x["tests"])
        return Imported(
            title=x["title"], prompt=x["prompt"], starter_code=x["starter_code"], sample_input=x["sample_input"],
            tests=[dict(t) for t in x["tests"]],
            source={"provider": self.id, "ref": ref, "set": s["id"], "url": "", "license": self.license,
                    "attribution": f"Student IDE question set '{s['title']}'", "fetched_at": time.time()},
            notes=[f"{len(x['tests']) - hidden} visible examples and {hidden} hidden tests, compared exactly "
                   "(trailing spaces ignored)."],
        )

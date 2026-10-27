"""Codeforces problems from the open-r1 Codeforces dataset, and CodeChef
problems from the CodeContests dataset.

Codeforces: open-r1/codeforces (Penedo et al., Hugging Face 2025, CC BY 4.0)
has 10,000+ Codeforces problems up to 2025 with statements, tags, ratings,
official and generated tests, and a validated Python checker for problems
that accept several right answers (judged with grading's "checker" compare).
Every problem our runner can run is bundled (data/codeforces.jsonl.gz, built
by scripts/build_codeforces.py), at every rating.

CodeChef: CodeContests (Li et al., "Competition-level code generation with AlphaCode",
Science 2022) collects competitive-programming problems with statements,
tags, difficulty and stdin/stdout tests, released by DeepMind under CC BY 4.0.
Its Codeforces problems are sourced from codeforces.com, its CodeChef problems
from the MIT-licensed Description2Code dataset. That makes it the permitted
route to these platforms' problems: the sites themselves still can't be
fetched (see unavailable.py), but this openly licensed research copy can.

The dataset is only published as large Riegeli files, so a filtered copy is
bundled (data/codecontests.jsonl.gz, built by scripts/build_codecontests.py):
Codeforces problems rated 800 to 2000 with their tags, and CodeChef problems
marked easy or medium. Statements are as published (Codeforces' LaTeX made
readable), with the original link kept for attribution.
"""

from __future__ import annotations

import gzip
import json
import re
import time
from functools import lru_cache
from pathlib import Path

from .base import Category, Imported, Provider, ProviderError, Summary, topic_categories

DATA = Path(__file__).parent / "data" / "codecontests.jsonl.gz"
CF_DATA = Path(__file__).parent / "data" / "codeforces.jsonl.gz"
ATTRIBUTION = ("CodeContests dataset (DeepMind, CC BY 4.0; Li et al., Science 2022), "
               "problem originally from {site}")
CF_ATTRIBUTION = "open-r1 Codeforces dataset (Penedo et al., Hugging Face 2025, CC BY 4.0), problem originally from Codeforces"

# Codeforces tag -> shared topic (base.TOPICS). Tags not listed fall under no topic.
CF_TOPICS = {
    "implementation": "implementation", "math": "math", "matrices": "math", "probabilities": "math", "fft": "math",
    "chinese remainder theorem": "number-theory", "number theory": "number-theory", "combinatorics": "combinatorics",
    "greedy": "greedy", "dp": "dp", "sortings": "sorting", "binary search": "searching", "ternary search": "searching",
    "two pointers": "two-pointers", "brute force": "brute-force", "meet-in-the-middle": "brute-force",
    "strings": "strings", "hashing": "strings", "string suffix structures": "strings", "expression parsing": "strings",
    "data structures": "data-structures", "dsu": "data-structures", "graphs": "graphs", "dfs and similar": "graphs",
    "shortest paths": "graphs", "flows": "graphs", "graph matchings": "graphs", "2-sat": "graphs", "trees": "trees",
    "bitmasks": "bits", "geometry": "geometry", "constructive algorithms": "constructive", "games": "games",
    "divide and conquer": "divide-conquer",
}
CF_LEVELS = (("beginner", "Beginner (800-1000)", 800, 1000), ("easy", "Easy (1100-1300)", 1100, 1300),
             ("medium", "Medium (1400-1600)", 1400, 1600), ("hard", "Hard (1700-2000)", 1700, 2000),
             ("expert", "Expert (2100-2600)", 2100, 2600), ("master", "Master (2700+)", 2700, 9999),
             ("unrated", "Unrated", 0, 0))
CC_LEVELS = (("easy", "Easy"), ("medium", "Medium"))
REAL_ANSWER = re.compile(r"absolute or relative error|relative error|absolute error", re.I)


@lru_cache(maxsize=2)
def _load(path: Path = DATA) -> dict[str, dict]:
    if not path.exists():
        raise ProviderError(f"the question set {path.name} is missing from this install", 503)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return {r["ref"]: r for r in map(json.loads, f)}


def topics(row: dict) -> list[str]:
    return sorted({CF_TOPICS[t] for t in row["tags"] if t in CF_TOPICS})


def level(row: dict) -> str:
    if row["source"] == "codeforces":
        return next((k for k, _, lo, hi in CF_LEVELS if lo <= row["level"] <= hi), "master")
    return row["level"]


class _CodeContests(Provider):
    status = "bundled"
    license = "CC BY 4.0"
    terms_url = "https://github.com/google-deepmind/code_contests#license"
    source: str
    data: Path = DATA
    attribution: str = ATTRIBUTION

    def _rows(self) -> list[dict]:
        return [r for r in _load(self.data).values() if r["source"] == self.source]

    def categories(self, language: str) -> list[Category]:
        rows = self._rows()
        levels = CF_LEVELS if self.source == "codeforces" else [(k, label, 0, 0) for k, label in CC_LEVELS]
        return topic_categories([topics(r) for r in rows],
                                [(k, label, sum(1 for r in rows if level(r) == k)) for k, label, *_ in levels])

    def search(self, language: str, category: str | None = None, query: str = "") -> list[Summary]:
        q = query.strip().lower()
        out = []
        for r in self._rows():
            if category and category.startswith("topic:") and category[6:] not in topics(r):
                continue
            if category and category.startswith("level:") and category[6:] != level(r):
                continue
            if q and q not in r["title"].lower() and q not in r["ref"]:
                continue
            label = f"{r['level']}" if self.source == "codeforces" and r["level"] else ""
            out.append(Summary(r["ref"], r["title"], level(r), r["tags"] or [], label))
        order = [k for k, *_ in (CF_LEVELS if self.source == "codeforces" else CC_LEVELS)]
        return sorted(out, key=lambda s: (order.index(s.difficulty) if s.difficulty in order else 9, s.title))[:400]

    def fetch(self, language: str, ref: str) -> Imported:
        r = _load(self.data).get(ref)
        if r is None or r["source"] != self.source:
            raise ProviderError(f"no {self.name} problem '{ref}' in the question set", 404)
        # Real-number answers are compared with a tolerance; everything else exactly.
        real = REAL_ANSWER.search(r["prompt"]) or any(re.search(r"\d\.\d{3,}", t["expected"]) for t in r["tests"])
        checker = r.get("checker", "")
        compare = "checker" if checker else "tokens" if real else "text"
        notes = ["Read input from standard input and print the answer; tests compare your output "
                 + ("number by number, allowing a 1e-6 error." if real else "exactly.")]
        if checker:
            notes = ["Read input from standard input and print the answer. This problem accepts more than one right "
                     "answer, so a checker program judges each output (shown expected outputs are one right answer)."]
        if not r["tests"]:
            notes = ["This problem accepts more than one correct answer, so its tests were left out (exact comparison "
                     "would mark right answers wrong). Add tests yourself if you want students to check their work."]
        return Imported(
            title=r["title"], prompt=r["prompt"], sample_input=r["sample_input"],
            tests=[t | {"name": f"{'Example' if not t['hidden'] else 'Test'} {i + 1}", "compare": compare}
                   for i, t in enumerate(r["tests"])],
            source={"provider": self.id, "ref": ref, "url": r["url"] or _codechef_url(r["title"]), "license": self.license,
                    "attribution": self.attribution.format(site=self.name), "tags": r["tags"], "level": r["level"],
                    "fetched_at": time.time()},
            checker=checker, notes=notes,
        )


class Codeforces(_CodeContests):
    id = "codeforces"
    name = "Codeforces"
    source = "codeforces"
    data = CF_DATA
    attribution = CF_ATTRIBUTION
    terms_url = "https://huggingface.co/datasets/open-r1/codeforces"
    about = ("9,000+ problems up to 2025 at every rating, by topic and rating, with test cases (and a checker where "
             "several answers are right), from the openly licensed open-r1 Codeforces dataset (CC BY 4.0).")
    hosts = ("codeforces.com",)


class CodeChef(_CodeContests):
    id = "codechef"
    name = "CodeChef"
    source = "codechef"
    about = ("300+ easy and medium problems with test cases, from the openly licensed CodeContests dataset "
             "(CC BY 4.0). CodeChef's own site can't be fetched (its API closed in 2020), so other problems can only be linked.")
    hosts = ("codechef.com",)


def _codechef_url(code: str) -> str:
    """CodeChef problem codes are the dataset's names (e.g. "acball" -> ACBALL)."""
    return f"https://www.codechef.com/problems/{code.upper()}" if re.fullmatch(r"[A-Za-z0-9_]{2,20}", code) else ""

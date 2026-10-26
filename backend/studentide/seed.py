"""Fill a database with synthetic students so the review timeline can be demoed.

    python -m studentide.seed --db data/demo.sqlite3 --students 6

Each simulated student gets four honest baseline sessions, one a week, then
assessed sessions in weeks five and six covering the study conditions
(honest, full proxy, takeover, copying out, paste). Ground truth goes into
the session's client_meta under "synthetic", which the review screen shows
as an overlay; real sessions never have it. The assessed weeks belong to a
teacher-made demo lab (see teach.py), so the authoring screens have content too. Uses the phase 2 generator, so
these are simulated people, not data about anyone.
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .db import Database
from .detector.synth import generate_session, nearest_speed, population
from .schema import SCHEMA_VERSION
from .teach import question_json

TASKS = ("warmup-fizzbuzz", "word-frequency", "free")
# assessed sessions per student, cycled so a small demo still shows every condition
ASSESSED = [("takeover", "honest"), ("copying", "paste"), ("honest", "proxy"), ("paste", "takeover"),
            ("honest", "copying"), ("takeover", "honest")]
WEEK = 7 * 86400

DEMO_LABS = [
    ("Lab 5: Strings and dictionaries", "Week 5 lab. Work through the questions in order; run your code as often as you like.", "open", [
        ("Count vowels", "Read a line of text and print how many vowels (a, e, i, o, u, either case) it contains.",
         "line = input()\n", "Programming is fun"),
        ("Anagram check", "Read two words, one per line. Print YES if they are anagrams of each other, otherwise NO.",
         "a = input()\nb = input()\n", "listen\nsilent"),
        ("Top three words", "Read a paragraph and print the three most common words with their counts, most common first.",
         "text = input()\n", "the cat and the hat and the bat"),
    ]),
    ("Lab 6: Recursion", "Draft for next week.", "draft", [
        ("Power set", "Read a list of distinct integers and print every subset, one per line, in any order.", "nums = list(map(int, input().split()))\n", "1 2 3"),
    ]),
]


def seed_labs(db: Database, students: list[str]) -> list[dict]:
    """Demo labs; returns the questions of the first (open) lab."""
    first: list[dict] = []
    for n, (title, about, status, qs) in enumerate(DEMO_LABS):
        lab_id = f"lab_demo{n + 1}"
        db.create_lab(lab_id, title, about)
        for k, (qt, prompt, starter, sample) in enumerate(qs):
            db.add_question(f"q_demo{n + 1}{k + 1}", lab_id,
                            {"title": qt, "prompt": prompt, "starter_code": starter, "sample_input": sample})
        db.set_roster(lab_id, students)
        db.update_lab(lab_id, {"status": status})
        if n == 0:
            first = [question_json(q) for q in db.lab_questions(lab_id)]
    return first


def seed(db: Database, n_students: int = 6, minutes: float = 25, seed: int = 11, start: float | None = None,
         log=print) -> list[str]:
    pop = population(max(n_students, 2), seed)[:n_students]
    t0 = start if start is not None else (time.time() - 6 * WEEK) // 86400 * 86400  # midnight UTC
    ids = []
    lab_qs = seed_labs(db, [f"DEMO{i + 1:02d}" for i in range(n_students)])
    for i, ty in enumerate(pop):
        sid_student = f"DEMO{i + 1:02d}"
        db.get_or_create_student(sid_student)
        db.record_consent(sid_student)
        plan = [(w, "honest") for w in range(4)] + [(4 + j, c) for j, c in enumerate(ASSESSED[i % len(ASSESSED)])]
        for j, (week, cond) in enumerate(plan):
            other = nearest_speed(pop, ty) if cond in ("proxy", "takeover") else None
            events, truth = generate_session(ty, cond, other=other, duration_s=minutes * 60,
                                             seed=seed * 10_000 + i * 100 + j)
            truth = asdict(truth)
            truth["author_after"] = f"DEMO{pop.index(other) + 1:02d}" if other else truth["author_after"]
            truth["student"] = sid_student
            session_id = uuid.uuid4().hex
            sw = truth["switch_t"]
            meta = {"ua": "synthetic", "synthetic": {**truth, "switch_s": sw / 1000 if sw is not None else None}}
            # baseline weeks are practice tasks; assessed weeks answer the demo lab
            q = lab_qs[(i + j) % len(lab_qs)] if week >= 4 else None
            db.create_session(session_id, sid_student, q["id"] if q else TASKS[j % len(TASKS)], SCHEMA_VERSION, meta, q)
            db.insert_events(session_id, events)
            started = t0 + week * WEEK + i * 3600 + 9.5 * 3600
            with db.connect() as conn:
                conn.execute("UPDATE sessions SET started_at = ?, ended_at = ?, end_reason = 'submit' WHERE id = ?",
                             (started, started + events[-1]["t"] / 1000, session_id))
            ids.append(session_id)
        log(f"  {sid_student}: {len(plan)} sessions")
    return ids


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default="data/demo.sqlite3")
    p.add_argument("--students", type=int, default=6)
    p.add_argument("--minutes", type=float, default=25)
    p.add_argument("--seed", type=int, default=11)
    a = p.parse_args()
    if Path(a.db).exists():
        raise SystemExit(f"{a.db} exists; seed a fresh file so demo data never mixes with real recordings")
    ids = seed(Database(a.db), a.students, a.minutes, a.seed)
    print(json.dumps({"db": a.db, "sessions": len(ids)}))


if __name__ == "__main__":
    main()

"""Fill a database with synthetic students so the review timeline can be demoed.

    python -m studentide.seed --db data/demo.sqlite3 --students 6

Each simulated student gets four honest baseline sessions, one a week, then
assessed sessions in weeks five and six covering the study conditions
(honest, full proxy, takeover, copying out, paste). Ground truth goes into
the session's client_meta under "synthetic", which the review screen shows
as an overlay; real sessions never have it. Uses the phase 2 generator, so
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

TASKS = ("warmup-fizzbuzz", "word-frequency", "free")
# assessed sessions per student, cycled so a small demo still shows every condition
ASSESSED = [("takeover", "honest"), ("copying", "paste"), ("honest", "proxy"), ("paste", "takeover"),
            ("honest", "copying"), ("takeover", "honest")]
WEEK = 7 * 86400


def seed(db: Database, n_students: int = 6, minutes: float = 25, seed: int = 11, start: float | None = None,
         log=print) -> list[str]:
    pop = population(max(n_students, 2), seed)[:n_students]
    t0 = start if start is not None else (time.time() - 6 * WEEK) // 86400 * 86400  # midnight UTC
    ids = []
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
            db.create_session(session_id, sid_student, TASKS[j % len(TASKS)], SCHEMA_VERSION, meta)
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

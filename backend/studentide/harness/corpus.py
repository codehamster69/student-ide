"""The evaluation corpus: labelled sessions, the same shape for synthetic and real data.

A corpus is a list of sessions, each with the student it belongs to, its
role (`baseline`: one of the student's first-weeks honest sessions;
`test`: a staged or honest session to score), the staged condition and,
for a switch, the time of the first keystroke made under the new
condition. Students carry free-form attributes used for the fairness
analysis (RQ4).

Two sources:

- `synthetic_corpus()` simulates a population with `detector.synth`
  (8 baseline sessions and 7 test sessions per typist). Attributes are
  derived from each typist's habit profile (typing speed, rhythm
  variability, build style), since simulated people have no demographics.
- `db_corpus()` reads recorded sessions from the editor's SQLite database
  plus a labels manifest written while running the Phase 2 study:

      sessions.csv  session_id,role,condition,variant,switch_s,partner
      students.csv  student,<any attribute columns, e.g. gender,layout,experience>

  `role` may be left empty: a student's honest sessions in the first 28 days
  after their first session are then the baseline. `switch_s` is seconds
  from session start (from the staging log); empty for honest, 0 for proxy.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import pickle
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..detector.features import Streams, streams, window_features
from ..detector.synth import Typist, generate_session, nearest_speed, population

# test sessions per simulated typist: (variant, condition, partner)
SYNTH_TESTS = [
    ("honest", "honest", None), ("honest2", "honest", None),
    ("proxy", "proxy", "matched"), ("takeover", "takeover", "matched"),
    ("takeover_random", "takeover", "random"), ("copying", "copying", None), ("paste", "paste", None),
]
VARIANT_LABELS = {
    "honest": "A honest", "proxy": "B full proxy (matched)", "takeover": "C takeover (matched)",
    "takeover_random": "C takeover (random partner)", "copying": "D copying out", "paste": "E paste",
}
CACHE_VERSION = 1


@dataclass
class Session:
    id: str
    student: str
    role: str  # baseline | test
    condition: str  # honest | proxy | takeover | copying | paste
    variant: str  # condition plus how it was staged, e.g. takeover_random
    switch_s: float | None
    duration_s: float
    st: Streams
    partner: str | None = None
    order: int = 0  # position among the student's sessions (baseline weeks first)


@dataclass
class Corpus:
    source: str
    sessions: list[Session]
    students: dict[str, dict]  # student -> attributes
    meta: dict = field(default_factory=dict)
    _win: dict = field(default_factory=dict, repr=False)

    def baseline(self, student: str, n: int | None = None) -> list[Session]:
        b = sorted((s for s in self.sessions if s.student == student and s.role == "baseline"), key=lambda s: s.order)
        return b[:n] if n else b

    def tests(self, students=None) -> list[Session]:
        keep = set(students) if students is not None else None
        return [s for s in self.sessions if s.role == "test" and (keep is None or s.student in keep)]

    def windows(self, s: Session, W: float, comments: str = "separate") -> list[dict]:
        key = (s.id, W, comments)
        if key not in self._win:
            self._win[key] = window_features(s.st, W, comments=comments)
        return self._win[key]

    def fingerprint(self) -> str:
        """Identifies the data a test run was made on (for the ledger)."""
        h = hashlib.sha256(self.source.encode())
        for s in sorted(self.sessions, key=lambda s: s.id):
            h.update(f"{s.id}|{s.student}|{s.role}|{s.variant}|{s.switch_s}|{len(s.st.k_t)}".encode())
        return h.hexdigest()[:16]


# ------------------------------------------------------------ synthetic

def _terciles(values: dict[str, float], labels: tuple[str, str, str]) -> dict[str, str]:
    lo, hi = np.quantile(list(values.values()), [1 / 3, 2 / 3])
    return {k: labels[0] if v <= lo else labels[2] if v > hi else labels[1] for k, v in values.items()}


def synthetic_attributes(pop: list[Typist]) -> dict[str, dict]:
    speed = _terciles({t.id: t.mu for t in pop}, ("fast", "medium", "slow"))  # mu = log latency
    rhythm = _terciles({t.id: t.sigma for t in pop}, ("steady", "medium", "variable"))
    return {t.id: {"typing_speed": speed[t.id], "rhythm": rhythm[t.id],
                   "build_style": "outline-first" if t.skeleton_p >= 0.5 else "top-down"} for t in pop}


def _simulate_typist(args) -> list[tuple]:
    i, ty, pop, seed, n_base, minutes, random_partner = args
    s0 = seed * 1_000_000 + i * 100
    out = []
    for j in range(n_base):
        ev, truth = generate_session(ty, "honest", duration_s=minutes * 60, seed=s0 + j)
        out.append((f"{ty.id}-b{j}", "baseline", "honest", "honest", None, truth.duration_ms / 1000, streams(ev), None, j))
    for j, (variant, cond, partner) in enumerate(SYNTH_TESTS):
        other = None
        if partner == "matched":
            other = nearest_speed(pop, ty)
        elif partner == "random":
            other = pop[random_partner]
        ev, truth = generate_session(ty, cond, other=other, duration_s=minutes * 60, seed=s0 + 50 + j)
        sw = None if truth.switch_t is None else truth.switch_t / 1000
        out.append((f"{ty.id}-{variant}", "test", cond, variant, sw, truth.duration_ms / 1000, streams(ev),
                    other.id if other else None, n_base + j))
    return out


def synthetic_corpus(n: int = 120, seed: int = 7, n_base: int = 8, minutes: float = 30,
                     cache: Path | None = None, workers: int | None = None, log=print) -> Corpus:
    """Simulate `n` typists. Cached on disk (keyed by every argument) because
    simulation is the slow part and the harness is rerun often."""
    key = f"synth-v{CACHE_VERSION}-n{n}-s{seed}-b{n_base}-m{minutes:g}"
    path = Path(cache) / f"{key}.pkl" if cache else None
    if path and path.exists():
        with open(path, "rb") as f:
            return pickle.load(f)
    pop = population(n, seed)
    rng = np.random.default_rng(seed)
    partners = [int(rng.choice([k for k in range(n) if k != i])) for i in range(n)]
    jobs = [(i, ty, pop, seed, n_base, minutes, partners[i]) for i, ty in enumerate(pop)]
    sessions = []
    workers = workers or min(8, os.cpu_count() or 1)
    log(f"simulating {n} typists x {n_base + len(SYNTH_TESTS)} sessions of {minutes:g} min on {workers} cores ...")
    with ProcessPoolExecutor(workers) as ex:
        for rows, ty in zip(ex.map(_simulate_typist, jobs, chunksize=2), pop):
            sessions += [Session(sid, ty.id, role, cond, var, sw, dur, st, partner, order)
                         for sid, role, cond, var, sw, dur, st, partner, order in rows]
    c = Corpus(f"synthetic:{key}", sessions, synthetic_attributes(pop),
               {"typists": n, "seed": seed, "n_base": n_base, "minutes": minutes})
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(c, f)
    return c


# ------------------------------------------------------------ recorded study data

BASELINE_DAYS = 28.0


def db_corpus(db_path: Path, labels_dir: Path) -> Corpus:
    """Recorded sessions + the study's labels manifest (see module docstring)."""
    from ..db import Database
    from ..export import load_session

    db = Database(str(db_path))
    labels_dir = Path(labels_dir)
    with open(labels_dir / "sessions.csv", newline="") as f:
        rows = {r["session_id"]: r for r in csv.DictReader(f)}
    students: dict[str, dict] = {}
    if (labels_dir / "students.csv").exists():
        with open(labels_dir / "students.csv", newline="") as f:
            for r in csv.DictReader(f):
                sid = r.pop("student")
                students[sid] = {k: v for k, v in r.items() if v != ""}
    meta = {r["id"]: dict(r) for r in db.list_sessions()}
    first: dict[str, float] = {}
    for sid in rows:
        m = meta[sid]
        first[m["student_id"]] = min(first.get(m["student_id"], m["started_at"]), m["started_at"])
    sessions = []
    for sid, r in rows.items():
        m = meta[sid]
        st = streams(load_session(db, sid))
        cond = r.get("condition") or "honest"
        role = r.get("role") or ("baseline" if cond == "honest" and m["started_at"] - first[m["student_id"]]
                                 <= BASELINE_DAYS * 86400 else "test")
        sw = r.get("switch_s", "")
        sessions.append(Session(sid, m["student_id"], role, cond, r.get("variant") or cond,
                                float(sw) if sw not in ("", None) else None, st.duration_ms / 1000, st,
                                r.get("partner") or None, int(m["started_at"])))
        students.setdefault(m["student_id"], {})
    return Corpus(f"db:{Path(db_path).name}", sessions, students, {"labels": str(labels_dir)})


def write_manifest_template(corpus: Corpus, out: Path) -> None:
    """Write sessions.csv / students.csv for a corpus (used by tests and as a template)."""
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "sessions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["session_id", "role", "condition", "variant", "switch_s", "partner"])
        for s in corpus.sessions:
            w.writerow([s.id, s.role, s.condition, s.variant, "" if s.switch_s is None else s.switch_s, s.partner or ""])
    attrs = sorted({k for a in corpus.students.values() for k in a})
    with open(out / "students.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["student", *attrs])
        for sid, a in corpus.students.items():
            w.writerow([sid, *(a.get(k, "") for k in attrs)])


def describe(corpus: Corpus) -> dict:
    by = {}
    for s in corpus.sessions:
        by[f"{s.role}:{s.variant}"] = by.get(f"{s.role}:{s.variant}", 0) + 1
    return {"source": corpus.source, "students": len(corpus.students), "sessions": by,
            "fingerprint": corpus.fingerprint(), **{k: v for k, v in corpus.meta.items()}}


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, default=float)

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
    meta: dict = field(default_factory=dict)  # classroom data: lab, question, device, started_at, person, splice
    # precomputed windows by window length ("separate" comments only): stored windows of a
    # purged session, or a window-level splice; Corpus.windows uses them before the streams
    win: dict[float, list[dict]] | None = None


@dataclass
class Corpus:
    source: str
    sessions: list[Session]
    students: dict[str, dict]  # student -> attributes
    meta: dict = field(default_factory=dict)
    _win: dict = field(default_factory=dict, repr=False)

    def baseline(self, student: str, n: int | None = None) -> list[Session]:
        b = sorted((s for s in self.sessions if s.student == student and s.role == "baseline"), key=lambda s: s.order)
        if "baseline_min" in self.meta:  # classroom data: the baseline is a number of minutes, not sessions
            return b
        return b[:n] if n else b

    def tests(self, students=None) -> list[Session]:
        keep = set(students) if students is not None else None
        return [s for s in self.sessions if s.role == "test" and (keep is None or s.student in keep)]

    def windows(self, s: Session, W: float, comments: str = "separate") -> list[dict]:
        if comments == "separate" and s.win and float(W) in s.win:
            return s.win[float(W)]
        key = (s.id, W, comments)
        if key not in self._win:
            self._win[key] = window_features(s.st, W, comments=comments)
        return self._win[key]

    def split_students(self, test_frac: float | None = None) -> tuple[list[str], list[str]]:
        """Dev and test students. A student key may be one person on one device class
        (classroom corpus with by_device): the split always hashes the person."""
        from .split import TEST_FRAC, assign
        person = {k: a.get("person", k) for k, a in self.students.items()}
        side = assign(set(person.values()), TEST_FRAC if test_frac is None else test_frac)
        return (sorted(k for k in person if side[person[k]] == "dev"),
                sorted(k for k in person if side[person[k]] == "test"))

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


# ------------------------------------------------------------ naturalistic classroom data

BASELINE_MIN = 10.0  # active typing minutes that make a student's baseline (pilot median total is short)
MIN_BASELINE_MIN = 3.0  # below this a student is not scored


def classroom_corpus(db_path: Path, baseline_min: float = BASELINE_MIN, by_device: bool = False,
                     test_frac: float | None = None) -> Corpus:
    """Every study session in the database, with no staging and no labels manifest.

    All sessions are honest as far as anyone knows. A student's baseline is their
    earliest `baseline_min` active typing minutes (30 s windows with enough keys), from
    whatever sessions those were in, but never their last session, so something is left
    to score; the rest are scored. A student whose baseline would be under
    MIN_BASELINE_MIN, or who has one usable session, is role "unscored". With `by_device`, each
    (student, device class) pair is its own "student" with its own baseline, and the
    split still hashes the person. Sessions with no active window are left out (role
    "idle") so empty tabs don't count as honest hours. Dev-hash students' sessions from
    PILOT_TEST_FROM on are role "later": held out with the test split (split.pilot_split).
    Labelled switches come from splicing these sessions (harness.splice).

    Purged sessions (raw keys deleted, retention.py) carry their stored windows in
    `Session.win`, so the thesis detector scores them; the keystroke baselines
    (scaled Manhattan, TypeNet-style) need raw keys and see nothing there."""
    from ..db import Database
    from ..export import load_session
    from ..pilot import device_class, device_fingerprint, ua_info
    from .split import PILOT_TEST_FROM, TEST_FRAC, assign

    db = Database(str(db_path))
    tf = TEST_FRAC if test_frac is None else test_frac
    rows = [dict(r) for r in db.list_sessions()]  # learning lab and previews are never study data
    with db.connect() as conn:
        kind = {r[0]: r[1] for r in conn.execute("SELECT id, kind FROM labs")}
        try:
            stored = {}
            for sid, w in conn.execute("SELECT session_id, window_s FROM session_windows"):
                stored.setdefault(sid, []).append(float(w))
        except Exception:  # noqa: BLE001 - no purge has run yet
            stored = {}
    fps, on_fp = {}, {}
    for r in rows:
        meta = json.loads(r["client_meta"] or "{}")
        client = "desktop" if (meta.get("client") or {}).get("kind") == "desktop" else "web"
        fps[r["id"]] = (device_fingerprint(meta), client, ua_info(meta.get("user_agent"))[0])
        on_fp.setdefault(fps[r["id"]][0], set()).add(r["student_id"])
    from ..retention import stored_windows
    sessions = []
    for r in sorted(rows, key=lambda r: r["started_at"]):
        if not r["n_events"]:
            continue
        fp, client, os_ = fps[r["id"]]
        q = json.loads(r["question_json"]) if r["question_json"] else {}
        ctx = r["context"] or ("competition" if kind.get(r["lab_id"]) == "competition" else
                               "lab" if r["lab_id"] in kind else "sandbox" if r["lab_id"] else "practice")
        dev = device_class(client, os_, len(on_fp[fp]))
        st = streams(load_session(db, r["id"]))
        win = {W: stored_windows(db, r["id"], W) for W in stored.get(r["id"], [])} if r["keys_purged_at"] else None
        person = r["student_id"]
        sessions.append(Session(
            r["id"], f"{person}@{dev}" if by_device else person, "", "honest", "honest", None,
            st.duration_ms / 1000, st, None, 0, win=win,
            meta={"person": person, "lab": r["lab_id"], "question": r["question_id"] or r["task_id"], "ctx": ctx,
                  "lang": q.get("language"), "device": dev, "os": os_, "fp": fp, "started_at": r["started_at"],
                  "purged": r["keys_purged_at"] is not None}))
    c = Corpus(f"classroom:{Path(db_path).name}", sessions, {},
               {"baseline_min": baseline_min, "by_device": by_device, "test_from": PILOT_TEST_FROM})
    side = assign({s.meta["person"] for s in sessions}, tf)
    used: dict[str, float] = {}
    order: dict[str, int] = {}
    usable: dict[str, list[Session]] = {}
    for s in sessions:  # already in time order
        active = sum(w["active"] for w in c.windows(s, 30.0)) * 0.5  # minutes
        if side[s.meta["person"]] == "dev" and s.meta["started_at"] >= PILOT_TEST_FROM:
            s.role = "later"
        elif not active:
            s.role = "idle"
        else:
            usable.setdefault(s.student, []).append(s)
        s.meta["active_min"] = active
    # baseline: the shortest run of earliest sessions reaching baseline_min, but never the
    # student's last session (something must be left to score); under MIN_BASELINE_MIN the
    # student is not scored at all ("unscored")
    for st, ss in usable.items():
        n, tot = 0, 0.0
        while n < len(ss) - 1 and tot < baseline_min:
            tot += ss[n].meta["active_min"]
            n += 1
        if len(ss) == 1 or tot < MIN_BASELINE_MIN:
            for s in ss:
                s.role = "unscored"
            continue
        for i, s in enumerate(ss):
            s.role = "baseline" if i < n else "test"
        used[st] = tot
    for s in sessions:
        active = s.meta["active_min"]
        s.order = order[s.student] = order.get(s.student, -1) + 1
        a = c.students.setdefault(s.student, {"person": s.meta["person"]})
        for k in ("device", "lang", "ctx"):
            a.setdefault(f"_{k}", {}).setdefault(s.meta[k], 0.0)
            a[f"_{k}"][s.meta[k]] += active
    for key, a in c.students.items():  # subgroup attributes for RQ4: where most of a student's typing happened
        for k in ("device", "lang", "ctx"):
            counts = a.pop(f"_{k}")
            a[k] = str(max(counts, key=counts.get)) if counts else ""
        a["baseline_min"] = round(used.get(key, 0.0), 1)
    return c


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

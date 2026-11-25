"""Labelled takeovers built from real, unlabelled classroom sessions.

The pilot has no staged sessions, so nobody knows when (or whether) a real change
of author happened. Splicing makes one whose time is known: student A's real
session runs up to a switch time tau, then continues with student B's real
typing from the same point in B's session on the same question, shifted in time
to follow on from A. Every key, edit and run on either side was really typed by
that student in class; only the join is made up.

Two levels, so it also works after the 28-day raw-key purge:

- `splice_streams`: the event streams themselves (all methods, including the
  keystroke baselines that need raw keys);
- `splice_windows`: the stored per-window features of each window length
  (thesis detector only), joined at a window boundary.

Partners come from the same question, so the task and its stage are comparable,
and from the same side of the dev/test split. A partner on the same device class
gives variant "takeover"; one on another device class, "takeover_random" (an
easier, less realistic case: the device change is part of the signal). Both reuse
the harness's takeover reporting. tau is a multiple of SNAP_S (the longest
window length), so the windows of every length line up with the join.

What a splice cannot show: B continues their own code, not A's, so line-level
build order (filling in above existing code) reflects B's document. A real
helper sitting down at A's code would also have to read it first; splices have
no such pause. Both make the process channel's job somewhat easier than a real
takeover, so splice detection is an optimistic estimate for that channel and the
thesis reports the identity channels on their own as well.
"""

from __future__ import annotations

import dataclasses
import math
import zlib

import numpy as np

from ..detector.features import Streams
from .corpus import Corpus, Session
from .split import TEST_FRAC, assign

SNAP_S = 90.0  # every window length in the frozen config divides this
MIN_BEFORE_S = 180.0  # at least this much of A before the switch
MIN_AFTER_S = 180.0  # and of B after it
MIN_ACTIVE = 2  # active 30 s windows needed on each side

# Streams fields that share one time axis; the first of each group is the time
GROUPS = [
    ("k_t", "k_code", "k_cls", "k_shift", "k_hold", "k_comment", "k_hand"),
    ("e_t", "e_append", "e_line", "e_inserted", "e_paste"),
    ("run_t",), ("focus_out_t",), ("switch_t",),
    ("l_t", "l_fill"), ("b_t", "b_open"),
]


def _take(v, idx):
    return v[idx] if isinstance(v, np.ndarray) else [v[i] for i in idx]


def _join(a, b):
    return np.concatenate([a, b]) if isinstance(a, np.ndarray) else list(a) + list(b)


def splice_streams(a: Streams, b: Streams, tau_s: float, b_from_s: float | None = None) -> Streams:
    """A before tau, then B from b_from (default: the same time tau) onwards, moved to start at tau."""
    tau, frm = tau_s * 1000, (tau_s if b_from_s is None else b_from_s) * 1000
    shift = tau - frm
    out = {}
    for g in GROUPS:
        ta, tb = getattr(a, g[0]), getattr(b, g[0])
        ia = np.flatnonzero(np.asarray(ta) < tau)
        ib = np.flatnonzero(np.asarray(tb) >= frm)
        for f in g:
            va, vb = _take(getattr(a, f), ia), _take(getattr(b, f), ib)
            if f == g[0]:
                vb = np.asarray(vb, float) + shift
            out[f] = _join(va, vb)
    return dataclasses.replace(a, duration_ms=max(tau, b.duration_ms + shift), meta={"splice": True}, **out)


def splice_windows(wa: list[dict], wb: list[dict], tau_s: float, b_from_s: float | None = None) -> list[dict]:
    """A's windows that end by tau, then B's windows that start at or after b_from, moved to follow on."""
    frm = tau_s if b_from_s is None else b_from_s
    shift = tau_s - frm
    left = [w for w in wa if w["end"] <= tau_s + 1e-6]
    right = [{**w, "start": w["start"] + shift, "end": w["end"] + shift} for w in wb if w["start"] >= frm - 1e-6]
    return left + right


def _active_between(corpus: Corpus, s: Session, lo: float, hi: float) -> int:
    return sum(1 for w in corpus.windows(s, 30.0) if w["active"] and w["start"] >= lo and w["end"] <= hi)


def _has_keys(s: Session) -> bool:
    return len(s.st.k_t) > 0 and not s.meta.get("purged")


def splice_session(corpus: Corpus, a: Session, b: Session, tau_s: float, variant: str) -> Session | None:
    """One spliced test session (A's student, switch at tau), or None if the two can't be joined."""
    sid = f"{a.id}~{b.id}@{tau_s:g}"
    meta = {**a.meta, "splice": True, "partner_session": b.id, "partner_device": b.meta.get("device")}
    if _has_keys(a) and _has_keys(b):
        st = splice_streams(a.st, b.st, tau_s)
        return Session(sid, a.student, "test", "takeover", variant, tau_s, st.duration_ms / 1000, st,
                       b.student, a.order, meta=meta)
    if a.win or b.win:  # one is purged: join windows at each length the purged side(s) stored
        Ws = sorted(set(a.win or b.win) & set(b.win or a.win))
        if not Ws:
            return None
        win = {W: splice_windows(corpus.windows(a, W), corpus.windows(b, W), tau_s) for W in Ws}
        dur = max([w["end"] for ws in win.values() for w in ws] or [tau_s])
        st = dataclasses.replace(a.st, duration_ms=dur * 1000, meta={"splice": True})  # stream-based methods: A only
        return Session(sid, a.student, "test", "takeover", variant, tau_s, dur, st, b.student, a.order,
                       meta={**meta, "windows_only": True}, win=win)
    return None


def add_splices(corpus: Corpus, seed: int = 0, per_session: int = 1, test_frac: float | None = None,
                group: tuple[str, ...] = ("question",)) -> list[Session]:
    """Add spliced takeovers to `corpus` (role test) and return them.

    For each honest test session A: partners B are other people's sessions on the
    same `group` key (by default the question) on the same side of the person split,
    with enough active typing after tau. tau is drawn uniformly from the SNAP_S
    multiples that leave MIN_BEFORE_S of A and MIN_AFTER_S of B. Same-device-class
    partners are preferred ("takeover"); otherwise any device ("takeover_random").
    Deterministic for a given seed. Sessions with no partner are skipped."""
    people = {s.meta.get("person", s.student) for s in corpus.sessions}
    side = assign(people, TEST_FRAC if test_frac is None else test_frac)
    pool: dict[tuple, list[Session]] = {}

    def side_of(s: Session) -> str:  # held-out later sessions (test run) are on the test side, whoever typed them
        return "test" if s.meta.get("held_out") else side[s.meta.get("person", s.student)]

    for s in corpus.sessions:
        if s.role in ("test", "baseline") and s.condition == "honest" and all(s.meta.get(k) for k in group):
            pool.setdefault((side_of(s), *(s.meta[k] for k in group)), []).append(s)
    made = []
    for a in [s for s in corpus.sessions if s.role == "test" and s.condition == "honest" and not s.meta.get("splice")]:
        if not all(a.meta.get(k) for k in group):
            continue
        me = a.meta.get("person", a.student)
        rng = np.random.default_rng([seed, zlib.crc32(a.id.encode())])
        cands = [b for b in pool.get((side_of(a), *(a.meta[k] for k in group)), []) if b.meta.get("person", b.student) != me]
        taus = np.arange(SNAP_S * math.ceil(MIN_BEFORE_S / SNAP_S), a.duration_s - MIN_AFTER_S + 1e-6, SNAP_S)
        taus = [t for t in taus if _active_between(corpus, a, 0, t) >= MIN_ACTIVE]
        if not cands or not taus:
            continue
        same = [b for b in cands if b.meta.get("device") == a.meta.get("device")]
        for _ in range(per_session):
            tau = float(rng.choice(taus))
            for variant, opts in (("takeover", same), ("takeover_random", cands)):
                ok = [b for b in opts if b.duration_s - tau >= MIN_AFTER_S
                      and _active_between(corpus, b, tau, b.duration_s) >= MIN_ACTIVE]
                if ok:
                    b = ok[int(rng.integers(len(ok)))]
                    s = splice_session(corpus, a, b, tau, variant)
                    if s is not None:
                        made.append(s)
                        break
    corpus.sessions.extend(made)
    corpus.meta["splices"] = {"seed": seed, "per_session": per_session, "group": list(group), "n": len(made)}
    return made

"""RQ2: composing versus transcribing, replicating Nosi at a larger N.

Lueder et al. (Nosi) classify windows of keystrokes as composing or
transcribing from one number, the L-scale of log inter-key time, with a
linear SVM under leave-one-participant-out cross-validation (N = 5 authors,
about 80% at 150 s). With one feature a linear SVM is a threshold, so here
the threshold (and its direction) is chosen on the other participants to
maximise balanced accuracy and applied to the held-out one.

Windows: composing = honest test sessions plus the part of copying-out
sessions before the switch; transcribing = windows wholly after the switch
in copying-out sessions (condition D). Three scorers:

- `nosi`      raw L-scale of log IAT, every key (comments included), one
              population threshold (the original recipe);
- `personal`  the same L-scale as a z-score against the student's own
              baseline (median / MAD), one population threshold on z;
- `process`   the thesis detector's process-channel distance (pauses,
              revisions, build order, runs, focus, paste) against the
              student's baseline.

Also: the accuracy spread when only 5 participants are available (random
5-person subsets, the size of Nosi's study), and the comment confound:
chunks of comment keystrokes scored with the composing/transcribing
threshold learnt on code.
"""

from __future__ import annotations

import math

import numpy as np

from ..detector.detector import Baseline, channel_features
from ..detector.features import PAUSE_MS, lscale
from .corpus import Corpus, Session

WINDOWS = [30, 60, 90, 120, 150, 300]
SCORERS = ("nosi", "personal", "process")


def _labelled(corpus: Corpus, students, W: float):
    """Rows (student, label 1=transcribing, nosi, personal, process) for one W."""
    rows = []
    feats = channel_features("process")
    for st in students:
        base = corpus.baseline(st, 4)
        bl = [w["dg_lscale"] for s in base for w in corpus.windows(s, W, "mixed") if w["active"] and not math.isnan(w["dg_lscale"])]
        if len(bl) < 3:
            continue
        med = float(np.median(bl))
        mad = max(1.4826 * float(np.median(np.abs(np.array(bl) - med))), 0.02)
        proc = Baseline.fit(st, [corpus.windows(s, W) for s in base], feats)
        for s in corpus.tests([st]):
            if s.condition not in ("honest", "copying"):
                continue
            mixed = corpus.windows(s, W, "mixed")
            sep = corpus.windows(s, W)
            for wm, ws in zip(mixed, sep):
                if not wm["active"] or math.isnan(wm["dg_lscale"]):
                    continue
                if s.condition == "copying":
                    if ws["start"] >= s.switch_s:
                        lab = 1
                    elif ws["end"] <= s.switch_s:
                        lab = 0
                    else:
                        continue  # straddles the switch
                else:
                    lab = 0
                d = proc.distance(ws)
                rows.append((st, lab, wm["dg_lscale"], (wm["dg_lscale"] - med) / mad,
                             (d - proc.mu0) / proc.sd0 if not math.isnan(d) else math.nan))
    return rows


def _best_threshold(x: np.ndarray, y: np.ndarray) -> tuple[float, int]:
    """Threshold and direction (+1: transcribing if x >= thr) maximising balanced accuracy."""
    best = (0.5, 0.0, 1)
    for thr in np.quantile(x, np.linspace(0.01, 0.99, 99)):
        for sgn in (1, -1):
            pred = (x >= thr) if sgn == 1 else (x <= thr)
            ba = 0.5 * (pred[y == 1].mean() + (~pred[y == 0]).mean())
            if ba > best[0]:
                best = (ba, float(thr), sgn)
    return best[1], best[2]


def lopo(rows, col: int) -> dict:
    """Leave-one-participant-out balanced accuracy for scorer column `col`."""
    rows = [r for r in rows if not math.isnan(r[col])]
    studs = sorted({r[0] for r in rows})
    S = np.array([r[0] for r in rows])
    y = np.array([r[1] for r in rows])
    x = np.array([r[col] for r in rows], float)
    pred = np.zeros(len(rows), bool)
    for st in studs:
        tr, te = S != st, S == st
        if len(set(y[tr])) < 2:
            continue
        thr, sgn = _best_threshold(x[tr], y[tr])
        pred[te] = (x[te] >= thr) if sgn == 1 else (x[te] <= thr)
    per = {}
    for st in studs:
        m = S == st
        if (y[m] == 1).any() and (y[m] == 0).any():
            per[st] = 0.5 * (pred[m & (y == 1)].mean() + (~pred[m & (y == 0)]).mean())
    ba = 0.5 * (pred[y == 1].mean() + (~pred[y == 0]).mean()) if (y == 1).any() else math.nan
    return {"bal_acc": float(ba), "per_student": per, "n_windows": len(rows), "n_students": len(studs),
            "n_transcribing": int((y == 1).sum())}


def _ci(per: dict, B: int = 1000, seed: int = 0) -> tuple[float, float]:
    v = np.array(list(per.values()))
    if not len(v):
        return (math.nan, math.nan)
    r = np.random.default_rng(seed)
    m = [v[r.integers(0, len(v), len(v))].mean() for _ in range(B)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def small_n(rows, col: int, n: int = 5, reps: int = 200, seed: int = 0) -> dict:
    """LOPO accuracy when only `n` participants exist (Nosi's study size)."""
    studs = sorted({r[0] for r in rows})
    r = np.random.default_rng(seed)
    accs = []
    for _ in range(reps):
        pick = set(r.choice(studs, min(n, len(studs)), replace=False))
        res = lopo([row for row in rows if row[0] in pick], col)
        if not math.isnan(res["bal_acc"]):
            accs.append(res["bal_acc"])
    return {"n": n, "mean": float(np.mean(accs)), "p5": float(np.percentile(accs, 5)),
            "p95": float(np.percentile(accs, 95)), "reps": len(accs)}


def _chunks(s: Session, comment: bool, after: float | None, size: int = 60) -> list[float]:
    st = s.st
    m = st.k_comment if comment else ~st.k_comment
    t = st.k_t[m]
    if after is not None:
        t = t[t >= after * 1000]
    lat = np.diff(t)
    lat = lat[(lat > 0) & (lat < PAUSE_MS)]
    return [lscale(np.log(lat[i:i + size])) for i in range(0, len(lat) - size + 1, size)]


def comment_confound(corpus: Corpus, students) -> dict:
    """Chunks of 60 inter-key times: composing code, comments, transcribing code."""
    code, com, tr = [], [], []
    for s in corpus.tests(students):
        if s.condition == "honest":
            code += _chunks(s, False, None)
            com += _chunks(s, True, None)
        elif s.condition == "copying":
            tr += _chunks(s, False, s.switch_s)
    x = np.r_[code, tr]
    y = np.r_[np.zeros(len(code)), np.ones(len(tr))]
    thr, sgn = _best_threshold(x, y)
    as_tr = lambda v: float(np.mean((np.array(v) >= thr) if sgn == 1 else (np.array(v) <= thr))) if v else math.nan  # noqa: E731
    return {"chunk_keys": 60, "lscale_mean": {"code": float(np.mean(code)), "comments": float(np.mean(com)) if com else math.nan,
                                              "transcribing": float(np.mean(tr))},
            "n_chunks": {"code": len(code), "comments": len(com), "transcribing": len(tr)},
            "judged_transcribing": {"code": as_tr(code), "comments": as_tr(com), "transcribing": as_tr(tr)}}


def run(corpus: Corpus, students, windows=WINDOWS, log=print) -> dict:
    out = {"windows": [], "small_n": {}, "comments": comment_confound(corpus, students)}
    rows150 = None
    for W in windows:
        rows = _labelled(corpus, students, W)
        row = {"window_s": W}
        for i, name in enumerate(SCORERS):
            res = lopo(rows, 2 + i)
            lo, hi = _ci(res["per_student"])
            row[name] = res["bal_acc"]
            row[f"{name}_lo"], row[f"{name}_hi"] = lo, hi
            row["n_students"], row[f"n_windows_{name}"] = res["n_students"], res["n_windows"]
        out["windows"].append(row)
        log(f"  RQ2 W={W:>3}s  nosi={row['nosi']:.3f}  personal={row['personal']:.3f}  process={row['process']:.3f}")
        if W == 150:
            rows150 = rows
    if rows150:
        out["small_n"] = {name: small_n(rows150, 2 + i) for i, name in enumerate(SCORERS)}
    return out

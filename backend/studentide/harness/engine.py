"""Scoring runs, operating points and metrics.

`score_run()` fits a method's population-level parts on `train` students,
fits every student's baseline, and scores (a) the evaluation students' test
sessions, (b) the calibration students' honest test sessions ("holdout"
calibration) and (c) every student's baseline sessions leave-one-session-out
("self" calibration: needs no staged sessions at all). `outcomes()` then
picks h per channel for a false-alarm target and turns each evaluated
session into an `Outcome`; the metric functions work on those records.

Cross-fitting on dev: `cv_runs()` repeats `score_run()` with each dev fold
held out once; outcomes of all folds are pooled, each fold with its own h.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .alarms import H_GRID, calibrate, combine, grid
from .corpus import Corpus, Session
from .methods import Method, Series
from .split import folds

CALIB_SOURCES = ("holdout", "self", "pooled")


@dataclass
class Run:
    method: Method
    eval_sessions: list[Session]
    series: dict[str, dict[str, Series]]  # session id -> channel -> series
    holdout: list[tuple[Session, dict[str, Series]]]  # calibration students' honest test sessions
    self_cal: list[tuple[float, dict[str, Series]]]  # (duration s, series) of baseline LOSO sessions
    _g: dict = field(default_factory=dict)
    _self_students: list = field(default_factory=list)
    _self_owner: list = field(default_factory=list)  # student of each self_cal entry

    def grids(self, k: dict[str, float], rule: str) -> dict:
        key = (tuple(sorted(k.items())), rule)
        if key not in self._g:
            ev = {s.id: {ch: grid(x, k[ch], s.switch_s, rule) for ch, x in self.series[s.id].items()}
                  for s in self.eval_sessions}
            ho = [{ch: grid(x, k[ch], None, rule) for ch, x in ser.items()} for _, ser in self.holdout]
            sc = [{ch: grid(x, k[ch], None, rule) for ch, x in ser.items()} for _, ser in self.self_cal]
            self._g[key] = (ev, ho, sc)
        return self._g[key]

    def h_index(self, k, rule, source: str, target: float, n_cal: int | None = None, rng=None) -> dict[str, int]:
        _, ho, sc = self.grids(k, rule)
        ho_h = [s.duration_s / 3600 for s, _ in self.holdout]
        sc_h = [d / 3600 for d, _ in self.self_cal]
        if n_cal is not None and rng is not None:
            # restrict calibration to n_cal students (calibration-size experiment)
            studs = sorted({s.student for s, _ in self.holdout} | {st for st in self._self_students})
            pick = set(rng.choice(studs, min(n_cal, len(studs)), replace=False))
            hi = [i for i, (s, _) in enumerate(self.holdout) if s.student in pick]
            si = [i for i, st in enumerate(self._self_owner) if st in pick]
            ho, ho_h = [ho[i] for i in hi], [ho_h[i] for i in hi]
            sc, sc_h = [sc[i] for i in si], [sc_h[i] for i in si]
        use = {"holdout": (ho, ho_h), "self": (sc, sc_h), "pooled": (ho + sc, ho_h + sc_h)}[source]
        chans = list(self.method.channels)
        return {ch: calibrate([g[ch] for g in use[0]], sum(use[1]), target / len(chans)) for ch in chans}


def score_run(method: Method, corpus: Corpus, train: list[str], evaluate: list[str], n_base: int = 4,
              calib_students: list[str] | None = None, self_cal: bool = True) -> Run:
    calib_students = train if calib_students is None else calib_students
    method.fit_population(corpus, train, n_base)
    models = {}
    for st in set(evaluate) | set(calib_students):
        models[st] = method.fit_student(corpus, st, corpus.baseline(st, n_base))
    ev = corpus.tests(evaluate)
    series = {s.id: method.score(corpus, models[s.student], s) for s in ev}
    holdout = [(s, method.score(corpus, models[s.student], s)) for s in corpus.tests(calib_students)
               if s.condition == "honest"]
    sc, owner = [], []
    if self_cal:
        for st in sorted(set(evaluate) | set(calib_students)):
            base = corpus.baseline(st, n_base)
            for s, ser in zip(base, method.loso_series(corpus, st, base)):
                sc.append((s.duration_s, ser))
                owner.append(st)
    r = Run(method, ev, series, holdout, sc)
    r._self_students = sorted(set(owner))
    r._self_owner = owner
    return r


def cv_runs(method_factory, corpus: Corpus, dev: list[str], k: int = 5, n_base: int = 4,
            self_cal: bool = True, log=None) -> list[Run]:
    runs = []
    for i, fold in enumerate(folds(dev, k)):
        train = [s for s in dev if s not in set(fold)]
        runs.append(score_run(method_factory(), corpus, train, fold, n_base, self_cal=self_cal))
        if log:
            log(f"    fold {i + 1}/{k}")
    return runs


# ------------------------------------------------------------------ records

def outcomes(runs: list[Run], corpus: Corpus, source: str = "holdout", target: float = 0.2,
             k: dict[str, float] | None = None, rule: str = "cusum") -> list[dict]:
    recs = []
    for run in runs:
        kk = k or run.method.k()
        idx = run.h_index(kk, rule, source, target)
        ev, _, _ = run.grids(kk, rule)
        for s in run.eval_sessions:
            o = combine(ev[s.id], idx)
            recs.append({"student": s.student, "variant": s.variant, "condition": s.condition,
                         "switch_s": s.switch_s, "duration_s": s.duration_s, "o": o,
                         "attrs": corpus.students.get(s.student, {}),
                         "h": {ch: float(H_GRID[i]) for ch, i in idx.items()}})
    return recs


def _med(v):
    return float(np.median(v)) if len(v) else math.nan


def summarise(recs: list[dict]) -> dict:
    """Point estimates. Variants other than honest: detected = alarm after the switch."""
    out = {}
    honest = [r for r in recs if r["condition"] == "honest"]
    hours = sum(r["duration_s"] for r in honest) / 3600
    out["honest"] = {"n": len(honest), "hours": hours,
                     "fa_per_h": sum(r["o"].alarms for r in honest) / hours if hours else math.nan,
                     "flagged": float(np.mean([r["o"].alarms > 0 for r in honest])) if honest else math.nan}
    for v in dict.fromkeys(r["variant"] for r in recs if r["condition"] != "honest"):
        rs = [r for r in recs if r["variant"] == v]
        hit = [r for r in rs if not math.isnan(r["o"].first_after)]
        delays = [r["o"].first_after - r["switch_s"] for r in hit]
        errs = [abs(r["o"].est_switch - r["switch_s"]) for r in hit]
        chans = {}
        for r in hit:
            chans[r["o"].channel] = chans.get(r["o"].channel, 0) + 1
        out[v] = {"n": len(rs), "detected": len(hit) / len(rs) if rs else math.nan,
                  "delay_median_s": _med(delays),
                  "delay_p90_s": float(np.percentile(delays, 90)) if delays else math.nan,
                  "switch_err_median_s": _med(errs), "early_alarms": sum(r["o"].before for r in rs),
                  "first_channel": chans}
    cheat = [r for r in recs if r["condition"] != "honest"]
    out["tpr"] = float(np.mean([not math.isnan(r["o"].first_after) for r in cheat])) if cheat else math.nan
    out["fpr"] = out["honest"]["flagged"]
    return out


def precision(tpr: float, fpr: float, prevalence: float) -> float:
    den = tpr * prevalence + fpr * (1 - prevalence)
    return tpr * prevalence / den if den > 0 else math.nan


def bootstrap(recs: list[dict], stat, B: int = 1000, seed: int = 0) -> tuple[float, float]:
    """95% percentile interval of stat(records), resampling students."""
    by: dict[str, list] = {}
    for r in recs:
        by.setdefault(r["student"], []).append(r)
    studs = list(by)
    if not studs:
        return (math.nan, math.nan)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(B):
        pick = rng.integers(0, len(studs), len(studs))
        v = stat([r for i in pick for r in by[studs[i]]])
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            vals.append(v)
    if not vals:
        return (math.nan, math.nan)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def stat_detected(variant):
    def f(rs):
        rs = [r for r in rs if r["variant"] == variant]
        return float(np.mean([not math.isnan(r["o"].first_after) for r in rs])) if rs else math.nan
    return f


def stat_delay(variant):
    def f(rs):
        d = [r["o"].first_after - r["switch_s"] for r in rs if r["variant"] == variant and not math.isnan(r["o"].first_after)]
        return _med(d)
    return f


def stat_fa(rs):
    h = [r for r in rs if r["condition"] == "honest"]
    hours = sum(r["duration_s"] for r in h) / 3600
    return sum(r["o"].alarms for r in h) / hours if hours else math.nan


def stat_flagged(rs):
    h = [r for r in rs if r["condition"] == "honest"]
    return float(np.mean([r["o"].alarms > 0 for r in h])) if h else math.nan


def stat_precision(prevalence):
    def f(rs):
        s = summarise(rs)
        return precision(s["tpr"], s["fpr"], prevalence)
    return f


def window_auc(runs: list[Run]) -> float:
    """Honest windows vs windows typed wholly by another person, first channel."""
    from ..detector.evaluate import auc
    neg, pos = [], []
    for run in runs:
        ch = next(iter(run.method.channels))
        for s in run.eval_sessions:
            x = run.series[s.id][ch]
            ok = ~np.isnan(x.x)
            if s.condition == "honest":
                neg += list(x.x[ok])
            elif s.condition in ("proxy", "takeover"):
                pos += list(x.x[ok & (x.start >= s.switch_s)])
    return auc(np.array(neg), np.array(pos))


def curve(runs: list[Run], corpus: Corpus, targets, source="holdout", k=None, rule="cusum") -> list[dict]:
    """Detection vs achieved false alarms per hour, sweeping the calibration target."""
    rows = []
    for t in targets:
        s = summarise(outcomes(runs, corpus, source, t, k, rule))
        row = {"target": t, "fa_per_h": s["honest"]["fa_per_h"], "flagged": s["honest"]["flagged"], "tpr": s["tpr"]}
        for v, m in s.items():
            if isinstance(m, dict) and "detected" in m:
                row[v] = m["detected"]
        rows.append(row)
    return rows


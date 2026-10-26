"""Harness command line: `dev` designs and freezes, `test` reports once.

    python -m studentide.harness dev  --thesis ../thesis/latex    # ~15 min on 4 cores
    python -m studentide.harness test --thesis ../thesis/latex    # ~5 min

    # recorded study data instead of simulated people:
    python -m studentide.harness dev --db data/study.sqlite3 --labels data/labels/

dev (dev students only, 5-fold cross-fitting):
  1. calibration: holdout vs self vs pooled sources, and how many calibration
     students h needs (target vs achieved false alarms per hour);
  2. the thesis detector's open choices (process-channel window, population
     prior, then how to use per-key-pair timing) and each baseline's alarm
     rule, k and window, by mean detection over the five non-honest
     conditions at <= target false alarms per hour;
  3. ablations: window length, channels, feature groups (incl. build order),
     alarm rule, comments, k;
  4. short baselines: 1-8 baseline sessions, with and without the prior;
  then writes the frozen configuration.

test (test students, scored once per frozen configuration; logged in the ledger):
  RQ1 detector vs baselines at the frozen operating point, detection-vs-false-
  alarm curves, per-condition results with bootstrap intervals; RQ2 composing vs
  transcribing; RQ4 precision at 1/100 and 1/500 prevalence and subgroup error
  rates; calibration check on unseen students.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

from ..detector.evaluate import write_csv
from ..detector.features import FEATURES, GROUPS, LEGACY_FEATURES
from . import report, rq2
from .corpus import Corpus, db_corpus, describe, synthetic_corpus
from .engine import (CALIB_SOURCES, bootstrap, curve, cv_runs, outcomes, precision, score_run, stat_delay,
                     stat_detected, stat_fa, stat_flagged, stat_precision, summarise, window_auc)
from .methods import ChannelSpec, ChannelMethod, ScaledManhattan, TypeNetStyle, nosi_style, thesis_detector
from .split import Ledger, config_hash, git_state, split

CHEAT = report.CHEAT
TARGETS = [0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO / "thesis" / "evaluation"

_CORPUS: Corpus | None = None  # shared with forked workers


def log(*a):
    print(*a, flush=True)


def load(a) -> Corpus:
    if a.db:
        return db_corpus(a.db, a.labels)
    return synthetic_corpus(a.typists, a.seed, n_base=8, minutes=a.minutes, cache=a.cache)


def row(recs, runs, extra: dict | None = None) -> dict:
    s = summarise(recs)
    r = dict(extra or {})
    r.update({"window_auc": window_auc(runs), "fa_per_h": s["honest"]["fa_per_h"], "flagged": s["honest"]["flagged"],
              "tpr": s["tpr"], "takeover_delay": s.get("takeover", {}).get("delay_median_s", math.nan),
              "mean_detected": float(np.mean([s[v]["detected"] for v in CHEAT if v in s]))})
    for v in CHEAT:
        if v in s:
            r[v] = s[v]["detected"]
            r[f"{v}_delay"] = s[v]["delay_median_s"]
            r[f"{v}_switch_err"] = s[v]["switch_err_median_s"]
    r["h"] = "/".join(f"{x:g}" for x in recs[0]["h"].values()) if recs else ""
    return r


# ------------------------------------------------------------- factories (picklable by name)

def make(spec: dict):
    kind = spec["kind"]
    if kind == "thesis":
        return thesis_detector(spec.get("features"), spec.get("identity_w", 30), spec.get("process_w", 30),
                               spec.get("prior_n", 0.0), spec.get("comments", "separate"), k=spec.get("k"),
                               pairs=spec.get("pairs"))
    if kind == "channels":
        return ChannelMethod(spec.get("name", "custom"), {ch: ChannelSpec(*c) for ch, c in spec["channels"].items()},
                             spec.get("comments", "separate"), spec.get("prior_n", 0.0))
    if kind == "sm":
        return ScaledManhattan(spec.get("window_s", 30), spec.get("k", 1.0))
    if kind == "typenet":
        return TypeNetStyle(spec.get("window_s", 30), spec.get("k", 1.0), steps=spec.get("steps", 1500),
                            seed=spec.get("seed", 0))
    if kind == "nosi":
        return nosi_style(spec.get("window_s", 150), spec.get("k", 0.5))
    raise ValueError(kind)


def _cv_job(job):
    label, spec, dev, n_base, source, target, k, rule = job
    runs = cv_runs(lambda: make(spec), _CORPUS, dev, n_base=n_base, self_cal=source != "holdout")
    recs = outcomes(runs, _CORPUS, source, target, k, rule)
    return row(recs, runs, {"config": label})


def parallel(jobs, workers):
    if workers <= 1 or len(jobs) == 1:
        return [_cv_job(j) for j in jobs]
    with mp.get_context("fork").Pool(workers) as p:
        return p.map(_cv_job, jobs, chunksize=1)


# ------------------------------------------------------------- dev

def calibration_experiment(runs, corpus, target, reps=20, seed=0) -> list[dict]:
    from .alarms import combine
    rows = []
    n_dev = len({s.student for r in runs for s in r.eval_sessions})
    n_train = n_dev - n_dev // len(runs)
    sizes = [n for n in (5, 10, 20, 40) if n < n_train] + ["all"]
    for source in ("holdout", "self", "pooled"):
        for n in sizes:
            fa = []
            rng = np.random.default_rng(seed)
            for rep in range(reps if n != "all" else 1):
                alarms = hours = 0.0
                for run in runs:
                    k = run.method.k()
                    idx = run.h_index(k, "cusum", source, target, None if n == "all" else n, rng)
                    ev, _, _ = run.grids(k, "cusum")
                    for s in run.eval_sessions:
                        if s.condition == "honest":
                            alarms += combine(ev[s.id], idx).alarms
                            hours += s.duration_s / 3600
                fa.append(alarms / hours)
            rows.append({"source": source, "n_cal": n if n != "all" else n_train, "label": str(n) if n != "all" else f"all ({n_train})", "fa_mean": float(np.mean(fa)),
                         "fa_p10": float(np.percentile(fa, 10)), "fa_p90": float(np.percentile(fa, 90)), "target": target})
            log(f"    calibration {source:<8} n={n!s:<4} achieved {np.mean(fa):.3f}/h")
    return rows


def dev(a):
    global _CORPUS
    corpus = _CORPUS = load(a)
    dev_s, test_s = split(corpus.students, a.test_frac)
    log(f"corpus {corpus.source}: {len(dev_s)} dev students, {len(test_s)} test students (test not touched)")
    out, th = a.out, a.thesis
    meta = f"{corpus.source}, dev split, {len(dev_s)} students, 5-fold"
    T = a.target
    t0 = time.time()

    # 1. calibration source, on the phase-2 detector as it stands
    log("1. calibration ...")
    base_runs = cv_runs(lambda: make({"kind": "thesis"}), corpus, dev_s, log=log)
    cal_rows = calibration_experiment(base_runs, corpus, T)
    # how far achieved is from target, |log(achieved / target)|, averaged over four
    # targets with every calibration student and over the calibration sizes at the
    # main target: the study will have fewer staged honest sessions than here
    def gap(fa, t):
        return abs(math.log(max(fa, 1e-3) / t))
    err = {src: float(np.mean([gap(summarise(outcomes(base_runs, corpus, src, t))["honest"]["fa_per_h"], t)
                               for t in (0.1, 0.2, 0.5, 1.0)] +
                              [gap(r["fa_mean"], T) for r in cal_rows if r["source"] == src])) for src in CALIB_SOURCES}
    source = min(err, key=err.get)
    log(f"   mean |log(achieved/target)|: {err} -> {source}")

    # 2. thesis detector open choices + baseline hyperparameters
    log("2. tuning ...")
    thesis_cands = [{"kind": "thesis", "process_w": w, "prior_n": p} for w in (30, 60, 90) for p in (0.0, 2.0)]
    jobs = [(json.dumps(sp), sp, dev_s, 4, source, T, None, "cusum") for sp in thesis_cands]
    trows = parallel(jobs, a.workers)
    def pick(cands, rows):
        return max(zip(cands, rows), key=lambda z: (z[1]["mean_detected"] - (1 if z[1]["fa_per_h"] > 2 * T else 0)))[0]
    best_t = pick(thesis_cands, trows)
    tuning = [{"method": f"thesis detector (process $W$, prior {sp['prior_n']:g})", "rule": "cusum", "k": 1.0,
               "window_s": sp["process_w"], "prior": sp["prior_n"], **r} for sp, r in zip(thesis_cands, trows)]
    # 2b. per-key-pair timing on top of the chosen settings: none, inside the
    # identity channel (pairs weighted `block` x the other identity features),
    # or a key-pair channel of its own (CUSUM k, vocabulary size n)
    pair_cands = [None] + [{"channel": "identity", "block": b, "n": 40} for b in (0.5, 1.0, 2.0)] + \
                 [{"channel": "pairs", "k": k, "n": n} for k in (0.25, 0.5, 1.0) for n in (20, 40, 80)]
    pair_specs = [best_t if pc is None else {**best_t, "pairs": {"normalise": True, "min_count": 1, **pc}} for pc in pair_cands]
    prows = parallel([(json.dumps(sp), sp, dev_s, 4, source, T, None, "cusum") for sp in pair_specs[1:]], a.workers)
    prows = [next(r for sp, r in zip(thesis_cands, trows) if sp == best_t)] + prows
    best_p = pick(pair_specs, prows)
    for sp, r in zip(pair_specs, prows):
        pc = sp.get("pairs")
        lab = ("no key pairs" if pc is None else f"key pairs in identity, weight {pc['block']:g}" if pc["channel"] == "identity"
               else f"key-pair channel, {pc['n']} pairs")
        tuning.append({"method": f"thesis detector ({lab})", "rule": "cusum",
                       "k": pc["k"] if pc and pc["channel"] == "pairs" else 1.0, "window_s": best_t["process_w"],
                       "prior": best_t["prior_n"], **r, "chosen": sp == best_p, "pairs": json.dumps(pc)})
    for t in tuning[:len(thesis_cands)]:
        t["chosen"] = False
    best_t = best_p
    log(f"   -> thesis detector: {best_t}")
    chosen = {"thesis": best_t}
    baselines = {"sm": [{"kind": "sm", "window_s": 30}], "typenet": [{"kind": "typenet", "window_s": 30, "steps": a.typenet_steps}],
                 "nosi": [{"kind": "nosi", "window_s": 30}, {"kind": "nosi", "window_s": 150}]}
    names = {"sm": "scaled Manhattan", "typenet": "TypeNet-style LSTM", "nosi": "Nosi-style L-scale"}
    for key, specs in baselines.items():
        best = None
        for sp in specs:
            log(f"   {names[key]} W={sp['window_s']} ...")
            runs = cv_runs(lambda: make(sp), corpus, dev_s, self_cal=source != "holdout")
            for rule in ("cusum", "window"):
                for k in ((0.25, 0.5, 1.0, 2.0) if rule == "cusum" else (0.0,)):
                    ch = next(iter(make(sp).channels))
                    r = row(outcomes(runs, corpus, source, T, {ch: k}, rule), runs)
                    rec = {"method": names[key], "rule": rule, "k": k, "window_s": sp["window_s"], **r}
                    tuning.append(rec)
                    score = r["mean_detected"] - (1 if r["fa_per_h"] > 2 * T else 0)
                    if best is None or score > best[0]:
                        best = (score, {**sp, "k": k, "rule": rule}, rec)
        best[2]["chosen"] = True
        chosen[key] = best[1]
        log(f"   -> {names[key]}: {best[1]}")

    # 3. ablations of the thesis detector (chosen configuration as reference)
    log("3. ablations ...")
    ref = dict(best_t)
    feats = list(FEATURES)
    ab = [("Chosen configuration", ref)]
    for g in GROUPS:
        ab.append((f"\\quad without {g.replace('_', ' ')}", {**ref, "features": [f for f in feats if FEATURES[f] != g]}))
    if "pairs" in ref:
        rp = ref["pairs"]
        nop = {k: v for k, v in ref.items() if k != "pairs"}
        ab += [("\\quad without key pairs", nop),
               ("\\quad key pairs not speed-normalised", {**ref, "pairs": {**rp, "normalise": False}}),
               ("\\quad key pairs need 2 typings per window", {**ref, "pairs": {**rp, "min_count": 2}})]
        if rp["channel"] == "pairs":
            ab += [("\\quad key pairs inside the identity channel", {**ref, "pairs": {**rp, "channel": "identity", "block": 1.0}}),
                   ("\\quad key-pair channel replaces identity channel",
                    {**ref, "features": [f for f in feats if FEATURES[f] not in ("rhythm", "digraph")]})]
    idf = [f for f in feats if FEATURES[f] in ("rhythm", "digraph")]
    prf = [f for f in feats if FEATURES[f] not in ("rhythm", "digraph")]
    pw = ref["process_w"]
    ab += [
        ("Identity channel only", {"kind": "channels", "channels": {"identity": (idf, "icc", 1.0, 30)}}),
        ("Process channel only", {"kind": "channels", "channels": {"process": (prf, "equal", 0.5, pw)}}),
        ("Old build order (edit position, caret jumps)",
         {"kind": "channels", "channels": {"identity": (idf, "icc", 1.0, 30),
                                           "process": ([f for f in prf if FEATURES[f] != "build_order"] + list(LEGACY_FEATURES), "equal", 0.5, pw)}}),
        ("Identity channel with $k=0.5$", {**ref, "k": {"identity": 0.5, "process": 0.5}}),
        ("Process channel with $k=1$", {**ref, "k": {"identity": 1.0, "process": 1.0}}),
        ("One channel, all features, equal weights", {"kind": "channels", "channels": {"all": (feats, "equal", 0.5, 30)}}),
        ("One channel, all features, ICC weights", {"kind": "channels", "channels": {"all": (feats, "icc", 0.5, 30)}}),
        ("Comments mixed into code", {**ref, "comments": "mixed"}),
    ]
    jobs = [(lab, sp, dev_s, 4, source, T, None, "cusum") for lab, sp in ab]
    jobs.append(("Per-window threshold instead of CUSUM", ref, dev_s, 4, source, T,
                 {ch: 0 for ch in make(ref).channels}, "window"))
    arows = parallel(jobs, a.workers)
    wl = [(f"{W:g}", {"kind": "thesis", "identity_w": W, "process_w": W}) for W in (10, 20, 30, 60, 90, 150)]
    wrows = parallel([(lab, sp, dev_s, 4, source, T, None, "cusum") for lab, sp in wl], a.workers)
    for r, (lab, _) in zip(wrows, wl):
        r["window_s"] = float(lab)

    # 4. short baselines (holdout calibration: self needs >= 2 sessions)
    log("4. short baselines ...")
    bl = [(n, p) for n in (1, 2, 3, 4, 6, 8) for p in (0.0, 2.0)]
    brows = parallel([(f"{n}/{p}", {**ref, "prior_n": p}, dev_s, n, "holdout", T, None, "cusum") for n, p in bl], a.workers)
    for r, (n, p) in zip(brows, bl):
        r.update({"n_base": n, "prior": "none" if p == 0 else f"{p:g} sessions",
                  "takeover": r["takeover"], "copying": r["copying"], "paste": r["paste"]})

    # operating point for the review timeline: the chosen detector fitted on
    # every dev student, h calibrated on them as `test` does
    log("5. operating point ...")
    op_run = score_run(make(best_t), corpus, dev_s, [], 4, calib_students=dev_s, self_cal=source != "holdout")
    op_k = op_run.method.k()
    from .alarms import H_GRID
    op = {"h": {ch: float(H_GRID[i]) for ch, i in op_run.h_index(op_k, "cusum", source, T).items()}, "k": op_k,
          "window_s": {ch: c.window_s for ch, c in op_run.method.channels.items()},
          "pair_vocab": op_run.method.vocab}
    log(f"   h {op['h']}")

    desc = describe(corpus)
    desc.pop("sessions")
    frozen = {"created": time.strftime("%Y-%m-%d"), "corpus": desc,
              "split": {"test_frac": a.test_frac, "dev": len(dev_s), "test": len(test_s)},
              "target_fa_per_h": T, "calibration_source": source, "n_base": 4, "methods": chosen,
              "calibration_error": err, "operating_point": op}
    out.mkdir(parents=True, exist_ok=True)
    (out / "frozen-config.json").write_text(json.dumps(frozen, indent=1, default=float) + "\n")
    (out / "dev-summary.json").write_text(json.dumps({"calibration": cal_rows, "tuning": tuning, "ablations": arows,
                                                       "window_length": wrows, "baseline_length": brows,
                                                       "minutes": (time.time() - t0) / 60}, indent=1, default=float) + "\n")
    if th:
        abl = th / "ablations"
        write_csv(abl / "harness-calibration/results.csv", cal_rows)
        report.write(abl / "harness-calibration/table.tex", report.table_calibration(cal_rows, meta, T))
        write_csv(abl / "harness-tuning/results.csv", tuning)
        report.write(abl / "harness-tuning/table.tex", report.table_tuning(tuning, meta))
        write_csv(abl / "harness-detector/results.csv", arows)
        report.write(abl / "harness-detector/table.tex", report.table_ablation(
            arows, meta, "Thesis-detector ablations on the dev students (5-fold cross-fitting, $h$ recalibrated per row"
            f" for $\\le {T:g}$ false alarms per hour, {source} calibration). Delay: median, matched takeovers.",
            "tab:harness-ablation-detector"))
        for r in wrows:
            r["config"] = f"{r['window_s']:g}\\,s"
        write_csv(abl / "harness-window-length/results.csv", wrows)
        report.write(abl / "harness-window-length/table.tex", report.table_ablation(
            wrows, meta, "Window length $W$ for both channels, no population prior (dev students, cross-fitted, $h$ recalibrated per row).",
            "tab:harness-window-length"))
        write_csv(abl / "harness-baseline-length/results.csv", brows)
        report.write(abl / "harness-baseline-length/table.tex", report.table_baseline_length(brows, meta))
        (th / "graphs").mkdir(exist_ok=True)
        report.plot_calibration(th / "graphs/harness-calibration.pdf", cal_rows, T)
        report.plot_baseline_length(th / "graphs/harness-baseline-length.pdf", brows)
    log(f"dev done in {(time.time() - t0) / 60:.1f} min; frozen config -> {out / 'frozen-config.json'}")


# ------------------------------------------------------------- test

def test(a):
    out, th = a.out, a.thesis
    fz_path = out / "frozen-config.json"
    if not fz_path.exists():
        sys.exit("no frozen configuration: run `dev` first (the test split is only scored with a frozen config)")
    fz = json.loads(fz_path.read_text())
    corpus = load(a)
    dev_s, test_s = split(corpus.students, fz["split"]["test_frac"])
    fp, ch = corpus.fingerprint(), config_hash({k: v for k, v in fz.items() if k != "created"})
    ledger = Ledger(out / "test-ledger.jsonl")
    prev = ledger.previous(fp, ch)
    if prev and not a.reason:
        sys.exit(f"the test split was already scored {len(prev)}x with this corpus and frozen config "
                 f"(last {prev[-1]['time']}); pass --reason '...' to score it again (it is logged)")
    T, source, nb = fz["target_fa_per_h"], fz["calibration_source"], fz["n_base"]
    meta = f"{corpus.source}, test split, {len(test_s)} students"
    log(f"test: {len(test_s)} students, calibration on {len(dev_s)} dev students ({source}), target {T}/h")
    t0 = time.time()
    m = fz["methods"]
    plan = [("Thesis detector", m["thesis"], None, "cusum")]
    for key, label in (("sm", "Scaled Manhattan"), ("typenet", "TypeNet-style LSTM"), ("nosi", "Nosi-style L-scale")):
        sp = m[key]
        method = make(sp)
        plan.append((label, sp, {next(iter(method.channels)): sp["k"]}, sp["rule"]))  # settings: tab:harness-tuning
    mrows, curves, results = [], {}, {}
    for label, sp, k, rule in plan:
        log(f"  {label} ...")
        run = score_run(make(sp), corpus, dev_s, test_s, nb, calib_students=dev_s, self_cal=source != "holdout")
        recs = outcomes([run], corpus, source, T, k, rule)
        r = row(recs, [run], {"method": label})
        mrows.append(r)
        results[label] = (run, recs, k, rule)
        curves[label] = curve([run], corpus, TARGETS, source, k, rule)
        log(f"    FA/h {r['fa_per_h']:.2f}  takeover {r['takeover']:.2f}  copying {r['copying']:.2f}  AUC {r['window_auc']:.3f}")

    main_label = plan[0][0]
    run, recs, _, _ = results[main_label]
    summ = summarise(recs)
    cis = {"fa": bootstrap(recs, stat_fa), "flagged": bootstrap(recs, stat_flagged)}
    for v in CHEAT:
        cis[v] = bootstrap(recs, stat_detected(v))
        cis[v + "_delay"] = bootstrap(recs, stat_delay(v))
    calib_check = []
    for src in CALIB_SOURCES:
        for t in (0.1, 0.2, 0.5, 1.0):
            s = summarise(outcomes([run], corpus, src, t))
            calib_check.append({"source": src, "target": t, "achieved": s["honest"]["fa_per_h"]})

    # RQ4: precision and fairness
    prec = []
    for label, (rn, rc, k, rule) in results.items():
        s = summarise(rc)
        p = {"method": label, "tpr": s["tpr"], "fpr": s["fpr"],
             "p100": precision(s["tpr"], s["fpr"], 1 / 100), "p500": precision(s["tpr"], s["fpr"], 1 / 500)}
        p["ratio100"] = s["fpr"] * 99 / s["tpr"] if s["tpr"] else math.nan
        p["ratio500"] = s["fpr"] * 499 / s["tpr"] if s["tpr"] else math.nan
        if label == main_label:
            p["fpr_ci"] = bootstrap(rc, stat_flagged)
            p["p100_ci"] = bootstrap(rc, stat_precision(1 / 100))
            p["p500_ci"] = bootstrap(rc, stat_precision(1 / 500))
        prec.append(p)
    fair = []
    attrs = sorted({k for at in corpus.students.values() for k in at})
    for at in attrs:
        for g in sorted({corpus.students[s].get(at) for s in test_s if corpus.students[s].get(at) is not None}):
            rs = [r for r in recs if r["attrs"].get(at) == g]
            fair.append({"attribute": at, "group": g, "students": len({r["student"] for r in rs}),
                         "flagged": stat_flagged(rs), "flagged_ci": bootstrap(rs, stat_flagged),
                         "fa_per_h": stat_fa(rs), "fa_ci": bootstrap(rs, stat_fa),
                         "takeover": stat_detected("takeover")(rs), "takeover_ci": bootstrap(rs, stat_detected("takeover"))})

    log("  RQ2 ...")
    r2 = rq2.run(corpus, test_s, log=log)

    git = git_state(REPO)
    summary = {"meta": meta, "frozen": fz, "methods": mrows, "conditions": summ, "cis": cis, "curves": curves,
               "calibration_check": calib_check, "precision": prec, "fairness": fair, "rq2": r2,
               "h": recs[0]["h"], "git": git, "minutes": (time.time() - t0) / 60}
    (out / "test-summary.json").write_text(json.dumps(summary, indent=1, default=float) + "\n")
    ledger.record({"corpus": fp, "config": ch, "students": len(test_s), "git": git["commit"], "dirty": git["dirty"],
                   "reason": a.reason or "first test run for this config"})
    if th:
        write_csv(th / "tables/harness-methods.csv", mrows)
        report.write(th / "tables/harness-methods.tex", report.table_methods(mrows, meta, T))
        report.write(th / "tables/harness-conditions.tex", report.table_conditions(summ, cis, meta, recs[0]["h"], run.method.k()))
        write_csv(th / "tables/harness-precision.csv", prec)
        report.write(th / "tables/harness-precision.tex", report.table_precision(prec, meta))
        write_csv(th / "tables/harness-fairness.csv", fair)
        report.write(th / "tables/harness-fairness.tex", report.table_fairness(fair, meta))
        write_csv(th / "tables/harness-rq2.csv", r2["windows"])
        report.write(th / "tables/harness-rq2.tex", report.table_rq2(r2, meta))
        g = th / "graphs"
        g.mkdir(exist_ok=True)
        report.plot_curves(g / "harness-detection-vs-false-alarms.pdf", curves)
        report.plot_precision(g / "harness-precision.pdf", curves[main_label])
        report.plot_fairness(g / "harness-fairness.pdf", fair)
        report.plot_rq2(g / "harness-rq2.pdf", r2)
    log(f"test done in {(time.time() - t0) / 60:.1f} min; ledger -> {ledger.path}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m studentide.harness", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["dev", "test"])
    p.add_argument("--typists", type=int, default=120)
    p.add_argument("--seed", type=int, default=2026, help="fresh population, never used in phase 2")
    p.add_argument("--minutes", type=float, default=30)
    p.add_argument("--db", type=Path, help="recorded study database (instead of synthetic)")
    p.add_argument("--labels", type=Path, help="folder with sessions.csv / students.csv")
    p.add_argument("--test-frac", type=float, default=0.3)
    p.add_argument("--target", type=float, default=0.2, help="false alarms per honest hour")
    p.add_argument("--typenet-steps", type=int, default=1500)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--cache", type=Path, default=Path(".cache/harness"))
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="frozen config, summaries, test ledger")
    p.add_argument("--thesis", type=Path, help="thesis/latex folder for tables and graphs")
    p.add_argument("--reason", help="test only: why the test split is being scored again")
    a = p.parse_args(argv)
    if a.db and not a.labels:
        p.error("--db needs --labels")
    (dev if a.mode == "dev" else test)(a)


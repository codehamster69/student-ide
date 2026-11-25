"""Classroom (pilot) evaluation: thresholds frozen on dev, the held-out split scored once, RQ2-RQ4.

    python -m studentide.harness freeze --db COPY.sqlite3 --classroom      # dev only, as often as needed
    python -m studentide.harness test   --db COPY.sqlite3 --classroom      # once; logged in the ledger
    python -m studentide.harness rq     --db COPY.sqlite3 --classroom      # RQ2 + RQ3, descriptive

`freeze` keeps the detector settings that are live (`--base-config`, by default the
frozen-config.json chosen on simulated typists; Rohan kept them, 2026-11-25) and sets
only what has to come from real data: the calibration source (holdout = dev students'
real sessions, self = their own baseline minutes scored leave-one-out, or both) and every
method's thresholds h for `--target` false alarms per active hour, on dev students only.
It writes classroom-frozen-config.json and classroom-dev-summary.json.

`test` loads the corpus with the held-out sessions (test-hash students, plus every
student's sessions from PILOT_TEST_FROM on, scored against the baseline from their
earlier weeks), splices takeovers among them, and scores them once at the frozen
thresholds: detection, delay, false alarms, the identity and process channels alone,
the operating point that is deployed, every keystroke baseline, precision at 1/100 and
1/500 and subgroup rates (device class, OS, language, lab vs competition, typing speed),
all with 95% intervals from resampling students. A second run on the same corpus and
config needs --reason and is logged.

`rq` scores every honest scored session (dev and held-out, reported apart) with the
frozen detector and relates it to weak copying signs (RQ2: outside pastes, pastes soon
after coming back to the window, blocked outside pastes, text typed with no key press;
association only, these are not labels), to time since the baseline (RQ3 drift) and to
the device class (RQ3 transfer: lab PC vs own laptop, also against a baseline of the
same device class). It also counts teachers' conversation outcomes (dev split).

Everything written is aggregates: no session or student ids, no code, no text.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from .alarms import H_GRID, grid
from .corpus import Corpus, classroom_corpus, describe
from .engine import (CALIB_SOURCES, bootstrap, curve, cv_runs, fixed_outcomes, outcomes, precision, score_run,
                     stat_delay, stat_detected, stat_fa, stat_flagged, summarise)
from .split import Ledger, config_hash, git_state

FROZEN = "classroom-frozen-config.json"
DEV_SUMMARY = "classroom-dev-summary.json"
TEST_SUMMARY = "classroom-test-summary.json"
RQ_SUMMARY = "classroom-rq.json"
CAL_TARGETS = (0.1, 0.2, 0.5, 1.0, 2.0)
TARGETS = [0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
VARIANTS = ("takeover", "takeover_random")
IDENTITY = ["identity", "pairs"]
SUBGROUPS = ("device", "os", "lang", "ctx", "speed")
MIN_GROUP_STUDENTS = 5


def log(*a):
    print(*a, flush=True)


def _k(key: str, sp: dict, method) -> dict[str, float]:
    return method.k() if key == "thesis" else {next(iter(method.channels)): sp["k"]}


def _restrict(run, evaluate_ok, calib: set[str]) -> None:
    """Keep only held-out sessions for evaluation and only dev students' (never held-out)
    sessions for calibration."""
    run.eval_sessions = [s for s in run.eval_sessions if evaluate_ok(s)]
    run.holdout = [(s, x) for s, x in run.holdout if s.student in calib and not s.meta.get("held_out")]
    keep = [i for i, st in enumerate(run._self_owner) if st in calib]
    run.self_cal = [run.self_cal[i] for i in keep]
    run._self_owner = [run._self_owner[i] for i in keep]
    run._self_students = sorted(set(run._self_owner))
    run._g.clear()


def _stat_precision(prev: float, variant: str = "takeover"):
    def f(rs):
        return precision(stat_detected(variant)(rs), stat_flagged(rs), prev)
    return f


def _ci(recs, stat, B=1000):
    return list(bootstrap(recs, stat, B))


def metrics(recs: list[dict], B: int = 1000) -> dict:
    """Headline numbers of one set of outcome records, with student-resampled 95% intervals."""
    s = summarise(recs)
    h = [r for r in recs if r["condition"] == "honest"]
    out = {"students": len({r["student"] for r in recs}),
           "honest": {"n": s["honest"]["n"], "hours": s["honest"]["hours"], "students": len({r["student"] for r in h}),
                      "fa_per_h": s["honest"]["fa_per_h"], "fa_per_h_ci": _ci(recs, stat_fa, B),
                      "flagged": s["honest"]["flagged"], "flagged_ci": _ci(recs, stat_flagged, B)}}
    for v in VARIANTS:
        if v in s:
            m = s[v]
            out[v] = {**{x: m[x] for x in ("n", "detected", "delay_median_s", "delay_p90_s", "switch_err_median_s",
                                           "early_alarms", "first_channel")},
                      "students": len({r["student"] for r in recs if r["variant"] == v}),
                      "detected_ci": _ci(recs, stat_detected(v), B), "delay_ci": _ci(recs, stat_delay(v), B)}
    if "takeover" in s:
        for p in (100, 500):
            out[f"precision_{p}"] = precision(s["takeover"]["detected"], s["honest"]["flagged"], 1 / p)
            out[f"precision_{p}_ci"] = _ci(recs, _stat_precision(1 / p), B)
    return out


def _speed_group(kpm, cuts) -> str | None:
    if kpm is None or not cuts:
        return None
    return "slow" if kpm < cuts[0] else "medium" if kpm < cuts[1] else "fast"


def subgroups(recs: list[dict], speed_cuts) -> list[dict]:
    """RQ4: rates by session attribute (a splice counts under its first student's session)."""
    rows = []
    for at in SUBGROUPS:
        def val(r):
            return _speed_group(r["attrs"].get("speed_kpm"), speed_cuts) if at == "speed" else r["smeta"].get(at)
        for g in sorted({val(r) for r in recs if val(r) is not None}, key=str):
            rs = [r for r in recs if val(r) == g]
            m = metrics(rs, B=500)
            rows.append({"attribute": at, "group": str(g), "students": m["students"], "honest": m["honest"],
                         "takeover": m.get("takeover"), "small": m["students"] < MIN_GROUP_STUDENTS})
    return rows


# ------------------------------------------------------------------ freeze (dev only)

def freeze(a):
    from . import run as R
    t0 = time.time()
    base_path = a.base_config or R.DEFAULT_OUT / "frozen-config.json"
    base = json.loads(Path(base_path).read_text())
    corpus = R._CORPUS = R.load(a)
    dev_s, test_s = corpus.split_students(a.test_frac)
    dset = set(dev_s)
    T = a.target
    dep = {"k": base["operating_point"]["k"], "h": base["operating_point"]["h"]}
    log(f"freeze: {len(dev_s)} dev students ({len(test_s)} test students not touched), target {T}/h")
    spec = base["methods"]["thesis"]
    runs = cv_runs(lambda: R.make(spec), corpus, dev_s, log=log)

    def gap(fa, t):
        return abs(math.log(max(fa, 1e-3) / t))
    err = {src: float(np.mean([gap(summarise(outcomes(runs, corpus, src, t))["honest"]["fa_per_h"], t) for t in CAL_TARGETS]))
           for src in CALIB_SOURCES}
    source = min(err, key=err.get)
    log(f"  calibration error {err} -> {source}")
    dev = {"calibration_error": err, "calibration_source": source, "target": T,
           "calibration_check": [{"source": src, "target": t,
                                  "achieved": summarise(outcomes(runs, corpus, src, t))["honest"]["fa_per_h"]}
                                 for src in CALIB_SOURCES for t in CAL_TARGETS],
           "curve": curve(runs, corpus, TARGETS, source),
           "curve_identity": [{"target": t, **{v: summarise(outcomes(runs, corpus, source, t, channels=IDENTITY)).get(v, {}).get("detected")
                                               for v in VARIANTS},
                               "fa_per_h": summarise(outcomes(runs, corpus, source, t, channels=IDENTITY))["honest"]["fa_per_h"]}
                              for t in TARGETS],
           "at_target": metrics(outcomes(runs, corpus, source, T)),
           "identity_at_target": metrics(outcomes(runs, corpus, source, T, channels=IDENTITY)),
           "deployed": metrics(fixed_outcomes(runs, corpus, dep["k"], dep["h"]))}
    log(f"  dev at target: {json.dumps(dev['at_target'], default=float)[:400]}")

    speeds = [corpus.students[s].get("speed_kpm") for s in dev_s if corpus.students[s].get("speed_kpm")]
    cuts = [float(x) for x in np.percentile(speeds, [100 / 3, 200 / 3])] if len(speeds) >= 6 else []
    # the larger, cross-fitted dev sample for RQ4 subgroups and the baseline comparison
    # (each fold's h from the other folds' students; the test split stays untouched)
    dev["subgroups"] = subgroups(outcomes(runs, corpus, source, T), cuts)
    dev["subgroups_deployed"] = subgroups(fixed_outcomes(runs, corpus, dep["k"], dep["h"]), cuts)
    dev["methods"] = {}
    for key, sp in base["methods"].items():
        if key == "thesis":
            continue
        log(f"  dev cross-fit {key} ...")
        rm = cv_runs(lambda sp=sp: R.make(sp), corpus, dev_s)
        kk = _k(key, sp, rm[0].method)
        dev["methods"][key] = {"metrics": metrics(outcomes(rm, corpus, source, T, kk, sp["rule"])),
                               "curve": curve(rm, corpus, TARGETS, source, kk, sp["rule"])}
    ops = {}
    for key, sp in base["methods"].items():
        m = R.make(sp)
        run = score_run(m, corpus, dev_s, [], base.get("n_base", 4), calib_students=dev_s, self_cal=True)
        _restrict(run, lambda s: False, dset)
        kk, rule = _k(key, sp, m), "cusum" if key == "thesis" else sp["rule"]
        idx = run.h_index(kk, rule, source, T)
        ops[key] = {"k": kk, "h": {ch: float(H_GRID[i]) for ch, i in idx.items()}, "rule": rule,
                    "window_s": {ch: c.window_s for ch, c in m.channels.items()}}
        if key == "thesis":
            ops[key]["pair_vocab"] = m.vocab
        log(f"  {key}: h {ops[key]['h']}")
    desc = describe(corpus)
    fz = {"created": time.strftime("%Y-%m-%d"), "kind": "classroom", "corpus": desc,
          "base_config": {"file": Path(base_path).name, "hash": config_hash({k: v for k, v in base.items() if k != "created"})},
          "split": {"test_frac": a.test_frac, "dev": len(dev_s), "test": len(test_s), "test_from": corpus.meta["test_from"]},
          "baseline_min": a.baseline_min, "target_fa_per_h": T, "calibration_source": source, "calibration_error": err,
          "n_base": base.get("n_base", 4), "methods": base["methods"], "operating_points": ops,
          "deployed_point": dep, "speed_cuts_kpm": cuts, "splice_seed": a.seed}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / FROZEN).write_text(json.dumps(fz, indent=1, default=float) + "\n")
    dev["minutes"] = (time.time() - t0) / 60
    (a.out / DEV_SUMMARY).write_text(json.dumps(dev, indent=1, default=float) + "\n")
    log(f"freeze done in {dev['minutes']:.1f} min -> {a.out / FROZEN}")


# ------------------------------------------------------------------ test (once)

def test(a):
    from . import run as R
    t0 = time.time()
    fz_path = a.out / FROZEN
    if not fz_path.exists():
        sys.exit(f"no {FROZEN}: run `freeze --classroom` on dev first")
    fz = json.loads(fz_path.read_text())
    a.held_out, a.baseline_min, a.test_frac, a.seed = True, fz["baseline_min"], fz["split"]["test_frac"], fz["splice_seed"]
    corpus = R.load(a)
    dev_s, test_s = corpus.split_students(a.test_frac)
    tset, dset = set(test_s), set(dev_s)
    later = sorted({s.student for s in corpus.sessions if s.meta.get("held_out")})
    evaluate = sorted(tset | set(later))
    fp, ch = corpus.fingerprint(), config_hash({k: v for k, v in fz.items() if k != "created"})
    ledger = Ledger(a.out / "test-ledger.jsonl")
    prev = ledger.previous(fp, ch)
    if prev and not a.reason:
        sys.exit(f"the classroom test split was already scored {len(prev)}x with this corpus and config "
                 f"(last {prev[-1]['time']}); pass --reason '...' to score it again (it is logged)")

    def held(s):
        return s.student in tset or bool(s.meta.get("held_out"))
    res, dep = {}, fz["deployed_point"]
    for key, sp in fz["methods"].items():
        log(f"  {key} ...")
        m = R.make(sp)
        run = score_run(m, corpus, dev_s, evaluate, fz["n_base"], calib_students=dev_s, self_cal=True)
        _restrict(run, held, dset)
        op = fz["operating_points"][key]
        if key == "thesis" and op.get("pair_vocab") and m.vocab != op["pair_vocab"]:
            log("  warning: key-pair vocabulary differs from the frozen one")
        recs = fixed_outcomes([run], corpus, op["k"], op["h"], op["rule"])
        res[key] = {"metrics": metrics(recs), "curve": curve([run], corpus, TARGETS, fz["calibration_source"], op["k"], op["rule"])}
        log(f"    {json.dumps(res[key]['metrics'], default=float)[:300]}")
        if key == "thesis":
            res["thesis_identity"] = {"metrics": metrics(fixed_outcomes([run], corpus, op["k"], op["h"], channels=IDENTITY))}
            res["thesis_process"] = {"metrics": metrics(fixed_outcomes([run], corpus, op["k"], op["h"], channels=["process"]))}
            res["deployed"] = {"metrics": metrics(fixed_outcomes([run], corpus, dep["k"], dep["h"]))}
            res["by_block"] = {"test students": metrics([r for r in recs if not r["smeta"].get("held_out")], B=500),
                               "later sessions of dev students": metrics([r for r in recs if r["smeta"].get("held_out")], B=500)}
            res["subgroups"] = subgroups(recs, fz["speed_cuts_kpm"])
            res["subgroups_deployed"] = subgroups(fixed_outcomes([run], corpus, dep["k"], dep["h"]), fz["speed_cuts_kpm"])
            res["purged_share"] = float(np.mean([bool(s.meta.get("purged") or s.meta.get("windows_only")) for s in run.eval_sessions])) if run.eval_sessions else math.nan
    git = git_state(R.REPO)
    desc = describe(corpus)
    summary = {"corpus": desc, "evaluate": {"test_students": len(test_s), "dev_students_with_later_sessions": len(later)},
               "frozen": {k: fz[k] for k in ("created", "target_fa_per_h", "calibration_source", "operating_points", "deployed_point")},
               "results": res, "git": git, "minutes": (time.time() - t0) / 60}
    (a.out / TEST_SUMMARY).write_text(json.dumps(summary, indent=1, default=float) + "\n")
    ledger.record({"corpus": fp, "config": ch, "students": len(evaluate), "git": git["commit"], "dirty": git["dirty"],
                   "kind": "classroom", "reason": a.reason or "first classroom test run: thresholds frozen on dev (classroom-frozen-config.json)"})
    log(f"test done in {summary['minutes']:.1f} min; ledger -> {ledger.path}")


# ------------------------------------------------------------------ RQ2 / RQ3 (descriptive)

BIG_PASTE = 80  # characters, as pilot.BIG_PASTE
AWAY_S = 60.0
NO_KEY_MS = 300.0
AFTER_SIGN_S = 180.0
SIGNS = ("outside paste", "big outside paste", "paste after look-away", "blocked outside paste", "keyless text")
DRIFT_BINS = [(0, 1, "same day"), (1, 7, "1-7 days"), (7, 14, "1-2 weeks"), (14, 21, "2-3 weeks"), (21, 1e9, "3+ weeks")]
CHANNELS = ("identity", "pairs", "process")


def sign_times(db, sid: str, st, purged: bool) -> dict[str, list[float]]:
    """Seconds from session start of each weak copying sign."""
    out = {k: [] for k in SIGNS}
    ins = np.asarray(st.e_inserted)
    for t, n, p in zip(st.e_t, ins, st.e_paste):
        if p:
            out["outside paste"].append(t / 1000)
            if n >= BIG_PASTE:
                out["big outside paste"].append(t / 1000)
    back, last_down, typed, nokey, nokey_chars = -1e12, -1e12, 0, [], 0
    for e in db.iter_events(sid, ("key", "edit", "clipboard", "focus")):
        t, d, typ = e["t"], e["data"], e["type"]
        if typ == "focus" and d.get("target") in ("window", "page") and d.get("state") == "in":
            back = t
        elif typ == "clipboard" and d.get("action") in ("paste", "drop") and d.get("blocked"):
            out["blocked outside paste"].append(t / 1000)
        elif typ == "key" and d.get("action") == "down" and not d.get("repeat") and d.get("surface", "editor") == "editor":
            last_down = t
        elif typ == "edit" and d.get("origin") in ("input.type", "input.type.compose") and not purged:
            typed += 1
            if t - last_down > NO_KEY_MS:
                nokey.append(t / 1000)
                nokey_chars += sum(len(c[2]) for c in d["changes"])
        elif typ == "edit" and str(d.get("origin", "")).startswith("input.paste") and t - back < AWAY_S * 1000:
            if any(abs(t / 1000 - x) < 1.0 for x in out["outside paste"]):
                out["paste after look-away"].append(t / 1000)
    if nokey_chars >= 200 and len(nokey) > 0.2 * max(1, typed):  # pilot.copying_signs rule
        out["keyless text"] = nokey
    return out


def _auc(pos, neg) -> float:
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    pos, neg = pos[np.isfinite(pos)], neg[np.isfinite(neg)]
    if not len(pos) or not len(neg):
        return math.nan
    r = np.argsort(np.argsort(np.r_[pos, neg])) + 1.0
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def _boot(rows, stat, B=1000, seed=0):
    by = {}
    for r in rows:
        by.setdefault(r["student"], []).append(r)
    ks = list(by)
    if len(ks) < 2:
        return [math.nan, math.nan]
    rng = np.random.default_rng(seed)
    v = []
    for _ in range(B):
        x = stat([r for i in rng.integers(0, len(ks), len(ks)) for r in by[ks[i]]])
        if x is not None and np.isfinite(x):
            v.append(x)
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else [math.nan, math.nan]


def _fa(rows, chans=CHANNELS):
    h = sum(r["hours"] for r in rows)
    return sum(r["alarms"][c] for r in rows for c in chans if c in r["alarms"]) / h if h else math.nan


def _score_sessions(a, corpus: Corpus, fz: dict, db, with_signs: bool = True) -> list[dict]:
    from . import run as R
    dev_s, _ = corpus.split_students(fz["split"]["test_frac"])
    sp, op = fz["methods"]["thesis"], fz["operating_points"]["thesis"]
    m = R.make(sp)
    m.fit_population(corpus, dev_s, fz["n_base"])
    dset = set(dev_s)
    base_end, base_dev = {}, {}
    for s in corpus.sessions:
        if s.role == "baseline":
            base_end[s.student] = max(base_end.get(s.student, 0), s.meta["started_at"] + s.duration_s)
            base_dev.setdefault(s.student, {}).setdefault(s.meta["device"], 0.0)
            base_dev[s.student][s.meta["device"]] += s.meta["active_min"]
    rows = []
    models = {}
    tests = [s for s in corpus.sessions if s.role == "test" and s.condition == "honest"]
    for i, s in enumerate(tests):
        if i % 100 == 0:
            log(f"    scoring {i}/{len(tests)}")
        if s.student not in models:
            models[s.student] = m.fit_student(corpus, s.student, corpus.baseline(s.student))
        ser = m.score(corpus, models[s.student], s)
        bd = base_dev.get(s.student, {})
        r = {"student": s.student, "person": s.meta["person"], "split": "dev" if s.student in dset and not s.meta.get("held_out") else "test",
             "device": s.meta["device"], "base_device": max(bd, key=bd.get) if bd else None, "ctx": s.meta["ctx"],
             "days": (s.meta["started_at"] - base_end.get(s.student, s.meta["started_at"])) / 86400,
             "hours": s.duration_s / 3600, "id": s.id, "mean": {}, "alarms": {}, "series": ser}
        for ch, x in ser.items():
            v = x.x[np.isfinite(x.x)]
            r["mean"][ch] = float(v.mean()) if len(v) else math.nan
            g = grid(x, op["k"][ch], None, "cusum", np.array([op["h"][ch]]))
            r["alarms"][ch] = int(g.n_alarms[0])
        w30 = [w for w in corpus.windows(s, 30.0) if w["active"]]
        for f in ("del_per_100", "pause_per_100"):
            v = [w[f] for w in w30 if np.isfinite(w.get(f, np.nan))]
            r[f] = float(np.median(v)) if v else math.nan
        if with_signs:
            r["signs"] = sign_times(db, s.id, s.st, bool(s.meta.get("purged")))
        rows.append(r)
    return rows


def rq2(rows: list[dict]) -> dict:
    out = {}
    for split in ("dev", "test", "all"):
        R = [r for r in rows if split == "all" or r["split"] == split]
        res = {"sessions": len(R), "students": len({r["student"] for r in R}), "signs": {}}
        for sg in SIGNS:
            pos = [r for r in R if r["signs"][sg]]
            neg = [r for r in R if not r["signs"][sg]]
            e = {"sessions": len(pos), "students": len({r["student"] for r in pos}), "events": sum(len(r["signs"][sg]) for r in pos)}
            if len(pos) >= 3 and len(neg) >= 3:
                for ch in CHANNELS:
                    pm = [r["mean"].get(ch, math.nan) for r in pos]
                    nm = [r["mean"].get(ch, math.nan) for r in neg]
                    e[ch] = {"median_with": float(np.nanmedian(pm)) if np.isfinite(pm).any() else math.nan,
                             "median_without": float(np.nanmedian(nm)) if np.isfinite(nm).any() else math.nan,
                             "auc": _auc(pm, nm),
                             "auc_ci": _boot(R, lambda rs, ch=ch, sg=sg: _auc([r["mean"].get(ch, math.nan) for r in rs if r["signs"][sg]],
                                                                               [r["mean"].get(ch, math.nan) for r in rs if not r["signs"][sg]]), 500),
                             "flagged_with": float(np.mean([r["alarms"].get(ch, 0) > 0 for r in pos])),
                             "flagged_without": float(np.mean([r["alarms"].get(ch, 0) > 0 for r in neg]))}
                for f in ("del_per_100", "pause_per_100"):
                    e[f] = {"median_with": float(np.nanmedian([r[f] for r in pos])), "median_without": float(np.nanmedian([r[f] for r in neg])),
                            "auc": _auc([r[f] for r in pos], [r[f] for r in neg])}
                # inside the session: windows starting within AFTER_SIGN_S after a sign vs the session's other windows
                for ch in CHANNELS:
                    diffs = []
                    for r in pos:
                        x = r["series"].get(ch)
                        if x is None:
                            continue
                        near = np.zeros(len(x.x), bool)
                        for t in r["signs"][sg]:
                            near |= (x.start >= t - 1e-6) & (x.start < t + AFTER_SIGN_S)
                        ok = np.isfinite(x.x)
                        if (near & ok).any() and (~near & ok).any():
                            diffs.append({"student": r["student"], "d": float(x.x[near & ok].mean() - x.x[~near & ok].mean())})
                    e[f"{ch}_within"] = {"sessions": len(diffs), "mean_diff": float(np.mean([d["d"] for d in diffs])) if diffs else math.nan,
                                         "ci": _boot(diffs, lambda ds: float(np.mean([d["d"] for d in ds])) if ds else math.nan, 500)}
            res["signs"][sg] = e
        anysign = [r for r in R if any(r["signs"][s] for s in SIGNS if s != "outside paste")]
        res["any_strong_sign_sessions"] = len(anysign)
        out[split] = res
    return out


def _spearman(x, y) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5:
        return math.nan
    rx, ry = np.argsort(np.argsort(x[ok])), np.argsort(np.argsort(y[ok]))
    return float(np.corrcoef(rx, ry)[0, 1])


def rq3_drift(rows: list[dict]) -> dict:
    bins = []
    for lo, hi, lab in DRIFT_BINS:
        R = [r for r in rows if lo <= r["days"] < hi]
        b = {"bin": lab, "sessions": len(R), "students": len({r["student"] for r in R}), "hours": sum(r["hours"] for r in R),
             "fa_per_h": _fa(R), "fa_ci": _boot(R, _fa, 500)}
        for ch in CHANNELS:
            v = [r["mean"].get(ch, math.nan) for r in R]
            b[ch] = float(np.nanmedian(v)) if np.isfinite(v).any() else math.nan
            b[f"{ch}_ci"] = _boot(R, lambda rs, ch=ch: float(np.nanmedian([r["mean"].get(ch, math.nan) for r in rs])) if rs else math.nan, 500)
        bins.append(b)
    rho = {ch: _spearman([r["days"] for r in rows], [r["mean"].get(ch, math.nan) for r in rows]) for ch in CHANNELS}
    rho_ci = {ch: _boot(rows, lambda rs, ch=ch: _spearman([r["days"] for r in rs], [r["mean"].get(ch, math.nan) for r in rs]), 500)
              for ch in CHANNELS}
    return {"bins": bins, "spearman": rho, "spearman_ci": rho_ci}


def rq3_devices(rows: list[dict], rows_dev: list[dict] | None) -> dict:
    """Students with scored sessions on both a lab-PC-like machine and a personal-like one."""
    pcs = ("lab-PC-like", "personal-like")
    persons = {}
    for r in rows:
        if r["device"] in pcs:
            persons.setdefault(r["person"], set()).add(r["device"])
    both = {p for p, d in persons.items() if len(d) == 2}
    R = [r for r in rows if r["person"] in both and r["device"] in pcs and r["base_device"] in pcs]
    same = [r for r in R if r["device"] == r["base_device"]]
    other = [r for r in R if r["device"] != r["base_device"]]

    def side(rs):
        d = {"sessions": len(rs), "students": len({r["student"] for r in rs}), "hours": sum(r["hours"] for r in rs),
             "fa_per_h": _fa(rs), "fa_ci": _boot(rs, _fa, 500),
             "flagged": float(np.mean([sum(r["alarms"].values()) > 0 for r in rs])) if rs else math.nan}
        for ch in CHANNELS:
            v = [r["mean"].get(ch, math.nan) for r in rs]
            d[ch] = float(np.nanmedian(v)) if np.isfinite(v).any() else math.nan
            d[f"{ch}_fa"] = _fa(rs, (ch,))
        return d
    out = {"students_both": len(both), "same_device": side(same), "other_device": side(other),
           "by_base_device": {bd: {"same": side([r for r in same if r["base_device"] == bd]),
                                   "other": side([r for r in other if r["base_device"] == bd])} for bd in pcs}}
    # paired within student: other-device minus same-device mean score
    pair = {}
    for ch in CHANNELS:
        ds = []
        for p in both:
            a_ = [r["mean"].get(ch, math.nan) for r in same if r["person"] == p]
            b_ = [r["mean"].get(ch, math.nan) for r in other if r["person"] == p]
            if np.isfinite(a_).any() and np.isfinite(b_).any():
                ds.append({"student": p, "d": float(np.nanmean(b_) - np.nanmean(a_))})
        pair[ch] = {"students": len(ds), "median_diff": float(np.median([d["d"] for d in ds])) if ds else math.nan,
                    "ci": _boot(ds, lambda x: float(np.median([d["d"] for d in x])) if x else math.nan, 500)}
    out["paired_score_shift"] = pair
    if rows_dev is not None:
        # the same other-device sessions, scored against a baseline from that device class
        by_id = {r["id"]: r for r in rows_dev}
        matched = [(r, by_id[r["id"]]) for r in other if r["id"] in by_id]
        out["other_device_matched"] = {"sessions": len(matched), "students": len({r["person"] for r, _ in matched}),
                                       "person_baseline": side([r for r, _ in matched]),
                                       "device_baseline": side([{**d, "student": r["student"]} for r, d in matched])}
    return out


# RQ3 on every recorded session, not only scored ones: most students have one scored
# session, so few have scored sessions on two device classes; session profiles (median of
# each feature over a session's active windows) can compare all their sessions instead.
PROFILE = {"rhythm": ["dg_median", "dg_lscale", "hold_median", "dg_alt_hand", "dg_same_hand", "dg_to_space", "dg_from_space",
                      "dg_shifted"],
           "process": ["pause_per_100", "pause_median", "del_per_100", "del_burst", "fill_in_frac", "run_rate", "focus_out_rate"]}
PCS = ("lab-PC-like", "personal-like")
MIN_PROFILE_W = 4  # active 30 s windows a session needs for a profile
MIN_FEATS = 3
GAP_BINS = [(0, 1, "same day"), (1, 7, "1-7 days"), (7, 14, "1-2 weeks"), (14, 1e9, "2+ weeks")]


def _profiles(corpus: Corpus) -> list[dict]:
    feats = [f for g in PROFILE.values() for f in g]
    out = []
    for s in corpus.sessions:
        if s.meta.get("device") not in PCS or s.role == "idle":
            continue
        w = [x for x in corpus.windows(s, 30.0) if x["active"]]
        if len(w) < MIN_PROFILE_W:
            continue
        p = {}
        for f in feats:
            v = [x[f] for x in w if f in x and x[f] is not None and np.isfinite(x[f])]
            p[f] = float(np.median(v)) if len(v) >= 2 else math.nan
        out.append({"person": s.meta["person"], "device": s.meta["device"], "q": s.meta.get("question"),
                    "t": s.meta["started_at"], "p": p})
    return out


def rq3_profiles(corpus: Corpus, max_between: int = 5, seed: int = 0) -> dict:
    P = _profiles(corpus)
    feats = [f for g in PROFILE.values() for f in g]
    scale = {}
    for f in feats:
        v = np.array([x["p"][f] for x in P if np.isfinite(x["p"][f])])
        scale[f] = max(1.4826 * float(np.median(np.abs(v - np.median(v)))), 1e-6) if len(v) > 5 else math.nan

    def dist(a, b, group):
        z = [abs(a["p"][f] - b["p"][f]) / scale[f] for f in PROFILE[group]
             if np.isfinite(a["p"][f]) and np.isfinite(b["p"][f]) and np.isfinite(scale[f])]
        return float(np.mean(np.minimum(z, 6.0))) if len(z) >= MIN_FEATS else math.nan

    by_p = {}
    for x in P:
        by_p.setdefault(x["person"], []).append(x)
    pairs = []  # (kind, person, days apart, rhythm, process)
    for per, xs in by_p.items():
        for i in range(len(xs)):
            for j in range(i + 1, len(xs)):
                a, b = xs[i], xs[j]
                kind = "same" if a["device"] == b["device"] else "cross"
                pairs.append({"kind": kind, "student": per, "days": abs(a["t"] - b["t"]) / 86400,
                              "rhythm": dist(a, b, "rhythm"), "process": dist(a, b, "process")})
    rng = np.random.default_rng(seed)
    by_q = {}
    for x in P:
        by_q.setdefault((x["q"], x["device"]), []).append(x)
    for x in P:
        others = [y for y in by_q.get((x["q"], x["device"]), []) if y["person"] != x["person"]]
        for k in (rng.choice(len(others), min(max_between, len(others)), replace=False) if others else []):
            y = others[int(k)]
            pairs.append({"kind": "between", "student": x["person"], "days": abs(x["t"] - y["t"]) / 86400,
                          "rhythm": dist(x, y, "rhythm"), "process": dist(x, y, "process")})

    def per_student_median(rows, g):
        by = {}
        for r in rows:
            if np.isfinite(r[g]):
                by.setdefault(r["student"], []).append(r[g])
        return {k: float(np.median(v)) for k, v in by.items()}

    out = {"sessions": len(P), "students": len(by_p), "pairs": {}, "paired": {}, "gap": {}, "spearman_days": {}}
    for kind in ("same", "cross", "between"):
        R = [r for r in pairs if r["kind"] == kind]
        e = {"pairs": len(R), "students": len({r["student"] for r in R})}
        for g in PROFILE:
            m = per_student_median(R, g)
            rows = [{"student": k, "v": v} for k, v in m.items()]
            e[g] = float(np.median(list(m.values()))) if m else math.nan
            e[f"{g}_ci"] = _boot(rows, lambda rs: float(np.median([r["v"] for r in rs])) if rs else math.nan, 500)
        out["pairs"][kind] = e
    both = sorted({r["student"] for r in pairs if r["kind"] == "cross"} & {r["student"] for r in pairs if r["kind"] == "same"})
    for g in PROFILE:
        ms = per_student_median([r for r in pairs if r["kind"] == "same"], g)
        mc = per_student_median([r for r in pairs if r["kind"] == "cross"], g)
        mb = per_student_median([r for r in pairs if r["kind"] == "between"], g)
        ds = [{"student": k, "d": mc[k] - ms[k]} for k in both if k in ms and k in mc]
        db = [{"student": k, "d": mb[k] - mc[k]} for k in mc if k in mb]
        out["paired"][g] = {"students": len(ds), "median_cross_minus_same": float(np.median([d["d"] for d in ds])) if ds else math.nan,
                            "ci": _boot(ds, lambda x: float(np.median([d["d"] for d in x])) if x else math.nan, 1000),
                            "share_cross_larger": float(np.mean([d["d"] > 0 for d in ds])) if ds else math.nan,
                            "between_minus_cross_students": len(db),
                            "median_between_minus_cross": float(np.median([d["d"] for d in db])) if db else math.nan,
                            "between_minus_cross_ci": _boot(db, lambda x: float(np.median([d["d"] for d in x])) if x else math.nan, 1000)}
    same = [r for r in pairs if r["kind"] == "same"]
    for lo, hi, lab in GAP_BINS:
        R = [r for r in same if lo <= r["days"] < hi]
        e = {"pairs": len(R), "students": len({r["student"] for r in R})}
        for g in PROFILE:
            m = per_student_median(R, g)
            rows = [{"student": k, "v": v} for k, v in m.items()]
            e[g] = float(np.median(list(m.values()))) if m else math.nan
            e[f"{g}_ci"] = _boot(rows, lambda rs: float(np.median([r["v"] for r in rs])) if rs else math.nan, 500)
        out["gap"][lab] = e
    for g in PROFILE:
        out["spearman_days"][g] = {"rho": _spearman([r["days"] for r in same], [r[g] for r in same]),
                                   "ci": _boot(same, lambda rs, g=g: _spearman([r["days"] for r in rs], [r[g] for r in rs]), 500)}
    # which features move: within students with both classes, personal minus lab-PC median, in population scale units
    shift = []
    for f in feats:
        ds = []
        for per in both:
            lab = [x["p"][f] for x in by_p[per] if x["device"] == "lab-PC-like" and np.isfinite(x["p"][f])]
            own = [x["p"][f] for x in by_p[per] if x["device"] == "personal-like" and np.isfinite(x["p"][f])]
            if lab and own and np.isfinite(scale[f]):
                ds.append({"student": per, "d": (float(np.median(own)) - float(np.median(lab))) / scale[f]})
        shift.append({"feature": f, "group": next(g for g, fs in PROFILE.items() if f in fs), "students": len(ds),
                      "median": float(np.median([d["d"] for d in ds])) if ds else math.nan,
                      "ci": _boot(ds, lambda x: float(np.median([d["d"] for d in x])) if x else math.nan, 1000),
                      "share_positive": float(np.mean([d["d"] > 0 for d in ds])) if ds else math.nan})
    out["feature_shift"] = shift
    out["students_both"] = len(both)
    return out


def rq(a):
    from ..db import Database
    from ..pilot import outcome_counts
    t0 = time.time()
    fz = json.loads((a.out / FROZEN).read_text())
    db = Database(str(a.db))
    log("rq: person baselines ...")
    c1 = classroom_corpus(a.db, fz["baseline_min"], False, fz["split"]["test_frac"], held_out=True)
    rows = _score_sessions(a, c1, fz, db)
    log("rq: device-class baselines ...")
    c2 = classroom_corpus(a.db, fz["baseline_min"], True, fz["split"]["test_frac"], held_out=True)
    rows2 = _score_sessions(a, c2, fz, db, with_signs=False)
    out = {"sessions": {"scored": len(rows), "students": len({r["student"] for r in rows}),
                        "hours": sum(r["hours"] for r in rows),
                        "by_split": {sp: sum(r["split"] == sp for r in rows) for sp in ("dev", "test")},
                        "by_device": {d: sum(r["device"] == d for r in rows) for d in sorted({r["device"] for r in rows})}},
           "rq2": rq2(rows),
           "rq3_drift": {sp: rq3_drift([r for r in rows if sp == "all" or r["split"] == sp]) for sp in ("dev", "test", "all")},
           "rq3_devices": {sp: rq3_devices([r for r in rows if sp == "all" or r["split"] == sp],
                                           [r for r in rows2 if sp == "all" or r["split"] == sp]) for sp in ("dev", "test", "all")},
           "rq3_profiles": rq3_profiles(c1),
           "outcomes": outcome_counts(str(a.db)),
           "minutes": (time.time() - t0) / 60}
    (a.out / RQ_SUMMARY).write_text(json.dumps(out, indent=1, default=float) + "\n")
    log(f"rq done in {out['minutes']:.1f} min -> {a.out / RQ_SUMMARY}")

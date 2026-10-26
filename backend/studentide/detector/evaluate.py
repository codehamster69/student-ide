"""Evaluation on synthetic sessions: detection delay, false alarms, ablations.

    python -m studentide.detector.evaluate --typists 60 --seed 7 --thesis ../thesis/latex

Protocol
--------
1. Simulate a population. Each typist gets 4 honest baseline sessions
   ("first four lab weeks") and 7 test sessions: honest x2, proxy,
   takeover by a speed-matched partner, takeover by a random partner,
   copying-out and paste. Matched partners stand in for the study's
   grade-matched proxies and are the hard case.
2. Split typists: the first third calibrate the CUSUM threshold h, the rest
   are the test set. h is the smallest value whose false-alarm rate on the
   calibration typists' honest sessions is <= --target-fa per hour.
3. On the test set report, per condition, the share of sessions with an
   alarm after the switch, the median detection delay (alarm - switch), the
   median error of the estimated switch time, and false alarms per hour of
   honest work. Also report window-level separation (AUC and best balanced
   accuracy of the raw distance, honest windows vs windows typed by another
   person), the number comparable to Nosi's ~80% at 150 s.
4. Ablations: window length (10-150 s), each feature group removed, a
   Nosi-style detector that only uses the L-scale of log inter-key time, and
   comments mixed into code instead of kept apart.

Writes CSV + LaTeX tables to <thesis>/ablations/ and <thesis>/tables/, and
PDF graphs to <thesis>/graphs/. All numbers are synthetic: they show that the
pipeline works and how its knobs trade off, not how it does on students.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .detector import CHANNELS, Baseline, channel_features, cusum, detect, feature_weights
from .features import FEATURES, GROUPS, Streams, streams, window_features
from .synth import Truth, generate_session, nearest_speed, population

TEST_CONDITIONS = [
    ("honest", "honest", None), ("honest2", "honest", None),
    ("proxy", "proxy", "matched"), ("takeover", "takeover", "matched"),
    ("takeover_random", "takeover", "random"), ("copying", "copying", None), ("paste", "paste", None),
]
LABELS = {
    "honest": "A honest", "proxy": "B full proxy (matched)", "takeover": "C takeover (matched)",
    "takeover_random": "C takeover (random partner)", "copying": "D copying out", "paste": "E paste",
}
WINDOWS = [10, 20, 30, 60, 90, 120, 150]
H_GRID = np.round(np.arange(0.5, 60.01, 0.25), 2)


@dataclass
class Sess:
    typist: str
    name: str
    truth: Truth
    st: Streams


def build_dataset(n: int, seed: int, minutes: float, n_base: int = 4, log=print):
    pop = population(n, seed)
    rng = np.random.default_rng(seed)
    base: dict[str, list[Streams]] = {}
    tests: list[Sess] = []
    t0 = time.time()
    for i, ty in enumerate(pop):
        s0 = seed * 1_000_000 + i * 100
        base[ty.id] = [streams(generate_session(ty, "honest", duration_s=minutes * 60, seed=s0 + j)[0])
                       for j in range(n_base)]
        for j, (name, cond, partner) in enumerate(TEST_CONDITIONS):
            other = None
            if partner == "matched":
                other = nearest_speed(pop, ty)
            elif partner == "random":
                other = pop[int(rng.choice([k for k in range(n) if k != i]))]
            ev, truth = generate_session(ty, cond, other=other, duration_s=minutes * 60, seed=s0 + 50 + j)
            tests.append(Sess(ty.id, name, truth, streams(ev)))
        if (i + 1) % 10 == 0:
            log(f"  simulated {i + 1}/{n} typists ({time.time() - t0:.0f} s)")
    return pop, base, tests


class Windows:
    """Cache of window features per (window length, comment mode)."""

    def __init__(self, base, tests):
        self.base, self.tests, self.cache = base, tests, {}

    def get(self, W: float, comments: str = "separate"):
        key = (W, comments)
        if key not in self.cache:
            b = {tid: [window_features(s, W, comments=comments) for s in ss] for tid, ss in self.base.items()}
            t = [window_features(s.st, W, comments=comments) for s in self.tests]
            self.cache[key] = (b, t)
        return self.cache[key]


def _fa_per_hour(series: list[list[float]], hours: float, k: float, h: float) -> float:
    return sum(len(cusum(x, k, h)[1]) for x in series) / hours


def auc(neg: np.ndarray, pos: np.ndarray) -> float:
    """P(pos > neg) + P(tie) / 2, i.e. the Mann-Whitney AUC."""
    if not len(neg) or not len(pos):
        return math.nan
    ns = np.sort(neg)
    below = np.searchsorted(ns, pos, side="left")
    upto = np.searchsorted(ns, pos, side="right")
    return float((below + 0.5 * (upto - below)).sum() / (len(pos) * len(neg)))


def best_balanced_acc(neg: np.ndarray, pos: np.ndarray) -> float:
    if not len(neg) or not len(pos):
        return math.nan
    best = 0.5
    for thr in np.quantile(np.r_[neg, pos], np.linspace(0.01, 0.99, 99)):
        best = max(best, 0.5 * ((neg < thr).mean() + (pos >= thr).mean()))
    return float(best)


def _series(baselines: dict, tests, twin) -> tuple[list, list]:
    xs, dists = [], []
    for s, w in zip(tests, twin):
        b = baselines[s.typist]
        d = b.distances(w)
        dists.append(d)
        xs.append([(v - b.mu0) / b.sd0 for v in d])
    return xs, dists


def run_config(pop, wins: Windows, W: float, channels: dict[str, tuple[list[str], str]],
               comments: str = "separate", target_fa: float = 0.2, calib_frac: float = 1 / 3) -> dict:
    """`channels`: name -> (features, weighting "icc" | "equal", k). Each channel
    gets its own baselines and CUSUM, with h calibrated for target_fa / n_channels."""
    bwin, twin = wins.get(W, comments)
    tests = wins.tests
    ids = [t.id for t in pop]
    calib = set(ids[: max(2, int(len(ids) * calib_frac))])
    honest = [i for i, s in enumerate(tests) if s.truth.condition == "honest"]
    cal_h = [i for i in honest if tests[i].typist in calib]
    hours = sum(tests[i].truth.duration_ms for i in cal_h) / 3.6e6

    chans = {}
    for ch, (feats, weighting, k) in channels.items():
        weights = feature_weights(bwin, feats) if weighting == "icc" else None
        baselines = {tid: Baseline.fit(tid, bwin[tid], feats, weights) for tid in ids}
        xs, dists = _series(baselines, tests, twin)
        h = float(H_GRID[-1])
        for cand in H_GRID:
            if _fa_per_hour([xs[i] for i in cal_h], hours, k, cand) <= target_fa / len(channels):
                h = float(cand)
                break
        chans[ch] = {"features": feats, "weighting": weighting, "weights": weights, "h": h, "k": k,
                     "xs": xs, "dists": dists, "baselines": baselines}

    def alarms(i):
        out = []
        for ch, c in chans.items():
            _, al, st = cusum(c["xs"][i], c["k"], c["h"])
            out += [(twin[i][a]["end"], twin[i][b]["start"], ch) for a, b in zip(al, st)]
        return sorted(out)

    res: dict = {"window_s": W, "comments": comments,
                 "h": {ch: c["h"] for ch, c in chans.items()},
                 "k": {ch: c["k"] for ch, c in chans.items()},
                 "channels": {ch: {k2: c[k2] for k2 in ("features", "weighting", "weights", "h", "k")} for ch, c in chans.items()}}
    test_idx = [i for i, s in enumerate(tests) if s.typist not in calib]
    th = [i for i in test_idx if tests[i].truth.condition == "honest"]
    th_hours = sum(tests[i].truth.duration_ms for i in th) / 3.6e6
    res["fa_per_h"] = sum(len(alarms(i)) for i in th) / th_hours
    res["honest_flagged"] = float(np.mean([bool(alarms(i)) for i in th]))
    per = {}
    for name, _, _ in TEST_CONDITIONS[2:]:
        idx = [i for i in test_idx if tests[i].name == name]
        hit, delays, errs, early, by = 0, [], [], 0, {ch: 0 for ch in chans}
        for i in idx:
            sw = tests[i].truth.switch_t / 1000
            al = alarms(i)
            early += sum(1 for a in al if a[0] <= sw)
            after = [a for a in al if a[0] > sw]
            if after:
                a_t, e_t, ch = after[0]
                hit += 1
                by[ch] += 1
                delays.append(a_t - sw)
                errs.append(abs(e_t - sw))
        per[name] = {
            "n": len(idx), "detected": hit / len(idx) if idx else math.nan,
            "delay_median_s": float(np.median(delays)) if delays else math.nan,
            "delay_p90_s": float(np.percentile(delays, 90)) if delays else math.nan,
            "switch_err_median_s": float(np.median(errs)) if errs else math.nan,
            "alarms_before_switch": early, "first_channel": by,
        }
    res["conditions"] = per

    # window-level separation on the first channel: honest windows vs windows
    # wholly typed by someone else (comparable to Nosi's per-window accuracy)
    first = next(iter(chans.values()))
    dists = first["dists"]
    neg = np.array([v for i in th for v in dists[i] if not math.isnan(v)])
    pos = []
    for i in test_idx:
        s = tests[i]
        if s.name in ("takeover", "proxy"):
            sw = s.truth.switch_t / 1000
            pos += [v for v, w in zip(dists[i], twin[i]) if w["start"] >= sw and not math.isnan(v)]
    pos = np.array(pos)
    res["window_auc"] = auc(neg, pos)
    res["window_bal_acc"] = best_balanced_acc(neg, pos)
    res["_chans"] = chans
    return res


def default_channels(features: list[str] | None = None) -> dict[str, tuple[list[str], str, float]]:
    out = {}
    for ch, (_, weighting, k) in CHANNELS.items():
        feats = channel_features(ch, features)
        if feats:
            out[ch] = (feats, weighting, k)
    return out


# ------------------------------------------------------------------ outputs

def _fmt(v, nd=0, pct=False):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "--"
    if pct:
        return f"{100 * v:.0f}\\%"
    return f"{v:.{nd}f}"


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        fields = list(dict.fromkeys(k for r in rows for k in r))
        w = csv.DictWriter(f, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(rows)


def flat(res: dict, extra: dict | None = None) -> dict:
    c = res["conditions"]
    row = dict(extra or {})
    row.update({
        "window_s": res["window_s"], "h": "/".join(f"{v:g}" for v in res["h"].values()),
        "window_auc": round(res["window_auc"], 3), "window_bal_acc": round(res["window_bal_acc"], 3),
        "fa_per_h": round(res["fa_per_h"], 3), "honest_sessions_flagged": round(res["honest_flagged"], 3),
    })
    for name in c:
        for ch, n in c[name]["first_channel"].items():
            row[f"{name}_first_{ch}"] = n
        row[f"{name}_detected"] = round(c[name]["detected"], 3)
        row[f"{name}_delay_median_s"] = c[name]["delay_median_s"]
        row[f"{name}_switch_err_median_s"] = c[name]["switch_err_median_s"]
    return row


def table_window(rows: list[dict], meta: str) -> str:
    lines = [
        f"% Generated by studentide.detector.evaluate ({meta}). Do not edit by hand.",
        "\\begin{table}[ht]",
        "  \\centering\\small",
        "  \\caption{Window-length ablation on synthetic sessions. Window AUC/accuracy: one window,",
        "    honest vs.\\ typed by another person. Detection: CUSUM alarm after the switch, with $h$ set",
        "    for $\\le 0.2$ false alarms per hour on calibration typists (identity/process channel).",
        "    Delay and switch-time error are medians.}",
        "  \\label{tab:ablation-window-length}",
        "  \\resizebox{\\linewidth}{!}{\\begin{tabular}{@{}rcccrrrcc@{}}",
        "    \\toprule",
        "    $W$ (s) & Win.\\ AUC & Win.\\ acc. & $h$ & Takeover & Delay (s) & Switch err.\\ (s) & Copying & FA/h \\\\",
        "    \\midrule",
    ]
    for r in rows:
        lines.append(
            f"    {r['window_s']:.0f} & {r['window_auc']:.2f} & {r['window_bal_acc']:.2f} & {r['h']} & "
            f"{_fmt(r['takeover_detected'], pct=True)} & {_fmt(r['takeover_delay_median_s'])} & "
            f"{_fmt(r['takeover_switch_err_median_s'])} & {_fmt(r['copying_detected'], pct=True)} & {r['fa_per_h']:.2f} \\\\")
    lines += ["    \\bottomrule", "  \\end{tabular}}", "\\end{table}", ""]
    return "\n".join(lines)


def table_features(rows: list[dict], meta: str) -> str:
    lines = [
        f"% Generated by studentide.detector.evaluate ({meta}). Do not edit by hand.",
        "\\begin{table}[ht]",
        "  \\centering\\small",
        "  \\caption{Detector ablation on synthetic sessions ($W=30$\\,s, $h$ recalibrated per row",
        "    for $\\le 0.2$ false alarms per hour). Share of sessions detected after the switch;",
        "    delay is the median for matched-partner takeovers. Win.\\ AUC is for the first channel listed.}",
        "  \\label{tab:ablation-feature-groups}",
        "  \\resizebox{\\linewidth}{!}{\\begin{tabular}{@{}lccccccr@{}}",
        "    \\toprule",
        "    Configuration & Win.\\ AUC & Proxy & Takeover & Copying & Paste & Delay (s) & FA/h \\\\",
        "    \\midrule",
    ]
    for r in rows:
        lines.append(
            f"    {r['config']} & {r['window_auc']:.2f} & {_fmt(r['proxy_detected'], pct=True)} & "
            f"{_fmt(r['takeover_detected'], pct=True)} & {_fmt(r['copying_detected'], pct=True)} & "
            f"{_fmt(r['paste_detected'], pct=True)} & {_fmt(r['takeover_delay_median_s'])} & {r['fa_per_h']:.2f} \\\\")
    lines += ["    \\bottomrule", "  \\end{tabular}}", "\\end{table}", ""]
    return "\n".join(lines)


def table_conditions(res: dict, meta: str) -> str:
    lines = [
        f"% Generated by studentide.detector.evaluate ({meta}). Do not edit by hand.",
        "\\begin{table}[ht]",
        "  \\centering\\small",
        f"  \\caption{{Switch detection by condition on synthetic test typists ($W={res['window_s']:.0f}$\\,s,",
        f"    $k={'/'.join(f'{v:g}' for v in res['k'].values())}$, $h={'/'.join(f'{v:g}' for v in res['h'].values())}$ for identity/process). Honest sessions: {res['fa_per_h']:.2f} false alarms per hour,",
        f"    {100 * res['honest_flagged']:.0f}\\% of honest sessions flagged at least once.}}",
        "  \\label{tab:detection-by-condition}",
        "  \\resizebox{\\linewidth}{!}{\\begin{tabular}{@{}lrcrrrrc@{}}",
        "    \\toprule",
        "    Condition & $n$ & Detected & Delay med.\\ (s) & Delay p90 (s) & Switch err.\\ (s) & Early alarms & First: id/proc \\\\",
        "    \\midrule",
    ]
    for name, c in res["conditions"].items():
        lines.append(
            f"    {LABELS[name]} & {c['n']} & {_fmt(c['detected'], pct=True)} & {_fmt(c['delay_median_s'])} & "
            f"{_fmt(c['delay_p90_s'])} & {_fmt(c['switch_err_median_s'])} & {c['alarms_before_switch']} & "
            f"{'/'.join(str(v) for v in c['first_channel'].values())} \\\\")
    lines += ["    \\bottomrule", "  \\end{tabular}}", "\\end{table}", ""]
    return "\n".join(lines)


# palette: fixed categorical order (blue, orange, aqua, yellow, magenta), recessive axes
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def _style(plt):
    plt.rcParams.update({
        "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
        "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "lines.linewidth": 1.6,
        "legend.frameon": False, "pdf.fonttype": 42,
    })


def plot_trace(path: Path, wins_end, x, S, k, h, switch_s, alarms, est):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _style(plt)
    m = np.array(wins_end) / 60
    S = cusum(list(x), k, math.inf)[0]  # drawn without the post-alarm restart, for readability
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.2, 3.8), sharex=True, gridspec_kw={"height_ratios": [1, 1]})
    a1.plot(m, x, color=C[0], marker="o", markersize=2.5, linewidth=1.0)
    a1.axhline(k, color=INK2, linewidth=0.8, linestyle=":")
    a1.set_ylabel("score $x_t$")
    a2.plot(m, S, color=C[0])
    a2.axhline(h, color=INK2, linewidth=0.8, linestyle="--")
    a2.text(m[0], h, f" threshold h = {h:.1f}", color=INK2, va="bottom", fontsize=8)
    a2.set_ylabel("CUSUM $S_t$")
    a2.set_xlabel("session time (min)")
    for a in (a1, a2):
        a.axvline(switch_s / 60, color=C[1], linewidth=1.4)
    a1.text(switch_s / 60, a1.get_ylim()[1], "true switch ", color=INK, va="top", ha="right", fontsize=8)
    if alarms:
        a2.plot([alarms[0] / 60], [h], marker="v", color=C[1], markersize=8, linestyle="none")
        a2.annotate(f"alarm, est. switch {est[0] / 60:.1f} min", (alarms[0] / 60, h), xytext=(6, 8),
                    textcoords="offset points", fontsize=8, color=INK)
        a2.axvline(est[0] / 60, color=C[2], linewidth=1.0, linestyle="--")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_window(path: Path, rows: list[dict]):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _style(plt)
    W = [r["window_s"] for r in rows]
    fig, axs = plt.subplots(1, 3, figsize=(6.6, 2.4))
    axs[0].plot(W, [r["window_bal_acc"] for r in rows], color=C[0], marker="o", markersize=4)
    axs[0].set_title("one window: balanced acc.", fontsize=9, color=INK)
    axs[0].set_ylim(0.5, 1.0)
    axs[1].plot(W, [100 * r["takeover_detected"] for r in rows], color=C[0], marker="o", markersize=4, label="takeover")
    axs[1].plot(W, [100 * r["copying_detected"] for r in rows], color=C[1], marker="o", markersize=4, label="copying")
    axs[1].set_title("sessions detected (%)", fontsize=9, color=INK)
    axs[1].set_ylim(0, 100)
    axs[1].legend(fontsize=7, loc="lower right")
    axs[2].plot(W, [r["takeover_delay_median_s"] / 60 for r in rows], color=C[0], marker="o", markersize=4)
    axs[2].set_title("takeover delay, median (min)", fontsize=9, color=INK)
    axs[2].set_ylim(bottom=0)
    for a in axs:
        a.set_xlabel("window W (s)")
        a.set_xticks([10, 30, 60, 90, 120, 150])
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_conditions(path: Path, res: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _style(plt)
    names = list(res["conditions"])
    vals = [100 * res["conditions"][n]["detected"] for n in names]
    fig, ax = plt.subplots(figsize=(6.0, 2.4))
    y = np.arange(len(names))[::-1]
    ax.barh(y, vals, color=C[0], height=0.55)
    ax.set_yticks(y, [LABELS[n] for n in names])
    for yi, v in zip(y, vals):
        ax.text(v + 1, yi, f"{v:.0f}%", va="center", fontsize=8, color=INK)
    ax.set_xlim(0, 110)
    ax.set_xlabel(f"sessions with an alarm after the switch (%), W = {res['window_s']:.0f} s")
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--typists", type=int, default=60)
    p.add_argument("--minutes", type=float, default=30)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--target-fa", type=float, default=0.2, help="false alarms per hour allowed on calibration typists")
    p.add_argument("--main-window", type=float, default=30)
    p.add_argument("--thesis", type=Path, default=None, help="thesis/latex folder to write tables and graphs into")
    p.add_argument("--out", type=Path, default=Path("detector-results"))
    a = p.parse_args()

    t0 = time.time()
    print(f"simulating {a.typists} typists x 11 sessions of {a.minutes:.0f} min ...")
    pop, base, tests = build_dataset(a.typists, a.seed, a.minutes)
    wins = Windows(base, tests)
    feats = list(FEATURES)
    meta = f"seed {a.seed}, {a.typists} typists, {a.minutes:.0f}-min sessions"

    chans = default_channels(feats)
    print("window-length ablation ...")
    wrows, main_res = [], None
    for W in WINDOWS:
        r = run_config(pop, wins, W, chans, target_fa=a.target_fa)
        wrows.append(flat(r))
        if W == a.main_window:
            main_res = r
        c = r["conditions"]
        print(f"  W={W:>3}s  h={r['h']}  winAUC={r['window_auc']:.3f}  takeover={c['takeover']['detected']:.2f}  "
              f"delay={c['takeover']['delay_median_s']:.0f}  copying={c['copying']['detected']:.2f}  FA/h={r['fa_per_h']:.2f}")

    print("ablations ...")
    W0 = a.main_window
    frows = [flat(main_res, {"config": "Two channels (default)"})]
    for g in GROUPS:
        sub = default_channels([f for f in feats if FEATURES[f] != g])
        frows.append(flat(run_config(pop, wins, W0, sub, target_fa=a.target_fa),
                          {"config": f"\\quad without {g.replace('_', ' ')}"}))
    extra = [
        ("Identity channel only", {"identity": chans["identity"]}, "separate"),
        ("Process channel only", {"process": chans["process"]}, "separate"),
        ("Identity channel with $k=0.5$", {"identity": chans["identity"][:2] + (0.5,), "process": chans["process"]}, "separate"),
        ("One channel, all features, equal weights", {"all": (feats, "equal", 0.5)}, "separate"),
        ("One channel, all features, ICC weights", {"all": (feats, "icc", 0.5)}, "separate"),
        ("Nosi-style: L-scale of log IKI only", {"nosi": (["dg_lscale"], "equal", 0.5)}, "separate"),
        ("Comments mixed into code", chans, "mixed"),
    ]
    for label, cfg, com in extra:
        frows.append(flat(run_config(pop, wins, W0, cfg, comments=com, target_fa=a.target_fa), {"config": label}))
    for row in frows:
        print(f"  {row['config']:<44} AUC={row['window_auc']:.3f} proxy={row['proxy_detected']:.2f} "
              f"takeover={row['takeover_detected']:.2f} copying={row['copying_detected']:.2f} "
              f"paste={row['paste_detected']:.2f} FA/h={row['fa_per_h']:.2f}")

    a.out.mkdir(parents=True, exist_ok=True)
    summary = {"meta": meta, "args": {k: str(v) for k, v in vars(a).items()},
               "main": {k2: v for k2, v in main_res.items() if not k2.startswith("_")},
               "window_ablation": wrows, "feature_ablation": frows}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1, default=float))

    if a.thesis:
        th = a.thesis
        write_csv(th / "ablations/window-length/results.csv", wrows)
        (th / "ablations/window-length/table.tex").write_text(table_window(wrows, meta))
        write_csv(th / "ablations/feature-groups/results.csv", frows)
        (th / "ablations/feature-groups/table.tex").write_text(table_features(frows, meta))
        (th / "tables").mkdir(exist_ok=True)
        (th / "tables/detection-by-condition.tex").write_text(table_conditions(main_res, meta))
        (th / "graphs").mkdir(exist_ok=True)
        plot_window(th / "graphs/window-length-tradeoff.pdf", wrows)
        plot_conditions(th / "graphs/detection-by-condition.pdf", main_res)
        # example trace: the first matched takeover in the test set that is
        # caught after the switch with no earlier alarm
        bwin, twin = wins.get(W0)
        ch0 = main_res["_chans"]
        for i, s in enumerate(tests):
            if s.name != "takeover" or s.typist not in ch0["identity"]["baselines"]:
                continue
            det = detect(ch0["identity"]["baselines"][s.typist], twin[i], ch0["identity"]["k"], ch0["identity"]["h"])
            sw = s.truth.switch_t / 1000
            after = [(al, e) for al, e in zip(det.alarms_s, det.switch_est_s) if al > sw]
            if after and not [al for al in det.alarms_s if al <= sw] and sw > 400:
                plot_trace(th / "graphs/cusum-trace-takeover.pdf", det.window_end_s, det.score, det.cusum,
                           ch0["identity"]["k"], ch0["identity"]["h"], sw, [after[0][0]], [after[0][1]])
                break
        print(f"wrote tables and graphs under {th}")
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()

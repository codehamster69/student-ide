"""Re-tuning the detector on pilot classroom data, development part only.

    # on the VM, inside the app container, next to the database (slow: minutes per variant)
    python -m studentide.pilot_tune --db /data/studentide.sqlite3 --out /tmp/tune.json
    # anywhere: calibrate h and print flag rates per variant
    python -m studentide.pilot_tune --summary tune.json [--target 0.2]

The pilot (docs/pilot-data.md) has no labels, so every flag on it counts
toward an upper bound on the false-alarm rate. This tool asks which design
changes bring that bound down without throwing away what the detector is for,
and recalibrates the CUSUM thresholds h on real sessions.

Only DEVELOPMENT sessions are ever scored or written out: students that
`harness.split.pilot_split` puts in "dev": dev-hash students, sessions that started
before TEST_FROM (2026-11-24 00:00 IST). Test students and the later weeks
stay untouched for the held-out evaluation (thesis ch 6/7). The class-level
parts of the detector (ICC weights, key-pair vocabulary, prior) are fitted on
dev students too, so nothing from the test part leaks in.

The first form writes, per variant and per dev session: the standardised
window scores x_t of each channel (what CUSUM accumulates), the session's
context, device class, a salted pseudonym for the student and device (fresh
salt per run, not saved) and paste counts. No key codes, code, clipboard
text, names, roll numbers or session ids. The second form runs CUSUM on
those scores, so h can be chosen off the server.

Variants (cumulative unless said otherwise):
  frozen      the review screen as live before this change (every paste counts, log(0 ms) = -inf)
  fixes       pastes of the student's own text from inside the IDE do not count, and 0 ms
              latencies are floored at 1 ms (features.LOG_FLOOR_MS)
  no_build    ... and build order (fill_in_frac, open_blocks) left out of "process"
  min_base    ... and a baseline needs MIN_BASE_WINDOWS active 30 s windows (10 min of typing)
  device      ... and the baseline is the student's sessions on the same device when it has two
  keep_build  fixes + min_base + device, build order kept (isolates build order)
"""

from __future__ import annotations

import argparse
import collections as C
import copy
import hashlib
import json
import math
import secrets
import sys
import time

import numpy as np

from .detector.detector import cusum
from .detector import features as F
from .detector.features import feature_group, streams
from .harness.split import PILOT_TEST_FROM, pilot_split as _split
from .pilot import AWAY_PASTE_S, BIG_PASTE, device_class, device_fingerprint, ua_info

TEST_FROM = PILOT_TEST_FROM  # 2026-11-24 00:00 IST: sessions from here on are test data for every student
MIN_BASE_WINDOWS = 20
TARGET_FA_PER_H = 0.2  # as the harness: all channels together
H_GRID = np.round(np.arange(2.0, 80.01, 0.25), 2)

VARIANTS: dict[str, dict] = {
    "frozen": {"own_pastes": False, "log_floor_ms": 0.0},
    "fixes": {},
    "no_build": {"drop": ("build_order",)},
    "min_base": {"drop": ("build_order",), "min_baseline_windows": MIN_BASE_WINDOWS},
    "device": {"drop": ("build_order",), "min_baseline_windows": MIN_BASE_WINDOWS, "device_baseline": True},
    "keep_build": {"min_baseline_windows": MIN_BASE_WINDOWS, "device_baseline": True},
}


def pilot_split(student_id: str, started_at: float, test_from: float = TEST_FROM) -> str:
    """harness.split.pilot_split; `test_from` other than TEST_FROM only in tests on seeded data."""
    if test_from != TEST_FROM:
        return "test" if started_at >= test_from else _split(student_id, 0.0)
    return _split(student_id, started_at)


def _fp(s: dict) -> str:
    return device_fingerprint(json.loads(s["client_meta"] or "{}"))


def _settings(base, spec: dict):
    st = copy.deepcopy(base)
    drop = spec.get("drop", ())
    st.channels = {ch: [f for f in feats if feature_group(f) not in drop] for ch, feats in st.channels.items()}
    st.own_pastes = spec.get("own_pastes", True)
    st.min_baseline_windows = spec.get("min_baseline_windows", 0)
    st.device_baseline = spec.get("device_baseline", False)
    return st


def _pastes(rv, s: dict) -> dict:
    """Paste counts for the separate copying signal: outside text only (own pastes discounted)."""
    evs = list(rv.db.iter_events(s["id"], ("edit", "clipboard", "snapshot", "focus")))
    out = {}
    for own in (False, True):
        st = streams(evs, rv.known_text(s) if own else (), own)
        back = sorted(e["t"] for e in evs if e["type"] == "focus" and e["data"].get("state") == "in"
                      and e["data"].get("target") in ("window", "page"))
        pi = np.flatnonzero(st.e_paste)
        big = [i for i in pi if st.e_inserted[i] >= BIG_PASTE]
        away = 0
        for i in pi:
            j = np.searchsorted(back, st.e_t[i], side="right") - 1
            away += j >= 0 and st.e_t[i] - back[j] < AWAY_PASTE_S * 1000 and st.e_inserted[i] >= 20
        tag = "own_discounted" if own else "all"
        out[tag] = {"pastes": int(len(pi)), "big": len(big), "away": int(away),
                    "chars": int(st.e_inserted[pi].sum()), "inserted": int(st.e_inserted.sum())}
        if own:
            out["internal"] = int(st.meta.get("internal_pastes", 0))
    return out


def run(db_path: str, variants: list[str], log=print, test_from: float = TEST_FROM) -> dict:
    """`test_from` is for tests on seeded data only; the CLI always uses TEST_FROM."""
    from .db import Database
    from .review import Reviewer, load_settings

    t0 = time.time()
    salt = secrets.token_hex(8)
    ph = lambda x, n=8: hashlib.sha256((salt + str(x)).encode()).hexdigest()[:n]  # noqa: E731
    db = Database(db_path)
    base = load_settings(h_override="")

    class DevReviewer(Reviewer):
        def _load_sessions(self):  # dev sessions only: baselines and the class population never see test data
            return [s for s in super()._load_sessions() if pilot_split(s["student_id"], s["started_at"], test_from) == "dev"]

    def reviewer(spec):
        rv = DevReviewer(db, settings=_settings(base, spec))
        rv.fresh_s = 0
        return rv

    sessions = DevReviewer(db, settings=base)._load_sessions()
    n_all = len(db.list_sessions())
    shared = C.defaultdict(set)
    for s in sessions:
        shared[_fp(s)].add(s["student_id"])
    usual = {}
    for st_id in {s["student_id"] for s in sessions}:
        usual[st_id] = C.Counter(_fp(s) for s in sessions if s["student_id"] == st_id).most_common(1)[0][0]

    rows: dict[str, dict] = {}
    rv_paste = reviewer({})
    for s in sessions:
        meta = json.loads(s["client_meta"] or "{}")
        os_, _, _ = ua_info(meta.get("user_agent"))
        dk = _fp(s)
        rows[s["id"]] = dict(
            student=ph(s["student_id"], 6), ctx=s["context"], lang=s.get("language"), os=os_, device_fp=ph(dk),
            device=device_class((meta.get("client") or {}).get("kind") or "web", os_, len(shared[dk])),
            usual_device=usual[s["student_id"]] == dk, pastes=_pastes(rv_paste, s), v={})
    log(f"dev sessions {len(rows)} of {n_all}, pastes done in {time.time() - t0:.0f} s")

    cache = {}
    for name in variants:
        spec = VARIANTS[name]
        rv = reviewer(spec)
        key = (spec.get("own_pastes", True), spec.get("log_floor_ms", 1.0))
        F.LOG_FLOOR_MS = key[1]
        if key in cache:  # windows depend only on how pastes are counted: share them
            rv._windows = cache[key]
        cache[key] = rv._windows
        for i, s in enumerate(sessions):
            if i % 200 == 0:
                log(f"  {name} {i}/{len(sessions)} ({time.time() - t0:.0f} s)")
            r = rv.review(s["id"], detail=False)
            b = r["baseline"]
            out = {"ready": b["status"] == "ready", "base_n": b["n_sessions"], "base_min": b.get("typing_min"),
                   "active": sum(w["active"] for w in rv.windows(s))}
            if out["ready"]:
                out["ch"] = {ch: {"W": c["window_s"], "k": c["k"],
                                  "x": [None if v is None else round(v, 3) for v in c["score"]]}
                             for ch, c in r["channels"].items()}
            rows[s["id"]]["v"][name] = out
        F.LOG_FLOOR_MS = 1.0
    return {"generated": time.time(), "took_s": round(time.time() - t0), "split": "dev", "test_from": TEST_FROM,
            "frozen_h": base.h, "variants": {n: VARIANTS[n] for n in variants},
            "rows": list(rows.values())}  # session ids stay behind


# -- off the server: CUSUM, calibration, rates

def _episodes(x: list, W: float, k: float, h: float) -> int:
    """Episodes as the review screen counts them: alarms whose estimated start
    falls within one window of the previous alarm extend the same episode."""
    xs = [math.nan if v is None else v for v in x]
    _, alarms, starts = cusum(xs, k, h)
    n, last = 0, None
    for a, st in zip(alarms, starts):
        if last is None or st * W > (last + 1) * W + 1e-6:
            n += 1
        last = a
    return n


def _hours(rows, name) -> float:
    return sum(r["v"][name]["active"] for r in rows if r["v"][name]["ready"]) * 30 / 3600


def rates(rows: list[dict], name: str, h: dict[str, float]) -> dict:
    R = [r for r in rows if r["v"][name]["ready"]]
    hours = _hours(rows, name)
    per = C.Counter()
    flagged = 0
    for r in R:
        n = {ch: _episodes(c["x"], c["W"], c["k"], h[ch]) for ch, c in r["v"][name]["ch"].items()}
        per.update(n)
        flagged += any(n.values())
    tot = sum(per.values())
    return {"sessions": len(R), "flagged": flagged, "hours": round(hours, 1),
            "per_h": round(tot / hours, 2) if hours else None,
            "by_channel": {ch: round(v / hours, 2) for ch, v in sorted(per.items())} if hours else {}}


def calibrate(rows: list[dict], name: str, target: float) -> dict[str, float]:
    """Smallest h per channel with that channel's episodes per active hour at
    or under target / n_channels (the harness's rule), on these rows."""
    R = [r for r in rows if r["v"][name]["ready"]]
    hours = _hours(rows, name)
    chans = sorted({ch for r in R for ch in r["v"][name]["ch"]})
    h = {}
    for ch in chans:
        for cand in H_GRID:
            n = sum(_episodes(c["x"], c["W"], c["k"], cand) for r in R if (c := r["v"][name]["ch"].get(ch)))
            if n / hours <= target / len(chans):
                h[ch] = float(cand)
                break
        else:
            h[ch] = float(H_GRID[-1])
    return h


def with_k(rows: list[dict], name: str, k: dict[str, float]) -> list[dict]:
    """The same scores run through CUSUM with another reference value k per channel."""
    out = []
    for r in rows:
        v = r["v"][name]
        if v["ready"]:
            v = dict(v, ch={c: dict(d, k=k.get(c, d["k"])) for c, d in v["ch"].items()})
        out.append(dict(r, v={**r["v"], name: v}))
    return out


def drift(rows: list[dict], name: str) -> dict[str, dict]:
    """Mean and spread of the standardised score per channel. On honest data built as
    intended it is about 0 and 1; anything above 0 is drift the baseline did not see."""
    out = {}
    for ch in ("identity", "pairs", "process"):
        x = [v for r in rows if r["v"][name]["ready"] for v in r["v"][name]["ch"].get(ch, {}).get("x", []) if v is not None]
        if x:
            out[ch] = {"n": len(x), "mean": round(float(np.mean(x)), 2), "sd": round(float(np.std(x)), 2)}
    return out


PROPOSAL = ("no_build", {"identity": 2.0, "pairs": 2.0, "process": 2.0})  # brain 2026-11-25-06


def halves(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Two halves of the dev students: calibrate on one, check on the other."""
    a = {r["student"] for r in rows if int(hashlib.sha256(r["student"].encode()).hexdigest(), 16) % 2 == 0}
    return [r for r in rows if r["student"] in a], [r for r in rows if r["student"] not in a]


def summary(rep: dict, target: float = TARGET_FA_PER_H) -> dict:
    rows = rep["rows"]
    A, B = halves(rows)
    out = {"dev_sessions": len(rows), "students": len({r["student"] for r in rows}), "target_per_h": target,
           "frozen_h": rep["frozen_h"], "variants": {}}
    for name in rep["variants"]:
        h_all = calibrate(rows, name, target)
        h_a = calibrate(A, name, target)
        v = {"frozen_h": rates(rows, name, rep["frozen_h"]), "calibrated_h": h_all,
             "at_calibrated": rates(rows, name, h_all),
             "half_check": rates(B, name, h_a)}  # calibrated on one half of the students, rate on the other half
        for k, sel in (("usual_device", lambda r: r["usual_device"]), ("other_device", lambda r: not r["usual_device"]),
                       ("lab_pc", lambda r: r["device"] == "lab-PC-like"), ("personal", lambda r: r["device"] == "personal-like"),
                       ("lab", lambda r: r["ctx"] == "lab"), ("competition", lambda r: r["ctx"] == "competition"),
                       ("outside_paste", lambda r: r["pastes"]["own_discounted"]["big"] + r["pastes"]["own_discounted"]["away"] > 0),
                       ("no_outside_paste", lambda r: r["pastes"]["own_discounted"]["big"] + r["pastes"]["own_discounted"]["away"] == 0)):
            sub = [r for r in rows if sel(r)]
            v[k] = {"frozen_h": rates(sub, name, rep["frozen_h"]), "calibrated_h": rates(sub, name, h_all)}
        v["drift"] = drift(rows, name)
        out["variants"][name] = v
    name, k = PROPOSAL
    if name in rep["variants"]:
        Rk, Ak, Bk = with_k(rows, name, k), with_k(A, name, k), with_k(B, name, k)
        h_all, h_a = calibrate(Rk, name, target), calibrate(Ak, name, target)
        p = {"variant": name, "k": k, "frozen_h": rates(Rk, name, rep["frozen_h"]), "calibrated_h": h_all,
             "at_calibrated": rates(Rk, name, h_all), "half_check": rates(Bk, name, h_a)}
        for key, sel in (("usual_device", lambda r: r["usual_device"]), ("other_device", lambda r: not r["usual_device"]),
                         ("lab_pc", lambda r: r["device"] == "lab-PC-like"), ("personal", lambda r: r["device"] == "personal-like")):
            p[key] = rates([r for r in Rk if sel(r)], name, rep["frozen_h"])
        out["proposal"] = p
    P = [r["pastes"] for r in rows if r["ctx"] in ("lab", "competition")]
    out["pastes"] = {
        "sessions": len(P),
        "with_paste_all": sum(p["all"]["pastes"] > 0 for p in P),
        "with_paste_outside": sum(p["own_discounted"]["pastes"] > 0 for p in P),
        "internal_pastes": sum(p["internal"] for p in P), "all_pastes": sum(p["all"]["pastes"] for p in P),
        "copy_sign_all": sum(p["all"]["big"] + p["all"]["away"] > 0 for p in P),
        "copy_sign_outside": sum(p["own_discounted"]["big"] + p["own_discounted"]["away"] > 0 for p in P),
    }
    return out


def print_summary(s: dict) -> str:
    L = [f"dev sessions {s['dev_sessions']}, students {s['students']}, target {s['target_per_h']}/h; frozen h {s['frozen_h']}"]
    L.append(f"pastes: {s['pastes']}")
    L.append(f"{'variant':<11} {'scored':>6} {'hours':>6} | {'frozen h /h':>11} {'chan':<34} | {'calib h':<38} {'/h':>5} {'other half':>10}")
    for n, v in s["variants"].items():
        f, c, hc = v["frozen_h"], v["at_calibrated"], v["half_check"]
        L.append(f"{n:<11} {f['sessions']:>6} {f['hours']:>6} | {f['per_h']!s:>11} {json.dumps(f['by_channel']):<34} | "
                 f"{json.dumps(v['calibrated_h']):<38} {c['per_h']!s:>5} {hc['per_h']!s:>10}")
    L.append("\nsplits (frozen h -> calibrated h, episodes per active hour):")
    for n, v in s["variants"].items():
        L.append(n + ": " + ", ".join(f"{k} {v[k]['frozen_h']['per_h']}->{v[k]['calibrated_h']['per_h']}"
                                      for k in ("usual_device", "other_device", "lab_pc", "personal", "lab", "competition",
                                                "outside_paste", "no_outside_paste")))
    if "proposal" in s:
        p = s["proposal"]
        L.append(f"\nproposal: {p['variant']} with k {p['k']}: frozen h {p['frozen_h']['per_h']}/h {p['frozen_h']['by_channel']}; "
                 f"calibrated h {p['calibrated_h']} -> {p['at_calibrated']['per_h']}/h, other half {p['half_check']['per_h']}/h; "
                 + ", ".join(f"{k} {p[k]['per_h']}" for k in ("usual_device", "other_device", "lab_pc", "personal")))
    L.append("drift (mean standardised score; 0 if the baseline saw this variation): "
             + json.dumps({n: {c: d["mean"] for c, d in v["drift"].items()} for n, v in s["variants"].items()}))
    return "\n".join(L)


LABELS = {"frozen": "as live", "fixes": "+ own pastes, 1 ms floor", "no_build": "+ no build order",
          "min_base": "+ 10 min baseline", "device": "+ same device", "keep_build": "build order kept"}


def thesis_outputs(s: dict, latex: str) -> list[str]:
    """Generated thesis files: tables/pilot-retune.tex and graphs/pilot-retune.pdf (rerun, don't edit)."""
    from pathlib import Path

    from .harness.report import _plt
    from .detector.evaluate import C, INK

    root = Path(latex)
    (root / "tables").mkdir(parents=True, exist_ok=True)
    (root / "graphs").mkdir(parents=True, exist_ok=True)
    V = s["variants"]
    rows = [(LABELS.get(n, n), v["frozen_h"], v["drift"]) for n, v in V.items()]
    p = s.get("proposal")
    if p:
        rows.append((f"no build order, $k={p['k']['process']:g}$ (proposal)", p["frozen_h"], V[p["variant"]]["drift"]))
    tex = ["% generated by python -m studentide.pilot_tune --summary ... --thesis; do not edit",
           "\\begin{tabular}{@{}lrrrrrr@{}}", "\\toprule",
           "Variant (cumulative) & Scored & Active h & Episodes/h & identity & pairs & process \\\\", "\\midrule"]
    for lab, r, _ in rows:
        bc = r["by_channel"]
        tex.append(f"{lab} & {r['sessions']} & {r['hours']:.1f} & {r['per_h']:.2f} & "
                   + " & ".join(f"{bc.get(c, 0.0):.2f}" for c in ("identity", "pairs", "process")) + " \\\\")
    tex += ["\\bottomrule", "\\end{tabular}"]
    (root / "tables" / "pilot-retune.tex").write_text("\n".join(tex) + "\n")

    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    chans = ("identity", "pairs", "process")
    left = np.zeros(len(rows))
    for i, ch in enumerate(chans):
        vals = np.array([r["by_channel"].get(ch, 0.0) for _, r, _ in rows])
        ax.barh(range(len(rows)), vals, left=left, color=C[i], label=ch, height=0.6)
        left += vals
    for y, (_, r, _) in enumerate(rows):
        ax.text(left[y] + 0.08, y, f"{r['per_h']:.2f}  ({r['sessions']} sessions)", va="center", fontsize=7, color=INK)
    ax.set_yticks(range(len(rows)), [lab.replace("$", "") for lab, _, _ in rows], fontsize=7)
    ax.invert_yaxis()
    ax.axvline(0.2, color=INK, linewidth=0.7, linestyle=":")
    ax.set_xlabel("detector episodes per active typing hour (dev, frozen $h$; target 0.2)", fontsize=8)
    ax.set_xlim(0, max(left) * 1.35)
    ax.legend(fontsize=7, frameon=False, loc="center right")
    fig.tight_layout()
    fig.savefig(root / "graphs" / "pilot-retune.pdf")
    plt.close(fig)
    return [str(root / "tables" / "pilot-retune.tex"), str(root / "graphs" / "pilot-retune.pdf")]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db")
    p.add_argument("--out")
    p.add_argument("--variants", default=",".join(VARIANTS))
    p.add_argument("--summary", metavar="TUNE_JSON")
    p.add_argument("--target", type=float, default=TARGET_FA_PER_H)
    p.add_argument("--json", action="store_true", help="with --summary: print JSON instead of tables")
    p.add_argument("--thesis", metavar="LATEX_DIR", help="with --summary: also write the thesis table and graph")
    a = p.parse_args()
    if a.summary:
        s = summary(json.load(open(a.summary)), a.target)
        print(json.dumps(s, indent=1) if a.json else print_summary(s))
        if a.thesis:
            for f in thesis_outputs(s, a.thesis):
                print("wrote", f, file=sys.stderr)
        return
    if not a.db:
        p.error("--db or --summary is required")
    rep = run(a.db, a.variants.split(","), log=lambda m: print(m, file=sys.stderr))
    if a.out:
        with open(a.out, "w") as f:
            json.dump(rep, f)
    else:
        json.dump(rep, sys.stdout)


if __name__ == "__main__":
    main()

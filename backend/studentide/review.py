"""Evidence for the teacher / interviewer review timeline (phase 3).

Turns a recorded session into what the review screen draws: both detector
channels' scores and CUSUM traces per window, the alarms with their
estimated switch time, which habits moved most at each alarm, and the
pastes, looks away and runs around them. Replay data (initial text plus
every edit) lets the browser rebuild the code at any moment.

Baselines follow the study plan: a student's sessions in the first four
weeks after their first session are their baseline. A baseline session is
itself reviewed against the other baseline sessions, so every session can
be opened. Thresholds h default to the synthetic calibration in
docs/detector.md and can be overridden with $STUDENTIDE_H as
"identity=5.25,process=16.5" once real calibration exists.

The wording on the screen, not this module, carries the policy, but it is
worth repeating: an alarm means "this part of the session is worth talking
about with the student", never "this student cheated".
"""

from __future__ import annotations

import json
import math
import os
import threading

import numpy as np

from .db import Database
from .detector.detector import CHANNELS, Baseline, channel_features, detect_channels, feature_weights, fit_channels
from .detector.features import COMMENT_FEATURES, FEATURES, streams, window_features

WINDOW_S = 30.0
BASELINE_DAYS = 28.0
MIN_BASELINE = 2  # sessions needed before anything is scored
MIN_WEIGHT_STUDENTS = 3  # students with a baseline needed for ICC weights; fewer -> equal weights
H_DEFAULT = {"identity": 5.25, "process": 16.5}

CHANNEL_INFO = {
    "identity": ("Typing rhythm", "Are these the same hands? Key timing and digraph speed compared with the student's own baseline."),
    "process": ("Way of working", "Pauses, revisions, build order, runs, looking away and pasting compared with the student's own baseline."),
}

# feature -> (plain-language label, unit kind). Unit kinds decode the stored
# value: "logms" is log milliseconds, the rest are stored as shown.
FEATURE_INFO: dict[str, tuple[str, str]] = {
    "dg_median": ("Time between keys", "logms"),
    "dg_lscale": ("Spread of key timing", "plain"),
    "hold_median": ("How long keys are held", "logms"),
    "dg_alt_hand": ("Speed, alternating hands", "logms"),
    "dg_same_hand": ("Speed, same hand", "logms"),
    "dg_to_space": ("Speed into the space bar", "logms"),
    "dg_from_space": ("Speed out of the space bar", "logms"),
    "dg_shifted": ("Speed into shifted characters", "logms"),
    "pause_per_100": ("Pauses per 100 keys", "plain"),
    "pause_median": ("Typical pause length", "logms"),
    "del_per_100": ("Deletions per 100 keys", "plain"),
    "del_burst": ("Length of deletion runs", "plain"),
    "fill_in_frac": ("Lines written above existing code", "frac"),
    "open_blocks": ("Blocks left open while writing", "plain"),
    "run_rate": ("Runs per minute", "plain"),
    "focus_out_rate": ("Looks away per minute", "plain"),
    "paste_frac": ("Share of code pasted", "frac"),
}


def parse_h(raw: str | None) -> dict[str, float]:
    h = dict(H_DEFAULT)
    for part in (raw or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() in h:
                h[k.strip()] = float(v)
    return h


def _num(v) -> float | None:
    """JSON-safe float (NaN and inf become null)."""
    if v is None:
        return None
    v = float(v)
    return round(v, 4) if math.isfinite(v) else None


def display_value(feature: str, v: float) -> float:
    kind = FEATURE_INFO[feature][1]
    if kind == "logms":
        return math.exp(v)
    if kind == "frac":
        return 100 * v
    return v


def display_unit(feature: str) -> str:
    return {"logms": "ms", "frac": "%", "plain": ""}[FEATURE_INFO[feature][1]]


class Reviewer:
    """Computes review payloads, caching window features per session."""

    def __init__(self, db: Database, h: dict[str, float] | None = None, window_s: float = WINDOW_S):
        self.db = db
        self.h = h or parse_h(os.environ.get("STUDENTIDE_H"))
        self.window_s = window_s
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, list[dict]]] = {}
        self._models: dict[tuple, dict[str, Baseline]] = {}
        self._weights: tuple[tuple, dict[str, float] | None] | None = None

    # -- data

    def _sessions(self) -> list[dict]:
        return [dict(r) for r in self.db.list_sessions()]

    def windows(self, session: dict) -> list[dict]:
        sid, n = session["id"], session["n_events"]
        with self._lock:
            hit = self._windows.get(sid)
        if hit and hit[0] == n:
            return hit[1]
        events = list(self.db.iter_events(sid))
        w = window_features(streams(events), self.window_s) if events else []
        with self._lock:
            self._windows[sid] = (n, w)
        return w

    def baseline_ids(self, student_sessions: list[dict]) -> list[str]:
        """The student's sessions in the first BASELINE_DAYS after their first one."""
        if not student_sessions:
            return []
        t0 = min(s["started_at"] for s in student_sessions)
        return [s["id"] for s in sorted(student_sessions, key=lambda s: s["started_at"])
                if s["started_at"] < t0 + BASELINE_DAYS * 86400 and s["n_events"] > 0]

    def weights(self, by_id: dict[str, dict]) -> dict[str, float] | None:
        """ICC feature weights from every student's baseline windows (equal weights until
        MIN_WEIGHT_STUDENTS students have a baseline)."""
        per_student: dict[str, list[str]] = {}
        for s in by_id.values():
            per_student.setdefault(s["student_id"], []).append(s)
        base = {st: self.baseline_ids(ss) for st, ss in per_student.items()}
        base = {st: ids for st, ids in base.items() if len(ids) >= MIN_BASELINE}
        key = tuple(sorted((i, by_id[i]["n_events"]) for ids in base.values() for i in ids))
        if self._weights and self._weights[0] == key:
            return self._weights[1]
        w = None
        if len(base) >= MIN_WEIGHT_STUDENTS:
            w = feature_weights({st: [self.windows(by_id[i]) for i in ids] for st, ids in base.items()})
        self._weights = (key, w)
        return w

    def models(self, student: str, ids: list[str], by_id: dict[str, dict]) -> dict[str, Baseline]:
        weights = self.weights(by_id)
        key = (student, tuple((i, by_id[i]["n_events"]) for i in ids), weights is None)
        if key not in self._models:
            self._models[key] = fit_channels(student, [self.windows(by_id[i]) for i in ids], weights)
        return self._models[key]

    def warm(self) -> None:
        """Compute every session's windows ahead of the first list request."""
        for s in self._sessions():
            self.windows(s)

    # -- review

    def review(self, session_id: str, detail: bool = True) -> dict:
        sessions = self._sessions()
        by_id = {s["id"]: s for s in sessions}
        if session_id not in by_id:
            raise KeyError(session_id)
        s = by_id[session_id]
        mine = [x for x in sessions if x["student_id"] == s["student_id"]]
        base_all = self.baseline_ids(mine)
        in_baseline = session_id in base_all
        base_ids = [i for i in base_all if i != session_id]
        wins = self.windows(s)
        duration_s = wins[-1]["end"] if wins else 0.0

        out: dict = {
            "session": _session_json(s, duration_s, in_baseline),
            "window_s": self.window_s,
            "baseline": {"status": "ready" if len(base_ids) >= MIN_BASELINE else "insufficient",
                         "n_sessions": len(base_ids), "needed": MIN_BASELINE, "session_ids": base_ids,
                         "days": BASELINE_DAYS},
            "channels": {}, "alarms": [], "episodes": [],
        }
        if out["baseline"]["status"] == "ready" and wins:
            models = self.models(s["student_id"], base_ids, by_id)
            dets, alarms = detect_channels(models, wins, self.h)
            out["baseline"]["n_windows"] = max(b.n_windows for b in models.values())
            for ch, d in dets.items():
                label, about = CHANNEL_INFO[ch]
                out["channels"][ch] = {
                    "label": label, "about": about, "h": self.h[ch], "k": CHANNELS[ch][2],
                    "score": [_num(v) for v in d.score], "cusum": [_num(v) for v in d.cusum],
                    "peak": _num(max(d.cusum) / self.h[ch]) if d.cusum else 0.0,
                }
            out["alarms"] = [{"t": a, "switch_est": e, "channel": ch} for a, e, ch in alarms]
            out["episodes"] = episodes(alarms, self.window_s)
            for ep in out["episodes"]:
                ep["evidence"] = _evidence(models[ep["channel"]], wins, ep["switch_est"], ep["first_alarm"]) if detail else []
        if detail:
            out["windows"] = [{"start": w["start"], "end": w["end"], "active": bool(w["active"]),
                               "n_keys": int(w["n_keys"])} for w in wins]
            out["events"] = _evidence_events(list(self.db.iter_events(session_id, ("clipboard", "focus", "run", "session_end"))))
        return out

    def summary(self, session_id: str) -> dict:
        r = self.review(session_id, detail=False)
        spark = {}
        for ch, c in r["channels"].items():
            spark[ch] = _downsample([(v or 0.0) / c["h"] for v in c["cusum"]], 48)
        return {**r["session"], "baseline": r["baseline"]["status"],
                "alarms": r["alarms"], "episodes": r["episodes"],
                "peak": {ch: c["peak"] for ch, c in r["channels"].items()}, "spark": spark}


def episodes(alarms: list[tuple[float, float, str]], window_s: float) -> list[dict]:
    """Merge alarms into episodes. After an alarm CUSUM restarts, so a lasting
    change raises a chain of alarms, each starting where the last one fired.
    A reviewer needs one moment to ask about, not a dozen."""
    out: list[dict] = []
    last: dict[str, dict] = {}
    for a, e, ch in alarms:
        ep = last.get(ch)
        if ep and e <= ep["last_alarm"] + window_s + 1e-6:
            ep["last_alarm"] = a
            ep["n_alarms"] += 1
            continue
        ep = {"channel": ch, "label": CHANNEL_INFO[ch][0], "switch_est": e, "first_alarm": a, "last_alarm": a, "n_alarms": 1}
        last[ch] = ep
        out.append(ep)
    return sorted(out, key=lambda x: x["switch_est"])


def _session_json(s: dict, duration_s: float, in_baseline: bool) -> dict:
    meta = json.loads(s["client_meta"]) if isinstance(s["client_meta"], str) else s["client_meta"]
    out = {k: s[k] for k in ("id", "student_id", "task_id", "started_at", "ended_at", "end_reason", "n_events")}
    out["duration_s"] = duration_s
    out["phase"] = "baseline" if in_baseline else "assessed"
    syn = meta.get("synthetic")
    out["synthetic"] = syn if isinstance(syn, dict) else None  # ground truth, demo data only
    return out


def _downsample(x: list[float], n: int) -> list[float]:
    if len(x) <= n:
        return [round(v, 3) for v in x]
    edges = np.linspace(0, len(x), n + 1).astype(int)
    return [round(float(max(x[a:b])), 3) for a, b in zip(edges[:-1], edges[1:])]


def _evidence(b: Baseline, wins: list[dict], start_s: float, alarm_s: float, top: int = 4) -> list[dict]:
    """Which habits moved most between the estimated switch and the alarm,
    in the student's own spread units, signed."""
    seg = [w for w in wins if w["active"] and w["start"] >= start_s - 1e-6 and w["end"] <= alarm_s + 1e-6]
    rows = []
    for f in b.features:
        if f not in b.centre or f in COMMENT_FEATURES:
            continue
        vals = [w[f] for w in seg if not math.isnan(w.get(f, math.nan))]
        if not vals:
            continue
        obs = float(np.median(vals))
        z = (obs - b.centre[f]) / b.spread[f]
        wt = b.weights.get(f, 0.0) if b.weights else 1.0
        rows.append((abs(z) * math.sqrt(wt), f, z, obs))
    rows.sort(reverse=True)
    return [{"feature": f, "label": FEATURE_INFO[f][0], "group": FEATURES[f], "z": round(z, 2),
             "baseline": round(display_value(f, b.centre[f]), 3), "observed": round(display_value(f, obs), 3),
             "unit": display_unit(f)} for _, f, z, obs in rows[:top]]


def _evidence_events(events: list[dict]) -> dict:
    pastes, focus, runs = [], [], []
    away: dict[str, float] = {}
    for ev in events:
        t, d = ev["t"] / 1000, ev["data"]
        if ev["type"] == "clipboard" and d["action"] == "paste":
            text = d.get("text") or ""
            pastes.append({"t": t, "length": d["length"], "lines": d["lines"],
                           "preview": text[:240], "truncated": d.get("truncated", False) or len(text) > 240})
        elif ev["type"] == "focus" and d["target"] in ("window", "page"):
            if d["state"] == "out":
                away.setdefault(d["target"], t)
            elif d["target"] in away:
                focus.append({"t": away.pop(d["target"]), "until": t, "target": d["target"]})
        elif ev["type"] == "run":
            runs.append({"t": t, "exit_code": d.get("exit_code"), "error_type": d.get("error_type")})
    focus.sort(key=lambda f: f["t"])
    return {"pastes": pastes, "focus": focus, "runs": runs}


def replay_data(db: Database, session_id: str) -> dict:
    """Everything the browser needs to rebuild the code at any moment, plus
    code key-press times for the rhythm strip. Offsets are UTF-16, like JS."""
    initial, edits, keys = None, [], []
    for ev in db.iter_events(session_id, ("snapshot", "edit", "key")):
        if ev["type"] == "snapshot" and initial is None:
            initial = ev["data"]["text"]
        elif ev["type"] == "edit":
            d = ev["data"]
            edits.append([round(ev["t"], 1), d["changes"], d["origin"]])
        elif ev["type"] == "key" and ev["data"]["action"] == "down" and not ev["data"].get("repeat") \
                and ev["data"]["cls"] not in ("modifier", "nav"):
            keys.append(round(ev["t"], 1))
    return {"initial": initial or "", "edits": edits, "keys": keys}

"""Evidence for the teacher / interviewer review timeline (phase 3).

Turns a recorded session into what the review screen draws: every detector
channel's scores and CUSUM traces per window, the alarms with their
estimated switch time, which habits moved most at each alarm, and the
pastes, looks away and runs around them. Replay data (initial text plus
every edit) lets the browser rebuild the code at any moment.

The detector runs exactly as the evaluation harness froze it
(`thesis/evaluation/frozen-config.json`, or $STUDENTIDE_CONFIG): each
channel's window length and CUSUM k, the per-key-pair timing channel, the
population prior for short baselines and the calibrated thresholds h. The
population parts (ICC feature weights, the key-pair vocabulary, the prior)
are fitted on this class's own baseline sessions once MIN_POP_STUDENTS
students have a baseline, as the harness fits them on its training
students; before that, equal weights, the frozen vocabulary and no prior.
$STUDENTIDE_H ("identity=19.25,process=7.25") overrides h, e.g. after
calibrating on real data.

Baselines follow the study plan: a student's sessions in the first four
weeks after their first session are their baseline. A baseline session is
itself reviewed against the other baseline sessions, so every session can
be opened.

The wording on the screen, not this module, carries the policy, but it is
worth repeating: an alarm means "this part of the session is worth talking
about with the student", never "this student cheated".
"""

from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .db import Database
from .detector.detector import (CHANNELS, Baseline, channel_features, detect, feature_weights, pair_block_weights,
                                population_prior)
from .detector.features import (COMMENT_FEATURES, PAIR_PREFIX, add_pair_features, feature_group,
                                pair_vocabulary, streams, window_features)

BASELINE_DAYS = 28.0
MIN_BASELINE = 2  # sessions needed before anything is scored
MIN_POP_STUDENTS = 3  # students with a baseline needed to fit weights, vocabulary and prior from the class
MIN_WEIGHT_STUDENTS = MIN_POP_STUDENTS  # old name
CONFIG_PATH = Path(__file__).resolve().parents[2] / "thesis" / "evaluation" / "frozen-config.json"

CHANNEL_INFO = {
    "identity": ("Typing rhythm", "Are these the same hands? Key timing and digraph speed compared with the student's own baseline."),
    "pairs": ("Key-pair timing", "Which pairs of keys this person types quickly or slowly, relative to their own pace, compared with the student's own baseline."),
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

_KEY_NAMES = {"Space": "space", "Enter": "enter", "Tab": "tab", "Minus": "-", "Equal": "=", "Comma": ",",
              "Period": ".", "Slash": "/", "Semicolon": ";", "Quote": "'", "BracketLeft": "[",
              "BracketRight": "]", "Backslash": "\\", "Backquote": "`"}


def key_name(code: str) -> str:
    if code.startswith("Key") and len(code) == 4:
        return code[3].lower()
    if code.startswith("Digit") and len(code) == 6:
        return code[5]
    return _KEY_NAMES.get(code, code)


def feature_info(f: str, pairs_normalised: bool = True) -> tuple[str, str]:
    if f.startswith(PAIR_PREFIX):
        a, b = f[len(PAIR_PREFIX):].split(">", 1)
        return f"Key pair {key_name(a)} → {key_name(b)}", "pace" if pairs_normalised else "logms"
    return FEATURE_INFO[f]


@dataclass
class Settings:
    """How the detector runs on the review screen, from the frozen config."""
    channels: dict[str, list[str]]  # channel -> base features (pair features are added once a vocabulary exists)
    window_s: dict[str, float]
    k: dict[str, float]
    h: dict[str, float]
    weighting: dict[str, str]
    prior_n: float = 0.0
    pairs: dict | None = None  # the frozen "pairs" spec, see harness.methods.ChannelMethod
    pair_vocab: list[str] = field(default_factory=list)  # fallback vocabulary (fitted on dev students)
    source: str = "built-in"

    @property
    def pair_channel(self) -> str | None:
        return self.pairs.get("channel", "identity") if self.pairs else None


# what the harness froze on 2026-10-26; used when no config file is found
_FALLBACK = {"methods": {"thesis": {"kind": "thesis", "process_w": 90, "prior_n": 2.0}},
             "operating_point": {"h": {"identity": 19.25, "process": 7.25}}}


def load_settings(path: str | os.PathLike | None = None, h_override: str | None = None) -> Settings:
    path = Path(path or os.environ.get("STUDENTIDE_CONFIG") or CONFIG_PATH)
    fz, source = (json.loads(path.read_text()), str(path)) if path.exists() else (_FALLBACK, "built-in")
    th = fz["methods"]["thesis"]
    op = fz.get("operating_point", {})
    chans, W, k, wt = {}, {}, {}, {}
    for ch, (_, weighting, k0) in CHANNELS.items():
        feats = [f for f in channel_features(ch, th.get("features")) if feature_group(f) != "pairs"]
        if feats:
            chans[ch], wt[ch] = feats, weighting
            W[ch] = float(th.get("identity_w", 30) if ch == "identity" else th.get("process_w", 30))
            k[ch] = float((th.get("k") or {}).get(ch, k0))
    pairs = th.get("pairs")
    if pairs and pairs.get("channel") == "pairs":
        chans["pairs"], wt["pairs"] = [], "equal"
        W["pairs"], k["pairs"] = W.get("identity", 30.0), float(pairs.get("k", 1.0))
    W.update({ch: float(v) for ch, v in op.get("window_s", {}).items() if ch in chans})
    k.update({ch: float(v) for ch, v in op.get("k", {}).items() if ch in chans})
    h = {ch: float(op.get("h", {}).get(ch, 10.0)) for ch in chans}
    h = parse_h(h_override if h_override is not None else os.environ.get("STUDENTIDE_H"), h)
    return Settings(chans, W, k, h, wt, float(th.get("prior_n", 0.0)), pairs, list(op.get("pair_vocab", [])), source)


def parse_h(raw: str | None, default: dict[str, float] | None = None) -> dict[str, float]:
    h = dict(default if default is not None else load_settings(h_override="").h)
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


def display_value(feature: str, v: float, pairs_normalised: bool = True) -> float:
    kind = feature_info(feature, pairs_normalised)[1]
    if kind in ("logms", "pace"):
        return math.exp(v)
    if kind == "frac":
        return 100 * v
    return v


def display_unit(feature: str, pairs_normalised: bool = True) -> str:
    return {"logms": "ms", "frac": "%", "plain": "", "pace": "× own pace"}[feature_info(feature, pairs_normalised)[1]]


@dataclass
class _Population:
    vocab: list[str]
    features: dict[str, list[str]]
    weights: dict[str, dict[str, float] | None]
    prior: dict[str, dict | None]


class Reviewer:
    """Computes review payloads, caching window features per session."""

    def __init__(self, db: Database, h: dict[str, float] | None = None, settings: Settings | None = None):
        self.db = db
        self.settings = settings or load_settings()
        if h:
            self.settings.h.update(h)
        self.h = self.settings.h
        self.window_s = self.settings.window_s.get("identity", min(self.settings.window_s.values()))
        self._lock = threading.Lock()
        self._windows: dict[tuple, tuple[int, list[dict]]] = {}
        self._models: dict[tuple, dict[str, Baseline]] = {}
        self._pop: tuple[tuple, _Population] | None = None

    # -- data

    def _sessions(self) -> list[dict]:
        return [dict(r) for r in self.db.list_sessions()]

    def windows(self, session: dict, window_s: float | None = None) -> list[dict]:
        W = window_s or self.window_s
        sid, n = session["id"], session["n_events"]
        with self._lock:
            hit = self._windows.get((sid, W))
        if hit and hit[0] == n:
            return hit[1]
        events = list(self.db.iter_events(sid))
        w = window_features(streams(events), W) if events else []
        with self._lock:
            self._windows[(sid, W)] = (n, w)
        return w

    def channel_windows(self, session: dict, ch: str, pop: _Population) -> list[dict]:
        w = self.windows(session, self.settings.window_s[ch])
        st = self.settings
        if ch == st.pair_channel and pop.vocab:
            w = add_pair_features(w, pop.vocab, st.pairs.get("normalise", True), st.pairs.get("min_count", 1))
        return w

    def baseline_ids(self, student_sessions: list[dict]) -> list[str]:
        """The student's sessions in the first BASELINE_DAYS after their first one."""
        if not student_sessions:
            return []
        t0 = min(s["started_at"] for s in student_sessions)
        return [s["id"] for s in sorted(student_sessions, key=lambda s: s["started_at"])
                if s["started_at"] < t0 + BASELINE_DAYS * 86400 and s["n_events"] > 0]

    def population(self, by_id: dict[str, dict]) -> _Population:
        """Key-pair vocabulary, ICC weights and population prior from every
        student's baseline sessions (frozen vocabulary, equal weights and no
        prior until MIN_POP_STUDENTS students have a baseline)."""
        per_student: dict[str, list[dict]] = {}
        for s in by_id.values():
            per_student.setdefault(s["student_id"], []).append(s)
        base = {st: self.baseline_ids(ss) for st, ss in per_student.items()}
        base = {st: ids for st, ids in base.items() if len(ids) >= MIN_BASELINE}
        key = tuple(sorted((i, by_id[i]["n_events"]) for ids in base.values() for i in ids))
        if self._pop and self._pop[0] == key:
            return self._pop[1]
        st = self.settings
        enough = len(base) >= MIN_POP_STUDENTS
        vocab = list(st.pair_vocab)
        if st.pairs and enough:
            W = st.window_s[st.pair_channel]
            vocab = pair_vocabulary([self.windows(by_id[i], W) for ids in base.values() for i in ids],
                                    st.pairs.get("n", 40))
        pop = _Population(vocab, {}, {}, {})
        for ch, feats in st.channels.items():
            if ch == st.pair_channel:
                feats = feats + [PAIR_PREFIX + p for p in vocab]
            pop.features[ch] = feats
            w = None
            if enough:
                bw = {s: [self.channel_windows(by_id[i], ch, pop) for i in ids] for s, ids in base.items()}
                w = feature_weights(bw, feats) if st.weighting[ch] == "icc" else None
            if ch == st.pair_channel and ch != "pairs":
                w = pair_block_weights(feats, w, st.pairs.get("block", 1.0))
            pop.weights[ch] = w
            pop.prior[ch] = None
            if enough and st.prior_n > 0:
                full = {s: Baseline.fit(s, bw[s], feats, w) for s in base}
                pop.prior[ch] = population_prior(full, st.prior_n)
        self._pop = (key, pop)
        return pop

    def weights(self, by_id: dict[str, dict]) -> dict[str, dict[str, float] | None]:
        return self.population(by_id).weights

    def models(self, student: str, ids: list[str], by_id: dict[str, dict]) -> tuple[dict[str, Baseline], _Population]:
        pop = self.population(by_id)
        key = (student, tuple((i, by_id[i]["n_events"]) for i in ids), self._pop[0])
        if key not in self._models:
            self._models[key] = {ch: Baseline.fit(student, [self.channel_windows(by_id[i], ch, pop) for i in ids],
                                                  feats, pop.weights[ch], pop.prior[ch])
                                 for ch, feats in pop.features.items() if feats}
        return self._models[key], pop

    def warm(self) -> None:
        """Compute every session's windows ahead of the first list request."""
        for s in self._sessions():
            for W in set(self.settings.window_s.values()):
                self.windows(s, W)

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
        st = self.settings
        duration_s = max([wins[-1]["end"] if wins else 0.0] +
                         [self.windows(s, W)[-1]["end"] for W in set(st.window_s.values()) if self.windows(s, W)])

        out: dict = {
            "session": _session_json(s, duration_s, in_baseline),
            "window_s": self.window_s,
            "baseline": {"status": "ready" if len(base_ids) >= MIN_BASELINE else "insufficient",
                         "n_sessions": len(base_ids), "needed": MIN_BASELINE, "session_ids": base_ids,
                         "days": BASELINE_DAYS},
            "channels": {}, "alarms": [], "episodes": [],
        }
        if out["baseline"]["status"] == "ready" and wins:
            models, pop = self.models(s["student_id"], base_ids, by_id)
            alarms, cw = [], {}
            for ch, b in models.items():
                cw[ch] = self.channel_windows(s, ch, pop)
                d = detect(b, cw[ch], st.k[ch], st.h[ch])
                alarms += [(a, e, ch) for a, e in zip(d.alarms_s, d.switch_est_s)]
                label, about = CHANNEL_INFO[ch]
                out["channels"][ch] = {
                    "label": label, "about": about, "h": st.h[ch], "k": st.k[ch], "window_s": st.window_s[ch],
                    "start": [w["start"] for w in cw[ch]], "end": d.window_end_s,
                    "score": [_num(v) for v in d.score], "cusum": [_num(v) for v in d.cusum],
                    "peak": _num(max(d.cusum) / st.h[ch]) if d.cusum else 0.0,
                }
            alarms.sort()
            out["baseline"]["n_windows"] = max(b.n_windows for b in models.values())
            out["alarms"] = [{"t": a, "switch_est": e, "channel": ch} for a, e, ch in alarms]
            out["episodes"] = episodes(alarms, st.window_s)
            norm = (st.pairs or {}).get("normalise", True)
            for ep in out["episodes"]:
                ch = ep["channel"]
                ep["evidence"] = _evidence(models[ch], cw[ch], ep["switch_est"], ep["first_alarm"], norm) if detail else []
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


def episodes(alarms: list[tuple[float, float, str]], window_s: float | dict[str, float]) -> list[dict]:
    """Merge alarms into episodes. After an alarm CUSUM restarts, so a lasting
    change raises a chain of alarms, each starting where the last one fired.
    A reviewer needs one moment to ask about, not a dozen. `window_s`: one
    window length, or one per channel."""
    out: list[dict] = []
    last: dict[str, dict] = {}
    for a, e, ch in alarms:
        ep = last.get(ch)
        W = window_s[ch] if isinstance(window_s, dict) else window_s
        if ep and e <= ep["last_alarm"] + W + 1e-6:
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


def _evidence(b: Baseline, wins: list[dict], start_s: float, alarm_s: float, norm: bool = True,
              top: int = 4) -> list[dict]:
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
    return [{"feature": f, "label": feature_info(f, norm)[0], "group": feature_group(f), "z": round(z, 2),
             "baseline": round(display_value(f, b.centre[f], norm), 3), "observed": round(display_value(f, obs, norm), 3),
             "unit": display_unit(f, norm)} for _, f, z, obs in rows[:top]]


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

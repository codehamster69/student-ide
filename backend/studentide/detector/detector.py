"""Per-student baseline, distance-from-baseline score and CUSUM switch detector.

Baseline (`Baseline.fit`): from a student's baseline sessions (the first
four lab weeks) keep only summary statistics per feature, a robust centre
(median) and spread (1.4826 x MAD, floored), plus the mean and standard
deviation of the student's own distance score, measured leave-one-session-out
so it reflects a new honest session rather than the ones the baseline was
fitted on. Nothing else is stored, so raw baseline keystrokes can be deleted.

Score: for window t, z_f = (x_f - centre_f) / spread_f per available
feature, clipped to +-Z_CAP, and d_t = sqrt(mean_f z_f^2). Standardised by
the student's own honest level: x_t = (d_t - mu0) / sd0.

CUSUM (Page 1954): S_t = max(0, S_{t-1} + x_t - k). An alarm is raised when
S_t > h; the switch time estimate is the end of the last window at which S
was zero before the alarm. After an alarm S restarts from zero, so false
alarms in a long honest session are all counted. Inactive windows (too few
keystrokes) leave S unchanged.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field

import numpy as np

from .features import FEATURES

# Two channels, each with its own baseline, score and CUSUM. "identity" asks
# whether the typing hands are the same person (rhythm and digraph timing,
# weighted by how well each feature tells students apart); "process" asks
# whether the way of working changed (pauses, revisions, build order, runs,
# looking away, pasting), which also catches copying out and pasting by the
# student themselves. An alarm on either channel is an alarm; the channel
# that fired tells the reviewer what kind of change it was.
# channel -> (feature groups, weighting, CUSUM reference value k). A change of
# typist moves the identity score a lot, so it gets a larger k, which also
# absorbs day-to-day drift; copying shifts the process score only slightly,
# so that channel keeps the textbook k = 0.5 (detects a half-sigma shift).
CHANNELS: dict[str, tuple[tuple[str, ...], str, float]] = {
    "identity": (("rhythm", "digraph"), "icc", 1.0),
    "process": (("pauses", "revision", "build_order", "runs", "focus", "paste"), "equal", 0.5),
}


def channel_features(channel: str, features: list[str] | None = None) -> list[str]:
    groups = CHANNELS[channel][0]
    return [f for f in (features or FEATURES) if FEATURES[f] in groups]

Z_CAP = 6.0
# floors on the spread, so a habit a student never varies (e.g. never pastes)
# does not turn a tiny change into an enormous z
SCALE_FLOOR = {
    "pause_per_100": 0.5, "pause_median": 0.15, "del_per_100": 1.0, "del_burst": 0.3,
    "fill_in_frac": 0.05, "open_blocks": 0.3, "nonappend_frac": 0.05, "jump_rate": 0.3, "run_rate": 0.1, "focus_out_rate": 0.3,
    "paste_frac": 0.02, "dg_lscale": 0.02,
}
DEFAULT_FLOOR = 0.04  # log-ms latency features


@dataclass
class Baseline:
    student: str
    features: list[str]
    centre: dict[str, float]
    spread: dict[str, float]
    n_windows: int
    mu0: float = 0.0
    sd0: float = 1.0
    weights: dict[str, float] | None = None  # per-feature, None = equal
    meta: dict = field(default_factory=dict)

    @staticmethod
    def _stats(windows: list[dict], feats: list[str], prior: dict | None = None,
               n_sessions: int = 0) -> tuple[dict, dict]:
        centre, spread = {}, {}
        for f in feats:
            x = np.array([w[f] for w in windows if w["active"] and not math.isnan(w[f])], float)
            if len(x) < 3:
                continue
            c = float(np.median(x))
            mad = float(np.median(np.abs(x - c))) * 1.4826
            if prior and f in prior["spread"]:
                # short baselines: shrink the spread towards the population's
                # typical spread, as if prior["n"] extra sessions had been seen
                a = n_sessions / (n_sessions + prior["n"])
                mad = math.sqrt(a * mad * mad + (1 - a) * prior["spread"][f] ** 2)
            centre[f] = c
            spread[f] = max(mad, SCALE_FLOOR.get(f, DEFAULT_FLOOR))
        return centre, spread

    @classmethod
    def fit(cls, student: str, sessions: list[list[dict]], features: list[str] | None = None,
            weights: dict[str, float] | None = None, prior: dict | None = None) -> "Baseline":
        """`sessions`: window-feature lists, one per baseline session.
        `weights`: optional per-feature weights, e.g. from `feature_weights`.
        `prior`: optional population prior for short baselines, from
        `population_prior`: {"spread": {feature: s}, "mu0", "sd0", "n"}; the
        student's own estimates count as len(sessions) sessions against the
        prior's n. None (the default) uses the student's data alone."""
        feats = list(features or FEATURES)
        all_w = [w for s in sessions for w in s]
        n = len(sessions)
        centre, spread = cls._stats(all_w, feats, prior, n)
        b = cls(student, feats, centre, spread, sum(w["active"] for w in all_w), weights=weights)
        # calibrate the student's honest distance level leave-one-session-out
        held = []
        if n >= 2:
            for i in range(n):
                rest = [w for j, s in enumerate(sessions) if j != i for w in s]
                c2, s2 = cls._stats(rest, feats, prior, n - 1)
                part = cls(student, feats, c2, s2, 0, weights=weights)
                held += [d for d in part.distances(sessions[i]) if not math.isnan(d)]
        else:
            held = [d for d in b.distances(all_w) if not math.isnan(d)]
        if len(held) >= 3:
            b.mu0 = float(np.mean(held))
            b.sd0 = max(float(np.std(held)), 0.05)
        if prior and "mu0" in prior:
            # one in-sample session underestimates the honest level; lean on the prior
            a = (n - 1) / (n - 1 + prior["n"]) if n >= 2 else 0.0
            b.mu0 = a * b.mu0 + (1 - a) * prior["mu0"]
            b.sd0 = a * b.sd0 + (1 - a) * prior["sd0"]
            b.meta["prior_n"] = prior["n"]
        return b

    def distance(self, w: dict) -> float:
        if not w["active"]:
            return math.nan
        num = den = 0.0
        for f in self.features:
            if f in self.centre and not math.isnan(w.get(f, math.nan)):
                z = min(Z_CAP, abs(w[f] - self.centre[f]) / self.spread[f])
                wt = self.weights.get(f, 0.0) if self.weights else 1.0
                num += wt * z * z
                den += wt
        return math.sqrt(num / den) if den else math.nan

    def distances(self, windows: list[dict]) -> list[float]:
        return [self.distance(w) for w in windows]

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> "Baseline":
        return cls(**json.loads(s))


def feature_weights(baselines: dict[str, list[list[dict]]], features: list[str] | None = None,
                    floor: float = 0.05) -> dict[str, float]:
    """How much each feature tells students apart, from honest baseline data only.

    Weight = intraclass correlation, between-student variance of the
    per-student medians over (between + mean within-student variance).
    Needs no impostor examples, only every student's baseline windows, so it
    can be computed after Phase 1 and stored with the baselines.
    """
    feats = list(features or FEATURES)
    out = {}
    for f in feats:
        med, within = [], []
        for sessions in baselines.values():
            x = np.array([w[f] for s in sessions for w in s if w["active"] and not math.isnan(w[f])], float)
            if len(x) < 3:
                continue
            med.append(np.median(x))
            within.append((1.4826 * np.median(np.abs(x - np.median(x)))) ** 2)
        if len(med) < 3:
            out[f] = floor
            continue
        b, wv = float(np.var(med)), float(np.mean(within))
        out[f] = max(floor, b / (b + wv)) if b + wv > 0 else floor
    return out


def population_prior(baselines: dict[str, "Baseline"], n: float = 2.0) -> dict:
    """Population prior for short baselines, from students whose baselines are
    complete: the median per-feature spread and the median honest level.
    `n` is how many sessions the prior is worth."""
    feats = sorted({f for b in baselines.values() for f in b.spread})
    spread = {f: float(np.median([b.spread[f] for b in baselines.values() if f in b.spread])) for f in feats}
    return {"spread": spread, "mu0": float(np.median([b.mu0 for b in baselines.values()])),
            "sd0": float(np.median([b.sd0 for b in baselines.values()])), "n": float(n)}


@dataclass
class Detection:
    window_end_s: list[float]
    score: list[float]  # standardised distance x_t (NaN for inactive windows)
    cusum: list[float]
    alarms_s: list[float]  # end of the window at which S crossed h
    switch_est_s: list[float]  # estimated change time for each alarm


def cusum(x: list[float], k: float, h: float) -> tuple[list[float], list[int], list[int]]:
    """Return (S trace, alarm indices, estimated change indices)."""
    S, trace, alarms, starts = 0.0, [], [], []
    last_zero = -1
    for i, v in enumerate(x):
        if not math.isnan(v):
            S = max(0.0, S + v - k)
            if S == 0.0:
                last_zero = i
        trace.append(S)
        if S > h:
            alarms.append(i)
            starts.append(last_zero + 1)
            S = 0.0
            last_zero = i
    return trace, alarms, starts


def fit_channels(student: str, sessions: list[list[dict]], weights: dict[str, float] | None = None,
                 features: list[str] | None = None) -> dict[str, Baseline]:
    """One baseline per channel. `weights` (from `feature_weights`) apply to icc channels."""
    out = {}
    for ch, (_, weighting, _) in CHANNELS.items():
        feats = channel_features(ch, features)
        if feats:
            out[ch] = Baseline.fit(student, sessions, feats, weights if weighting == "icc" else None)
    return out


def detect_channels(baselines: dict[str, Baseline], windows: list[dict], h: dict[str, float],
                    k: dict[str, float] | None = None) -> tuple[dict[str, Detection], list[tuple[float, float, str]]]:
    """Run every channel; return per-channel detections and all alarms as
    (alarm time, estimated switch time, channel), sorted by alarm time."""
    k = k or {ch: CHANNELS[ch][2] for ch in baselines}
    dets = {ch: detect(b, windows, k[ch], h[ch]) for ch, b in baselines.items()}
    alarms = sorted((a, e, ch) for ch, d in dets.items() for a, e in zip(d.alarms_s, d.switch_est_s))
    return dets, alarms


def detect(baseline: Baseline, windows: list[dict], k: float = 0.5, h: float = 5.0) -> Detection:
    d = baseline.distances(windows)
    x = [(v - baseline.mu0) / baseline.sd0 for v in d]
    trace, alarms, starts = cusum(x, k, h)
    ends = [w["end"] for w in windows]
    begins = [w["start"] for w in windows]
    return Detection(
        window_end_s=ends, score=x, cusum=trace,
        alarms_s=[ends[i] for i in alarms],
        switch_est_s=[begins[i] for i in starts],
    )

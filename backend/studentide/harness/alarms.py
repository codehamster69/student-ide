"""Shared alarm stage: CUSUM (or a per-window threshold) over a grid of h,
threshold calibration, and the per-session outcomes the metrics need.

For each session and channel, `grid()` runs the alarm rule for every h in
H_GRID at once and records, per h: the number of alarms, how many came
before the true switch, the first alarm after the switch and its estimated
switch time. Picking an operating point is then just an index, which makes
calibration curves and detection-vs-false-alarm curves cheap.

The CUSUM matches `detector.cusum` exactly (tested): S_t = max(0, S_{t-1} +
x_t - k), alarm at S_t > h, switch estimate = start of the window after the
last S = 0, restart after an alarm, inactive windows leave S unchanged.
The "window" rule alarms whenever a single window's x_t > h (classic
continuous verification, no accumulation), with the window itself as the
switch estimate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .methods import Series

H_GRID = np.round(np.r_[np.arange(0.1, 2.0, 0.1), np.arange(2.0, 20.0, 0.25), np.arange(20.0, 120.01, 1.0)], 3)


@dataclass
class Grid:
    n_alarms: np.ndarray  # (H,)
    n_before: np.ndarray  # alarms at or before the switch
    first_after: np.ndarray  # time (s) of the first alarm after the switch, NaN if none
    est_switch: np.ndarray  # its estimated switch time


def grid(series: Series, k: float, switch_s: float | None, rule: str = "cusum", hgrid=H_GRID) -> Grid:
    H = len(hgrid)
    S = np.zeros(H)
    last_zero = np.full(H, -1)
    n_al = np.zeros(H, int)
    n_bef = np.zeros(H, int)
    first = np.full(H, np.nan)
    est = np.full(H, np.nan)
    sw = -math.inf if switch_s is None else switch_s
    honest = switch_s is None
    for i, v in enumerate(series.x):
        if math.isnan(v):
            continue
        if rule == "cusum":
            S = np.maximum(0.0, S + (v - k))
            last_zero[S == 0.0] = i
        else:
            S = np.full(H, v)
            last_zero[:] = i - 1
        fired = S > hgrid
        if fired.any():
            n_al[fired] += 1
            t = series.end[i]
            if honest:
                pass
            elif t <= sw:
                n_bef[fired] += 1
            else:
                new = fired & np.isnan(first)
                first[new] = t
                est[new] = series.start[np.minimum(last_zero[new] + 1, len(series.start) - 1)]
            S[fired] = 0.0
            last_zero[fired] = i
    return Grid(n_al, n_bef, first, est)


def calibrate(honest: list[Grid], hours: float, target_per_h: float, hgrid=H_GRID) -> int:
    """Index of the smallest h whose false-alarm rate on `honest` is <= target."""
    if hours <= 0 or not honest:
        return len(hgrid) - 1
    fa = np.sum([g.n_alarms for g in honest], 0) / hours
    ok = np.flatnonzero(fa <= target_per_h)
    return int(ok[0]) if len(ok) else len(hgrid) - 1


@dataclass
class Outcome:
    """One session at one operating point (all channels combined)."""
    alarms: int
    before: int
    first_after: float
    est_switch: float
    channel: str | None


def combine(grids: dict[str, Grid], idx: dict[str, int]) -> Outcome:
    al = sum(int(g.n_alarms[idx[ch]]) for ch, g in grids.items())
    bef = sum(int(g.n_before[idx[ch]]) for ch, g in grids.items())
    best, est, who = math.nan, math.nan, None
    for ch, g in grids.items():
        t = g.first_after[idx[ch]]
        if not math.isnan(t) and (math.isnan(best) or t < best):
            best, est, who = float(t), float(g.est_switch[idx[ch]]), ch
    return Outcome(al, bef, best, est, who)

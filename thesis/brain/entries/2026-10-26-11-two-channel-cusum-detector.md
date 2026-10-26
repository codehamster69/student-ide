---
date: 2026-10-26
type: decision
title: Baseline from summary stats; two-channel (identity / process) CUSUM detector
thesis-chapter: 05-features-and-detector
---

## What happened

`backend/studentide/detector/detector.py`:

- **Baseline** per student: per-feature median and 1.4826×MAD (floored),
  plus μ0, σ0 of the student's own distance score measured
  leave-one-session-out over the baseline sessions. Serialises to a small
  JSON; nothing else is kept, so raw baseline keys can be deleted.
- **Score**: z per feature clipped at 6, d_t = weighted RMS of z,
  x_t = (d_t − μ0)/σ0.
- **Two channels**: identity (rhythm + digraph, weights = intraclass
  correlation across students' baseline windows, CUSUM k = 1) and process
  (pauses, revision, build order, runs, focus, paste; equal weights, k = 0.5).
  Alarm on either; the alarm carries the channel and an estimated switch time.
- **CUSUM**: S_t = max(0, S_{t−1} + x_t − k), alarm at S_t > h, switch
  estimate = start of the window after the last zero; restart after alarms.
  h per channel calibrated for ≤ 0.2 false alarms/h in total.

## Why

The first version was a single score with equal weights. Exploratory run
(30 typists, seed 3, W = 30 s, k = 0.5, not the reported run):

| design | matched takeover | copying | paste | FA/h |
|---|---|---|---|---|
| one channel, equal weights | 55% | 35% | 100% | 0.05 |
| one channel, ICC weights | 85% | 5% | 35% | 0.25 |
| two channels | 85% | 35% | 100% | 0.20 |

Equal weights let 9 noisy process features drown the rhythm; ICC weights
fix that but give near-zero weight to focus/paste, which barely vary
between honest students yet are exactly what copying and pasting change.
These are two different questions (who is typing vs how they are working),
so they get two channels. The channel that fires is also useful evidence
for the teacher timeline.

ICC weights need only every student's honest baseline windows, no impostor
data, so they can be computed after Phase 1.

k per channel: with k = 0.5 everywhere the identity channel needed h ≈ 15
because day-to-day drift makes a whole honest session sit slightly above
μ0 and the CUSUM integrates it. Same exploratory run, identity k = 1.0:
takeover delay 156 s → 94 s at a lower false-alarm rate; k = 1.0 for the
process channel killed copying detection (35% → 5%), so it stays at 0.5.

## Evidence

Ablation rows "One channel, …" and "Identity channel with k = 0.5" in
`thesis/latex/ablations/feature-groups/`.

## Follow-ups

- Calibrate h on more students; 20 calibration typists gave twice the
  target false-alarm rate on the test typists (entry 12).
- Consider different window lengths per channel (entry 12).

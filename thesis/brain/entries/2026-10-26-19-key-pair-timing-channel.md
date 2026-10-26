---
date: 2026-10-26
type: decision
title: Per-key-pair timing becomes a third CUSUM channel, chosen on dev students only
thesis-chapter: 05-features-and-detector
---

## What happened

The first harness test run (#9) showed scaled Manhattan catching 89% of
speed-matched takeovers against the detector's 64%. Scaled Manhattan compares
individual digraphs; the identity channel only had grouped ones (alternating
hands, into/out of space, shifted). Rohan agreed (2026-10-26) to add
per-key-pair features and choose how to use them on dev only.

Code (PR #10): `features.py` keeps per-window sums of log latency per key pair
typed in flow (`_pairs`, `_pace`); `pair_vocabulary()` picks the most-typed
pairs from training students' baseline sessions; `add_pair_features()` turns
each into a feature `pk:KeyT>KeyH` = pair mean log latency minus the window's
mean log latency (speed-normalised). `harness.methods.ChannelMethod(pairs=...)`
either adds them to the identity channel (`pair_block_weights`: the pairs
together get `block` x the other identity features' weight) or runs them as
their own channel "pairs" (equal weights, own k).

Dev grid (84 dev students, 5-fold, pooled calibration, <= 0.2 FA/h), mean
detection over the five non-honest conditions / matched takeovers:

- no key pairs: 85.0% / 57.1%
- inside identity, block 0.5 / 1 / 2: 85.5 / 85.7 / 86.9%; takeovers at most 63.1%
- own channel, k 0.25 / 0.5 / 1 x 20 / 40 / 80 pairs: 87.6-91.9%
- **chosen: own channel, k = 0.5, 80 pairs: 91.9% / 75.0%, proxies 95.2%, FA 0.17/h**

## Why

Inside the identity channel 80 noisy per-pair z values are averaged with a
few strong rhythm features, so either they dilute rhythm or (low block weight)
add little. A channel of its own lets many small, consistent per-pair
deviations accumulate in their own CUSUM. Speed-normalising keeps overall
speed (already in `dg_median`, and drifting with tiredness) out of it; on
synthetic data raw latencies did about as well (91.0%) with more false alarms
(0.19/h), so normalised was kept for the reason, not the number.

## Evidence

`thesis/latex/ablations/harness-tuning/` (all grid rows), `harness-detector/`
(ablations), `thesis/evaluation/dev-summary.json`, `frozen-config.json`.
Ablations: without key pairs takeovers 75 -> 57%; key pairs replacing the
rhythm channel 61%; needing 2 typings of a pair per window 76% (no gain).

## Follow-ups

- On real data, check the variable-rhythm subgroup (lowest takeover detection
  on test, 64%) and whether the vocabulary from Python lab code differs much
  from the synthetic programs.
- With 1 baseline session the prior now hurts takeovers (51% -> 37%); fine at
  >= 2 sessions. Consider no prior for the pair channel when n = 1.

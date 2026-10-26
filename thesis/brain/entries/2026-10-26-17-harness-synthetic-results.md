---
date: 2026-10-26
type: result
title: Harness test run (36 synthetic test students) - 83% of non-honest sessions caught at 0.28 FA/h; scaled Manhattan better on matched takeovers, blind to copying
thesis-chapter: 07-rq1-switch-detection
---

## What happened

`python -m studentide.harness dev` (14 min) then `test` (4 min), seed 2026,
120 students (84 dev / 36 test), frozen config, pooled calibration, target
0.2 FA/h. Ledger: one test run (`thesis/evaluation/test-ledger.jsonl`).

Frozen choices (dev): process channel W = 90 s (identity stays 30 s),
population prior worth 2 sessions on, pooled calibration; baselines all chose
CUSUM (SM k = 0.25, TypeNet k = 0.25, Nosi k = 0.5 at W = 30 s).

RQ1 test (detected after switch):

| method | proxy | takeover matched | takeover random | copying | paste | FA/h | AUC |
|---|---|---|---|---|---|---|---|
| two-channel CUSUM | 69% | 64% [47-78] | 81% | 100% | 100% | 0.28 [0.06-0.61] | 0.86 |
| scaled Manhattan | 83% | 89% | 81% | 6% | 8% | 0.30 | 0.86 |
| TypeNet-style | 56% | 56% | 72% | 14% | 0% | 0.33 | 0.83 |
| Nosi-style | 58% | 53% | 44% | 67% | 11% | 0.25 | 0.67 |

Matched takeover median delay 295 s; switch-time error 26 s. Over all
non-honest sessions: 83% vs 53 / 39 / 47%.

RQ2 test (LOPO balanced accuracy, composing vs transcribing): Nosi recipe 78%
at 150 s (Nosi reports ~80%); L-scale vs own baseline 91%; process channel
94%. At N = 5, Nosi recipe averages 73% but ranges 51-91% (5-95th pct.).
Comment chunks judged "transcribing" 37% vs 26% for code.

RQ4 test: TPR 83%, FPR 7% -> precision 11% [6-38] at 1/100, 2% at 1/500;
8 honest flags per real one at 1/100, 42 at 1/500. Subgroups (synthetic
terciles) range 0-14% honest flagged, all CIs overlapping (10-14 students each).

## Why it matters

- The two channels are what make the detector useful across conditions; any
  keystroke-only method misses copying and pasting.
- But scaled Manhattan's per-digraph latencies beat the identity channel's
  grouped digraph features on matched takeovers (89 vs 64%). The identity
  channel should get per-digraph features. This must be designed on dev and
  scored as a new frozen config; changing it now on the strength of the test
  result would be tuning on test.
- Matched takeovers are harder here than in the phase-2 pilot (64 vs 72%):
  with 120 students the nearest-speed partner is closer than with 60.
- Precision at 1/100 is ~11%: most flags will be honest students. This is the
  quantitative case for "a flag starts a conversation, never a penalty".
- A test set of 36 cannot show or rule out subgroup disparities of this size.

## Evidence

- `thesis/latex/tables/harness-{methods,conditions,precision,fairness,rq2}.tex` (+ csv)
- `thesis/latex/graphs/harness-{detection-vs-false-alarms,precision,fairness,rq2}.pdf`
- `thesis/evaluation/test-summary.json`, `frozen-config.json`
- Text: ch. 7 sec. "Evaluation harness", ch. 8 results, ch. 10

All numbers are simulated people.

## Follow-ups

- Per-digraph identity features (dev first, new frozen config, new ledger line).
- The review dashboard still runs both channels at 30 s without the prior;
  port the frozen settings (process 90 s, prior) once confirmed on real data.

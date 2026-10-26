---
date: 2026-10-26
type: result
title: Synthetic pilot - 75% of matched takeovers caught, median 86 s delay, 0.42 false alarms/h
thesis-chapter: 07-rq1-switch-detection
---

## What happened

Ran `python -m studentide.detector.evaluate --typists 60 --seed 7 --thesis ../thesis/latex`
(about 3 minutes). 60 simulated typists, each with 4 honest 30-min baseline
sessions and 7 test sessions. First 20 typists calibrate h (≤ 0.2 false
alarms/h total); the other 40 are the test set. W = 30 s unless stated.

| condition (test typists, n = 40 each) | detected | median delay | median switch error | first channel id/proc |
|---|---|---|---|---|
| B full proxy (speed-matched) | 88% | 150 s | 0 s | 31/4 |
| C takeover (speed-matched) | 75% | 86 s | 30 s | 28/2 |
| C takeover (random partner) | 88% | 65 s | 31 s | 33/2 |
| D copying out | 50% | 448 s | 37 s | 3/17 |
| E paste | 82% | 441 s | 40 s | 4/29 |

Honest sessions: 0.42 false alarms per hour; 10% of honest sessions flagged
at least once.

Window length (one-window balanced accuracy / matched takeover detected /
median delay / copying detected): 10 s 0.78/75%/50 s/40%; 30 s
0.80/75%/86 s/50%; 90 s 0.84/78%/294 s/90%; 150 s 0.85/62%/427 s/88%.

Ablations at 30 s (matched takeover / copying / paste): full 75/50/82;
without rhythm 45/45/82; without build order 80/95/92; without focus
78/8/48; one channel equal weights 48/48/88; one channel ICC weights
68/5/10; Nosi-style L-scale only 18/42/0; comments mixed in 72/48/85.

## Why it matters

- The CUSUM makes short windows sufficient for a change of typist: the
  per-window accuracy is only 0.80 at 30 s, but accumulating it catches
  takeovers in about 1.5 minutes. Nosi's ~80% at 150 s was for a single
  window, which is what our 0.85 at 150 s compares to.
- Copying out is a subtler process change and needs ≥ 90 s windows; points
  to running the process channel on longer windows than the identity channel.
- Build-order features (edit position, caret jumps) hurt. Not dropped yet,
  because removing them based on this test set would be tuning on test
  data, and real build order may behave differently.
- False alarms on test typists were twice the calibration target. At
  1-in-100 cheating prevalence, 10% of honest sessions flagged means most
  flags would be honest students: RQ4 and the "conversation, never penalty"
  rule matter.
- Comment separation made no difference here, as expected: simulated
  comments differ from code by one offset. Must be re-tested on real data.

## Evidence

- `thesis/latex/tables/detection-by-condition.tex`
- `thesis/latex/ablations/window-length/{results.csv,table.tex}`
- `thesis/latex/ablations/feature-groups/{results.csv,table.tex}`
- `thesis/latex/graphs/{cusum-trace-takeover,window-length-tradeoff,detection-by-condition}.pdf`
- Script: `backend/studentide/detector/evaluate.py`

All numbers are simulated people, not students.

## Follow-ups

- Per-channel window lengths (identity 30 s, process 90 s).
- More calibration students for h; or calibrate per-student.
- Scaled Manhattan and TypeNet-style baselines in the phase 4 harness.
- Replace simulated takeovers with splices of real Phase 1 sessions.

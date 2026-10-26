---
date: 2026-10-26
type: result
title: Open findings resolved on dev - calibrate h on students' own baseline weeks; a population prior makes 2 baseline sessions as good as 4
thesis-chapter: 07-rq1-switch-detection
---

## What happened

Two open findings from phase 2/3, studied on the dev students (cross-fitted).

**h calibration.** Phase 2: h set on 20 students' staged honest sessions gave
2x the target FA rate. Reproduced: holdout source with 20 students gives
0.43/h for a 0.2 target, 0.30/h even with all 68. New *self* source: score each
student's baseline sessions leave-one-session-out (no staged data needed) ->
0.20/h with 20 students; *pooled* (both) 0.19/h. Pooled had the smallest
average |log(achieved/target)| and is frozen. On unseen test students:
pooled 0.28, self 0.19, holdout 0.33 at target 0.2.

**Short baselines.** Added `population_prior()` and an optional `prior` to
`Baseline.fit` (default off; existing callers unchanged): per-feature spread
and the honest score level (mu0, sd0) shrink towards the population median as
if worth n = 2 sessions. Dev: 2 baseline sessions + prior = 57% matched
takeovers / 100% copying, vs 42% / 74% without; 1 session: honest flagged
12% -> 8%. At 6-8 sessions the prior makes no difference.

Also on dev: process channel on 90 s windows (copying needs >= 90 s, the
earlier open finding) + prior raised mean detection 73% -> 85% at the same
FA rate; build order now earns a small place (dropping it costs 7 points on
proxies), the old per-edit build order cuts copying 100% -> 77%.

## Why

- Each student has only 2 staged honest sessions, so holdout calibration sees
  very few alarms; baseline weeks quadruple the honest hours and exist for
  every enrolled student. In the study, h need not wait for Phase 2.
- Shrinkage is the standard fix for small-sample variance estimates; the
  prior only needs students with complete baselines, which the population has.

## Evidence

- `thesis/latex/ablations/harness-{calibration,baseline-length,tuning,detector,window-length}/`
- `thesis/latex/graphs/harness-{calibration,baseline-length}.pdf`
- `backend/studentide/detector/detector.py` (`population_prior`, `Baseline.fit(prior=...)`)
- `thesis/evaluation/dev-summary.json`

## Follow-ups

- Use the prior in the review dashboard for students with < 4 baseline sessions
  (addresses the 5/24 demo baseline sessions that raised moments).
- Re-check self calibration on real data: real day-to-day drift between lab
  weeks may differ from simulated drift.

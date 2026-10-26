---
date: 2026-10-26
type: decision
title: Competition sessions are measured separately, against the student's own other competitions
thesis-chapter: 04-system-design
supersedes: 2026-10-26-24-class-competitions (open point on baselines)
---

## What happened

Entry 24 left open whether timed competition sittings should count toward a
student's 4-week baseline. Rohan decided: "measure separately for
competition sessions, that's a different behaviour we can use".

`review.Reviewer` now tags each session with a context (`lab` or
`competition`, from `labs.kind`). `baseline_ids(sessions, context, lab_id)`:

- **lab:** the first 28 days of the student's *lab* sessions, as before, but
  competition sessions are never included, even inside those weeks;
- **competition:** the student's sessions from their *other* competitions
  (leave one competition out); MIN_BASELINE (2) still applies.

`/api/review/students` counts only lab baseline sessions. The timeline marks
competition sessions and says what they were compared with. Population
settings (pair vocabulary, ICC weights, prior) still come from lab baselines.

## Why

- Pressure, a clock and a leaderboard change rhythm and way of working;
  mixing them into the lab baseline widens it and hides real switches.
- Keeping them apart turns the difference into data: the gap between a
  student's competition and lab habits is a within-student measurement (a
  possible RQ2-style comparison), and competition takeovers are judged
  against the same student under the same pressure.
- Leave-one-competition-out mirrors the leave-one-session-out convention of
  the detector, and stops sessions of the same sitting vouching for each
  other (a proxy for a whole competition would otherwise look self-consistent).

## Evidence

- `backend/tests/test_review.py`: `test_competition_sessions_have_their_own_baseline`
  (pure) and `test_review_tags_competition_sessions` (API, seeded DB).

## Follow-ups

- Harness: add competition as a context in the labels manifest when Phase 1
  data exists; report lab vs competition separately.
- A student with fewer than two other competitions is not scored in
  competitions; consider a population prior for that cold start.

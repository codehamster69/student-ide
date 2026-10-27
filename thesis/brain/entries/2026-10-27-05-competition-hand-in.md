---
date: 2026-10-27
type: decision
title: Competitions hand in each student's code when time runs out; staff reach the leaderboard from every teacher screen
thesis-chapter: 04-system-design
---

## What happened

Rohan asked that a competition auto-submit when time ends, and said that as
an admin or teacher he could not see the leaderboard.

- **Hand-in.** When the clock ends (or the teacher ends early) the student's
  editor, which now shows the clock and polls `GET /api/competitions/{lab}/clock`
  every 5 s, stops, flushes its edits and returns to the arena. 20 s later
  (`GRACE_S`) the server rebuilds each student's latest code per question from
  edits received by `ends_at + GRACE_S` and grades it as a submission at
  `ends_at` (`submissions.auto = 1`). Skipped: empty or starter code, code equal
  to an earlier submission. Runs once (`competitions.handin_started/done`),
  in a background thread, started lazily by any view of the competition;
  retried after 10 min if it failed.
- **Leaderboard.** The backend already allowed owner, co-teachers and admins
  (PR #19); the board was only reachable via a small "Live board" link at the
  bottom of the competition card. It is now linked from the labs list
  (Leaderboard chip), the competition page header, a top-five preview on the
  competition card, and the live class view.

## Why

- Server-side from the edit log rather than a client "submit" at zero: the
  log is already authoritative (the detector reads it), it works when a
  laptop is closed or offline at the bell, and nothing new is trusted from
  the client after the end. The grace period only bounds network delay; a
  tampered client gains at most 20 s.
- Hand-in time = `ends_at`, so it behaves exactly like a last-second Submit
  (including the speed bonus left on the planned clock when ended early).
- Competitions already ended at deploy time are marked done in the migration
  so announced results do not change retroactively.

## Evidence

- `backend/tests/test_compete.py`: hand-in grades unsubmitted code, skips
  untouched and already-submitted code, ignores late edits, runs once; clock
  endpoint; migration keeps old results. `test_ownership.py`: co-teacher and
  admin get the same board. Full backend suite: 158 passed.
- `frontend/e2e/handin.mjs` (Google mode): owner, co-teacher and admin reach
  the board from the labs list; a student who never pressed Submit tops the
  board after the teacher ends early. Screenshots `thesis/latex/snapshots/handin/`.
- Thesis: paragraphs "Hand-in at the bell" and "Leaderboard for staff",
  figure `fig:compete-handin` in `chapters/04-system-design.tex`.

## Follow-ups

- Needs a redeploy of studentide.hokora.xyz.
- If Rohan wants it for a competition that ended before this shipped, it can
  be run once by clearing that competition's `handin_done`.

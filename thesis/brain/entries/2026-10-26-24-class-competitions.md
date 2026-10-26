---
date: 2026-10-26
type: decision
title: Class competitions with a live leaderboard; the only place correctness is scored
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for competitions "where they compete with the whole class to
stand out", which may later replace quizzes. Added `backend/studentide/compete.py`,
`frontend/src/compete/` and `docs/competitions.md`. A competition is a lab
with `kind = 'competition'`: same questions, roster and recorded sessions,
plus a clock, a lobby where students pick a board name, test-graded
submissions and a live leaderboard with a projector view and a podium.

## Decisions and why

- **Correctness is always scored in competitions.** First design scored effort
  (runs, clean runs) and made tests optional, matching labs. Rohan corrected
  it the same day: "the competition must ensure correctness, that's the only
  part we are seeing correctness for". So every competition question must
  have a test case before the clock starts, and only tests passed score.
  Labs keep correctness optional (the test-cases work treats lab tests as a
  self-check).
- **Partial credit, no penalty for wrong tries.** 100 x passed/total of the
  best submission, plus up to 50 for a full solve early. Trying is never
  punished, which keeps it fun for weaker students.
- **Speed bonus against the planned end.** Found in the browser check:
  measuring against `ends_at` made every bonus shrink when the teacher ended
  early (Ada 300 -> 202). Now measured from start + duration; a test pins it.
- **A competition is a lab, not a new object.** Reuses roster, questions,
  sessions, so the recorder, detector and review timeline need no change.
- **Nothing from the detector reaches the board.** `compete.py` imports
  neither review nor detector (tested). Matches the project rule that a
  highlighted moment leads to a conversation, never a penalty, and never
  public shaming.
- **Gentle visibility.** Default board shows the top ten plus your own place;
  nobody is displayed at the bottom; badges (first to solve, fastest per
  question, solved all, most bugs fixed) spread recognition; no medal at 0
  points. Students only ever see chosen board names, never roll numbers.

## Evidence

- `backend/tests/test_compete.py`: 7 tests; full suite 102 passed.
- `frontend/e2e/compete.mjs`, light and dark: teacher creates and opens it,
  student joins the lobby, clock starts, six API classmates submit (right,
  wrong, partial), student submits a wrong then a right answer in the editor;
  ranks `Ada 300, Grace 150, Rohan 150, ..., partial 33, wrong 0`; ending
  early keeps every score; competition keystrokes are recorded.
- Screenshots: `thesis/latex/snapshots/compete/`; figure in chapter 4,
  section "Class competitions".

## Open

- Should timed competition sessions count toward the 4-week baseline? Typing
  under time pressure may differ. Decide on Phase 1 data; `labs.kind` makes
  exclusion a one-line filter in `review.baseline_ids`.
- Live updates poll (3 s students, 2 s board); fine for a class of 80 on
  SQLite, switch to server-sent events if it ever runs larger.

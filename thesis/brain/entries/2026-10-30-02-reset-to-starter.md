---
date: 2026-10-30
type: decision
title: Students can reset a question to its starter code
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for a reset button so students can go back to the starter code.
Since questions resume the student's latest code (labs since 2026-10-27-02,
competitions since 2026-10-30-01), there was no way back to a clean start.
The editor now has a **Reset** button in the file-tab bar. It asks for
confirmation, then replaces the code with the question's starter (for the
language on screen) in one CodeMirror transaction with `userEvent: "reset"`.

## Why this design

- **Logged as a normal edit, origin `reset`.** No schema change (origin is a
  free string), replay and the time-up hand-in stay exact, and the review
  shows "student reset to the starter code" when the replay is on that edit.
  A new event type or a new session per reset was rejected: both would break
  "one session = one question" or need a schema bump for no gain.
- **Detector skips it.** `features.streams` applies the edit to its document
  copy but adds no edit, line or block samples, and puts the caret at 0. The
  starter was not typed, so counting it would look like a big burst of
  insertions and new lines (the same reason resumed code is a start snapshot).
- **Undoable.** The reset stays in the undo history, so Ctrl+Z restores the
  code. That undo is logged with origin `undo` and is counted like any undo;
  a rare single large insertion, accepted.
- Disabled while running or after a competition's time is up.

## Evidence

- `backend/tests/test_build_order.py::test_reset_to_starter_is_not_writing`
- `frontend/e2e/reset.mjs` (resume, cancel, reset, Ctrl+Z, reset, two `reset`
  edits recorded); screenshots in `thesis/latex/snapshots/reset/`.
- Thesis text: paragraph "Starting a question again" and `fig:reset` in `sec:sitting`.

## Follow-ups

None needed.

---
date: 2026-10-30
type: issue
title: Going back to the competition board no longer resets a question to its starter code
thesis-chapter: 04-system-design
---

## What happened

Rohan reported that a student who went back to the board to try another
question, then returned to a question they had already attempted, found the
editor reset to the starter code. Fixed on branch
`claude/project-thread-w2hg52`: `POST /api/sessions` now returns `resume_code`
for competition questions too, and `app.latest_code` only looks at the
student's earlier sessions on that question in the same language.

## Why

Each board visit opens a new session (one session = one question, one
language, see 2026-10-27-02). Lab sittings already resumed from the latest
session's code, but competitions were excluded when sittings were added,
because they predated sittings, not for a fairness reason: the code was the
student's own and already on the server. Restoring it in the browser only
(localStorage) was rejected: it is lost on another machine or a cleared
browser, and the server copy is the one the hand-in grades anyway.

The language filter matters for any-language competitions, where a question
can have one session per language; without it, C code could come back in a
Python editor. It also protects lab questions if a teacher changes a lab's
language.

Event logging is unchanged: the new session logs the restored code as its
`snapshot {reason: "start"}`, exactly as lab resumes do, so replay starts from
it, the detector never sees it as typing or a paste, and the time-up hand-in
(rebuilt from edits) finds the right code even if the student made no new edit.

## Evidence

- `backend/tests/test_compete.py::test_back_from_the_board_keeps_the_code`
- `backend/tests/test_any_language.py::test_coming_back_restores_the_code_of_that_language`
- Thesis text: paragraph "Coming back to a question" in `sec:competitions`.

## Follow-ups

None needed. The editor does not yet tell the student the code was restored;
add a small note if students find it surprising.

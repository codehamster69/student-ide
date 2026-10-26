---
date: 2026-10-26
type: decision
title: Teachers can create labs, add questions with starter code and assign students; sessions link to lab and question
thesis-chapter: 04-system-design
---

## What happened

Rohan asked whether a teacher can create sessions and add questions. They
could not: the three tasks were hard-coded in `backend/studentide/tasks.json`
and the only teacher screen was the review timeline. This PR adds teacher
authoring (`backend/studentide/teach.py`, `frontend/src/teach/`, `/#/teach`,
docs in `docs/teaching.md`):

- New tables `labs` (title, instructions, status draft/open/closed,
  `everyone`), `questions` (ordered; prompt, starter code, sample input),
  `lab_students` (roster of roll numbers, no FK so a class list can be
  assigned before anyone signs in).
- `sessions` gains `lab_id`, `question_id`, `question_json`; old files migrate
  on open. Students pick a question, the server checks lab open + roster.
- Teacher UI in the same token-gated area as the review timeline, with a
  Labs / Review switch; progress grid per student and question.
- Student task screen shows "Your labs" above practice tasks; editor header
  and panel show lab and question number.

## Why

- **Link through the session, not each event.** Every event already belongs
  to a session, so storing lab and question on the session row ties every
  keystroke to them with no schema bump (still v1) and no extra bytes per
  event. Considered adding them to `session_start`; rejected as redundant.
- **Freeze what the student saw.** `question_json` is a copy taken when the
  session starts. Teachers fix typos mid-lab; without the copy an old
  recording could silently point at a different prompt, which matters when
  RQ2 compares composing and transcribing on the same question.
- **Recorded work cannot be deleted from the UI.** A lab or question with
  sessions can be closed or edited but not removed, so research data is not
  lost by a tidy-up click.
- **`task_id` keeps the question id** so the detector, harness and review
  code, which group by task, work unchanged.
- **Same admin token as review.** One teacher area; per-teacher accounts are
  out of scope until the study needs more than one teacher.

This also gives the study protocol a home: Phase 1 baseline labs and the
Phase 2 staged conditions can each be a lab with its own roster, so the
condition label of a recording can come from which lab it was recorded in.

## Evidence

- `backend/tests/test_teach.py` (9 tests: token required, build/reorder/edit
  lab, cannot open empty lab, only open+assigned labs visible, roster
  validation, session linked + snapshot survives edits, deletion blocked,
  practice tasks unchanged, old DB migration). Full suite passes.
- `frontend/e2e/teach.mjs`: teacher creates a lab in the browser, adds two
  questions, reorders, assigns a fresh student, opens it; the student answers
  question 1 with the starter code in the editor; the recorded session has
  the lab, question and starter code and 160+ events. `record.mjs` still passes.
- Screenshots, light and dark: `thesis/latex/snapshots/teach/`; figure in
  chapter 4, section "Labs and questions".

## Follow-ups

- Tag a lab with a study condition (A to E) so the evaluation labels manifest
  can be generated from labs rather than written by hand.
- Optional time window (opens at / closes at) for timed labs.
- Per-teacher accounts if more than one teacher uses it.

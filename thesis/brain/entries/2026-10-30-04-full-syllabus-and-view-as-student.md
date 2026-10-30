---
date: 2026-10-30
type: decision
title: Learning lab filled out to a full syllabus; teachers get "View as student"
thesis-chapter: 04-system-design
---

## What happened

Rohan asked that the learning lab "not miss any concept" and for admins to be
able to view the app as a student. The lessons were checked against a full
first-year syllabus for C, C++ and Python and 25 lessons were added (57 to 82):
C types and casts, `switch`, loop control, scope, sorting and binary search,
command-line arguments and errors, multi-file programs, variadic functions;
C++ pointers and arrays, namespaces/`enum class`/`constexpr`, recursion and
backtracking, `this`/`static`/`friend`, iterators and more containers, streams,
`optional`/`variant`/`string_view`; Python operators, loop control, nested
lists, modules, argument passing and scope, `collections`/`heapq`, regular
expressions, properties and dataclasses, type hints and testing, sorting and
big-O. Teachers and admins now have **View as student** in the teacher header.
Docs: `docs/learning-lab.md`, `docs/view-as-student.md`.

## Why

- **New lessons slot in with a letter** (`05b-switch.md`), so the ids of
  existing lessons, and students' progress on them, never change.
- **Preview is decided by the server from the sign-in** (a staff account in
  Google mode, the admin token in dev mode), never by a flag the browser
  sends, so a student cannot hide their own sessions from the study.
- **Previews are not study data.** Sessions get `context = 'preview'` and are
  left out of baselines, detector, review, live view, lab progress, lab
  session counts and the export. Staff typing is not a student's rhythm, and
  mixing it in would contaminate baselines and the evaluation.
- **Drafts are shown** (marked) so a teacher can try a lab before opening it.
- **No competitions in preview**: joining would put the teacher on the class
  board, so join and question start are refused with a clear message.
- **No consent screen for staff**: they are not participants.

## Evidence

- `backend/tests/test_learn.py`: every model answer passes and every starter
  fails for all 82 lessons. `backend/tests/test_preview.py`: staff see own and
  shared labs (admins all), drafts marked, nothing reaches review/live/export,
  delete still works, students can't claim preview, competitions refused.
  Full suite: 324 passed.
- e2e `frontend/e2e/preview.mjs` and `frontend/e2e/learn.mjs` pass;
  screenshots in `thesis/latex/snapshots/preview/`.

## Open points

- Previews are kept (marked) rather than deleted; they age out with the raw-key
  purge like other sessions. Could be deleted outright if Rohan prefers.

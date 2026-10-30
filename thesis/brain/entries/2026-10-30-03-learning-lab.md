---
date: 2026-10-30
type: decision
title: Always-open learning lab with runnable lessons; practice recorded but kept apart
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for an open lab with concepts and "trial codes", like learn-c.org,
so students learn by changing code. The student home page now has a
**Learning lab** with two tracks written for this project: C from scratch
(12 lessons, hello world to recursion) and Python basics (6 lessons). Each
lesson is a Markdown file (`backend/studentide/learn/`) with the explanation,
examples the student can load into the editor ("Try it"), and an exercise
with tests and a hidden model answer. A track opens in the normal editor as
a sitting (tab per lesson); Check runs the exercise tests; progress and the
student's last code per lesson are kept. Docs: `docs/learning-lab.md`.

## Why

- **Reuse the editor, not a new screen.** A track is passed to the existing
  Workspace as a list of tasks with `lesson: true`, so Run, Check, Reset,
  resume, tabs and recording work as in labs. Only the side panel changes
  (rendered Markdown, wider, no question list).
- **Lessons as files in the repo** rather than a teacher authoring UI first:
  content can be reviewed in PRs and tested (every model answer must pass,
  every starter must fail). A Teach "Lessons" tab is a follow-up.
- **Record practice, keep it apart (Rohan's choice, 2026-10-30).** The
  alternative was saving only progress. Rohan chose to record keystrokes as
  separate practice for the thesis. Every such session has
  `sessions.context = 'learn'`; `list_sessions` excludes it by default, so
  baselines, the detector, review, the live view and the harness never see
  it, and practice does not start the four-week baseline clock. Export
  includes it. Unsupervised practice may be typed by anyone, so it is not
  used as baseline evidence; it could later inform population priors or
  composing-vs-transcribing analysis (RQ2) if the ethics approval covers it.
- No consent version bump: the consent screen already says typing is
  recorded while students work; the learning lab says plainly that this
  practice is never compared, shown to teachers or marked. Whether to bump
  the consent text is left to Rohan and the ethics committee.

## Evidence

- `backend/tests/test_learn.py` (26 tests incl. one per lesson), full backend
  suite 256 passed before the last UI changes.
- `frontend/e2e/learn.mjs`; screenshots in `thesis/latex/snapshots/learn/`.
- Thesis text: `sec:learning-lab` in `04-system-design.tex`.

## Later the same day

- Rohan asked whether students can scroll the question/lesson panel and
  resize panes ("they can't scroll the question part and can't resize
  individual windows"). Scrolling worked in Chromium at 1366×768 and
  1280×600; not reproduced, asked for the screen and browser. Every editor
  pane (side panel width, output height, input/output split) now has a drag
  handle, remembered per browser, double-click to reset, arrow keys when
  focused. Applies to labs and competitions too.
- Rohan asked for beginner to advanced in both languages. Added C 2 ·
  Advanced (10 lessons: dynamic memory, pointer arithmetic and 2D arrays,
  strings by hand, typedef/enum/union, linked lists, stacks and queues,
  function pointers and qsort, bits, preprocessor, files), Python 2 ·
  Intermediate (6) and Python 3 · Advanced (6). 46 lessons in five tracks,
  ordered by a track `order`; every model answer passes and every starter
  fails (`tests/test_learn.py`).
- Rohan then asked for C++ beginner to advanced too: C++ 1 · Beginner (6),
  C++ 2 · Intermediate (6: classes, RAII, operator overloading, maps/sets,
  algorithms and lambdas, templates) and C++ 3 · Advanced (5: virtual
  functions, smart pointers, move semantics, exceptions, queues/heaps/BFS),
  compiled as C++17 like lab code. 63 lessons in eight tracks, listed C,
  C++, Python, each beginner to advanced.

## Follow-ups

- Teacher authoring of lessons in the browser; more tracks (C++, Java, data structures).
- Decide with the ethics committee whether learning-lab keystrokes need a line in the consent text.

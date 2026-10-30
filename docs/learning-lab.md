# Learning lab

An always-open part of the student IDE where each lesson explains one idea
next to code the student can change and run. Inspired by sites like
learn-c.org; every lesson here is our own text.

Students open it from the **Learning lab** card on their home page. No
roster, no lab times, no teacher needed. A track (for example "C from
scratch") opens like a lab sitting: one editor, a tab per lesson, Previous /
Next, and the lesson text in the side panel. Each code example in the text
has **Try it**, which puts it in the editor (Ctrl+Z brings the student's code
back). Each lesson ends with a small exercise; **Check** runs its tests. A
lesson is *done* once Check passes (or, for a lesson without tests, once the
student ran code in it). Opening a lesson again brings back the student's
last code for it.

Every pane of the editor (lessons and lab questions alike) can be resized by
dragging its edge: the side panel's width, the output pane's height and the
input/output split. Sizes are remembered in the browser; double-click a
handle to reset it. Arrow keys move a focused handle.

Tracks today: **C from scratch** (12 lessons: hello world, variables and
types, scanf, arithmetic and `%`, if/else, loops, functions, arrays,
strings, pointers, structs, recursion) and **Python basics** (6 lessons).

## Writing a lesson

Lessons are files in `backend/studentide/learn/<track>/`:

```
learn/c/track.json        {"title": "C from scratch", "language": "c", "summary": "..."}
learn/c/06-loops.md       one lesson; lessons are ordered by file name
```

`language` is any runner language (`python`, `c`, `cpp`, `java`,
`javascript`). A lesson file:

````markdown
---
title: Loops
summary: Repeat code with for and while.
---
Explanation in Markdown: headings, lists, tables, `inline code`, **bold**.

```c
/* an example in the track's language: shown with a Try it button */
```

## Exercise

What to do.

```input
4729
```

```c starter
/* what the editor opens with (default: the first example) */
```

```c solution
/* model answer: never sent to the browser */
```

```tests
{"name": "4729", "stdin": "4729\n", "expected": "22"}
{"name": "big", "stdin": "999999999\n", "expected": "81", "hidden": true}
```
````

Tests use the same format as lab and competition tests (`docs/question-sources.md`,
`grading.py`): one JSON object per line, stdin in, stdout out, `hidden` tests
count but are never shown. `backend/tests/test_learn.py` runs every lesson's
model answer (it must pass every test) and its starter (it must not), so a
broken lesson fails CI. Lessons ship with the app; a Teach tab for writing
lessons in the browser is a possible follow-up.

## What is recorded

Practice is recorded like a lab (key timing, edits, runs, checks), because
it is extra real typing data for the thesis. It is kept apart:

* Every learning-lab session has `sessions.context = 'learn'`.
  `Database.list_sessions()` leaves those out unless asked
  (`include_learn=True`), so baselines, the detector, the review timeline,
  the live view, teacher session lists and the evaluation harness never see
  them.
* Practice before a student's first lab does not start their four-week
  baseline clock; raw keys are deleted after `$STUDENTIDE_RAW_KEY_DAYS` like
  any other session (`retention.py`).
* `python -m studentide.export` includes them, marked `context: "learn"`.
* The learning lab tells students this in plain words, and so does the
  "Recording" pill in the editor.

## API

```
GET  /api/learn[?student_id=]               tracks, lessons (no answers, no hidden tests), progress
GET  /api/learn/lessons/{track}/{slug}      one lesson
POST /api/sessions {student_id, lesson_id}  start practising; returns resume_code
```

Run and Check use the usual `/api/sessions/{id}/run` and `/check`, in the
lesson's language and against its tests.

---
title: Live view
summary: Follow an open lab in real time with the class view and a read-only student editor, and what students are always told.
order: 5
keywords: [live, class view, editor view, watch, typing, quiet, other tab, moments, read-only, notice, terminal mirror]
---

Open **Live** in the teacher area, or press **Watch live** on an open lab.

## Class view

One card per student, refreshed every few seconds:

| Field | Meaning |
| --- | --- |
| State | Typing, Working, Quiet, Other tab, Not connected, Finished, Left or Not started |
| Question | The student's latest question in this lab |
| Activity | Edits over the last ten minutes |
| Runs | How many, and the last error type if one failed |
| Tests | The last Check result (labs with tests) |
| Pastes | Pastes in the current session |
| Moments | Moments worth a conversation found so far, marked *new* when one appears while you watch |

No code is shown in the class view.

## Editor view

Press a student to see a read-only copy of their editor with their caret, recently changed lines tinted, recent runs with output, the last test check and the prompt. You cannot type in it. For a Sandbox Lab it also shows the open file and a read-only terminal mirror.

## Students are always told

- While you have a student's editor open, their top bar says your name is viewing their editor.
- While the class view is open they see a small **Class view on** pill.
- Every view is logged: teacher, lab, session, student and time.
- The consent screen says this, and students who agreed to an earlier text are asked again.

Nothing from a live view changes a mark, attendance or a competition score.

## Setting it down

The administrator can set the server to `editor` (class and editor views), `class` (class view only, no code ever shown) or `off`. The consent screen follows the setting.

---
date: 2026-10-27
type: decision
title: A lab opens as one sitting with question tabs; each question is still its own session, linked by a sitting id
thesis-chapter: 04-system-design
---

## What happened

Rohan saw the student "Your labs" page on the live site (Strings lab: three
questions as separate cards, each opening its own editor) and asked why a lab
is shown like that instead of as one whole session where students can switch
between problems. Before this change, each question card started a fresh
session from the lab list, and reopening a question started from the starter
code again.

Now (PR for branch `claude/project-thread-oig3ml`, stacked on #16):

- "Start lab" / "Continue lab" (or any question row) opens the whole lab in
  one editor: a tab per question (`q1.py`, `q2.py`, ...), a question list and
  Previous / Next in the side panel. Each question keeps its code, undo
  history, input, output and Check results while the student switches.
- "Finish lab" ends every question session of the sitting: `submit` if the
  code differs from the starter, `left` otherwise. Opening the lab again starts
  a new sitting where each question resumes its latest code (`resume_code`).
- Sessions get a `sitting_id` column. Switching logs a new focus target,
  `focus {target: "question"}` out/in (schema stays v1: additive).
- Detector features: a key gap spanning a return from another question is not
  a pause and not a digraph; question switches are not "looks away".
- Live view (#16): the class view follows the question on screen (the session
  that is polling), and leaving a question is not "other tab".

## Why

- One session per question visited, linked by `sitting_id`, instead of one
  session with per-question segments. Every downstream stage assumes one
  session = one question = one document: the replay that rebuilds code, window
  features and CUSUM per session, the review timeline and code replay, Check
  and Submit against the session's question snapshot, live view's code
  rebuild, competition scoring, and `task_id = question id` for the harness.
  A segmented session would break replay (several documents in one edit
  stream) and force every consumer to split sessions again. Linked sessions
  change nothing downstream and still let analysis regroup a lab visit.
- Sessions are created on first visit to a question, not for all questions at
  once, so an unopened question has no empty recording.
- Each question's recorder keeps its own clock; time spent on another question
  shows as an idle stretch in that question's session. Windows without enough
  keys are already inactive, so only the pause features needed the fix.
- Competitions keep their board (one question per visit, no resume): their
  scoring and lobby flow were built around it, and Rohan asked about labs.

## Evidence

- Backend tests `backend/tests/test_sitting.py` (linked sessions, bad sitting
  id refused, code carried to the next sitting, question switch not a pause,
  live view follows the question on screen); full suite passes.
- Browser test `frontend/e2e/sitting.mjs`; `record`, `teach`, `live` and
  `compete` e2e still pass (teach updated for the "Finish lab" label).
- Screenshots `thesis/latex/snapshots/sitting/` (light and dark); thesis
  subsection `sec:sitting` in 04-system-design.

## Follow-ups

- Review timeline could show a sitting's sessions side by side (one lane per
  question) so a teacher sees the whole lab visit at once.
- Rohan's message was cut off ("Also of..."); the rest may add to this.
- Live site needs a redeploy after merge.

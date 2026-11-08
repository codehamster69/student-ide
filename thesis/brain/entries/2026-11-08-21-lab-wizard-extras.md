---
date: 2026-11-08
type: event
title: Lab wizard extras: import, set up by hand, grading and late policy, mid-lab history with regrade, Vim mode
thesis-chapter: 12-conclusion
---

## What happened

Plan §5.2-5.5 items still missing after the teacher-side PR. Code: `backend/studentide/sandbox_authoring.py`
(pure rules), routes in `sandbox.py` and `previews.py`, screens in `frontend/src/sandbox/LabEditor.tsx`,
`SetupByHand.tsx`, `Subjects.tsx`; Vim in `frontend/src/editor/vim.ts`. Doc: docs/sandbox-labs.md
(Lab wizard extras). Tests: `backend/tests/test_sandbox_authoring.py`.

- Import a question from the web labs' sources as an assignment (statement with credit, one starter file,
  Run command for the chosen language, io tests; function-style questions bring their driver as
  `.studentide/harness.<ext>`). Copy an assignment from another lab.
- Set up by hand: a preview instance of the environment with a terminal; `history -a` logs every command;
  the page distils them (drops look-around commands and editors, strips sudo, adds apt -y) into a setup
  script that is appended to the recipe as a new environment version.
- Grading mode (tests / tests then review / by hand) and late policy (closed / accept / penalty per day
  with a cut-off), in the definition as `grading`; `late_policy()` is the one rule submissions use.
- History of changes after first publish (`sbx_lab_changes`, old values kept) with Undo; test or Run
  changes call `on_tests_changed` hooks (the grading thread's regrade) and record the count.
- Vim key bindings as a per-browser switch in the student editor and sandbox file editors.

## Why

- Rohan: UX "seamless and easy to understand". Each extra is one button or one choice with a plain
  sentence of consequence; the Publish step ends with a "What students will see" card. Comparable tools
  (Codio, CodeGrade) were checked; one complaint found (Codio) is that content updates regrade everything
  silently, so ours says after each save what students will notice and lets the teacher undo.
- Set up by hand records commands, not a container diff: a recipe is reviewable, rebuilds reproducibly and
  stays small; `docker commit` images would be opaque and huge.
- Vim mode keeps vim users in the best-logged surface; no schema change, detector config untouched
  (key events from normal mode are just keys; the identity channel sees them like any other editor keys).

## Evidence

`pytest -q` (whole backend), `npm run typecheck`, screenshots `latex/snapshots/sandbox/sandbox-light-11-publish-grading.png`,
`-09-history.png`; chapter 12 paragraph and Figure `fig:sandbox-wizard-extras`.

## Follow-ups

- Whether vim normal-mode keys should be excluded from the identity channel's digraphs (they are commands,
  not prose typing): check on the development split once real data exists.
- Import from a zip or a public Git folder (plan §5.3) is not built; uploading files covers most of it.

---
date: 2026-11-08
type: decision
title: Students see Sandbox Labs on their home and work on them in a desktop lab workspace
thesis-chapter: 04-system-design
---

## What happened

Branch claude/project-thread-tjj0c5. The student home gets a "Sandbox labs" section, one shelf
per subject (`frontend/src/screens/SandboxLabs.tsx`). In the desktop app a card opens
`SandboxLab.tsx`: an assignment rail, files, editor, an xterm.js terminal, Run/Check/Submit and a
Grade tab, wired to `window.studentDesktop.sandbox/terminal`. On the website the labs are listed
with "Open these in the Student IDE app". `POST /api/sessions` gained `sandbox_lab_id` +
`assignment_id`: one session per assignment visited, linked by the sitting id, context NULL
(study data), `question_json.kind = "sandbox"`. Docs: docs/sandbox-student.md; UX comparison:
thesis/plans/2026-11-08-sandbox-student-ux.md.

## Why

- Sessions follow the PR #17 sitting model, as plan 6.3 said ("reuse the sessions table … so the
  detector and review work unchanged"). Sandbox editor keys count as study data; terminal keys
  stay out of the identity channel (surface), as decided in PR #39.
- New edit origin `reload`: when the open file changes on disk (vim in the terminal, a tool), the
  editor reloads it. Counting that as typing would add fake insertions to the edit features, so
  the detector skips it like `reset`. No existing session has this origin, so the frozen
  config's results do not change.
- No schema bump: everything fits v2 (snapshot reason "start" per file, path on key/edit).
- No browser fallback for students (Rohan, 2026-10-30): labs need the local engine.

## Evidence

- `tests/test_sandbox.py::test_session_per_sandbox_assignment` (roster, draft and wrong-lab refusals,
  stored row shape, v2 events accepted).
- `frontend/e2e/sandbox-student.mjs` with a stand-in bridge: 2 sessions, 1 sitting, editor keys and
  edits with path, terminal keys, term_cmd and run events.
- Screenshots: `thesis/latex/snapshots/sandbox/sandbox-student-light-0{1,2,3,5,6}-*.png`.

## Follow-ups

Teachers other than admins cannot open sandbox sessions in Review yet (ownership checks use web
lab ids). The grading thread adds submissions/grades; the monitoring thread adds the journal
(read-only when offline) and consent v3; Vim mode comes from the P2 thread.

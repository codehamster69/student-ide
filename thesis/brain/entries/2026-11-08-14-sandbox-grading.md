---
date: 2026-11-08
type: decision
title: Sandbox Lab submissions graded on the server (preview service, one at a time); uploads checked against lab, roster and due time
thesis-chapter: 12-conclusion
---

## What happened

P0 gaps 2 and 3 of the Sandbox Labs audit (same day), built on the student-side branch
(which added a recorded session per sandbox assignment, gap 1).

- `backend/studentide/submissions.py`: each Submit snapshot becomes a row in `sbx_submissions`;
  one grader thread starts a fresh container of the lab's environment image through the preview
  driver (no network, 1 CPU, 1 GB), lays starter then student files, runs every test (hidden
  too), stores the result and removes the container. Student and teacher routes; regrade one or all.
- `workspaces.py` + `sandbox.upload_gate`: uploads need the lab open to the student (roster,
  section, published/closed, opens_at) and the assignment in it; Submit after due (+2 min) or on a
  closed lab is refused with a readable 409, backups still kept. Closed labs stay visible read-only.
- Teacher UI: a Submissions step (gradebook, filters, result panel, regrade, CSV), the default view
  of a published lab. Desktop: the upload error carries the server's reason; Submit returns the
  queued submission.

## Why

- **Preview service, not the code runner** (Rohan: "go with your picks"): lab images need Docker,
  and `preview_service.py` is already the only holder of the Docker socket, so no new privileged
  container. The code runner only runs single files in fixed languages.
- **One run at a time**: the VM is an e2-medium (2 vCPU, 4 GB) also hosting the app and up to three
  previews. A queue keeps a whole class submitting at the bell from starving the app; a run takes
  seconds, so 60 submissions clear in a few minutes. Grading is not a study signal, so delay is fine.
- **No network while grading**: tests must not depend on the internet, and student code is untrusted.
- **Hidden tests by name only** for students, like CodeGrade/Gradescope autograders: they know what
  failed without learning the inputs.
- **Refuse late Submits, keep backups**: a deadline must mean something, but losing work is worse.
  A late policy (accept / penalty) is the wizard thread's `late_policy`, to replace this one check.

## Evidence

- `backend/tests/test_submissions.py` (6), `test_workspaces.py` (+1); full suite 392 passed before rebase.
- `frontend/e2e/sandbox-grading.mjs` with screenshots `thesis/latex/snapshots/sandbox/sandbox-light-11-submissions.png`,
  `-12-submission-results.png` (stand-in driver for the screenshots; real Docker grades real C).

## Follow-ups

- Run once with real Docker on the VM and time a class-sized burst.
- Teachers can't open sandbox sessions in Review unless admin: `db.teacher_lab_ids` only knows web labs.
- Snapshot files that are not UTF-8 are not laid into the grading container.

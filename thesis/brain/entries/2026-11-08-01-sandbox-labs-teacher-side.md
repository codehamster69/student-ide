---
date: 2026-11-08
type: event
title: Sandbox Labs teacher side built: subjects, environments, labs, library, capped cloud previews
thesis-chapter: 12-conclusion (sec:desktop-client), 04-system-design
---

## What happened

Workstream 4 of the Sandbox Labs build (plan `thesis/plans/2026-10-30-desktop-client.md`,
milestone D4 and the catalogue part of D1), branch `claude/project-thread-m1plpc`:

- `backend/studentide/sandbox.py`: subjects (owner, co-teachers, TAs; roster with roll
  ranges and sections; copy for next semester), environments as versioned recipes
  (base + ticked tools + optional apt/pip/npm/setup; raw Dockerfile only after admin
  approval) rendered to a Dockerfile, a build-service callback for image digests,
  sandbox labs of assignments (statement, starter files, Run command, io or command
  tests with hidden cases, private reference solution), publish rules (assessed labs
  never on the open network, environment version pinned at publish), and a library of
  teacher-shared snapshots with "update available". Students get labs through
  `/api/sandbox/my/labs` in the format `studentide.sandbox-lab/1` agreed with the desktop
  shell and local-sandbox threads (`min_desktop_version` added at the shell's request).
- `backend/studentide/previews.py` + `preview_service.py`: "Try as a student" in a cloud
  instance for teachers only: 3 seats in total, one per teacher, 15 min idle stop, 60 min
  limit, 1 CPU / 1 GB, never the open internet; Run, Check (all tests), a terminal over a
  WebSocket, and the wizard's Check step (reference solution must pass, starter should fail).
  Only the separate preview service holds the Docker socket (Compose profile `previews`).
- Web UI at `#/sandbox` (`frontend/src/sandbox/`): subject cards, environment builder with a
  live size meter, lab wizard (Basics, Assignments, Check, Publish), library drawer, and the
  preview workspace (statement, file tree, CodeMirror, xterm.js terminal, Run/Check).

## Why

Rohan's decisions of 2026-10-30 stand: teachers create subjects freely, no preset labs, the
library holds only shared labs, cloud instances are only for teacher previews. Previews are
capped because VM cost was the reason compute moved to students' machines; giving the app the
Docker socket would make an app bug a host compromise, hence a separate service that accepts
only preview containers. Previews are not study data: they never create sessions.

Library entries are snapshots rather than live links so a colleague's copy cannot change under
their students; sharing again bumps a version and the copy shows "update available".

## Evidence

- `backend/tests/test_sandbox.py` (13) and `test_previews.py` (8, one on real Docker):
  pass; full suite run before the PR.
- A Dockerfile rendered from a C recipe built on Docker 29: `student` uid 1000 with sudo,
  gcc/gdb/valgrind/vim/nano/tmux/script present, `--network none` blocks all traffic.
- Real-Docker run found a bug the fake driver could not: Docker needs one `--cap-add` per
  capability (Podman accepts a comma list); fixed and told the local-runtime thread.
- `frontend/e2e/sandbox.mjs` passes end to end; screenshots in
  `thesis/latex/snapshots/sandbox/` (subject creation, assignment, tests, Check, Try as a
  student, publish, library, subject).

## Follow-ups

- A real build service (CI job polling `/api/sandbox/builds`) and a registry; until then
  previews on the VM need images built elsewhere or `STUDENTIDE_PREVIEW_BUILD_LOCAL=1`.
- Registries-only network for previews needs the allowlist proxy from the local runtime
  (`desktop/sandbox/src/registries.ts`); without it previews have no network at all.
- Not built yet: readiness board, live terminal mirror, submissions table (D4b), "set up by
  hand" environments, safe mid-lab edits with re-grading.

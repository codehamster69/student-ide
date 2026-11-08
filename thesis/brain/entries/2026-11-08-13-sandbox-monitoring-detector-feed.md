---
date: 2026-11-08
type: decision
title: Sandbox Labs monitoring (watcher, signed offline journal, review lanes, live mirror, readiness board) and which terminal events feed the detector
thesis-chapter: 04-system-design
---

## What happened

Sandbox Labs (desktop app) now record and show what happens outside our
editor, on branch `claude/project-thread-gm01lx`:

- A sidecar watcher container per instance (`desktop/sandbox/src/watcher.ts`)
  reports `fs_change` (with origin vim/nano, command, or outside, and a line
  diff) and `port_open`. Schema v3, additive.
- The desktop app journals every batch on disk (`journal.ts`), signs each with
  a per-install Ed25519 key and hash-chains them (`backend/studentide/batches.py`).
  Students keep working for 5 minutes offline, then the lab turns read-only
  until the connection returns. Tampered, missing or foreign batches are
  recorded as record breaks, never dropped.
- `evidence.py` marks lines in a workspace snapshot or submission that nothing
  we saw explains ("appeared without typing").
- Review: one replay per file plus "Terminal and files" lanes
  (`sandbox_review.py`, `SandboxLanes.tsx`). Live view: file name and a
  read-only terminal mirror. A readiness board / class grid for teachers
  (`sandbox_live.py`, `ClassBoard.tsx`), fed by presence reports from the app.
- Consent v3 for Sandbox Labs only (terminal, file changes, offline journal);
  the web consent stays at v2. The text waits on Rohan's approval.
- Attendance counts sandbox labs; terminal and vim typing count toward the
  40 typed characters (Rohan's pick).

## Why: what feeds the detector

The detector is unchanged; the frozen config (`thesis/evaluation/frozen-config.json`)
stays frozen.

- **Terminal and terminal-editor keys stay out of the identity channel.** Shell
  typing is mostly short, bursty, often recalled with arrow keys or tab
  completion, and vim keys mix commands with text. Their timing has never been
  tested on the dev split, so mixing them into the editor's key-pair profile
  would change the channel the evaluation measured. The detector already skips
  any key whose surface is not `editor`.
- **Terminal compile/run commands are already `run` events** (schema v2), so
  the process channel sees a student who builds from the shell like one who
  presses Run. Nothing new needed.
- **`fs_change` does not feed detector features.** A vim save is one event per
  save, not per keystroke; turning it into edits would invent timing we did not
  observe. It goes to evidence instead: the review lanes and the
  "appeared without typing" check, which are things to ask about, not scores.
- **Offline gaps are shown as gaps, never as moments**, so a flaky lab network
  cannot create a flag. `reload` and `reset` edits remain skipped.

Alternatives considered: feeding terminal keys as a third channel (rejected
until there is lab data to test it on the dev split), and treating unexplained
saves as a CUSUM input (rejected: one event per save is too coarse, and it
would turn evidence into a verdict).

## Evidence

- Real Docker check (`SANDBOX_IT=1 npm run test:engine` in `desktop/sandbox`):
  a vim `:wq` arrives as `fs_change` with origin `terminal-editor` and the new
  line as its diff; the app's own saves and vim swap files are not reported.
- Node signing verified by the Python server end to end; backend tests
  `test_batches.py`, `test_evidence.py`, `test_sandbox_review.py`,
  `test_sandbox_attendance.py`.
- Docs: `docs/event-schema.md` (v3), `docs/sandbox-runtime.md`, `docs/review.md`,
  `docs/live.md`, `docs/attendance.md`, `docs/sandbox-labs.md`, `docs/desktop.md`.

## Follow-ups

- Rohan approves the consent v3 wording before this goes live.
- Once a pilot has Sandbox Lab sessions, test terminal key timing as a channel
  on the dev split (never on the held-out test split casually).
- Wire the connection pill and read-only state into the student's SandboxLab
  screen when the student-screen PR lands (whichever merges second).

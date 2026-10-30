---
date: 2026-10-30
type: plan
title: Desktop plan revised into Sandbox Labs (preset labs, terminal everywhere, portable, online-only, vim allowed)
thesis-chapter: 12-conclusion (future work), 04-system-design
supersedes: 2026-10-30-03-desktop-client-plan.md
---

## What happened

Rohan answered the first draft's open questions (same day, same PR #29):

1. The desktop client is a **separate, new feature**: preset labs, **all with
   terminal access**.
2. Keep it **portable**, in case a lab PC does not work.
3. Offline work is not needed: **online is required** for submissions.
4. **Allow vim/nano.**
5. Best possible UX; still plan only.

`thesis/plans/2026-10-30-desktop-client.md` was rewritten as revision 2
("Sandbox Labs"); the figure and the chapter 12 future-work subsection were
updated to match.

## Why

- **Separate product side.** Sandbox Labs has its own catalogue (subjects,
  preset labs, assignments with starter files and tests, pinned images) and
  leaves web labs and competitions untouched. Sessions reuse the `sessions`
  table (`kind: "sandbox"`, sitting id), so the detector and review work
  unchanged. The per-lab "terminal on/off" switch of the first draft is gone.
- **Portable has three layers.** App: portable builds, no installer, no
  admin. Work: per-assignment workspace snapshots on the server (5 MB cap,
  uploaded on change, Run and Submit), so a student can move from a broken
  lab PC to a laptop mid-lab. Sandbox: a container runtime cannot be made
  portable (Windows needs admin + WSL2), so the engine order is Docker →
  Podman → a **capped cloud sandbox** on the VM as a safety net. The cloud
  fallback costs compute, so it is capped and visible to faculty.
- **Online-only** removes the offline mode: a 5-minute reconnect buffer
  (journal still written for crash safety), then read-only until the
  connection returns; Submit needs a live connection.
- **vim allowed.** Images ship vim, nano, tmux. Our editor gets a Vim mode so
  most vim users stay in the fully logged surface. Keys typed while vim/nano
  is in the foreground are tagged `surface: terminal-editor` (from shell
  hooks), and each save is an `fs_change` diff, so the review can replay a vim
  session save by save. This is weaker than editor edits and the review says
  so. `terminal-editor` keys are an identity-channel candidate to test on dev;
  shell-prompt keys stay out until tested.
- **Workspace snapshots change tamper checks.** Since files can come from the
  terminal, the server checks every file at upload/submit against the
  evidence (editor edits, terminal-editor keys with saves, pastes) and marks
  content with none as "appeared without typing".
- **UX** section expanded: principles, performance budgets (switch < 100 ms,
  key-to-glyph < 16 ms, 60 fps on a 4 GB lab PC), and concrete student and
  faculty screens (Lab doctor, Home shelves, workspace, submit sheet,
  readiness board, live terminal mirror).

## Evidence

- Plan revision 2: `thesis/plans/2026-10-30-desktop-client.md`.
- Figure: `thesis/latex/flowcharts/desktop-client.tex` (adds cloud fallback
  and workspace store).
- Chapter 12: `sec:desktop-client` rewritten.

## Follow-ups

- Rohan: first catalogue subjects (suggested C, then Linux and shell); how
  many cloud fallback seats the VM budget allows; whether IT can install
  Docker or Podman in one lab room for the pilot.
- D0 spike when he says go.

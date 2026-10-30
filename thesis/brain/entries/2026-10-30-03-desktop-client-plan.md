---
date: 2026-10-30
type: plan
title: Plan for a desktop client that runs labs in local Docker while monitoring still works
thesis-chapter: 12-conclusion (future work), 04-system-design
---

## What happened

Rohan saw a desktop lab tool that starts a private Docker sandbox per student
per lab on the student's own machine, with an Ubuntu terminal, file editor,
persistent edits and submission. He asked for a plan (no implementation) for
our own version: local Docker to cut VM compute, monitoring kept, easier
question switching, and a polished motion-rich UI for students and faculty.
The plan is `thesis/plans/2026-10-30-desktop-client.md`; the architecture
figure is `latex/flowcharts/desktop-client.tex`, used in a new future-work
subsection (`sec:desktop-client`) of chapter 12.

## Why

- **Electron over Tauri.** Same Chromium as the web editor, so keystroke
  timestamps are comparable between browser and desktop sessions and the
  recorder is shared code. Tauri's engine differs per OS (WebView2,
  WebKitGTK, WKWebView), which would add a device/engine confound to RQ1 and
  RQ3. Size and RAM are Tauri's advantages; a D0 spike measures RAM on a lab
  PC and timing parity before committing.
- **One container per student per lab, a folder per question.** Container
  start per question would make switching slow; the "one session per
  question, linked by sitting id" model (2026-10-27-02) is kept, so the
  detector and review do not change for switching.
- **Server stays the source of truth.** The local volume is a working copy;
  hand-ins use the server's replayed code, graded work is graded on the
  server runner. A local client cannot be tamper-proof, so the design makes
  tampering visible (signed, hash-chained batches; replay checks; files
  changed outside the editor logged like pastes) rather than promising
  prevention.
- **The terminal is logged, not hidden.** Additive schema v2 (`term_cmd`,
  `term_paste`, `fs_change`, `term_output`, `key.surface`). Terminal key
  timing is kept out of the identity channel until it is tested on the dev
  split, because command typing has a different distribution.
- **Compute.** Today's runs are cheap on the VM; what local Docker really
  buys is affordable per-student terminals and full toolchains.
- **Motion must not distort timing.** Compositor-only animations and a CI
  benchmark comparing inter-key intervals with and without animations.
- **Rejected:** moving faculty to the desktop app (they do not need Docker);
  screen capture or process lists for tamper resistance (breaks the ethics
  position of the web app).

## Evidence

- Plan: `thesis/plans/2026-10-30-desktop-client.md` (decisions table,
  architecture, monitoring and offline design, threat table, UI, faculty
  side, migration, risks, milestones D0 to D6).
- Figure: `thesis/latex/flowcharts/desktop-client.tex`
  (Figure `fig:desktop-client`).

## Follow-ups

- Rohan to answer: which subjects need a terminal first; lab PCs vs own
  laptops (and whether IT can install Docker); whether offline work is
  required; whether vim/nano are allowed in some labs.
- D0 spike when he says go.
- Consent v3 (terminal logging, local container) before any desktop pilot.

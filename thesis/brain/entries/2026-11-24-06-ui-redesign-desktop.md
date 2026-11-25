---
date: 2026-11-24
type: event
title: UI redesign part 5 of 5: desktop app matches the new look and opens the guides
thesis-chapter: 04-system-design
---

## What happened

Branch `claude/project-thread-10omt4-desktop` (on part 4). The desktop window loads the live site, so
parts 1–4 already restyle almost everything inside it. This part covers what the app draws itself:
- The offline and update pages (`desktop/app/static/`) use the same tokens and the rhythm-bar logo.
- The window background matches `--bg`.
- A new Help menu offers Student guide, Teacher guide, Keyboard shortcuts (F1) and Sandbox Labs. Each
  opens the public guide (`#/help/…`) in a separate window, so a lab session in the main window is never
  interrupted.
- The smoke test now expects the current bridge namespaces (journal, updates) and checks the Help menu.

## Why

A guide that replaced the lab window would end a recorded session mid-way; a second window can't.
Changing the static pages keeps the app looking like one product even offline.

## Evidence

- `desktop/app/e2e/smoke.mjs` under xvfb: the bridge, lock-down and new Help menu checks pass, and the guide
  window shows `#/help/student`.
- The later desktop-session check finds no key events in dev mode. This is pre-existing, not caused by this
  change: the journal uploads only after `GET /api/me` names a signed-in student, which dev mode (roll-number
  login, no cookie) never does, so its events stay on disk. The smoke test's namespace list was already out
  of date on main.
- `thesis/latex/snapshots/redesign/after/part5-*`.

## Follow-ups

- A desktop release tag (`desktop-v*`) ships the Help menu and pages; it waits for Rohan's OK.
- The dev-mode journal upload gap is worth its own fix, or a smoke test that runs in Google mode.

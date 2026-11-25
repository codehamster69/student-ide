---
date: 2026-11-24
type: event
title: UI redesign part 4 of 5: help centre renders the student and teacher guides in the app
thesis-chapter: 04-system-design
---

## What happened

Branch `claude/project-thread-10omt4-guide` (on part 3, includes #54's guide pages). `frontend/src/guide/`
loads the Markdown pages at build time and renders them as React elements (no HTML). The reader has a page
list, search, "On this page" and previous/next. Teachers get Guide in the sidebar, a Help button that opens
the page for the current screen, and guide pages in Ctrl+K. Students get a Guide tab (lazy-loaded so the
editor bundle doesn't grow) and a "How Student IDE works" link on sign-in. `#/help` is public for the
desktop Help menu and signed-out readers. Docs: `docs/guide.md`.

## Why

Rohan asked for docs and guides for both audiences. In-app guides are where people get stuck. Markdown
files in the repo stay reviewable next to the code they describe. Rendering without HTML keeps a guide file
from injecting markup. Contextual Help beats a separate manual nobody opens.

## Evidence

- `frontend/e2e/guide.mjs`: public index, search, cross-links on every page resolve, teacher Help button,
  Ctrl+K, student Guide tab.
- `record.mjs` still reports `longTasksWhileTyping: 0`.
- `thesis/latex/snapshots/redesign/after/part4-*`.

## Follow-ups

Keep guides in step with features. `docs/guide.md` says how to write a page.

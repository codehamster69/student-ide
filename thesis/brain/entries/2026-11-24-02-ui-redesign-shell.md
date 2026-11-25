---
date: 2026-11-24
type: decision
title: UI redesign part 1 of 5: design tokens, sidebar shell, Ctrl+K and a student app bar
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for a full redesign ("professional, sleek, easily navigable, with docs and guides for
students and teachers, then the desktop app"). Plan approved in the project thread as five stacked PRs:
(1) design system and app shells, (2) student screens, (3) teacher screens, (4) help centre and guides
(content in #54), (5) desktop app. This entry is part 1, branch `claude/project-thread-10omt4`.

- `frontend/src/ui/tokens.css`: cooler neutrals, refined indigo accent, `--sidebar`, 14 px base.
  `motion.ts`: shorter page/item transitions, stagger capped at 30 ms.
- New primitives: `AppShell` (sectioned sidebar, breadcrumb top bar, phone drawer), `Page`/`PageHeader`/
  `EmptyState`, `CommandPalette` (Ctrl+K / ⌘K). `ui/README.md` gained "Look" and "Page recipe".
- Teacher area (`review/ReviewApp.tsx`): top tabs → sidebar (Labs, Sandbox Labs, Subjects | In class:
  Live, Review | Workspace: Getting started, View as student); breadcrumbs from `routes.ts` `trail()`.
  Every existing URL still works.
- Student screens after sign-in (`screens/Shell.tsx`): an app bar with My labs and Learning lab.
- Logo: typing-rhythm bars ending in a caret.
- `frontend/e2e/tour.mjs`: screenshots of every main screen, used for the before/after sets.

## Why

The tool grew one feature at a time (labs, competitions, learning lab, live, review, Sandbox Labs,
attendance) and each page had its own header and back links; teachers had six tabs plus header links.
A sidebar groups them by when a teacher needs them and leaves room for Guide. Ctrl+K answers "where is
lab X" without hunting. One recipe per page makes later features consistent by default.
Alternatives: keep top tabs and only restyle (doesn't fix navigation); a full component library
(heavier bundle, fights the existing tokens). The rhythm-bar logo ties the brand to what the tool
measures instead of a generic keycap.

Recording safety: no change to `recorder.ts`/`capture.ts`/editor; the palette is never mounted on a
recording screen.

## Evidence

- `record.mjs`: 214 events, median key gap 49 ms, `longTasksWhileTyping: 0`.
- `teach.mjs`, `live.mjs` (card selector now `[data-student]`), `preview.mjs`, `compete.mjs`,
  `sitting.mjs`, `reset.mjs` pass. `learn.mjs` fails on reruns on main too (fixed student state);
  `ownership.mjs` needs Google mode.
- Screenshots: `thesis/latex/snapshots/redesign/before/` (every screen, light, from origin/main) and
  `after/part1-*`. Figure `fig:ui-redesign-2` in chapter 4.

## Follow-ups

Parts 2–5 restyle the pages themselves, add the help centre and update the desktop app.

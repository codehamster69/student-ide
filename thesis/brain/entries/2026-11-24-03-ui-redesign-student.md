---
date: 2026-11-24
type: event
title: UI redesign part 2 of 5: student screens follow the page recipe
thesis-chapter: 04-system-design
---

## What happened

Branch `claude/project-thread-10omt4-student` (on part 1). The student home (`screens/Tasks.tsx`) became a
dashboard: the lab to continue first with a progress bar and its questions as one divided list, then
competitions, Sandbox Labs, and "Learn and practice" (learning lab, warm-ups, free practice). The learning
lab, arena, Sandbox Labs shelf, saved screen, download and update screens lost their glows, uppercase
eyebrows and hover-lift motion. The workspace got an accent top border on the active file tab, a
sentence-case question label and a flatter console; on phones the task panel starts closed.

## Why

Students come to the home screen to do one thing: continue their lab. It now leads, and everything else
is secondary and quieter. The editor was deliberately left almost as it was: it is the measuring
instrument, and the first redesign already tuned it.

## Evidence

- Consent: only list styling changed; the wording is byte-identical (diff checked).
- `record.mjs`: 214 events, median key gap 49.6 ms, `longTasksWhileTyping: 0`.
- `compete`, `teach`, `anylang`, `preview`, `download`, `reset`, `screenshots` e2e pass.
- `thesis/latex/snapshots/redesign/after/part2-*` (compare with `before/`).

## Follow-ups

None beyond parts 3–5.

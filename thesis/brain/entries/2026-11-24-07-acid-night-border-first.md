---
date: 2026-11-24
type: decision
title: "Acid Night" look and border-first UI across the redesign stack
thesis-chapter: 04-system-design
---

## What happened

Rohan judged the first pass of the redesign "not cool enough" for the students who will use it, and
rejected three generic palettes because none matched the new logo. He chose "Acid Night", built from
the logo's own colours: ink (#0b0b0f), lime (#c6f432) and a pink second accent (#ff7cbb). A light theme
was added (warm off-white, ink text, a darker lime #3f6b00 for text so it keeps 4.5:1 contrast).
Page titles use Space Grotesk.

He then set a standing rule, saved as the `border-first-ui` skill: no background fills to highlight
things; borders only where an element must stand apart from its siblings; buttons are text that grow a
border (with a small lift and a lime glow for the main action) on hover or keyboard focus; selected
items use a border or left rule, never a filled pill. Fills stay only where they do a job (page base,
dialogs, the code editor, the console, charts, bars and dots).

Applied in every PR of the stack: tokens and primitives (#55), student screens plus a greeting hero on
the student home and friendlier copy (#56), teacher screens (#57), the help centre (#58), the desktop
offline and update pages and window background (#59). Consent wording is unchanged.

## Why

The students are the main users; a tool that looks like their own tools lowers the barrier to using it
for every lab. Borders instead of fills keep a dense teacher screen calm and make the one lime action on
each page easy to find.

## Evidence

- `frontend/e2e/record.mjs`: `longTasksWhileTyping: 0`, median key gap 49 ms, so the restyle adds no
  work while a student types. Hover motion is on chrome only, never in the editor.
- `live.mjs` and `guide.mjs` pass.
- `thesis/latex/snapshots/redesign/acid-night/` (dark and light, student, teacher, review, desktop).

## Follow-ups

- The rebrand to Scribelab (#60) sits on top and keeps these tokens.

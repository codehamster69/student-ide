---
date: 2026-11-24
type: event
title: UI redesign part 3 of 5: teacher screens (labs, lab editor, live, review, sandbox, attendance)
thesis-chapter: 04-system-design
---

## What happened

Branch `claude/project-thread-10omt4-teacher` (on part 2). Every teacher page now follows the page recipe.
- Labs: a filterable table (search, status chips with counts; status, kind, subject, questions, assigned,
  activity, last edit) with New lab as the primary action.
- Lab editor: a header with an editable title, a facts row and the Draft/Open/Closed switch. Questions are one
  divided list with Progress below. The sidebar holds Basics, Roster, Class groups and attendance, and Sharing.
- Getting started: one first-run checklist ("2 of 6 done").
- Review: a joined stat row and scannable lists; the session page reads summary banner, timeline, replay, moments.
- Live: a calmer student-card grid with no layout animation. Sandbox, subjects, people, attendance,
  leaderboard and similar submissions got the same treatment. "← Back" rows gave way to breadcrumbs.

## Why

Teachers scan; tables and divided lists show more labs per screen than floating cards and make status
comparable at a glance. The review page keeps its evidence language and channel colours unchanged: the
redesign is presentation only, so nothing the thesis evaluates moved.

## Evidence

- `teach`, `live`, `compete`, `sources`, `leetcode`, `anylang`, `review-screenshots` e2e pass.
- `questions.mjs` times out at the same step on origin/main (pre-existing). `handin` needs Google mode.
  `attendance` needs a fresh Roll Call setup. The Sandbox e2e scripts need Docker and the preview service.
- `thesis/latex/snapshots/redesign/after/part3-*`.

## Follow-ups

- On a 390 px phone the session timeline page still scrolls about 29 px sideways.
- Breadcrumbs say "Lab" rather than the lab's name. A later pass could let pages name the last crumb.

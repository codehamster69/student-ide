---
date: 2026-10-27
type: decision
title: Teachers see only their own (and shared) labs; admins see everything; Review starts from lab sessions
thesis-chapter: 04-system-design
---

## What happened

Rohan asked that teachers only see the sessions they created ("But admin can
see it all"), and that the Review tab be organised by lab session, since labs
are timed class meetings. Until now any teacher account saw every lab,
competition, recording, review timeline and live view (an open follow-up from
the deployment PR #14).

Now:

- `labs.owner_email` records the creating teacher (labs and competitions);
  `lab_teachers` holds co-teachers. A teacher sees and manages only labs they
  own or were added to, and only sessions, review timelines, replays, live
  views and competition boards from those labs. Lists filter; direct links get
  403 with a header the browser uses to show the message instead of signing
  the teacher out.
- Admins ($STUDENTIDE_ADMINS or the People screen), the admin token and dev
  mode see everything. Labs from before this change have no owner and are
  admin-only until an admin hands them over in the lab's Teachers panel.
  Sessions outside any lab (practice tasks) are admin-only.
- Sharing: the owner (or an admin) adds co-teacher addresses; co-teachers have
  the owner's rights except changing the sharing. Student addresses and
  addresses outside the college are refused. Only admins change an owner.
- Review tab: first screen lists lab sessions, one row per lab per day (local
  time), with time span, students, sessions and how many students have a
  moment to discuss. A row opens that class's sessions sorted student by
  student. "Every session in one list" keeps the old view.

## Why

- Ownership by lab, not by student: a student is taught by several teachers,
  and a teacher's view should follow the classes they run.
- The baseline is unchanged: it stays the student's, built from all their lab
  sessions regardless of whose lab they were in. Otherwise the same session
  would get different evidence depending on who looks, and new teachers would
  have no baseline for their students. Teachers see only baseline counts and
  ids of sessions outside their labs, never the sessions themselves.
- Unowned old labs go to admins rather than to "everyone", so nothing becomes
  more visible than before for non-admin teachers after the migration.
- Co-teacher sharing was cheap (one table, one endpoint, one panel) and covers
  shared lab courses and TAs.
- Lab session = lab + calendar day because a lab is usually one class meeting
  but may be reopened on another day; scheduled time windows remain a
  possible follow-up.

## Evidence

- Backend tests `backend/tests/test_ownership.py` (scoping of every teacher
  endpoint, sharing rules, unowned labs, competitions, review by lab); full
  suite passes.
- Browser test `frontend/e2e/ownership.mjs` against a Google-mode server with a
  fake token check; screenshots `thesis/latex/snapshots/ownership/` (light and
  dark); thesis subsection `sec:ownership` in 04-system-design.

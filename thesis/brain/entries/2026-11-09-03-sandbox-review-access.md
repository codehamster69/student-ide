---
date: 2026-11-09
type: issue
title: Sandbox Lab sessions now show in Review for subject teachers (were admin-only, and missing from the lab list)
thesis-chapter: 04-system-design
---

## What happened

Teachers who are not admins could open one Sandbox Lab session only by its link. Their Review
lists did not show those sessions: the lab list, the session list and the student list all
filtered by `db.teacher_lab_ids`, which knows only web labs.

The lab list left out Sandbox Labs for admins too, because it took lab titles from the web `labs`
table only. The fix:

- `auth.lab_ids` adds the Sandbox Labs of the subjects the teacher owns, teaches or assists
  (`db.sandbox_labs(email)`).
- `/api/review/labs` lists Sandbox Labs with kind `sandbox` and their subject.
- The lab list marks them with a box icon.

The attendance per-lab summary uses the same ids, so subject teachers now see attendance for their
Sandbox Labs too.

## Why

Sandbox Labs belong to subjects, not to a lab owner. Access to them should therefore follow the
subject's people, the same way the session page already did (`db.sandbox_lab_teacher`).

## Evidence

`backend/tests/test_sandbox.py::test_subject_teachers_review_their_sandbox_sessions` covers:

- a subject teacher and an admin each see the lab, its session and the student
- a teacher of another subject sees none of them

## Follow-ups

None.

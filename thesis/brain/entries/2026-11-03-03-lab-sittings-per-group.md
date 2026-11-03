---
date: 2026-11-03
type: decision
title: Opening a lab asks which class group is performing; each opening is a sitting marked for its groups alone
thesis-chapter: 04-system-design
---

## What happened

Rohan asked whether one lab could run for different groups (G1 on Monday, G2 on
Thursday). With the first design, closing the lab on Monday would have marked
every G2 student absent. A first fix skipped groups with no activity that day;
Rohan then asked for a different way: **the teacher decides which group is
performing before opening the lab**.

Built on student-ide #33 (not merged yet; students are working on the live site):

- **Sittings.** New table `lab_runs(id, lab_id, class_ids, opened_at, opened_by,
  closed_at)`. Opening a lab that has class groups shows *Which group is
  performing?* (tick one or more). `PATCH /api/teach/labs/<id>` takes
  `performing: [class ids]` (400 if one is not attached).
- **Only that group works.** While a sitting with chosen groups is open, a
  student who is on some attached roster but on none of the sitting's groups
  does not see the lab (`labs_for_student`). Students on no attached roster
  are not restricted (the roster prefix can be wrong; they still show up as
  "not on any roster").
- **Next group / close.** The green "Open for …" bar has *Next group*: it ends
  the sitting, sends that day's attendance for its groups only (minus groups
  already sent that day), and opens a sitting for the next group. Closing ends
  the last sitting the same way. A lab closed with no sitting keeps the old
  behaviour (every day not sent).
- **Idle groups never sent.** Kept from the first fix: a group with no student
  activity that day and no override is skipped, so a mistaken sitting cannot
  mark a whole group absent.
- The attendance page preview for a day lists the sittings of that day and
  only their groups.

## Why

Attendance is per class group per day, and lab groups of a section rotate
through the same lab. Asking at the moment of opening matches how a lab
assistant thinks ("G2 is in now") and also keeps the wrong group out of the
lab, which the activity heuristic alone could not.

## Evidence

- `backend/tests/test_attendance.py::test_teacher_picks_the_performing_group_when_opening`
  (sittings `[[], [G1], [G2]]`, G2 cannot see the lab during G1's sitting,
  Monday marks G1 only) and `test_one_lab_for_groups_on_different_days`.
- e2e `frontend/e2e/attendance.mjs` opens the lab through the picker
  (screenshots `03a-which-group`, `03-lab-class-groups`, light and dark).

## Thesis

`sec:attendance`, new paragraph *Sittings* in chapter 4.

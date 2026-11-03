---
date: 2026-11-03
type: decision
title: Labs mark attendance in Roll Call; present = effective participation, in each student's own class group
thesis-chapter: 04-system-design
---

## What happened

Rohan asked (2026-11-03) that creating a lab offer to pick or create a class
from the attendance site (Roll Call, codehamsters/attendance), that students
who effectively took part be marked present at the end, that a lab can have
several class groups with each student marked in their own group, plus a
subjects view on both sites, easy onboarding for new faculty and a systematic
page routing scheme.

Built across two PRs:

- **Roll Call** (codehamsters/attendance): saved subjects (synced like classes),
  Subjects pages (`/subjects`, `/subjects/<slug>`, per-class and per-student
  percentages), a class page (`/classes/<id>`), an integration API `/api/v1`
  (Bearer sync key: list/create classes and subjects, `PUT /api/v1/sessions/<uuid>`
  to record a session), "Connect Student IDE" in Settings, a Getting started
  checklist (`/start`), and one routing table (`lib/routes.ts`) with the old
  paths redirected.
- **Student IDE**: `backend/studentide/attendance.py` (connection, lab class
  groups, rule, preview, send, send on close), lab sidebar card and
  `#/teach/labs/<id>/attendance` page, `#/teach/subjects`, `#/teach/setup`, and
  one hash routing table (`frontend/src/routes.ts`) with old links rewritten.

## Why

- **Sync key, not accounts.** Roll Call is local-first with a per-faculty sync
  key and no sign-in; adding accounts there was out of scope. The key stays on
  the Student IDE server (never sent to a browser), one per teacher, and a
  class group is always written through the key of the teacher who attached it,
  so co-teachers' groups land in the right Roll Call.
- **Effective participation = 10 active minutes and 40 typed characters**
  (proposed default, per-lab configurable, optional "must run or check").
  Active minutes (distinct minutes with an edit, Run or Check) resist a student
  who opens the lab and leaves; typed characters exclude pasting a whole answer.
  Learning-lab practice and staff previews never count. Only edit/run/check
  records are read, so it survives raw-key retention, and it never reads the
  detector: a flag must not change attendance (flags lead only to a conversation).
- **One Roll Call session per class group and lab day**, with a uuid5 of
  lab+class+day, so resending is idempotent and each student is marked in their
  own group's register. Rejected: one session per lab (students from several
  groups would sit in one register).
- **Send at close** (auto, can be turned off) plus a manual preview/override
  page, because teachers want to correct edge cases (a student on a shared
  machine, a late joiner) before it reaches the register. Failed sends are
  stored and retried; closing the lab never fails because of Roll Call.

## Evidence

- `backend/tests/test_attendance.py` (6 tests: rule, overrides, own-group
  marking, idempotent resend, close-time send, rule config, learn sessions
  excluded, failed send, per-teacher keys); full backend suite passes.
- `frontend/e2e/attendance.mjs` drives both apps together (Roll Call on a local
  Postgres): connect, create and attach groups, five students, preview,
  override, send, Roll Call sessions/subjects/report, old links.
- Screenshots: `thesis/latex/snapshots/attendance/`; thesis `sec:attendance`.

## Follow-ups

- Rohan to confirm the default thresholds (10 min, 40 chars) after a real lab.
- On the live site: set `STUDENTIDE_ATTENDANCE_URL` (defaults to
  https://attendance.hokora.xyz) and `STUDENTIDE_PUBLIC_URL`; Roll Call must be
  redeployed first so `/api/v1` exists.
- Roll Call rosters must use the college-address prefix (e.g. `UG23CS`, 3 digits).

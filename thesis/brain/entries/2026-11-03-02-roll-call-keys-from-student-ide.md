---
date: 2026-11-03
type: decision
title: Student IDE makes the Roll Call keys; teachers sign in with one press, students see only their own marks
thesis-chapter: 04-system-design
---

## What happened

After the attendance integration (entry 2026-11-03-01), Rohan asked what happens
if a student opens the attendance site, and then asked that Student IDE
generate a unique key per teacher (each teacher sees only their own data), that
teachers sign in to Roll Call with that key or straight from Student IDE, and
that students get a view-only Roll Call based on their own keys.

Built on the same two PRs (student-ide #33, attendance #6):

- **Teacher keys.** *Set up Roll Call for me* (Getting started) makes a 40-char
  key = a new Roll Call workspace; pasting an existing key still works
  (`attendance_links.issued` tells them apart). *Open Roll Call* (Getting
  started, lab card, header) asks Roll Call `POST /api/v1/login-codes` for a
  one-time link `/login#code=…` (2 minutes, single use, the key stored AES-GCM
  encrypted with the code, code only as a hash); the browser lands signed in.
  *Show key* lets the owner sign in by hand at `/login`.
- **Student keys.** *My attendance* in the student app (only when a lab they are
  in has class groups) makes `st_…` per student, grants it per teacher whose
  attached groups list the student (`PUT /api/v1/viewers`, sha256 only), then a
  one-time link to `/me`: finished sessions they are marked in, by subject,
  read-only. A student key never opens a workspace (`/api/sync`, `/api/v1`
  refuse it) and a browser holding one is sent to `/me` from any faculty page.
- **Shared computers.** Roll Call Settings → Sign out forgets the key and local
  records; signing in where another person's records sit asks "move them in" or
  "leave them, start clean", so registers never mix.

## Why

Roll Call has no accounts, only keys, and the first version asked teachers to
copy a key between sites, which is the step new faculty get wrong. Generating it
server-side keeps onboarding to one press and keeps the key off students'
screens. Students needed their own view without any access to a register, so a
separate key type with read access to one student id, granted by the teacher's
workspace, is the smallest change that keeps Roll Call account-free.

## Results

- Backend: 333 tests pass (2 new: keys made per teacher and reused, student
  view granted through both teachers, only for yourself, none for a student in
  no attached group).
- e2e `frontend/e2e/attendance.mjs` (light and dark) across both apps: set up,
  attach, send, Open Roll Call signs in with no pasting, a used link is refused,
  a shared browser asks before mixing records, a student opens My attendance
  and sees only their own mark, their key is refused by `/api/sync`.
- Screenshots `thesis/latex/snapshots/attendance/` (01b key, 15 shared device,
  16 student labs, 17 My attendance); thesis `sec:attendance` paragraph and
  `fig:my-attendance`.

## Open points

- A student key is long-lived (no expiry); a "new key" button would revoke a leaked one.
- Teachers who already used Roll Call before must choose "I already use Roll
  Call", or their first Open Roll Call starts an empty register (Roll Call then
  offers to move the device's records in).

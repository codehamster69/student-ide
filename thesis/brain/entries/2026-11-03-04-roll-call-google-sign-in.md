---
date: 2026-11-03
type: decision
title: Roll Call gets faculty Google sign-in with the Student IDE client; one register per teacher across both apps
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for a Google login for teachers on the attendance site, with the
same OAuth client as Student IDE, so faculty who run no labs can still keep
their ordinary class registers there.

Built in codehamsters/attendance (new PR on `claude/project-thread-z8rrqh`) and
student-ide #33:

- **Sign in with Google** on Roll Call `/login`. Roll Call checks the ID token
  with Google (audience = the Student IDE client, verified address on the
  college domain). Student-shaped addresses (`ug23cs001@…`, the Student IDE rule)
  are sent to My attendance. The first sign-in makes the teacher's register; any
  later sign-in, on any device, opens the same one. Roll Call stays local-first:
  the browser still holds the key, which Roll Call now also keeps per address,
  encrypted with `ROLLCALL_SECRET` (table `teacher_accounts`).
- **One register per teacher.** With a shared secret (`LINK_SECRET` /
  `STUDENTIDE_ROLLCALL_LINK_SECRET`), Student IDE calls `POST /api/link/teacher`:
  setting up adopts a register the teacher already made in Roll Call; a key made
  in Student IDE is recorded so Google sign-in opens it; existing teachers are
  linked once at start. *Make a new key* now also sends the new key so the
  Google account follows the rotated register.
- **Admins in Roll Call.** `ADMINS` (same list as `STUDENTIDE_ADMINS`) get a
  12-hour signed pass and a *Teachers' registers* page (`/admin`, from Settings):
  full access, the existing "Admin access" banner, opens logged in `admin_opens`.

## Why

Keys made by Student IDE only reached teachers who use Student IDE. Google
sign-in gives every faculty member a register without a key to copy, and the
link keeps the two apps from splitting one teacher's records across two
registers. Linking needs a secret because the link call returns a teacher's key.

## Evidence

- `backend/tests/test_attendance.py::test_one_register_per_teacher_with_roll_calls_google_sign_in`
  (no secret = no linking; adopt Google-first register; link Student-IDE-first
  key; rotation moves the account; Roll Call down = still works).
- Roll Call API checked end to end on local Postgres with a stand-in tokeninfo
  (wrong audience, other domain, student address, admin pass, rotate with and
  without `new_key`), and a browser run with a stand-in Google button:
  screenshots `rc-google-light-01-login`, `rc-google-light-04-admin`.

## Open

Rohan must add the Roll Call address as an authorised JavaScript origin on the
OAuth client and set the Vercel env vars (`GOOGLE_CLIENT_ID`, `ROLLCALL_SECRET`,
`ADMINS`, `LINK_SECRET`) plus `STUDENTIDE_ROLLCALL_LINK_SECRET` on the VM.

## Thesis

`sec:attendance`, paragraph *Faculty without labs*.

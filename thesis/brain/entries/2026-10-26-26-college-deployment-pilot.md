---
date: 2026-10-26
type: decision
title: Pilot deployment at IIIT Surat with college Google sign-in, raw-key purge and an isolated runner
thesis-chapter: 04-system-design
---

## What happened

Rohan wants to deploy Student IDE at IIIT Surat only ("a google login with
@iiitsurat.ac.in emails, I have the college permission") and chose an
Indian cloud VM (Mumbai/Hyderabad region) for hosting. He gave the student
address format: `<ug|pg><year><branch><roll>@iiitsurat.ac.in`, e.g. his own
PG25CS07. Framed as a **pilot**: real study data still needs ethics approval.

Built (PR "Deploy Student IDE at IIIT Surat"):

- `backend/studentide/auth.py`: Google mode when `STUDENTIDE_GOOGLE_CLIENT_ID`
  is set. ID token checked with google-auth (signature, audience, expiry),
  `email_verified`, and both the `hd` claim and the address must be the college
  domain. HttpOnly Secure SameSite=Lax cookie; only its SHA-256 is stored.
  Roles from the address: the pattern is a student, any other college address
  a teacher; `STUDENTIDE_ADMINS` are admins and can override roles on a new
  People page (`#/teach/people`). Student endpoints act only for the signed-in
  student; teacher endpoints need a teacher account. Dev mode (roll number +
  admin token) is unchanged for local work and the test suite.
- `backend/studentide/retention.py`: raw `key` events deleted once due
  (baseline sessions when the 4 baseline weeks end; any session after 28 days),
  after storing the detector's window features at every frozen window length.
  `Reviewer.windows` reads the stored windows for purged sessions.
  `--erase-student` removes everything about one student.
- `backend/studentide/runner_service.py`: student code runs in its own container
  (`STUDENTIDE_RUNNER_URL`), read-only, no capabilities, no internet, no data.
- `backend/studentide/backup.py`: nightly SQLite online backup, integrity
  check, gzip, 0600, 14 days kept; `--restore`.
- `Dockerfile`, `deploy/` (Compose: caddy, app, runner, backup; Caddyfile with
  HSTS and security headers; `.env.example`), `docs/deploy.md`.

## Why

- **Student ID = the whole local part (PG25CS07), not the roll digits.** The
  digits repeat across programs, years and branches. The coordinator relayed
  "use the roll number as the student ID"; the full code is what the college
  calls the roll number and what the login placeholder already showed.
- **Branch part matches any 2-4 letters by default.** A fixed list
  (`STUDENTIDE_BRANCH_CODES`) is possible, but with a list a student of an
  unlisted branch would fall through to *teacher* and see every recording.
  Failing towards "student" is the safe direction.
- **Server-side cookie sessions, not JWTs in localStorage.** Can be revoked
  (demoting a teacher signs them out at once), and script injection cannot read
  them. No client secret is needed with the GIS popup flow.
- **Purge stores windows, not baselines.** A baseline is refitted whenever the
  class population (ICC weights, key-pair vocabulary, prior) changes, so
  storing only per-student baselines would freeze them. Window features are
  already aggregates (30-90 s), so keeping them is still "summary statistics
  only". Test: on the seeded demo class, scores, alarms and episodes are
  identical before and after purging.
- **Separate runner container.** In one container a student program could read
  the database file (same Unix user). Separating it was simpler and stronger
  than setuid tricks inside one container.
- **SQLite kept.** One VM, about 80 students; WAL mode is enough. The online
  backup API gives consistent copies without stopping the app.
- **Caddy** for automatic Let's Encrypt certificates; host-agnostic Compose.

## Evidence

- Tests: `tests/test_auth.py`, `test_retention.py`, `test_runner_service.py`,
  `test_backup.py`; full suite 117 passed before the last additions.
- Stack brought up locally with Compose (image without the apt toolchains,
  which the sandbox's network blocks): HTTPS with HSTS and headers, HTTP→HTTPS
  redirect, student limited to themselves (403 on other students and teacher
  APIs), a student program in the runner saw no database, no secrets and no
  internet; backup written as 0600 and restored over newer data.
- Screenshots: `thesis/latex/snapshots/deploy/`. Figure:
  `thesis/latex/flowcharts/deployment.tex`. Text: chapter 4, sections
  "Privacy and data lifecycle" (with the DPDP table) and "Deployment at IIIT Surat".

## Follow-ups

- Rohan: create the Google OAuth client (docs/deploy.md step 3), the VM and DNS.
- Edit events keep per-change timestamps; coarsen them after the same deadline
  if the ethics committee counts them as keystroke data.
- Per-teacher lab ownership (today every teacher sees every lab and student).
- Off-VM backups: provider disk snapshots in the same India region.

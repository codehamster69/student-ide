---
date: 2026-11-25
type: decision
title: Desktop updates are mandatory: newest release is the minimum, installed at a safe moment, never mid-lab
thesis-chapter: 04-system-design
---

## What happened

Rohan (2026-11-25): "when there is an update it's necessary to update". The
server now makes the newest `desktop-v*` release the minimum desktop version
(`VersionPolicy` in `backend/studentide/desktop.py`, env
`STUDENTIDE_DESKTOP_REQUIRE_LATEST`, default on). An outdated app (User-Agent
`StudentIDE-Desktop/<v>`) can finish open work but gets 426
`desktop_update_required` on `POST /api/sessions` and competition join. The
app (`desktop/app/src/main/modules/updates.ts`) checks every 15 minutes,
downloads in the background and shows the blocking update page at the first
safe moment: no lab/sitting/competition open (web app `updates.setBusy`, open
journal sessions), journal uploaded, and the person idle 2 minutes or the
window in the background, or on "Update now" / a 426. It reopens on the page
it was on. macOS (unsigned) gets its own download-and-swap of the app bundle
(`modules/macupdate.ts`, SHA-256 checked against GitHub's asset digest);
portable .exe, .deb and Macs that can't replace the bundle get the blocking
page with a download link. Docs: docs/desktop.md (Updates), docs/deploy.md.

## Why

Same capture code for every desktop session: a timing difference between
students must not come from app versions (fairness, RQ3 device analysis).
Restarting mid-lab would interrupt a student and risk the record, so the gate
waits for open work, and the server stops new work instead of cutting
uploads. A grace period was not added because Rohan asked for no old versions;
GitHub being unreachable falls back to the fixed minimum so students are never
locked out by an outage. Squirrel.Mac refuses unsigned apps, and paid signing
is deferred (2026-11-08), so the Mac swaps its own bundle.

## Evidence

`backend/tests/test_desktop_updates.py` (mandatory gate, open work finishes,
switch off, GitHub down); desktop smoke section 3 (`desktop/app/e2e/smoke.mjs`):
an open lab blocks the update, closing it shows the update page, an outdated
app starts on the update page. The Mac swap script was exercised with stubbed
`hdiutil`/`ditto` on Linux only.

## Follow-ups

Real runs on Windows and a Mac with the next tag (v0.3.1 then v0.3.2, so an
installed app actually updates). Apps before this release still use the old
logic for that one hop (they show the gate at start, and on Mac only a link).

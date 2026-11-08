---
date: 2026-11-08
type: decision
title: Desktop auto-update through the server from GitHub Releases; builds stay unsigned
thesis-chapter: 12-conclusion
---

## What happened

Sandbox Labs P2 (audit of 2026-11-08). Rohan: "go with your picks". A `desktop-vX.Y.Z` tag makes CI
(`.github/workflows/desktop.yml`, job `release`) build every OS and publish a GitHub release with the
installers and electron-builder's feeds (`latest.yml`, `latest-linux.yml`). The app's updater
(`desktop/app/src/main/modules/updates.ts`, electron-updater, generic provider) reads
`<server>/api/desktop/updates/`, served by `backend/studentide/desktop_updates.py`. New bridge namespace
`updates` (status, check, restart; event `updates.status`); the web app shows a quiet "ready, installs
when you close the app" note outside editor sessions. The min-version gate now updates in place.

## Why

- The repository is private: electron-updater's GitHub provider would need a token inside the app,
  which anyone could extract. The server holds a read-only token and only answers with a 302 to GitHub's
  short-lived signed URL, so installers (about 150 MB) never cost VM egress and the feed follows
  whichever server the app is locked to (dev, pilot).
- Never restart by itself: a lab must not be interrupted; install on quit, or "Restart now".
- Signing: no certificates bought yet (Rohan has not chosen). Unsigned Windows NSIS updates work;
  Squirrel.Mac refuses unsigned apps, so macOS, the portable exe and the .deb are "manual" (version +
  download link). What signing needs is in docs/desktop-installer.md (Signing).
- Alternatives: a separate public releases repo (needs Rohan to create and manage a repo), serving
  files from the VM (egress cost, storage), or a cloud bucket (another account and credentials).

## Evidence

- `backend/tests/test_desktop_updates.py` (feed copy, signed redirects, cache, public repo, off).
- Packaged AppImage (`npm run package -- --linux AppImage`) writes `latest-linux.yml`; the packaged app,
  pointed at a local server with a fake release of 0.1.1, fetched the feed through the server, found the
  newer version and downloaded it through the redirect (2026-11-08, cloud session).

## Follow-ups

- Set `STUDENTIDE_UPDATES_REPO` and `STUDENTIDE_UPDATES_TOKEN` on the VM, then tag `desktop-v0.2.0`.
- Buy certificates when decided; then macOS can move to automatic updates (needs a zip target).
- A full update on real Windows is part of the D0 run.

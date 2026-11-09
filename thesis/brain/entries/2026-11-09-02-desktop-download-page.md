---
date: 2026-11-09
type: decision
title: Students download the desktop app from a public #/download page that picks their installer
thesis-chapter: 04-system-design
---

## What happened

Rohan asked where students get the desktop app. The only link was the "Get the app" button on the
web home's Sandbox Labs banner. It showed only after a student had a sandbox lab, and it always
served the Windows installer. This change adds:

- a public page `#/download` (`frontend/src/screens/Download.tsx`, helpers in `frontend/src/download.ts`)
- a server listing at `GET /api/desktop/release` (`backend/studentide/desktop_updates.py`)
- a link on the login page

The banner button now downloads the installer for the student's computer.

## Why

Teachers need a link to share with a class before the first lab. Mac and Linux students must not
get a Windows .exe. The installers stay on the private repository's GitHub releases, and the server
hands out short-lived links, so students never need GitHub access. Mac CPU detection is
best-effort: Safari reports Intel on every Mac. The page therefore defaults to Apple silicon and
always lists both Mac builds.

## Evidence

- `backend/tests/test_desktop_updates.py::test_release_lists_installers_for_the_download_page`
- `frontend/e2e/download.mjs` (Windows, Mac and phone visitors, no release, login link)

## Follow-ups

None.

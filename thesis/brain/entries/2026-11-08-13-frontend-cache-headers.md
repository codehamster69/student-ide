---
date: 2026-11-08
type: issue
title: The desktop app kept an old web page after a deploy, because index.html had no Cache-Control
thesis-chapter: 04-system-design
---

## What happened

After the deploy that added desktop browser sign-in, the Mac app still showed the
old page (bundle `index-D9LirWE_.js`) and the plain Google button. That button
opens Google's popup in the system browser, so sign-in never came back to the app.
The server sent `index.html` with only an ETag and Last-Modified, so Chromium
reused its cached copy (heuristic freshness) without asking the server. Students'
browsers would do the same after each release.

Fix: `FrontendFiles` in `backend/studentide/app.py` sends `no-cache` for
index.html and other unhashed files, and `public, max-age=31536000, immutable`
for the hashed `assets/` files.

## Why

Vite hashes every asset name, so only index.html needs revalidating, and that
costs one 304 per load. The alternative, the app bypassing its cache on every
load, would fix only the desktop app and not browsers.

## Evidence

Checked over CDP in the running app: `window.studentDesktop` was present but the
page script was the old hash. After a cache clear, the new bundle loaded and showed
"Sign in with your browser". Test: `backend/tests/test_frontend_cache.py`.

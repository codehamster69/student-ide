---
date: 2026-11-08
type: decision
title: Desktop app shell (Sandbox Labs workstream 1): Electron window on the live web app, bridge contract, browser sign-in
thesis-chapter: 12-conclusion (sec:desktop-client); system design
---

## What happened

Rohan asked for the Sandbox Labs desktop app to "have it all": every web feature plus the
new local labs, built in four parallel threads. This thread built the shell and the contract
the other three plug into (PR #37):

- `desktop/app/`: Electron app. Sandboxed renderer, context isolation, no Node; navigation
  locked to the server origin (other links go to the system browser); camera, microphone,
  screen, location permissions always refused; offline and update pages; portable mode;
  a hashed per-install device id.
- `window.studentDesktop` bridge with namespaces `app`, `auth` (shell), `engine`
  (installer thread), `sandbox`/`terminal` (sandbox thread). Types in
  `desktop/app/src/shared/`, shared with the frontend (`frontend/src/desktop.ts`). Contract
  in `docs/desktop.md`.
- `backend/studentide/desktop.py`: `/api/desktop/config` (minimum app version) and a
  browser sign-in handoff (RFC 8252 loopback + PKCE): `#/desktop/signin` in the system
  browser grants a one-time code bound to the app's challenge; the app trades it with its
  verifier for the normal session cookie.
- Web app: "Sign in with your browser" inside the app; every session records
  `client_meta.client` (`web`, or `desktop` with app version, platform, Chromium, device id).

## Why

**The window loads the server's web app instead of a bundled copy** (the plan said
"bundles the frontend build"). Reasons: every existing feature works in the app the day it
ships on the server; the frontend and API cannot drift apart during a pilot that redeploys
often; and keystroke timing is produced by the very same `recorder.ts` in the same Chromium
as the web baseline, which is the measurement-consistency argument for Electron in the first
place. The cost is that the bridge is exposed to code the server serves; it is limited to the
server origin's top-level page and checked on every call. Bundling stays possible later
(same contract) if offline start is ever wanted; online is required anyway (plan 4.3).

**Browser sign-in, not Google inside the window**: Google refuses OAuth in embedded browsers,
and a loopback redirect needs no new OAuth client, no custom URL scheme (portable apps can't
register one) and reuses the existing domain checks. Codes last 2 minutes, work once and only
with the verifier.

**Client in `client_meta`, not a schema bump**: it is session metadata, not an event payload;
schema v2 (terminal events) belongs to the sandbox thread.

## Evidence

- `backend/tests/test_desktop.py` (handoff, one-use codes, wrong verifier, dev mode).
- `desktop/app/e2e/smoke.mjs`: drives the built app with Playwright against a dev-mode and a
  fake-Google server; checks bridge, lock-down, a desktop session with key events, and the
  full browser sign-in. Screenshots in `thesis/latex/snapshots/desktop-*.png`.

## Follow-ups

- Plan 4.3/4.4 pieces still open in the shell: per-session journal with 5-minute reconnect
  buffer, signed hash-chained batches, auto-update (D2).
- Timing parity browser vs Electron (D0) is still to be measured on a lab PC; the smoke test
  only shows key events are recorded.
- The review timeline could show "desktop" / "new device" as context from `client_meta.client`.

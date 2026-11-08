---
date: 2026-11-08
type: issue
title: First real macOS install of the desktop app found three Mac-only packaging bugs
thesis-chapter: 04-system-design
---

## What happened

The arm64 dmg built by CI for PR #38 (head 7c9e02a) was installed on an Apple
Silicon Mac (macOS 26.6) as an ordinary user, the first non-scripted Mac run.

1. The app was killed at launch: `SIGKILL (Code Signature Invalid)` in
   `electron::fuses::IsRunAsNodeEnabled()`. electron-builder flips the fuses in the
   Electron Framework binary, and the unsigned CI build never re-signs it.
   arm64 macOS refuses to run code whose ad-hoc signature no longer matches.
   Fix: `electronFuses.resetAdHocDarwinSignature: true`. Checked by hand: re-signing
   only the framework ad hoc makes the same build start.
2. The bundled Lima 1.0.7 refused the VM template: `field probe[0].script must
   start with a '#!' line`. The scripted tests faked `limactl`, so they never saw
   this. Fix: `#!/bin/bash` on every provision and probe script.
3. Fedora 41 is end-of-life. download.fedoraproject.org sent the Mac to a mirror
   running at about 80 KB/s for a 472 MB image. The permanent archive is now listed
   first, with the mirror network as fallback. Both are pinned to the same digest.

## Why

The scripted tests check the flow logic, not the real tools. A real run is the only
thing that catches signing and tool-version contract changes, so CI now starts the
packaged Mac app for 15 s and runs `limactl validate` on the shipped template.
Unit tests also assert both fixes so they cannot silently regress.

## Evidence

Crash report `studentide-2026-11-08-150234.ips` (termination namespace CODESIGNING,
"Invalid Page"); `limactl start` output; `desktop/installer/src/test/packaging.test.ts`.

## Follow-ups

- Lima's downloader does not resume, and a stalled mirror means a long first setup
  on lab Wi-Fi. Consider shipping or side-loading the Fedora image, or moving to a
  supported Fedora release.
- Developer ID signing and notarization stay open: a browser-downloaded dmg is
  still quarantined by Gatekeeper.

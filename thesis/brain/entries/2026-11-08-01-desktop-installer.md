---
date: 2026-11-08
type: result
title: One-click desktop installer sets up its own container engine on Windows, macOS and Linux
thesis-chapter: 12-desktop-client
---

## What happened

Rohan asked (2026-10-30, again 2026-11-08) for an installer that installs the
dependencies on the student's PC instead of listing prerequisites. Built as
`desktop/installer/` (`@studentide/installer`), wired into the desktop app's
`engine.*` module, with electron-builder packaging and a CI workflow
(`.github/workflows/desktop.yml`). Docs: `docs/desktop-installer.md`.

- Windows: checks virtualization, turns on WSL2 through one UAC prompt only
  when it is off (DISM fallback for old inbox WSL), resumes after the reboot
  via RunOnce, imports our own Alpine + rootless Podman WSL distro.
- macOS: bundled Lima 1.0.7 starts a Fedora VM (vz) with rootless Podman, no
  host folders mounted, no admin.
- Linux: existing Podman, else the distro package via one pkexec prompt, else
  static Podman 5.3.1 in the app's data folder (no admin).
- Then pulls lab images, runs the setup check, saves `engine.json`.
- Lab rooms: `prepare-lab-pc.ps1` lets IT do the one admin step for a room.

## Why

- Plan section 3.6 (Podman + own VM, not Docker Desktop): Podman and Lima are
  Apache-2.0 and can be shipped; Docker Desktop cannot be redistributed and
  asks students to accept its licence. Rootless everywhere: the sandbox never
  runs as root on the host.
- Idempotent steps instead of a saved state machine: setup is simply run
  again after a reboot or failure and skips what is done. Less to go wrong.
- The engine's own isolation matters for the thesis's "no extra
  surveillance" stance in reverse: the sandbox must not see the student's
  files, so the WSL distro disables drive automount and the VM mounts nothing.
- Plain-English errors with codes, because the failure cases (BIOS
  virtualization, no admin) need a person to act and must say who and how.
- Fallback to an already-installed Docker/Podman only when our engine is
  blocked by admin/BIOS, so the default stays one controlled engine.

## Evidence

- 21 unit tests on scripted Windows, macOS and Linux machines (every stop
  reason, reruns, fallbacks, idempotent imports) pass.
- Real run in this Linux container as an ordinary user without Podman or
  sudo: static route set up Podman 5.3.1, pulled an image, ran the check
  ("Ready: podman 5.3.1"). With a subuid range but no `newuidmap`, it stops
  with NEEDS_ADMIN asking for `uidmap`, as designed.
- WSL rootfs built from `assets/wsl/Containerfile`: 34 MB compressed (plan
  estimated ~150 MB); inside it, rootless Podman pulled and ran an Alpine
  container and created/removed a volume.
- Linux AppImage and deb packaged locally with fuses applied.

## Follow-ups

- Real Windows and macOS runs on a lab PC and a Mac (D0 spike), with timings.
- Code signing (Windows) and notarization (macOS) need certificates as secrets.
- CPU/memory limits under rootless Podman without systemd (WSL distro, static
  route) may not apply; decide whether the distro should run systemd.
- Swap the built-in check for desktop/sandbox's `setupCheck` when it lands.

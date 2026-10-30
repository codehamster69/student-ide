---
date: 2026-10-30
type: decision
title: The Sandbox Labs installer installs its own container engine; no prerequisites
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for an installer that installs the dependencies instead of
requiring Docker as a prerequisite. The plan gains section 3.6: one installer
per OS that sets up a private engine for Student IDE. Windows: turn on WSL2
if needed and import our own small WSL distro with Podman. macOS: a small
Lima VM (Apple Virtualization framework) with Podman, no admin. Linux:
rootless Podman from packages or static binaries in the home folder. Existing
Docker or Podman installs can still be used; the portable build stays for
machines already set up.

## Why

- Podman and Lima are Apache 2.0, so they can be shipped inside our
  installer; Docker Desktop cannot be redistributed that way and needs its own
  licence acceptance. Rootless Podman also keeps the sandbox off host root.
- Limits stated honestly: BIOS virtualization cannot be turned on by
  software (detected first, with a guide); turning on WSL2 needs admin once
  (IT can push a silent installer); very low-RAM machines get a warning.
- This trades some portability (Windows may need one admin step and one
  reboot) for no prerequisites, which matters more for students.

## Evidence

`thesis/plans/2026-10-30-desktop-client.md` sections 2, 3.2, 3.6, 8, 9
(D0 now prototypes the installer), 10; chapter 12 `sec:desktop-client`.

## Follow-ups

Can IT turn on virtualization and run the installer once in one lab room
for the pilot?

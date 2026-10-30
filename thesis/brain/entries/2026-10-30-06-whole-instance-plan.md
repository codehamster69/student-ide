---
date: 2026-10-30
type: plan
title: Sandbox Labs plan revision 4, a whole Linux instance per student and subject, versatile for any stack
thesis-chapter: 12-conclusion (future work), 04-system-design
supersedes: 2026-10-30-05-teacher-setup-plan.md
---

## What happened

Rohan asked (PR #29) to make Sandbox Labs "versatile for all the subjects,
users may install a variety of tech stack since we are giving them a whole
instance". Revision 4 of `thesis/plans/2026-10-30-desktop-client.md` adds
section 3.5 (whole instance) and updates the container design, monitoring,
tamper table, environment builder, publish step, risks and milestone D3.

## Why

- **Instance per (student, subject), not a locked runner per lab.** Sudo,
  writable root, any package manager, services and ports (one-click preview
  in an in-app browser tab), ptrace for gdb, NET_ADMIN/NET_RAW in its own
  namespace for networking labs. Kept for the semester so installs persist
  across a subject's labs; "Reset instance" rebuilds it and keeps lab files.
- **Setup recipe instead of syncing installed packages.** Packages are too
  big to sync between machines; install commands are recorded and replayed
  on a new machine. The same mechanism lets teachers "set up by hand" and
  save the result as an environment, so no one writes a Dockerfile.
- **Network modes per lab** (open, registries only, off) through a small
  filtering proxy that logs host names, not contents. Open internet makes
  fetching solutions easy, so assessed labs default to registries only and
  the evidence check at submission stays the main defence.
- **Capture moves out of reach of root.** With sudo the student can kill
  anything inside the instance, so key timing stays in the app and the file
  watcher, process observer and proxy run in a sidecar container (read-only
  workspace mount, shared PID namespace). Shell hooks remain best-effort,
  and their going quiet is visible in the review.
- **Isolation from the host** stays: never privileged, user namespaces or
  rootless Podman, listed capabilities only, resource limits including
  disk.
- **Honest limits**: no GPU, nested VMs/Android emulator, kernel modules or
  Windows-only tools; GUI via noVNC later; Docker-in-Docker only via Sysbox
  or rootless Podman where supported.
- New events (schema v2, additive): `pkg_install`, `net_conn`, `port_open`
  / `service`.

## Evidence

- Plan revision 4: `thesis/plans/2026-10-30-desktop-client.md`, section 3.5.
- Figure `thesis/latex/flowcharts/desktop-client.tex` and chapter 12
  `sec:desktop-client` updated.

## Follow-ups

- Rohan: allow open network in assessed labs at all, or registries-only as
  the floor (suggested)?
- Grading with student-installed packages: subject environment plus the
  student's recipe limited to registry packages; check cost in D3.

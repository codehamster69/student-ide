---
date: 2026-10-30
type: decision
title: No cloud fallback for students; cloud instances only for teacher previews
thesis-chapter: 04-system-design
supersedes: (partly) the capped student cloud fallback in 2026-10-30-04
---

## What happened

Asked whether to keep a capped cloud fallback for students whose machine
cannot run the sandbox, Rohan chose "teacher previews only". The plan, figure
and chapter 12 now say: student instances always run on the student's
machine (Docker or Podman); a small pool of preview instances on the VM
serves only teachers' "Try as a student".

## Why

Each cloud seat is a whole Linux instance on the VM, which is the compute
local Docker exists to save. Portability is kept another way: work syncs
through the server, so a student whose machine fails moves to one that works
and loses nothing. The Lab doctor tells them why and how; the readiness
board shows teachers which PCs IT must fix.

## Evidence

`thesis/plans/2026-10-30-desktop-client.md` sections 2, 3.2, 5.6, 6.2, 7, 8,
9 and 10; `latex/flowcharts/desktop-client.tex`; chapter 12.

## Follow-ups

Remaining open: whether IT can install Docker or Podman in one lab room for
the pilot, since lab PCs are now the guarantee for students without a
working laptop.

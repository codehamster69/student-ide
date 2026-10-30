---
date: 2026-10-30
type: decision
title: Assessed Sandbox Labs never get open internet (registries only or off)
thesis-chapter: 04-system-design
---

## What happened

Rohan agreed (PR #29 thread) that assessed labs may use only the
"registries only" or "off" network modes; "open" is for practice labs and
projects. Recorded in section 3.5 of `thesis/plans/2026-10-30-desktop-client.md`.

## Why

Open internet makes fetching a solution trivial, and the host log only tells
us after the fact. Registries only still lets students install any stack
(apt, pip, npm, Maven, crates, Go proxy), which is what the whole-instance
design (2026-10-30-06) needs.

## Evidence

Plan revision 4, section 3.5 network modes table.

## Follow-ups

Package registries can still host code (e.g. a package containing a
solution); the evidence check at submission remains the main defence.

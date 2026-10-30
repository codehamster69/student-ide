---
date: 2026-10-30
type: decision
title: Teachers create Sandbox Lab subjects freely; no admin preset labs
thesis-chapter: 04-system-design
---

## What happened

Rohan decided (PR #29 thread): teachers create subjects without admin
approval, and no subject gets admin-made preset labs. The plan
(`thesis/plans/2026-10-30-desktop-client.md`, sections 1, 2, 5 and 10) and
chapter 12 now say the library holds only labs teachers share. He also asked
why cloud fallback seats are needed; that is answered in the thread and left
open.

## Why

Teachers know their courses; admin-made presets would be work nobody asked
for. Starter environments (C/DSA, Java, Python/ML, web, DBMS, compilers, OS,
networks, DevOps) still give teachers a quick start without presets, and
admins keep only one gate: approving raw Dockerfiles.

## Evidence

Plan revision 4 with these decisions; brain 2026-10-30-05 and -06.

## Follow-ups

Cloud fallback: keep it (and how many seats) or drop it.

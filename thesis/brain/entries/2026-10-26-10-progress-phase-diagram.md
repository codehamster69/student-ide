---
date: 2026-10-26
type: event
title: Progress phase diagram added (Artifact page, STATUS.md with Mermaid, TikZ in appendix D)
thesis-chapter: appendices/D-project-progress
---

## What happened

Rohan asked for a phase diagram that keeps track of what is done and what is
pending. Three views of the same data were added:

- A live page, https://claude.ai/artifact/7nwKBLuR3yH3HDyJ3588Bd, built from
  `thesis/progress/phase-diagram.html` (statuses in its JS data block).
- `thesis/progress/STATUS.md`: tables per track plus a Mermaid diagram that
  GitHub renders.
- `thesis/latex/flowcharts/phase-progress.tex`, shown as appendix D.

State on this date: thesis folder (#1), related work (#3), editor (#2) and UI
redesign (#5) merged; detector (#6) open and being reworked; dashboard and
evaluation harness not started; survey, ethics approval and all real data
collection not started; official IIIT Surat template pending.

## Why

The project runs on two clocks: a software build order (editor, detector,
dashboard, evaluation) and a study timeline (phases 0 to 3 over months 1 to
12). Showing them as two lanes with cross-lane dependencies (logger feeds
phase 0, ethics gates phase 1, phase 2 data feeds the evaluation harness)
makes the critical path visible: ethics approval is now the item that blocks
the study, while the detector is the item that blocks the build.

## Evidence

Files listed above. 26 tracked items: 6 done, 5 in progress, 15 pending.

## Follow-ups

Every later PR that changes a tracked item updates all three views and
republishes the page to the same link.

---
date: 2026-10-26
type: decision
title: Teacher timeline now runs exactly the frozen evaluated configuration
thesis-chapter: 04-system-design
supersedes: 2026-10-26-15-review-timeline.md (detector settings part only)
---

## What happened

`review.py` used 30 s windows for both channels, no prior and hand-set h
(identity 5.25, process 16.5). It now reads `thesis/evaluation/frozen-config.json`
(or `$STUDENTIDE_CONFIG`; built-in copy as fallback) via `load_settings()`:
channels and their window lengths (typing rhythm 30 s, key-pair timing 30 s,
way of working 90 s), k, the key-pair spec, prior n = 2 and h from the new
`operating_point` block that `harness dev` writes (chosen detector fitted on all
dev students, h calibrated as `test` does: 24 / 8.75 / 11.25). Population parts
(ICC weights, key-pair vocabulary, prior) are fitted on the class's own
baselines once 3 students have one. `STUDENTIDE_H` still overrides h.
Frontend: third lane "Key-pair timing" (`--ch-pairs`), each lane on its own
window grid.

## Why

What the teacher sees must be what was evaluated; otherwise the thesis numbers
say nothing about the screen.

## Evidence

Demo (6 simulated students): 7 of 8 non-honest sessions get a moment (one
matched takeover missed), 0 of 4 honest, 0 of 24 baseline-week sessions (was
5 of 24, the open follow-up from phase 3). Screenshots regenerated in
`thesis/latex/snapshots/review/`.

## Follow-ups

h on the screen comes from dev students; the test run's h (27 / 8.25 / 11)
differs a little because self-calibration also uses the evaluated students'
own baseline weeks. On real data, recalibrate on the class and set
`STUDENTIDE_H`.

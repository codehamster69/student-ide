---
date: 2026-10-26
type: decision
title: 30-second habit features; comment keystrokes kept apart from code keystrokes
thesis-chapter: 05-features-and-detector
---

## What happened

`backend/studentide/detector/features.py` turns a session into per-key
streams (one pass with document replay) and then into features per window
of W seconds (default 30, non-overlapping). 17 scored features in 9 groups:
rhythm (digraph median, L-scale of log IKI, hold median), digraph groups
(alternate/same hand, to/from space, into shifted char), pauses (≥2 s per
100 keys, median pause), revision (deletions per 100 keys, burst length),
build order (non-append edits, caret jumps), runs (trailing 5 min), focus
losses, paste share. Comment keystrokes get two unscored features.

## Why

- Log latencies so differences mean the same at every typing speed.
- Digraphs only between adjacent non-deletion keys and under 2 s; longer
  gaps are pauses, a separate habit.
- L-scale of log IKI is Nosi's spread measure (Lueder et al. 2026); including
  it lets us run a Nosi-style comparison inside the same pipeline.
- Comments apart: Nosi notes comment text looks like retyping. Comment status
  comes from replaying edits and checking for `#` outside a string before
  the caret. `comments="mixed"` folds them back in for the ablation.
- Windows with < 20 code keys are inactive and leave the CUSUM unchanged, so
  reading/thinking time does not pull the score towards "normal".
- Run rate uses a 5-minute trailing span because runs are too rare for 30 s.

## Evidence

Feature table in chapter 5 (`tab:features`). Tests in
`backend/tests/test_detector.py`.

## Follow-ups

- AST-level build order (which constructs appear first) is not in yet;
  the current build-order features are edit-position based and turned out
  noisy (entry 12).

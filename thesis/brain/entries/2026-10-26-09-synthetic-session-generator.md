---
date: 2026-10-26
type: decision
title: Synthetic session generator writes editor-format logs for five study conditions
thesis-chapter: 05-features-and-detector
---

## What happened

Built `backend/studentide/detector/synth.py` (+ `corpus.py`). It simulates
typists and writes sessions in event schema v1 (key down/up, edits, clipboard,
cursor, runs, snapshots, focus, session start/end). Every generated event
passes the same pydantic validation as the ingest API and the replay matches
every snapshot (tests in `backend/tests/test_detector.py`). Conditions:
A honest, B full proxy, C takeover at a random minute (5–40 s seat swap,
partner continues the same code), D copying out (switch to transcribing),
E paste. Partners default to the typist nearest in base speed, a stand-in
for the study's grade-matched proxies.

## Why

- Phase 2 lab data does not exist yet; the detector, its features and
  thresholds have to be built and tuned on something with known ground truth.
- Writing the *editor's* format (not a simplified feature table) means the
  feature extractor that runs on simulations is the one that will run on
  students, including replay-based comment detection.
- Habits per typist: base digraph latency (log-normal), spread, personal
  digraph offsets (hash of typist + key pair), hand-alternation speed-up,
  space/shift/digit offsets, hold time, hesitations and think pauses,
  typo + correction, revise-last-word, skeleton-first vs linear code order,
  run frequency, glances away, comments typed more fluently. Day-to-day
  drift on every habit per session, so a student's own sessions differ.
- Alternative considered: splicing two real sessions at a known minute
  (the plan in chapter 5). Still the plan once Phase 1 data exists; the
  generator can't capture real between-student similarity.

## Evidence

`python -m studentide.detector.synth --out synthetic/` writes example
JSONL sessions. ~0.1 s per 30-min session.

## Follow-ups

- Simplifications: Tab indentation (real editor auto-indents and
  auto-closes brackets), no mouse editing, independent habit draws.
- Once Phase 1 data exists: fit generator parameters to it, and add
  splice-based takeovers from real sessions.

---
date: 2026-10-26
type: event
title: Project scope taken from the mid-semester presentation
thesis-chapter: 01-introduction, 03-problem-and-rqs, 06-study-design
---

## What happened

The project was set up from Rohan's mid-semester presentation, *Who Is at
the Keyboard*. The scope below is what the deck commits to, and what every
later decision should be checked against.

- **Thesis:** *Who is at the keyboard? Process-Aware Authorship Continuity
  in Programming Assessment*. M.Tech CSE, IIIT Surat (Rohandeep, PG25CS07;
  guide Dr. Ritesh Kumar). Roughly 12 months over two semesters.
- **Problem:** existing tools check identity at the start of an assessment,
  or copying / AI use at the end, or paste-vs-typed. Nobody checks that the
  *same person* keeps writing the code in between. The target is a
  mid-session takeover by a friend, paid proxy or impersonator.
- **System (Student IDE):** a lab code editor that logs key press/release
  timing, pastes, edits, cursor moves, code runs, errors and file snapshots.
  No webcam, no screen recording.
- **Pipeline:** (1) event recorder; (2) habit features per 30 s window
  (digraph latency, inter-key-time spread, pauses, deletions, AST build
  order, run frequency); (3) per-student baseline from the first four lab
  weeks, keeping summary statistics and deleting raw keystrokes; (4) switch
  detector, distance from own baseline fed to CUSUM change-point detection,
  which also estimates when the switch happened; (5) evidence timeline for
  the teacher. Parts 3 to 5 are the novel contribution.
- **Baselines to beat:** scaled Manhattan keystroke identification, a
  TypeNet-style model, and the Nosi IDE inter-key-time rhythm measure
  (closest prior work, N = 5).
- **Research questions:**
  - RQ1, detect a mid-session switch (detection delay, false alarms). Main
    contribution.
  - RQ2, distinguish composing from transcribing (replicate Nosi at larger N).
  - RQ3, transfer from lab to a remote interview on the student's own laptop.
  - RQ4, fairness by subgroup and precision at realistic prevalence
    (1 in 100, 1 in 500).
- **Study phases:** Phase 0 survey, ethics, build logger (months 1–2);
  Phase 1 baseline labs with 60–80 volunteers (3–4); Phase 2 staged
  conditions A honest, B full proxy, C takeover at a random minute,
  D copying out, E paste, with grade-matched proxies (5–6); Phase 3 mock
  remote interview, 20–30 people (7); build, measure, write (8–12).
- **Constraints:** ethics approval first; India DPDP Act 2023; EU AI Act
  high-risk requirements as a design target. Out of scope: engagement
  scores, grade prediction, deepfakes, deployment, deliberate imitation.

## Why

These commitments shape the design. Three are worth keeping in front of
every thread:

- **A flag starts a conversation, never a penalty.** Precision at
  realistic cheating rates (RQ4) matters more than raw accuracy, because
  even a good detector produces mostly false flags when cheating is rare.
- **Privacy by construction.** No video; raw keystrokes are deleted once
  a baseline is built; only summary statistics persist.
- **Each student is compared to themselves,** not to a population model,
  which is what makes "continuity" measurable.

## Evidence

Mid-semester deck (Claude artifact): https://claude.ai/artifact/HLfjpd6UgL372ox2XtbST8

## Follow-ups

- Find and cite the exact Nosi IDE paper (currently a TODO in the bib).
- Confirm the IIIT Surat thesis format requirements with the guide.

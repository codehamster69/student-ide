---
date: 2026-11-25
type: result
title: Detector re-tuned on pilot dev data: 6.8 → 0.28 episodes per active hour (no build order, k = 2)
thesis-chapter: 06-study-design
---

## What happened

Rohan chose (decision card, pilot-analysis thread) to re-tune the detector on the pilot
recordings as development data only. New `backend/studentide/pilot_tune.py` runs next to
the database, scores six cumulative variants on the **dev split only**
(`harness.split.pilot_split`: dev-hash students, sessions before 2026-11-24 00:00 IST,
agreed with the classroom-data thread, entry 2026-11-25-05) and writes per-window
standardised scores with fresh-salt pseudonyms; CUSUM, calibration and the tables then run
off the server. Class-level parts (ICC weights, pair vocabulary, prior) were fitted on dev
students only. Run on a copy of the live database on 2026-11-25 (snapshot
`studentide-pre-20261125-retune` first; temporary key removed and gcloud signed out after;
the database copy deleted). Only `pilot-tune.json` (scores, pseudonyms) left the VM.

Code changes that came out of it:
- **Own pastes don't count** (`features.internal_paste`): a paste or drop whose text, ignoring
  whitespace, was copied/cut in the editor before (this session or the student's other
  sessions that day), already stands in the document, or is in the question statement, is
  not "pasted"; neither is any origin containing `internal` (paste guard, #62,
  `input.paste.internal`). Purged sessions get `paste_frac` redone from their kept edits.
  Rohan: "our detector even flagged copying and pasting from our own ide".
- **0 ms floor** (`features.LOG_FLOOR_MS`): real browsers stamp two keys in the same
  millisecond; log(0) made `dg_median`/`dg_lscale` −inf. Stored windows read −inf as missing.
- Review settings `own_pastes`, `min_baseline_windows`, `device_baseline` (off in the frozen
  config) and `thesis/evaluation/pilot-dev-config.json`, the dev-tuned proposal.

## Evidence

Dev: 876 sessions, 207 students; 332 scorable (baseline ready, some typing), only 10.7 active
typing hours. Table `thesis/latex/tables/pilot-retune.tex`, graph `graphs/pilot-retune.pdf`.

| Variant (cumulative) | scored | episodes/h | identity / pairs / process |
|---|---|---|---|
| as live | 332 | 6.81 | 0.28 / 2.61 / 3.92 |
| + own pastes, 1 ms floor | 332 | 6.72 | 0.28 / 2.61 / 3.83 |
| + no build order | 332 | 4.95 | 0.28 / 2.61 / 2.05 |
| + 10 min baseline typing | 84 | 4.29 | 0 / 3.21 / 1.07 |
| + same-device baseline | 79 | 4.33 | 0 / 3.09 / 1.24 |
| no build order, k = 2 (proposal) | 332 | **0.28** | 0 / 0.09 / 0.19 |

- **Pastes:** 434 of 518 pastes (84%) were the student's own text. Sessions with a paste
  194 → 54; with a big or after-look-away paste 81 → 50 (5.7% of dev sessions).
- **Why so many flags:** the standardised honest score averages 1.2-1.6 on every channel
  (0 by design): day-to-day drift the short leave-one-session-out baselines never saw. With
  k = 0.5 CUSUM climbs about 0.8 per window on honest work. A 10-min baseline cuts the drift
  (identity 1.27 → 0.76) but leaves a quarter of sessions scorable.
- **Recalibrating h** at the old k needs h 3-6× larger (identity 31, pairs 43, process 53);
  with 10.7 h that is fitted on ~2 episodes: in-sample 0/h, other half of students 0.57/h.
  Too thin to freeze, so the proposal keeps h and raises k instead.
- **Same-device baselines** changed nothing measurable (too few students with two sessions
  on a second device); other-device sessions still flag more (6.9 vs 4.6/h without build order, old k).
- **Outside pastes don't drive the detector:** sessions with an outside big/away paste flag
  *less* (3.4 vs 5.1/h without build order). So copying goes to its own signal: outside
  pastes are counted and shown directly, and the paste guard (#62) now blocks them.
- **Synthetic check** (dev seed 3, 60 typists, `detector.evaluate`): without build order
  copying 78 → 95%, paste 55 → 90%, matched takeover 75 → 72%, proxy 82 → 78%,
  false alarms 0.35 → 0.47/h. The cost of k = 2 on detection is not measured yet.

## Why

Build order follows the question (skeleton-first starters, fill-in exercises) more than the
person, and on synthetic data it never earned much. Raising k is the textbook response to a
known honest drift: CUSUM should ignore shifts the student shows anyway and keep reacting to
larger ones; a takeover moves identity by several sd. Raising h instead would slow every
alarm. Minimum baseline and device baselines stay off because the data can't support them yet.

## Follow-ups

- Measure what k = 2 costs on takeovers spliced from real sessions (classroom harness,
  #63) on dev, then freeze. Until then `pilot-dev-config.json` is a proposal, not live.
- Recalibrate h once dev has more active hours (later labs; test weeks stay untouched).
- Pairs channel was the largest source at the old k: check its vocabulary on real classes.
- The first-look numbers (entry -01) were computed on all sessions; disclosed in ch 6.

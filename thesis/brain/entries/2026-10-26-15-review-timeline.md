---
date: 2026-10-26
type: decision
title: Teacher review timeline built (phase 3), with alarms merged into "moments to discuss" and conversation-first wording
thesis-chapter: 04-system-design
---

## What happened

Build step 3. The review screen lives in the same web app under `#/review`
(lazy-loaded, 61 kB, so the student bundle is unchanged) and reuses the
design system in `frontend/src/ui/`. It is gated by the existing research
token (`STUDENTIDE_ADMIN_TOKEN`). Backend: `backend/studentide/review.py`
(evidence per session), five `/api/review/*` endpoints in `app.py`, and
`backend/studentide/seed.py` (simulated students for demos). Docs:
`docs/review.md`.

Screens: token gate → overview (stat tiles, filters, per-session sparkline
of both channels, moments) → session view (two channel lanes with score
strip + CUSUM vs threshold, pastes / looked away / runs / typing lanes,
draggable playhead with 1–60× replay, code rebuilt at the playhead with
recent lines tinted, keystroke-rhythm strip, moment cards with the habits
that moved, suggested questions).

## Why

- **Merge alarm chains into moments.** CUSUM restarts after an alarm, so a
  takeover for the rest of a session raised up to 14 alarms in one demo
  session. Each new alarm's estimated start equals the previous alarm, so
  chains are easy to detect (`episodes()`); a reviewer needs one moment to
  ask about.
- **Explain with the detector's own numbers.** The "what moved" list is the
  per-feature z (median over the windows between the estimated start and the
  first alarm), weighted like the detector, shown in natural units ("usual
  158 ms → here 134 ms"). Alternatives (SHAP-style attributions, a separate
  explainer) would explain something other than what fired.
- **Wording.** No "flag/alert/cheating/suspicious" anywhere; sessions have
  "moments worth a conversation" or "nothing stood out", each moment comes
  with three suggested questions and the note that no mark follows. This is
  the project's standing rule (a flag only leads to a conversation) and the
  EU AI Act high-risk design target (human oversight, explanation).
- **Baseline = sessions in the first 28 days**, at least 2 to score; a
  baseline session is scored against the other baseline sessions and
  labelled as a baseline check, so every session can be opened but baseline
  weeks are never presented as judgments.
- **Replay in the browser.** The server sends initial text + edits; the
  browser rebuilds the code with checkpoints every 200 edits, so scrubbing is
  instant. UTF-16 offsets in the schema match JS string indexing.
- **Ground truth overlay only for seeded sessions** and off by default: it is
  for checking the detector on demo data, and real sessions have none.
- **Chart colours**: identity indigo / process teal, validated as a 2-slot
  palette for colour-vision deficiency in light and dark; channels are also
  separated by lane and labelled, so colour is never the only cue.

## Evidence

- `backend/tests/test_review.py` (7 tests): token gating, summaries,
  takeover → identity moment within 180 s of the simulated switch with
  evidence rows, replay rebuilds the final code, no scoring without
  baseline, alarm-chain merging. Whole backend suite: 45 passed.
- JS replay checked against all 524 stored snapshots of 8 demo sessions:
  0 mismatches.
- Student e2e (`frontend/e2e/record.mjs`) still passes: 214 events, same
  per-type counts, 0 long tasks while typing.
- Demo (seed 11, 6 students, 25 min): all 8 non-honest assessed sessions
  get a moment on the expected channel (3 takeovers + 1 proxy on identity,
  2 copying + 2 paste on process), with the estimated start within 50 s of
  the simulated switch; none of the 4 honest assessed sessions gets one.
  The proxy session (someone else from the start) shows two identity
  moments, from 0:30 and 8:00. Baseline checks raise moments in 5 of 24
  baseline sessions: with only 3 other baseline sessions the leave-one-out
  reference is thin. This is a 12-session demo, not an evaluation.
- Screenshots: `thesis/latex/snapshots/review/` (light + dark), made by
  `frontend/e2e/review-screenshots.mjs`. Text and figures:
  `thesis/latex/chapters/04-system-design.tex`, section "Teacher evidence
  timeline" (`fig:review-overview`, `fig:review-session`).

## Follow-ups

- Moments in baseline weeks (5/24 in the demo) suggest the baseline-check
  view needs more baseline sessions or a looser threshold; revisit with real
  data in phase 4.
- Thresholds are still the synthetic calibration; set `STUDENTIDE_H` after
  real calibration.
- A teacher may want to record the outcome of the conversation on the
  screen; not built, because storing outcomes needs its own ethics wording.

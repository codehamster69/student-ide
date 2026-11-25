---
date: 2026-11-25
type: result
title: Classroom evaluation: thresholds frozen on dev, held-out test scored once, RQ1-RQ4 written up
thesis-chapter: 07-rq1-switch-detection, 08-rq2-composing-vs-transcribing, 09-rq3-remote-transfer, 10-rq4-fairness-and-precision
---

## What happened

New harness modes (`backend/studentide/harness/classroom.py`, report in `classroom_report.py`):
`freeze` (dev only), `test --classroom` (once, logged), `rq` (RQ2/RQ3, descriptive). Run on a
copy of the live database inside the app container (snapshot `studentide-pre-20261125-final-eval`
first; aggregates only came off the server; copy, SSH key and gcloud sign-in removed after).
Results in `thesis/evaluation/classroom-*.json`, tables `thesis/latex/tables/cls-*.tex`, graphs
`graphs/cls-*.pdf`; ch 7-10 and the abstract rewritten around them.

## Why

Rohan kept the live detector settings (re-tune rejected, brain -07), so only the thresholds h
and the calibration source were set from data, on dev students' real sessions, at the 0.2 false
alarms per active hour fixed before any data. Synthetic thresholds gave 1.59 per hour on real
dev sessions. Holdout calibration (other dev students' real sessions) was chosen because it hit
its targets best (mean |log achieved/target| 0.06 vs pooled 0.33, self 0.50); self calibration
overshoots because baseline minutes are more alike than later sessions (drift).

Held-out sessions of dev students from 24 Nov are now scored in `test` (`held_out` corpus
option) and never used for calibration; there were none yet in this copy.

## Evidence

- Frozen h: rhythm 18.5, key pairs 27.0, process 26.0 (synthetic: 24, 11.25, 8.75). Config hash
  2630c8689000.
- Test (ledger line 3, corpus 2a209845068f9fa4, commit bbac70e): 20 of 69 test students scored,
  21 sessions, 6.5 h, 4+1 splices. 0.15 FA/h (0-0.49), 1/21 flagged, 1/4 same-device caught.
  Deployed thresholds: 1.23 FA/h, 3/4. Too small for detection; FA matches the target.
- Dev cross-fitted (90 sessions, 27.7 h, 45 splices): 31% caught (18-45), delay 10 min,
  0.22 FA/h; identity only 29% at 0.14; deployed 64% at 1.59. Scaled Manhattan 29% at 0.18,
  TypeNet-style 16%, Nosi-style 13%. Precision 5.4% at 1/100 (2.7-20.1), 1.1% at 1/500.
- RQ2 (111 sessions): process AUC 0.71-0.74 vs outside-paste signs, 0.61-0.64 without paste and
  focus features; rhythm, key pairs, L-scale ~0.5. No blocked pastes or keyless text yet.
- RQ3: no student had scored sessions on both device classes; 4 with profiles on both.
  Profiles: rhythm within-student 0.62 vs between 0.99, stable over time (rho -0.11);
  process within 1.17 > between 0.84, grows with days (rho 0.45).
- RQ4 (dev): C = competition and Python = lab coincide; competitions (8 min sessions) never
  flagged or caught. Deployed thresholds: Windows 2.38 FA/h vs Linux 0.66, Python labs 2.05 vs
  C competitions 0.28. No conversation outcomes noted yet.

## Follow-ups

- Rerun `test --classroom` at the end of term: every session from 24 Nov is held out, so the
  test set grows; log it with its own corpus fingerprint.
- Device transfer (RQ3) needs students who switch between lab and laptop; rerun `rq` then.
- Live site still uses synthetic thresholds (1.6 FA/h, Windows/Python labs flagged most);
  switching to the frozen classroom h is Rohan's decision.

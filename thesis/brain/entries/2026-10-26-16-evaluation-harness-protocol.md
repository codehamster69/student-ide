---
date: 2026-10-26
type: decision
title: Evaluation harness (phase 4) - one protocol for synthetic and study data, strict student-level dev/test split with a test ledger
thesis-chapter: 06-study-design
---

## What happened

Build step 4. New package `backend/studentide/harness/` (docs:
`docs/evaluation.md`), run as `python -m studentide.harness dev|test`.

- Corpus: `synthetic_corpus()` (120 simulated students, 8 honest baseline
  sessions + 7 test sessions each, seed 2026) or `db_corpus()` (editor
  database + a labels manifest `sessions.csv` / `students.csv` filled in while
  running the Phase 2 study). Same downstream code for both.
- Split: 30% of students are test, by salted hash of the id (stable as
  students enrol; order-independent). Every population-level piece (ICC
  weights, population prior, TypeNet embedder, digraph vocabulary, h) is fit
  on dev students only, and a test checks it.
- `dev`: 5-fold cross-fitting within dev for calibration, tuning and
  ablations; writes `thesis/evaluation/frozen-config.json`.
- `test`: refuses without a frozen config; calibrates on dev, scores test once,
  appends to `thesis/evaluation/test-ledger.jsonl` (time, commit, config hash,
  corpus fingerprint). Re-scoring the same corpus+config needs `--reason`.
- Baselines share the detector's standardisation, alarm stage and
  calibration: scaled Manhattan (top-40 digraphs + top-15 key holds),
  TypeNet-style LSTM with triplet loss (NumPy, 1 layer x 32, gradient-checked),
  Nosi-style L-scale. Each gets its own alarm rule / k / window on dev.
- Metrics: per-condition detection, delay, switch-time error with student
  bootstrap CIs; detection vs FA/h curves; RQ2 LOPO accuracy; RQ4 precision at
  1/100 and 1/500 and per-subgroup error rates.

## Why

- Phase 2 tuned and reported on one population. A thesis claim needs a test
  set nobody tuned on; splitting students (not sessions) is the only split
  that matches deployment (new students, never seen).
- Hash-based assignment means the real study's split is fixed before data
  arrives and cannot be "re-rolled" after seeing results.
- The ledger makes "scored once" checkable rather than a promise.
- Fresh seed 2026: the phase-2 seed-7 population had already been looked at.
  Note that `population(n, seed)` reuses the first typists for larger n, so a
  new seed, not a larger n, was needed.
- NumPy LSTM instead of PyTorch: torch could not be installed in the cloud
  session, and a 100 MB+ dependency for one baseline would make the thesis
  harder to reproduce. Scaled down from TypeNet's 2x128 (we have ~84 training
  students, not 168k).
- Ablations reported on dev, headline numbers on test: ablations are design
  studies, so they must not touch test.

## Evidence

- Code: `backend/studentide/harness/{corpus,split,methods,lstm,alarms,engine,rq2,report,run}.py`
- Tests: `backend/tests/test_harness.py` (13 tests: split stability, CUSUM grid
  = detector CUSUM, LSTM gradient check, every method scores, population parts
  see only dev, db+manifest loader, test needs frozen config)
- Flowchart: `thesis/latex/flowcharts/evaluation-harness.tex` (ch. 6, `fig:harness`)
- Text: ch. 6 "Evaluation protocol"

## Follow-ups

- When Phase 1-2 data exists: fill the labels manifest and run the same two
  commands with `--db/--labels`; the ledger then gets a new corpus fingerprint.
- RQ3 (remote interview) is another labelled corpus; not yet wired into a report.

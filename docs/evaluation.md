# Evaluation harness (phase 4)

Code: `backend/studentide/harness/`. One protocol for simulated people now and
for the Phase 1–2 study recordings later: the same command, the same split
rules, the same metrics, only the corpus changes.

```bash
pip install -e 'backend[analysis]'
cd backend
python -m studentide.harness dev  --thesis ../thesis/latex   # design + freeze, ~20 min on 4 cores
python -m studentide.harness test --thesis ../thesis/latex   # report once, ~5 min

# recorded study data
python -m studentide.harness dev  --db data/study.sqlite3 --labels data/labels/ --thesis ../thesis/latex
python -m studentide.harness test --db data/study.sqlite3 --labels data/labels/ --thesis ../thesis/latex
```

| module | what it does |
|--------|--------------|
| `corpus.py` | labelled sessions: `synthetic_corpus()` (120 simulated students, 8 baseline + 7 test sessions each) or `db_corpus()` (editor database + labels manifest) |
| `split.py` | dev/test split by student (salted hash), dev cross-fitting folds, frozen-config hash, test ledger |
| `methods.py` | the thesis detector and the baselines, all producing standardised window scores |
| `lstm.py` | NumPy LSTM + triplet loss for the TypeNet-style baseline (gradient-checked in tests) |
| `alarms.py` | shared alarm stage: CUSUM or per-window threshold over a grid of h, calibration |
| `engine.py` | scoring runs, operating points, metrics, student-bootstrap intervals, precision |
| `rq2.py` | composing vs transcribing (Nosi replication) |
| `report.py` | LaTeX tables, CSVs and PDF graphs |
| `run.py` | the `dev` / `test` command line |

## Protocol

1. **Split students, not sessions.** 30% of students are test, by a salted
   hash of their id, so the split never depends on who else enrolled. Every
   population-level piece (ICC feature weights, the population prior, the
   TypeNet embedder, the scaled-Manhattan digraph vocabulary, thresholds h) is
   fitted on dev students only; a test asserts this.
2. **`dev`** works only on dev students with 5-fold cross-fitting (population
   parts fitted on 4 folds, scored on the fifth), so dev numbers are
   out-of-sample too. It chooses the calibration source, the detector's open
   settings (process-channel window, population prior) and each baseline's
   alarm rule, k and window, runs the ablations, and writes
   `thesis/evaluation/frozen-config.json`.
3. **`test`** refuses to run without a frozen config, calibrates h on dev
   students, scores the test students once and appends a line to
   `thesis/evaluation/test-ledger.jsonl` (time, commit, config hash, corpus
   fingerprint). Scoring the same corpus with the same config again needs
   `--reason`, which is logged. The thesis can then state how often the test
   set was looked at.
4. The synthetic population uses seed 2026, never used in phase 2 (phase-2
   design used seed 3, its report seed 7).

## Metrics

- **RQ1**, per condition: share of sessions with an alarm after the switch,
  median and 90th-percentile delay, median switch-time error, alarms before the
  switch, which channel fired first; false alarms per honest hour and share of
  honest sessions with any alarm; window AUC (one window, honest vs typed by
  another person); detection vs false-alarm curves by sweeping the calibration
  target. 95% intervals resample students.
- **RQ2**: leave-one-participant-out balanced accuracy, composing vs
  transcribing windows, for Nosi's raw L-scale, L-scale against the student's
  own baseline, and the process channel, by window length; accuracy spread at
  N = 5 (Nosi's study size); the comment confound.
- **RQ4**: precision of a flag at prevalence 1/100 and 1/500 (TPR from
  non-honest sessions, FPR from honest sessions), honest flags per real one,
  and error rates per subgroup with intervals.

## Calibrating h

Three sources, compared on dev:

- *holdout*: staged honest sessions of calibration students (what phase 2 did);
- *self*: every student's own baseline sessions, each scored against a
  baseline of the other baseline sessions. Needs no staged sessions at all,
  so it is available for every student in a real class;
- *pooled*: both.

Phase 2 found that 20 holdout students gave twice the target false-alarm rate;
the calibration table in `thesis/latex/ablations/harness-calibration/` shows how
each source behaves as the number of calibration students grows.

## Short baselines

`Baseline.fit(..., prior=population_prior(...))` shrinks a student's
per-feature spread and honest score level towards the population's, as if
the population were worth `n` extra sessions (default 2). The harness compares
1–8 baseline sessions with and without it. The prior is off unless the frozen
config turns it on.

## Labels manifest for real data

`--labels` points at a folder with

```
sessions.csv  session_id,role,condition,variant,switch_s,partner
students.csv  student,<attribute columns: gender, layout, experience, own_laptop, ...>
```

- `condition`: honest / proxy / takeover / copying / paste (A–E).
- `role`: baseline / test; leave empty to use "honest sessions in the first
  28 days after the student's first session".
- `switch_s`: seconds from session start to the first keystroke under the new
  condition (from the staging log); empty for honest, 0 for proxy.
- `variant`: optional finer label (e.g. `takeover_random`).

Every column of `students.csv` becomes a fairness subgroup in RQ4.

## Baselines, as implemented

- **Scaled Manhattan** (Killourhy and Maxion 2009, free-text form): per window,
  mean log latency of the 40 most common code digraphs and mean log hold of
  the 15 most common keys (vocabulary from dev students); template = mean and
  mean absolute deviation over the student's baseline windows; score = mean of
  |x − mean| / mad over the features present (at least 5).
- **TypeNet-style** (Acien et al. 2022): sequences of 30 code keystrokes
  (stride 10), each keystroke = hold, release→press, press→press,
  release→release, key code; one LSTM layer of 32 (TypeNet: two of 128) with a
  32-d embedding, triplet loss with margin 1.5, trained on dev students'
  baseline sessions; window score = mean distance of its sequences to up to
  300 enrollment sequences.
- **Nosi-style** (Lueder et al. 2026): L-scale of log inter-key time, every key
  including comments, one channel.

All three get the same standardisation by the student's own honest level, the
same alarm stage and the same calibration as the thesis detector, plus their
own choice of alarm rule (CUSUM k or per-window threshold) on dev.

## Known gaps

- All current numbers are simulated people. The generator types indentation
  with Tab and its comments differ from code by one latency offset, so the
  comment confound cannot show up in synthetic data.
- Synthetic subgroups are terciles of the simulated habit profile, not
  demographics.
- RQ3 (lab → remote interview) needs the Phase 3 recordings; the harness
  already accepts them as another labelled corpus.

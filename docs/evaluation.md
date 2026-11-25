# Evaluation harness (phase 4)

Code: `backend/studentide/harness/`. One protocol for simulated people and for
real classroom recordings: the same command, the same split rules, the same
metrics, only the corpus changes. The thesis concludes from **classroom data
only** (no staged sessions, no labels; see "Classroom data" below).

```bash
pip install -e 'backend[analysis]'
cd backend
python -m studentide.harness dev  --thesis ../thesis/latex   # design + freeze, ~20 min on 4 cores
python -m studentide.harness test --thesis ../thesis/latex   # report once, ~5 min

# classroom data (a copy of the live database): spliced takeovers, no labels needed
python -m studentide.harness dev    --db data/pilot.sqlite3 --classroom [--by-device] [--baseline-min 10]   # design sweeps
python -m studentide.harness freeze --db data/pilot.sqlite3 --classroom   # live settings, h set on dev real sessions
python -m studentide.harness test   --db data/pilot.sqlite3 --classroom   # held-out split, once, at the frozen h
python -m studentide.harness rq     --db data/pilot.sqlite3 --classroom   # RQ2 / RQ3, descriptive
python -m studentide.harness.classroom_report --eval ../thesis/evaluation --thesis ../thesis/latex   # tables, graphs

# staged recordings with a labels manifest (kept for completeness; the thesis no longer stages sessions)
python -m studentide.harness dev  --db data/study.sqlite3 --labels data/labels/ --thesis ../thesis/latex
python -m studentide.harness test --db data/study.sqlite3 --labels data/labels/ --thesis ../thesis/latex
```

| module | what it does |
|--------|--------------|
| `corpus.py` | sessions to score: `synthetic_corpus()` (120 simulated students, 8 baseline + 7 test sessions each), `classroom_corpus()` (every study session, baseline = earliest active minutes) or `db_corpus()` (editor database + labels manifest) |
| `splice.py` | labelled takeovers from real sessions: student A up to tau, then student B on the same question |
| `split.py` | dev/test split by student (salted hash), `pilot_split` (also by week), dev cross-fitting folds, frozen-config hash, test ledger |
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

## Classroom data

Rohan's decision (2026-11-25): students are a class, not staged subjects, so the
thesis uses only what real classes record. No session has a known switch and none
is known clean. `--classroom` builds the corpus like this:

- **Sessions.** Every study session (`list_sessions`: no learning lab, no previews).
  Sessions with no active 30 s window are role `idle` and not scored. Purged
  sessions (raw keys gone after 28 days) carry their stored windows (`Session.win`),
  so the thesis detector still scores them; scaled Manhattan and TypeNet-style need
  raw keys and only see recent sessions.
- **Baseline.** A student's earliest `--baseline-min` (10) active minutes, from
  whatever sessions those were in, but never the student's last session (so something
  is scored); a student with under 3 baseline minutes or one usable session is
  `unscored`. Baseline sessions are never scored. (At 20 min the pilot dev split had
  nothing left to score: most students type well under 20 active minutes in total.) `--by-device`
  keys each (student, device class) separately, the split still hashing the person.
  Device class comes from `pilot.device_fingerprint` / `device_class` (a fingerprint
  shared by 3+ students = lab-PC-like).
- **Split (shared with the detector re-tune).** `split.pilot_split(student_id,
  started_at)`: test = the 30 % test-hash students, plus every session from
  `PILOT_TEST_FROM` (2026-11-24 00:00 IST) for everyone. Dev students' later
  sessions are role `later` and are not touched by `dev`. Hash the real
  `sessions.student_id`, never the pilot tool's per-run pseudonym.
- **Splices** (`splice.add_splices`). For each scored real session A, a partner B is
  another student's session on the same question and the same split side; tau is a
  multiple of 90 s leaving >= 3 min and 2 active windows each side. Same device
  class -> variant `takeover`; other class -> `takeover_random` (so the existing
  reports apply). Raw-event splice when both have keys, window splice otherwise.
  Deterministic per `--seed`.
- **What it reports.** Real sessions -> false alarms per hour (an upper bound: some
  may hide real cheating). Splices -> detection, delay, switch-time error.
  Precision at 1/100 and 1/500 from both (a lower bound). RQ2 there is weak-label
  agreement (big pastes, blocked outside pastes, paste after look-away, keyless
  text), run by `rq` (`classroom.rq2`): per-sign AUC of each channel's session score,
  also for the process channel without its paste and focus features, and the
  within-session score after a sign. The short-baselines sweep (by session count) is skipped; sweep
  `--baseline-min` on dev instead.
- **Comparing configs on dev** (as often as needed; aggregates only):
  `python -m studentide.harness compare --db <copy> --classroom --configs a.json b.json --compare-out c.json`
  scores dev students' real and spliced sessions at each config's own k and h (not
  recalibrated), 5-fold cross-fitted: false alarms per hour, takeover detection, delay,
  with student-bootstrap intervals. Window features come from the harness, so review-side
  stream options (own-paste filtering) only apply to sessions scored from stored windows.
- **Limits of a splice.** B continues B's own code, so build order is B's document,
  and there is no "read the other person's code" pause. Both favour the process
  channel; report the identity channels alone as well.

- **Classroom freeze and test** (`harness/classroom.py`). `freeze` keeps the detector
  settings of `--base-config` (the live `frozen-config.json`) and chooses the calibration
  source and every method's h on dev students' real sessions for `--target` (0.2/h),
  writing `classroom-frozen-config.json`, plus a cross-fitted dev summary (curves,
  subgroups, baselines). `test --classroom` loads the corpus with `held_out=True`: dev
  students' sessions from PILOT_TEST_FROM become scored test sessions (never calibration),
  splices pair them on the test side, and every method is scored at its frozen h, once
  per corpus and config (ledger, `--reason` to repeat). `rq` scores every honest scored
  session for RQ2 and RQ3 (detector drift by days since baseline; session-profile
  distances within and between students and device classes). On the VM run these on a
  database copy inside the app container with `PYTHONPATH` pointing at a copy of the
  code and `STUDENTIDE_GIT_COMMIT` set, so the ledger records the commit.

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

## Frozen configurations so far

| config | chosen on dev | test (36 students, scored once) |
|--------|---------------|---------------------------------|
| `8e2ce5f7faa6` (#9) | two channels, process W = 90 s, prior n = 2 | 83% of non-honest, matched takeovers 64%, 0.28 FA/h |
| `be03e7dea805` (#10) | + key-pair channel (80 pairs, speed-normalised, k = 0.5) | 92% of non-honest, matched takeovers 86% (scaled Manhattan 89%), 0.19 FA/h |

Classroom (`classroom-frozen-config.json`, `2630c8689000`, 2026-11-25): live settings above,
holdout calibration on dev real sessions, h = 18.5 / 27.0 / 26.0 (rhythm / pairs / process).
Dev cross-fitted: 31% of same-device splices at 0.22 FA/h; held-out test (20 students,
4 splices): 0.15 FA/h, 1 of 4 caught. Brain entry 2026-11-25-09.

`dev` also writes an `operating_point` block (h per channel, k, window
lengths, key-pair vocabulary) from the chosen detector fitted on all dev
students; the review timeline loads it (see [review.md](review.md)). `test`
recalibrates h the same way but its self-calibration also uses the test
students' own baseline weeks, so its h differs slightly (27 / 8.25 / 11 vs
24 / 8.75 / 11.25).

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

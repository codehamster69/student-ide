# Evaluation records

Written by the evaluation harness (`python -m studentide.harness`, see
[docs/evaluation.md](../../docs/evaluation.md)). Commit these files with the
tables and graphs they produced.

| file | written by | what it is |
|------|------------|------------|
| `frozen-config.json` | `dev` | every choice made on dev students: calibration source, detector settings, each baseline's rule / k / window, corpus fingerprint |
| `dev-summary.json` | `dev` | all dev numbers (calibration, tuning, ablations, window length, short baselines) |
| `test-summary.json` | `test` | the reported test-split numbers, with bootstrap intervals |
| `classroom-frozen-config.json` | `freeze --classroom` | classroom thresholds: live detector settings, h per method and calibration source set on dev students' real sessions |
| `classroom-dev-summary.json` | `freeze --classroom` | dev cross-fitted numbers: calibration check, curves, subgroups, baselines |
| `classroom-test-summary.json` | `test --classroom` | the held-out classroom numbers, with student-bootstrap intervals |
| `classroom-rq.json` | `rq --classroom` | RQ2 copying-sign association, RQ3 drift and device profiles, conversation-outcome counts |
| `test-ledger.jsonl` | `test` | one line per test run: time, commit, config hash, corpus fingerprint, reason. Append-only; never edit by hand |

The ledger is what lets the thesis say how often the test students were
looked at. A new line with an unchanged corpus and config needs `--reason`.
Classroom-data runs (`--classroom`) go in the same ledger with their own corpus
fingerprint; the frozen config of a classroom `dev` run replaces the synthetic one
only when Rohan decides the detector re-tune is final.

Classroom tables and graphs (`thesis/latex/tables/cls-*`, `graphs/cls-*`) are regenerated from
the four classroom files with `python -m studentide.harness.classroom_report --eval
../thesis/evaluation --thesis ../thesis/latex`. The classroom runs happen on a copy of the
live database on the VM (docs/pilot-data.md); only these aggregate files leave it.

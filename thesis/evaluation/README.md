# Evaluation records

Written by the evaluation harness (`python -m studentide.harness`, see
[docs/evaluation.md](../../docs/evaluation.md)). Commit these files with the
tables and graphs they produced.

| file | written by | what it is |
|------|------------|------------|
| `frozen-config.json` | `dev` | every choice made on dev students: calibration source, detector settings, each baseline's rule / k / window, corpus fingerprint |
| `dev-summary.json` | `dev` | all dev numbers (calibration, tuning, ablations, window length, short baselines) |
| `test-summary.json` | `test` | the reported test-split numbers, with bootstrap intervals |
| `test-ledger.jsonl` | `test` | one line per test run: time, commit, config hash, corpus fingerprint, reason. Append-only; never edit by hand |

The ledger is what lets the thesis say how often the test students were
looked at. A new line with an unchanged corpus and config needs `--reason`.
When the study data arrives, its runs go in the same ledger with a different
corpus fingerprint.

---
date: 2026-10-26
type: result
title: Second frozen config scored once on test - matched takeovers 64% -> 86%, all non-honest 83% -> 92%, 0.19 FA/h
thesis-chapter: 07-rq1-switch-detection
---

## What happened

After the dev choice (entry 19) the dev run was repeated in full, writing a
new `frozen-config.json` (config hash be03e7dea805). The test split (36
synthetic students, same corpus f4cd7f5ee7179c97) was then scored once with
`--reason "new frozen config: key-pair timing channel chosen on dev
(2026-10-26); scored once"`. The ledger now has two lines, one per config.

## Evidence

Test students, thesis detector (h identity/process/pairs = 27/8.25/11):

| | two channels (#9) | + key-pair channel (#10) | scaled Manhattan |
|---|---|---|---|
| proxy | 69% | 89% | 83% |
| matched takeover | 64% | 86% (75-97) | 89% |
| random takeover | 81% | 83% | 81% |
| copying / paste | 100 / 100% | 100 / 100% | 6 / 8% |
| all non-honest | 83% | 92% | 53% |
| FA per honest hour | 0.28 | 0.19 (0.06-0.39) | 0.30 |
| precision at 1/100 | 11% | 12% (7-26) | 4% |

First channel to fire: matched takeovers 16 pairs / 14 identity / 1 process;
random-partner takeovers mostly identity (21 of 30). Matched-takeover delay
4.6 min (SM 3.5). Fairness: variable-rhythm group 64% of matched takeovers,
steady-rhythm group 12% of honest sessions flagged; all intervals overlap.

Tables and graphs regenerated: `thesis/latex/tables/harness-*`,
`graphs/harness-*`, `thesis/evaluation/test-summary.json`.

## Follow-ups

The gap to scaled Manhattan on matched takeovers is gone within noise; it is
still faster. Real data decides whether the extra channel's false alarms stay
this low.

---
date: 2026-11-25
type: result
title: Splice check rejects k = 2: false alarms vs missed takeovers on dev pilot data
thesis-chapter: 06-study-design
supersedes: 2026-11-25-06-pilot-retune.md (only its proposal; the paste and 0 ms fixes stand)
---

## What happened

Ran `harness compare --classroom` (#63, commit 4076ca8) on a copy of the live database,
dev split only, scoring each config at its own k and h on real honest sessions and on
takeovers spliced from two real sessions on the same question (snapshot
`studentide-pre-20261125-compare` first; copy deleted, key removed after). Only aggregates
left the VM.

## Evidence

Baseline = earliest 10 active minutes (M = 5 and 20 give the same picture). 90 honest
sessions (27.7 active hours), 45 same-device-class splices.

| Config | false alarms / h [95% CI] | sessions flagged | takeovers caught [CI] | median delay |
|---|---|---|---|---|
| frozen (build order, k 1/0.5/0.5) | 1.59 [1.12, 2.06] | 29% | 64% [49, 78] | 450 s |
| build order, k = 1 | 0.87 [0.54, 1.21] | 20% | 49% [33, 64] | 450 s |
| no build order, frozen k | 1.15 [0.78, 1.50] | 24% | 51% [36, 65] | 450 s |
| no build order, k = 1 | 0.58 [0.34, 0.80] | 17% | 40% [26, 55] | 585 s |
| no build order, k = 1.5 | 0.07 [0, 0.19] | 2% | 27% [13, 40] | 660 s |
| no build order, k = 2 (entry -06 proposal) | 0.04 [0, 0.12] | 1% | 11% [3, 20] | 1140 s |

Also: of 521 idle dev sessions (no 30 s window with 20 code keys), 430 have under 50
events (opened and left); purged sessions are not over-represented (not a loader bug).
Only 2-3 cross-device-class splices exist, so "takeover by a stranger on another kind of
machine" can't be measured yet.

## Why

No setting is free: every step that removes false alarms also loses takeovers, and the
splice set is small. k = 2 hides the drift and the takeovers with it. Build order, which
looked like noise from the flag rates alone, carries part of the splice detection (spliced
code continues the other student's own build order; the splice harness may favour the
process channel, so this needs care). Live settings are Rohan's call (decision card);
recommendation: keep the frozen config and revisit when more weeks of dev data exist.

## Follow-ups

- The thesis reports this trade-off curve rather than one tuned point.
- Pairs channel fires first on most caught splices: its vocabulary on real classes is
  where a better operating point is most likely.

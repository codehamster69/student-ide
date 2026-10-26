---
date: 2026-10-26
type: decision
title: Build order measured per completed line, not per edit; copying detection 50% -> 80%
thesis-chapter: 05-features-and-detector
supersedes: 2026-10-26-10-habit-features-and-comments.md (build-order features only); headline numbers of 2026-10-26-12-synthetic-detector-results.md
---

## What happened

Rohan asked (thread, 2026-10-26) to fix the build-order features, with mock
data and edge cases. Replaced `nonappend_frac` (share of edits away from the
end of the file) and `jump_rate` (caret jumps per minute) with two
line-level features over the trailing 5 minutes:

- `fill_in_frac`: of the code lines completed (blank and comment lines
  excluded), the share that were written above code that already existed.
  Writing top to bottom gives 0; writing a skeleton and filling it in gives more.
- `open_blocks`: mean number of block headers (a code line ending in `:`)
  whose next code line is not indented deeper, i.e. a def/if/for written
  before its body.

The old pair is still computed (`LEGACY_FEATURES`) for the ablation row
"Old build order". New tests in `backend/tests/test_build_order.py` build
mock sessions by hand (linear vs skeleton writer, Enter in mid-line,
multi-line paste above code, paste at the end, trailing blank/comment lines,
deleting lines, a two-change multi-cursor edit, tabs, `#` and `:` inside
strings, an empty session, too few lines -> NaN not 0) plus two
generator-level checks (skeleton typists fill in more; the new feature has
lower window-to-window spread than the old one).

## Why

The old features were per-edit and per-window: within 30 s you may or may
not happen to touch an earlier line, so they jumped around, widened every
student's normal range and hid the small process change copying causes
(removing them raised copying detection 50% -> 95%). A finished line is the
natural unit of build order, and five minutes holds enough of them.

To avoid tuning on the test set, the design was chosen on a separate
development population (30 typists, seed 3): copying at 30 s 35% (old) ->
75% (new) at 0.1 FA/h; each new feature alone gave similar results, so both
were kept since they measure different things. The reported run (seed 7)
was made once afterwards.

## Evidence

Seed 7, 60 typists, W = 30 s, test typists:

| condition | before | after |
|---|---|---|
| B proxy (matched) | 88% | 90% |
| C takeover (matched) | 75%, 86 s | 72%, 80 s |
| C takeover (random) | 88% | 88% |
| D copying out | 50% | 80% |
| E paste | 82% | 78% |
| honest false alarms | 0.42/h, 10% of sessions | 0.42/h, 11% of sessions |

Dropping build order entirely: copying 95%, 0.47 FA/h. Window length:
copying now 80% at 30 s and 90-100% at >= 90 s.

## Follow-ups

- Simulated typists' build order does not change when they transcribe
  except for skeleton writers, so on synthetic data the feature mostly adds a
  stable habit. Whether it earns its place has to be decided on real data.
- A full AST version (which constructs appear first) is still possible
  later; the line-level version needs no parser and works on code that
  does not compile yet, which is most of the time while students type.

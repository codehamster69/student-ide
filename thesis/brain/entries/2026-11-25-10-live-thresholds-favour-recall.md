---
date: 2026-11-25
type: decision
title: Live site keeps the simulated-typist thresholds (recall) over the classroom-calibrated ones
thesis-chapter: 07-rq1-switch-detection
---

## What happened

After the classroom evaluation (entry 2026-11-25-09), Rohan decided the live site keeps the
thresholds calibrated on simulated typists (64% of spliced takeovers caught at 1.59 false alarms
per active hour on dev) rather than switching to the thresholds frozen on dev classroom data
(31% at 0.22). The choice and its cost are written into ch 7 (`sec:operating-point`) and ch 10.

## Why

A flag only starts a conversation (ch 3), so a missed takeover costs more than a conversation
about honest work. Recall doubles and the delay falls from 10 to 7.5 minutes. The cost, also in
the thesis: about 45 honest sessions flagged per real one at 1/100 instead of 18, and flags
concentrated in Python labs and on Windows machines.

## Evidence

`thesis/evaluation/classroom-dev-summary.json` (`at_target` vs `deployed`), tables
`cls-dev-methods`, `cls-subgroups-deployed`.

## Follow-ups

Calibrated thresholds stay in `classroom-frozen-config.json` as the alternative. Final held-out
test run at the end of term on the later weeks.

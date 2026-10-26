---
date: 2026-10-26
type: event
title: Detector tests, mock edge cases and dev-set runs written up as thesis appendix D
thesis-chapter: appendix D (detector verification)
---

## What happened

Rohan asked whether all testing and results were in the thesis. The results
were (chapters 5 and 7, appendix C), but the test suite, the mock-session
edge cases and the development-set runs were only in brain entries. Added
`thesis/latex/appendices/D-detector-verification.tex`: what each detector
test checks, the table of mock sessions and expected results, the dev/test
protocol (design on seed 3, report on seed 7) with the dev runs behind each
decision, and how to reproduce. Chapter 7 points to it.

## Why

Examiners will ask how the code was checked and whether the design was
tuned on the test data; the answer now sits in the thesis, not just the log.

## Evidence

38 tests pass; thesis builds without errors or overfull boxes.

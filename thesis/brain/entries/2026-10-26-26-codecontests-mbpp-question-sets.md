---
date: 2026-10-26
type: decision
title: Larger question sets by topic: Codeforces and CodeChef via the CodeContests dataset (bundled), MBPP (live)
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for a "run around" to get a better set of platform questions,
browsable by topic. Without scraping or breaking terms, the answer is openly
licensed research datasets that already contain those platforms' problems.

- **CodeContests** (DeepMind, Li et al., Science 2022; CC BY 4.0) contains
  Codeforces problems (sourced from codeforces.com) and CodeChef problems (via
  MIT-licensed Description2Code) with statements, tags, difficulty and
  stdin/stdout tests. Published only as Riegeli files on
  `gs://dm-code_contests`, so `backend/scripts/build_codecontests.py`
  (hand-written Riegeli + protobuf reader, only dependency `zstandard`)
  builds a filtered 3.6 MB bundle: 4,551 Codeforces problems rated 800 to
  2000 with tags (3,725 with tests) and 332 easy/medium CodeChef problems
  (323 with tests).
- **MBPP** (Austin et al. 2021, Google Research; Apache 2.0 repo / CC BY 4.0
  card): 974 beginner Python problems fetched live from GitHub; 961 convert
  to tests.
- One topic vocabulary across sources (`providers/base.TOPICS`); Codeforces'
  37 tags map onto 19 topics, then 4 rating bands. New `tokens` comparison
  (numbers within 1e-6) for real-number answers.
- Codeforces and CodeChef are now "Dataset" providers that also keep the link
  form; LeetCode and HackerRank stay link only.

## Why

- **Licensed copy beats scraping.** The platforms' own sites still can't be
  fetched (no statement API, terms), but a CC BY research copy can be reused
  with attribution, which every imported question records (licence, source
  link, dataset citation).
- **Bundled, not live,** because CodeContests has no per-problem API; the
  coordinator agreed bundling a licensed dataset is fine. The bundle is
  reproducible from the build script.
- **No tests for "print any valid answer" problems**: exact comparison would
  fail correct answers; the teacher can add a checker-free test themselves.
- **MBPP topics are guessed** from keywords and labelled as such, since MBPP
  has none.
- Rejected: TACO and APPS (only via Hugging Face / a university server,
  unreachable here, and overlapping CodeContests); Project Euler (CC BY-NC-SA,
  no tests, asks answers stay private); Rosetta Code (GFDL, no tests).
  Codeforces' own API has tags but no statements or tests.

## Evidence

- `backend/tests/test_questions.py`: Codeforces topics/levels/import/check,
  CodeChef set, tolerance comparison, MBPP offline fixture and assert
  conversion. Full suite: 108 passed.
- `frontend/e2e/sources.mjs`: teacher browses Codeforces by topic, adds a
  Codeforces, a CodeChef and an MBPP question; a student passes all 10 tests
  of the Codeforces one. `questions.mjs` and `teach.mjs` still pass.
- Screenshots: `thesis/latex/snapshots/sources/`; chapter 4 paragraph and
  figure `fig:datasets`; bib entries `li2022alphacode`, `austin2021program`.

## Follow-ups

- A tolerant checker for "any valid answer" problems would recover ~800
  Codeforces problems' tests.
- TACO could add tags to CodeChef problems if Hugging Face becomes reachable.

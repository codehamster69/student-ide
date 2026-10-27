---
date: 2026-10-27
type: decision
title: LeetCode and MBPP questions in every lab language, with the same tests
thesis-chapter: 04-system-design
---

## What happened

Rohan saw "request failed (400)" in the LeetCode (and sometimes MBPP) tab of a
C lab, and asked: "why only in python? It's just a programming question with
test cases and expected outputs, it should support all the languages, right?"

- The 400 was the Python-only providers refusing a C lab. Providers now say
  which languages they serve, the picker explains instead of showing a bare
  status, API errors show the server's reason, and live sources reuse their
  last copy when a fetch hiccups (timeout 8 s -> 15 s).
- LeetCode and MBPP now work in C, C++, Java and JavaScript
  (`backend/studentide/providers/polyglot.py`). Argument types come from
  LeetCode's Python type hints, or from the test values for MBPP, narrowed by
  the values (64-bit ints -> long long, one-character strings -> char). The
  student gets a LeetCode-style starter; the harness reads one JSON value per
  argument per line, calls the function and prints the answer as JSON, so the
  expected outputs are shared.
- Python imports use the same JSON-line inputs now, so a problem's tests are
  identical in every language (the any-language competitions thread relies on
  this).

## Results

- LeetCode: 2,828 of 2,834 problems in every language (28,067 tests; JavaScript
  drops 33 tests with integers beyond 2^53). MBPP: 836 of 974.
- `scripts/check_polyglot.py`: 170 round-trip checks pass (identity function,
  up to 40 real values per type, in order and any order, 5 languages); 5,040
  generated programs compile (all C programs, every signature shape in
  C++/Java/JS, LeetCode + MBPP). One clash found and fixed: MBPP's `remove`
  collides with C's stdio `remove()`, so C names it `remove_`.
- `tests/test_polyglot.py`: our own solutions to 6 problems (Two Sum, Add Two
  Numbers, Invert Binary Tree, Median of Two Sorted Arrays, Group Anagrams,
  Valid Parentheses) pass in C, C++, Java and JavaScript; wrong ones fail.
  211 backend tests pass. e2e `leetcode.mjs`: a C++ lab adds Two Sum, same
  tests as Python, a C++ answer passes 10/10 (screenshot 07-cpp-preview).

## Limits

- Types inferred from MBPP's three tests can be narrower than the problem
  intends (an average that happens to be whole is typed int).
- Java returns lists of lists and lists of strings as `List<...>`, other 1-D
  answers as arrays; LeetCode itself varies per problem.
- Any-order answers that are lists of real numbers stay Python only (their
  sort order depends on Python's float text).
- Questions imported before this keep their old Python input format.
- The runner compiles C with `-std=c11`, so POSIX helpers like `strdup` are
  not declared; worth switching to `gnu11` as LeetCode does.

---
date: 2026-10-27
type: event
title: Original "C fundamentals" question set (13 questions, 91 tests) as a bundled source for competitions
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for beginner C fundamentals questions with test cases for a fun
class competition. Thirteen original questions were written, in teaching
order: Hello, Competitor! (I/O); Stopwatch Display and Samosa Offer
(operators); Leap Year Detective and Report Card (conditionals); Digit Sum
and Chai Samosa (loops); Number Staircase (pattern); Top Score and Backwards
Queue (arrays); Palindrome Checker and Vowel Counter (strings); Prime Time
(complete a function). Each has two visible examples and 3 to 10 hidden tests.

They ship as a new bundled provider, "Student IDE sets"
(`backend/studentide/providers/originals.py`, data in
`providers/data/sets/c-fundamentals.json`), so a teacher adds them from
"Add a question from a platform" in any C lab or competition. The site had no
way to import questions from a file before this.

## Why

- Platform problems (Codeforces, CodeChef) are mostly too long or tricky for
  a first-year class competition, and MBPP is Python only. Original problems
  can also ship with the app without licence questions.
- A provider rather than a one-off seed script: it reuses the existing import
  path (source recorded, snapshot kept), works for every teacher from the UI,
  and needs no admin token on the production server.
- Expected outputs come from a Python model of each problem at build time
  (`backend/scripts/build_question_sets.py`), not typed by hand; a pytest runs
  each reference C solution through `grading.grade` (same runner as students)
  and checks the starter code fails, so a broken test cannot reach a contest.
- Hidden tests target the usual slips (century rule, 1 not prime, grade
  boundaries, N = 0 for digit sum, single-element arrays, spaces in a line).
- Prompts are plain text because the editor shows prompts with
  `whitespace-pre-line`, not Markdown.

## Evidence

- `backend/tests/test_question_sets.py`: 16 tests pass (13 reference
  solutions x all tests, starters fail, browse + import into a competition
  gives a competition-ready question without the solution).
- Table `thesis/latex/tables/question-set-c-fundamentals.tex` (generated),
  paragraph in `chapters/04-system-design.tex`.

## Follow-ups

- Needs a deploy to reach studentide.hokora.xyz.
- Possible: "add the whole set" in one click; more sets (Python basics, C
  pointers); a provider chip that says "Original" instead of "Dataset".

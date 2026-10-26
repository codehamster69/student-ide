---
date: 2026-10-26
type: decision
title: Optional tests, lab language and subject, and questions from platforms (Exercism live; LeetCode, HackerRank, CodeChef link only)
thesis-chapter: 04-system-design
---

## What happened

Rohan asked that test cases be optional ("in class it's just about efforts"),
that a teacher or interviewer can set the subject and programming language of
a session, and that they can pick questions from LeetCode, HackerRank or
CodeChef, fetched live rather than pre-stored, with that platform's tests
where available. He then clarified that competitions (built in a parallel
thread) are the only place correctness is used.

Built on PR #11 (labs):

- `questions` gain `tests_json` (stdin/stdout, optional `hidden`, `text` or
  `json` comparison), `harness`, `source_json`; `labs` gain `subject`,
  `language`. New `checks` table. Old files migrate on open.
- `grading.grade()` compiles once and runs every test; `competition_ready()`
  for the competitions work. Students press Check (ungraded); a competition
  lab refuses a question with no tests.
- Runner supports Python, C, C++, Java and JavaScript (`runner.Program`).
- Pluggable providers (`studentide/providers/`): Exercism live, the other
  three link only.

## Why

- **Platforms.** Checked each platform's terms and APIs first. LeetCode has
  no public API (its GraphQL endpoint is internal) and its problems are its
  copyrighted content; HackerRank's API covers only a company's own tests and
  its terms forbid copying any part of the service; CodeChef shut its public
  API in 2020 and uses captchas. Fetching any of them means scraping against
  their terms, so they are link only: the teacher keeps the link and writes
  the question. (LeetCode's terms page could not be loaded from the build
  environment; the decision rests on the absence of any API or licence.)
  Exercism is MIT-licensed and served from public GitHub repositories, so it
  is the live provider; it also ships shared test data.
- **stdin/stdout tests** work the same in every language; function-style
  exercises are bridged with a short driver (arguments as JSON in, return
  value as JSON out). A case is only imported when the translation is
  certain (function exists in the stub with the right arity, not an error case).
- **Snapshot.** Checks run against the session's snapshot of the question,
  consistent with #11: what a session was checked against never changes.
- **Checks are server side**, not a new client event, so the event schema
  stays v1.
- **Language in the snapshot.** Typing rhythm differs by language (braces,
  semicolons); baselines should be compared within a language. Noted as a
  detector follow-up.

## Evidence

- `backend/tests/test_questions.py` (23 tests: comparison rules, hidden-test
  redaction, harness, compile errors, all five languages, lab settings,
  student check against snapshot, run in lab language, competition guard,
  migration, provider listing, Exercism browse/import against recorded
  fixtures, link-only host validation). Full suite passes.
- `frontend/e2e/questions.mjs` against a live server with internet: Exercism
  "Isogram" imported live with 14 tests (7 hidden), student check 0/14 then
  14/14; LeetCode link question; teacher-written question with a hidden test;
  a C++ lab runs C++ in the editor. `teach.mjs` still passes.
- Screenshots: `thesis/latex/snapshots/questions/`; chapter 4 subsection
  "Optional tests, languages and question sources".

## Follow-ups

- Detector: group baseline sessions by language before scoring.
- Codeforces provider (official API for problem list and tags; no statements).
- Run untrusted code in a container before exposing beyond a lab network
  (unchanged from phase 1; more relevant now that C/C++ are compiled).

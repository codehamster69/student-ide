---
date: 2026-10-27
type: decision
title: Any-language competitions and a similarity check for competition submissions
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for an "any language" option for competitions (college-level
contests where each student solves in the language they like) and, if
possible, a reliable plagiarism check. Branch `claude/project-thread-vi45e2`.

- Competitions can have language `any`. Each student picks C, C++, Java,
  JavaScript or Python per question in the editor; each language tried is its
  own session; submissions are graded in the session's language and store it;
  the board shows each row's languages. Per-language starter code and test
  driver live in `questions.variants_json`; imports fetch every language.
- `similarity.py`: token normalisation + winnowing + greedy string tiling,
  starter and class-common code masked, shown to staff as "Similar submissions
  worth a look" with a side-by-side view and typed/pasted characters.
- Detector: a competition session is compared with the same student's
  competition sessions in the same language once there are at least two.

## Why

- One session per language (instead of a language-change event) keeps
  "one session = one question, one language" for the detector and replay,
  needs no event-schema change, and lets the server grade in the session's
  language rather than one the browser claims.
- Tests stay stdin/stdout so one test set fits every language; only starter
  code and drivers vary. Function-style questions open only where a driver
  exists, rather than failing at submit time.
- Token-based winnowing + tiling (MOSS/JPlag family) is robust to renaming,
  reformatting and comments, works for all five languages with one lexer per
  family, and its matches map back to code for a side-by-side view. AST or
  embedding methods were not worth the dependency for programs this size, and
  cross-language translation is out of reach of any token method (said so on
  the page instead of pretending).
- Wording follows the project rule: never "plagiarism" or "copied" on screen,
  never a score change, students never see it. Typed vs pasted characters come
  from the edit log, so the teacher sees process evidence next to the match.
- Masking code most of the class shares avoids flagging the natural way to
  write a short program; the cost is that a whole-class leak is masked too
  (same trade-off as MOSS's -m).
- Lab baselines were left unchanged (frozen detector config); only the
  competition context got the same-language preference.

## Evidence

- `python backend/scripts/eval_similarity.py`: 6 problems x 3 independent
  solutions per family (C/C++, Python). Independent pairs (n=36): median 0.00,
  max 0.36, none at 0.4. Disguised copies (n=36 per level): renamed +
  reformatted min 0.83; + rewritten constructs min 0.77; + dead code every
  third statement min 0.67, 97% at 0.7+. `thesis/latex/ablations/similarity/`,
  `graphs/similarity-separation.pdf`, table `tab:similarity-separation`.
- Tests: `backend/tests/test_any_language.py`, `test_similarity.py`.
- Browser: `frontend/e2e/anylang.mjs`, screenshots
  `thesis/latex/snapshots/anylang/`, figure `fig:anylang`.

## Follow-ups

- The independent corpus was written by one author in deliberately different
  styles; the pilot contests should record how often honest pairs reach 0.5.
- Java/JavaScript have tokenizer tests but no independent-solution corpus yet.
- Tiny questions (under 15 own tokens) are not compared at all.

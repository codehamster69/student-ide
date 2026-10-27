---
date: 2026-10-27
type: decision
title: LeetCode problems with tests (text loaded live, never stored); Codeforces moved to open-r1 with checkers
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for LeetCode questions with test cases, sorted by topic, stored on
our server if possible, and then for a Codeforces dataset that has tests for
more problems.

- **LeetCode** is now a browsable source (Python labs): 2,834 problems from
  LeetCodeDataset (Xia et al. 2025, Hugging Face `newfacade/LeetCodeDataset`,
  Apache 2.0), by LeetCode's tags mapped to our topic vocabulary (27 topics,
  8 new: linked lists, stacks and queues, heaps, matrices, sliding window,
  prefix sums, backtracking, simulation) and by Easy / Medium / Hard. Each
  problem keeps 2 visible + up to 8 hidden tests (28,232 in all), starter
  code with LeetCode's usual imports and `ListNode`/`TreeNode` classes, and a
  harness that builds the arguments, calls `Solution().method` and prints the
  result as JSON.
- **Codeforces** now comes from open-r1/codeforces (Penedo et al. 2025,
  CC BY 4.0) instead of CodeContests: 9,103 problems up to 2025 at every
  rating (was 4,551 rated 800-2000), 7 rating bands. 1,761 problems that
  accept several right answers are judged by the dataset's validated Python
  checker (new compare mode `checker`, run through the sandboxed runner), so
  they have tests at last; under CodeContests about 800 such problems had
  none. CodeChef stays on CodeContests (332 problems).

## Why

- LeetCodeDataset's licence covers its tests, tags and code, but its
  `problem_description` is LeetCode's text: LeetCode claims copyright and
  has filed DMCA takedowns over copies. Every other LeetCode dataset found
  (greengerong/leetcode, doocs) copies the text too. Rohan chose "keep it
  unstored if there is a way, as long as every question is categorised and
  has tests; teachers may change the text". So the server stores no
  statement: an imported question has an empty prompt plus
  `source.live_prompt` (a Hugging Face dataset-viewer rows URL and the
  `task_id` to check), and the browser fetches the text each time. A teacher
  prompt replaces it. If the viewer is unreachable, students get a link to
  leetcode.com.
- open-r1 over CodeContests: twice the problems, newer contests, checkers for
  multi-answer problems, and generated tests for problems whose official tests
  Codeforces truncates.
- Checkers are model-generated code from the dataset, so they run exactly where
  student code runs (runner container in deployment), never in the API
  process, and students never receive them (like hidden tests).
- JSON comparison now allows 1e-5 on real numbers, as LeetCode does, which
  also makes Exercism and MBPP float answers less brittle.

## Evidence

- `backend/tests/test_leetcode.py`: our own solutions to six problems
  (Two Sum, Add Two Numbers, Inorder Traversal, Invert Binary Tree, Median of
  Two Sorted Arrays, Subsets) pass every bundled test; wrong answers fail;
  the bundle holds no description text.
- `tests/test_questions.py`: a correct answer to cf-1170A printed in a
  different order than the expected output passes via the checker; a wrong
  one fails. 169 backend tests pass.
- `frontend/e2e/leetcode.mjs`: teacher browses by topic, preview shows the
  live text, student reads it and passes 10/10. Screenshots in
  `thesis/latex/snapshots/leetcode/`.
- Thesis: rewritten paragraphs and a new figure in
  `chapters/04-system-design.tex`; bib entries `xia2025leetcodedataset`,
  `penedo2025codeforces`.

## Limits and follow-ups

- `build_leetcode.py --verify` (runs the dataset's reference solutions) was
  blocked in the build container; worth running once on a dev machine.
- LeetCode problems are Python only; C/C++/Java would need a per-language
  harness.
- The live text is LeetCodeDataset's plain-text copy, so superscripts are lost
  (10^4 shows as 104 in constraints).
- Session snapshots of LeetCode questions do not contain the text (by
  design); the review timeline links to the original instead.
- Students' browsers need to reach `datasets-server.huggingface.co`.

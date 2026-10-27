# Question sources, optional tests and lab languages

## Optional tests

A question may have no tests (effort only, the default) or a list of
stdin/stdout tests, each optionally **hidden** (the student sees pass/fail
only, never the input or expected output). In a lab, students can press
**Check**; the result is shown to them and kept server side (`checks` table,
`GET /api/sessions/{id}/checks`), and is never a grade. Competitions are the
only place correctness counts, so a question in a competition must keep at
least one test (`grading.competition_ready`, and `PATCH` with `tests: []` is
refused for a competition lab).

- Comparison `text` (default): trailing spaces per line and trailing blank
  lines ignored. `json`: both sides parsed and compared as JSON values, real
  numbers within 1e-5. `tokens`: whitespace-separated, numbers within 1e-6.
  `checker`: for problems with several right answers, the question's
  `checker` (a Python program from the open-r1 Codeforces dataset, run as
  `checker.py input.txt correct_output.txt solution_output.txt`, printing 1
  for right) judges the output. It runs through the same runner as student
  code (the runner container on a deployment), and is never sent to students.
- `harness`: optional code appended after the student's code when tests run
  (used by imported function-style questions).
- Checks run against the session's snapshot of the question, so editing tests
  mid-lab never changes what an open session is checked against.
- `grading.grade(question, code, language)` is the one entry point; it
  compiles once and runs every test (`runner.Program`).

## Lab subject and language

Each lab has a free-text `subject` and a `language`: `python`, `c` (gcc,
C11), `cpp` (g++, C++17), `java` (class name taken from `public class X`),
`javascript` (Node; ES module syntax runs as `.mjs`). The editor syntax mode,
file name, Run and Check follow the lab. `GET /api/teach/languages` says which
toolchains this server has. Practice tasks stay Python. The language is copied
into each session's snapshot: keystroke baselines should be compared within a
language, since typing C++ is not typing Python.

## Platforms

Providers live in `backend/studentide/providers/` behind one interface
(`categories`, `search`, `fetch`). Three kinds:

- **Live**: lists and questions are fetched from the source when the teacher
  browses, and the pick is fetched again as it is added.
- **Dataset** (`bundled`): an openly licensed dataset shipped with the app,
  used where the source publishes no API that serves single problems.
- **Link only**: no permitted source; the teacher pastes a link (checked
  against the platform's host) and writes the question in their own words.

Either way the pick is copied into the lab as an ordinary question with
`source` (provider, url, licence, attribution), so recordings keep a snapshot.
Categories use one topic vocabulary across sources (`base.TOPICS`: Strings,
Dynamic programming, Graphs, Trees, Sorting, Math, ...), then difficulty.

| Platform | Support | Size | Topics | Tests | Licence and why |
|---|---|---|---|---|---|
| Student IDE sets | **Bundled**, original | 13 C questions (C fundamentals) | Input and output, Operators, Conditionals, Loops, Patterns, Arrays, Strings, Functions; warm-up/easy/medium | every question: 2 visible examples + 3 to 10 hidden | Written for this app (`providers/data/sets/*.json`, built by `backend/scripts/build_question_sets.py`). Every reference solution passes every test and every starter fails (`tests/test_question_sets.py`); solutions are never sent to the browser. Lists only for its language. |
| Codeforces | **Dataset** + link | 9,103 problems up to 2025, every rating | 19 topics from Codeforces' own tags; 7 rating bands (Beginner 800-1000 ... Master 2700+, Unrated) | every problem: examples visible, up to 10 small official or generated tests hidden; 1,761 problems with several right answers judged by the dataset's checker; real-number answers within 1e-6 | From **open-r1/codeforces** (Penedo et al., Hugging Face 2025), **CC BY 4.0**: every problem the dataset could run (not interactive, standard input). Replaced CodeContests on 2026-10-27, which had half as many problems and no tests for multi-answer ones. Built by `backend/scripts/build_codeforces.py`. Codeforces' own API lists problems and tags but not statements or tests, so it is not used. |
| CodeChef | **Dataset** + link | 332 easy and medium problems | difficulty only (CodeChef problems carry no tags in the dataset) | yes, as above | Also from **CodeContests** (CC BY 4.0; CodeChef material via the MIT-licensed Description2Code). codechef.com itself can still only be linked. |
| Exercism | **Live** | ~140 per language | concepts (Python track) and difficulty | Python and JavaScript | MIT-licensed, served from public GitHub repositories. Canonical cases become JSON-argument tests plus a small driver. C, C++ and Java exercises have no `main()`, so they import without tests. |
| MBPP | **Live** (Python only) | 974 beginner problems | guessed from the wording (labelled as such) | 961 of 974 have tests: the first visible, two hidden | Google Research, Austin et al. 2021; Apache 2.0 repository, CC BY 4.0 dataset card. Only `assert f(literals) == literal` asserts are converted; the reference solution is never shown, only its `def` line. |
| LeetCode | **Dataset**, text live (Python only) | 2,834 problems | 27 topics from LeetCode's tags; Easy / Medium / Hard | every problem: 2 visible + up to 8 hidden, calling `Solution().method` with lists, linked lists and trees; "any order" answers compared sorted | Tests, tags and starter code from **LeetCodeDataset** (Xia et al. 2025, Apache 2.0), built by `backend/scripts/build_leetcode.py`. **LeetCode's problem text is never stored**: LeetCode claims copyright in it, so an imported question keeps an empty prompt and `source.live_prompt`, and the browser loads the text from the Hugging Face dataset viewer (`datasets-server.huggingface.co`) each time it is shown, checking the row's `task_id`. A teacher can write their own prompt, which then replaces it. Any other problem can still be linked. |
| HackerRank | **Link only** | | | | Its API covers a company's own tests only; its terms forbid copying any part of the service. |

Codeforces statements are kept as published, with `$$$` LaTeX made
readable and the original link kept for attribution
(`providers/data/codeforces.jsonl.gz`, about 9 MB, see
`build_codeforces.py`). CodeChef still comes from CodeContests
(`providers/data/codecontests.jsonl.gz`, CodeChef rows only, from
`build_codecontests.py`); its problems that accept several answers keep no
tests.

LeetCode problems need a browser that can reach
`datasets-server.huggingface.co` to show their text; if it can't, the
student sees a link to the original instead. The harness builds the
arguments from the test input (`nums=[2, 7], target=9`, with `list_node(...)`
and `tree_node(...)` for linked lists and trees), calls the method and prints
the result as JSON; the starter code carries LeetCode's usual imports and
the `ListNode`/`TreeNode` classes. Problems that change their input in place
(26) were left out, since their tests only check the method returns.
`build_leetcode.py --verify` runs the dataset's reference solutions through
the harness; that step was not run in the build container (running dataset
code was blocked there), so the tests were checked with our own solutions
instead (`tests/test_leetcode.py`).

Looked at and not added: **TACO** (Apache 2.0, tags for every problem) and
**APPS** (MIT) are only distributed through Hugging Face or a university
server, which this build environment cannot reach, and they overlap
CodeContests; **Project Euler** (CC BY-NC-SA) has no test cases and asks that
answers not be published; **Rosetta Code** (GFDL) tasks have no tests and are
written as demonstrations rather than exercises.

## Endpoints (teacher token)

```
GET  /api/teach/sources
GET  /api/teach/sources/{provider}/categories?language=
GET  /api/teach/sources/{provider}/questions?language=&category=&q=
GET  /api/teach/sources/{provider}/questions/{ref}?language=     preview
POST /api/teach/labs/{id}/import   {provider, ref}
POST /api/teach/labs/{id}/link     {provider, url, title}
POST /api/teach/questions/{id}/check   {code}    try a model answer
```

Student: `POST /api/sessions/{id}/check {code}` (409 if the question has no tests).

The Exercism provider needs outbound HTTPS to `raw.githubusercontent.com`.
Browser tests: `frontend/e2e/questions.mjs` (screenshots in
`thesis/latex/snapshots/questions/`) and `frontend/e2e/leetcode.mjs`
(`snapshots/leetcode/`).

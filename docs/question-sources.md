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
  lines ignored. `json`: both sides parsed and compared as JSON values.
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
(`categories`, `search`, `fetch`). Nothing is pre-stored: lists and questions
are fetched when the teacher browses, and the pick is fetched again and copied
into the lab as an ordinary question with `source` (provider, url, licence).

| Platform | Support | Why |
|---|---|---|
| Exercism | **Live**, with tests for Python and JavaScript | MIT-licensed, served from public GitHub repositories (`exercism/<track>`, `exercism/problem-specifications`). Canonical cases become stdin (arguments as JSON) / expected (return value as JSON) tests plus a small driver; cases about errors or other functions are skipped. C, C++ and Java exercises have no `main()`, so they import the statement with a stdin/stdout starter and no tests. |
| LeetCode | **Link only** | No public API; the GraphQL endpoint the site uses is internal and undocumented, and the problems are LeetCode's copyrighted content. |
| HackerRank | **Link only** | Its API covers a company's own tests only; its terms forbid copying any part of the service. |
| CodeChef | **Link only** | Public API shut down in 2020; pages are behind captchas. |

Link only means the teacher pastes a link to the original (checked against the
platform's host) and writes the question in their own words; the link stays
with the question. If a platform later offers an API or a licence, add a
provider class and list it in `providers/__init__.py`. A Codeforces provider
is a candidate: it has an official API for the problem list and tags, but not
for statements or tests.

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
Browser test: `frontend/e2e/questions.mjs` (screenshots in
`thesis/latex/snapshots/questions/`).

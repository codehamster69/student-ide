# Class competitions

A fun, class-wide mode where students race through a few questions and climb
a live leaderboard. It may later replace short quizzes.

**Correctness is always checked here.** Class labs treat correctness as
optional (tests there are only a self-check; effort is what counts). A
competition is the one place where it is scored: every question needs at
least one test case before the clock can start, and only passing tests earns
points.

## Using it

Teacher, at `/#/teach`:

1. **New competition**: title, instructions, clock in minutes (empty = no
   clock, you end it), and what students see on the board.
2. Add questions as for a lab (write them, or import from a platform), each
   with test cases. The *Competition* card lists which questions still need
   tests; the last test of a competition question cannot be removed.
3. Assign the class and set the lab to **Open**. Students see a gold
   competition card, enter the **lobby** and pick the name shown on the board
   (or keep their roll number). Questions stay hidden.
4. **Start the clock**. Questions appear for everyone at once. Students open
   a question in the normal editor (recorded exactly like a lab), **Run** as
   often as they like, and **Submit** to run the tests. **Back to board**
   and opening the question again (or a reload) picks up the code where they
   left it, in the language they were using; each visit is still its own
   recorded session, starting from a snapshot of that code.
5. **Live board** (`/#/teach/c/<lab id>`) is made for the projector:
   *Present* goes full screen and hides roll numbers. **End now** stops
   submissions early; otherwise the clock does. The podium shows at the end.

## Hand-in when time runs out

Nobody loses points for code they forgot to submit. When the clock runs out,
or the teacher presses **End now**:

1. Each student's editor sees the end (it checks the clock every 5 s), stops,
   sends its last edits and returns to the competition screen.
2. After a 20 s grace period (`compete.GRACE_S`) the server rebuilds each
   student's code for every question from the edits that reached it in time
   and grades it as a submission made at the end. A question counts as worked
   on when the code is not empty and differs from the starter code. Code
   identical to something the student already submitted is not graded again.
   Edits that arrive after the grace period are ignored.
3. Until grading is done, the student screen and the teacher's board say the
   final standings are coming; then the podium shows. Answers handed in this
   way are marked *At the bell* for the student and `auto` in the API.

It runs once per competition, in the background, started by whoever looks at
the competition next (students, the board, the lab page). If the runner fails
it is retried after 10 minutes. Competitions that had ended before this
feature shipped keep their results.

Ending early: the hand-in counts as a submission at the moment the clock was
stopped, so a full solve still earns the speed bonus left on the planned
clock, just as a last-second Submit would.

## Who sees the leaderboard

The full board (roll numbers, per-question tries and tests) is for the
competition's owner, its co-teachers and admins. It is linked from the
*Leaderboard* chip in the labs list, the *Leaderboard* button and top-five
preview on the competition's page, and the live class view. A competition
made before lab ownership has no owner and is admins-only until an admin
hands it over (see `docs/teaching.md`).

## Scoring

Per question a student keeps their best submission:

| | points |
| --- | --- |
| tests passed | 100 x passed / total (partial credit) |
| speed, only when every test passes and there is a clock | up to 50, scaled by the share of the planned time still left |

A wrong submission costs nothing. Ties go to whoever reached the score first.
The speed bonus is measured against the *planned* end, so ending early never
shrinks a bonus already earned. Runs and fixed errors never score.

Badges let more of the class stand out than just the top score: *First to
solve*, *Fastest on Qn*, *Solved them all*, *Most bugs fixed* (error followed
by a clean run, at least two). No badge or label ever marks someone as low.

## What students see

| Board setting | During | After |
| --- | --- | --- |
| Top 10 (default) | top ten + their own place | same |
| Everyone | the whole class ranked | same |
| Reveal at end | only their own score | top ten |

Other students' roll numbers never reach the browser; only the names they
picked. Hidden tests return pass/fail only, never their input or output.

## Integrity and the thesis

The leaderboard reads nothing from the review timeline or the detector
(`compete.py` imports neither, and a test checks that). A "moment worth a
conversation" stays between the teacher and the student and can never cost a
place or appear on the board. Competition sessions are ordinary sessions, so
keystrokes, runs and pastes are logged as in any lab.

**Competition sessions are measured separately** (Rohan, 2026-10-26: "that's
a different behaviour we can use"). A timed, competitive sitting is not a
normal lab, so the review timeline never mixes the two:

- a student's lab baseline (first four weeks) leaves competition sessions
  out, even inside those weeks;
- a competition session is compared only with the same student's sessions
  from their *other* competitions (leave one competition out), and is not
  scored until there are at least two of those;
- the timeline marks such sessions *Competition* and says what they were
  compared with.

The population-level settings (key-pair vocabulary, feature weights, prior)
still come from lab baselines.

## Any language

Set a competition's language to **Any language** (when creating it, or under
Session settings) for an open contest: each student picks C, C++, Java,
JavaScript or Python per question from the switcher above the editor.

- Tests are stdin/stdout, shared by every language. Starter code (and the test
  driver of an imported function-style problem) is kept per language in
  `questions.variants_json` (`{language: {starter_code, harness}}`); the
  question form shows one starter-code tab per language. A question whose
  tests need a driver opens only in the languages that have one
  (`grading.question_languages`).
- Importing from a platform fetches the problem in every language and keeps
  each language whose tests match the first one.
- Each language a student tries on a question is its own session
  (`POST /api/sessions {..., language}`), so switching back keeps the code.
  Submissions are graded in the session's language and store it
  (`submissions.language`); the hand-in at the bell takes the language edited
  last. The board shows the languages each row's points came from.
- Switching an existing competition to or from Any language moves each
  question's starter code into, or out of, that language's variant.
- Review timeline: a competition session is compared with the student's
  competition sessions in the same language once there are at least two,
  otherwise with all of them (`review.Reviewer.baseline_ids`).

## Similar submissions

Staff open **Similar submissions** from the competition panel or the board
(`#/teach/similar/<lab id>`). It is a pointer for a conversation, never a
verdict: it never says "copied", students never see it, and nothing on it
changes a score.

How (`backend/studentide/similarity.py`): the last submission of each student
per question and language is tokenised with names, layout, comments, string
and number literals and include/import lines normalised away; winnowing
fingerprints (8-token windows, window 4) pick candidate pairs; greedy string
tiling (runs of at least 8 tokens) measures them. Starter code and stretches
shared by half the class (at least 5 submissions) are masked; programs with
fewer than 15 tokens of their own are skipped. C and C++ are compared with
each other, other languages within themselves; a hand translation between
languages is not detected. Pairs from 30% are reported, the page shows 50%+
by default. The side-by-side view colours matching stretches alike on both
sides and shows typed vs pasted characters from the session's edit log, with
a link to each session's timeline.

Accuracy check: `python backend/scripts/eval_similarity.py` (corpus in
`backend/tests/fixtures/similarity/`, 6 problems x 3 independent solutions in
C/C++ and in Python) writes `thesis/latex/ablations/similarity/`. Independent
pairs: median 0.00, max 0.36. Disguised copies (renamed + reformatted,
+ rewritten constructs, + dead code every third statement): min 0.67, 97% at
0.7 or more.

API: `GET /api/teach/competitions/{lab_id}/similarity` and
`GET /api/teach/competitions/{lab_id}/similarity/{a}/{b}` (owner, co-teachers, admins).

## API

Teacher (admin token): `POST /api/teach/competitions`,
`GET|PATCH /api/teach/competitions/{lab_id}`, `POST .../start`, `POST .../end`.
Student: `GET /api/competitions/{lab_id}?student_id=`,
`POST /api/competitions/{lab_id}/join {student_id, handle}`,
`POST /api/sessions/{session_id}/submit {code}`.
Tables: `competitions`, `competition_players`, `submissions` (every graded
submission with its code), plus `labs.kind`. Grading is `grading.grade`.

## Tests

`backend/tests/test_compete.py` (lifecycle, lobby, hidden tests, board modes,
roster, scoring with partial credit, speed and ties, ending early, badges, no
detector imports). Browser: `node frontend/e2e/compete.mjs <dir> [light|dark]`
plays a whole competition with one browser student and six API students and
writes the screenshots in `thesis/latex/snapshots/compete/`.
`backend/tests/test_any_language.py` and `test_similarity.py` cover any-language
competitions and the similarity check; `node frontend/e2e/anylang.mjs <dir>`
runs both in the browser (screenshots in `thesis/latex/snapshots/anylang/`).

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
   often as they like, and **Submit** to run the tests.
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

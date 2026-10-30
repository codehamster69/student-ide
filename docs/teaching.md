# Teacher authoring: labs and questions

Teachers set up the sittings students record in. A **lab** is one sitting
(a weekly lab class, an assignment, or one of the staged study sessions) with
ordered **questions**, each holding a title, a prompt, optional starter code
that opens in the editor and a sample input that prefills the input box. A
lab is assigned to a roster of roll numbers, or to everyone who signs in.

## Using it

Open `/#/teach` and sign in with a teacher account (college Google sign-in, see
[deploy.md](deploy.md)); in dev mode enter the research token instead
(`STUDENTIDE_ADMIN_TOKEN`, the same one the review timeline uses). The header switches between **Labs** and
**Review**.

1. **New lab**: title and instructions for students.
2. **Add question**: title, prompt, starter code (Tab indents), sample input.
   Questions can be edited, reordered with the arrows, or removed while no
   student has recorded on them.
3. **Assigned to**: paste roll numbers (commas, spaces or new lines), click
   students who have already signed in, or tick *Everyone who signs in*.
   Roll numbers can be assigned before those students ever log in. With Google
   sign-in, full addresses work too and everything is upper-cased
   (`pg25cs07@iiitsurat.ac.in` becomes `PG25CS07`).
4. **Status**: *Draft* (only the teacher sees it), *Open* (assigned students
   see it and can start; needs at least one question), *Closed* (hidden from
   students, recordings kept). A lab with recordings cannot be deleted, only
   closed.
5. **Progress** shows, per student and question, who has started and who has
   finished (pressed Finish).

Students see their open labs above the practice tasks after consent. A lab
opens as **one sitting**: "Start lab" / "Continue lab" (or any question row)
opens the editor with every question of the lab as a tab, plus a question list
and Previous / Next in the side panel. Each question keeps its own code, undo
history, input, output and test results while the student moves between them.
"Finish lab" hands in the sitting. Opening the lab again later starts a new
sitting in which each question picks up the code where the student left it.

## How recordings link to it

`POST /api/sessions` takes `question_id` instead of `task_id`. The server
checks the lab is open and the student is on its roster, then stores on the
session row `lab_id`, `question_id` (also in `task_id`, so older analysis code
keeps working) and `question_json`, a copy of the question as the student saw
it. Every event belongs to a session, so every keystroke, edit and run is tied
to a lab and question through it; the event schema is unchanged (still v1).
Editing a question later changes what new sessions see, never what an old
recording was answering. Practice tasks from `tasks.json` still work and have
all three columns NULL. Older database files gain the columns on open.

### One sitting, one session per question

A sitting is not one session. Each question the student opens in a sitting
gets its own session (created on first visit), and all of them share a
`sitting_id` on the session row. So one session is still one question: the
detector's windows, the review timeline, the code replay, Check and the live
view all work per question exactly as before, and nothing has to split a
session by question afterwards. The `sitting_id` groups them back into the
lab visit for analysis.

- Switching questions logs `focus {target: "question", state: "out"}` on the
  session being left and `"in"` on the one returned to (a new question starts
  with its own `session_start` and `snapshot`). Window/page focus events go to
  the question on screen. The detector does not count a question switch as
  looking away, and a key gap that spans one is not a pause (the student was
  working on another question, not stuck).
- On "Finish lab" every session of the sitting ends; questions with code
  (different from the starter code) end as `submit`, untouched ones as `left`.
- In a later sitting, `POST /api/sessions` returns `resume_code`: the code of
  the student's latest session on that question (in the same language),
  rebuilt from its edits. The new session's start snapshot holds it, so replay
  still starts from it. Competitions do the same each time a student goes
  back to the board and opens a question again (see `docs/competitions.md`).
- Older sessions have `sitting_id` NULL (one question per visit).

Research API: `GET /api/sessions?lab_id=...`; the export includes the same
fields. The review timeline titles lab sessions by their question.

## Who sees which lab

Each lab and competition records the teacher who made it (`labs.owner_email`).
With Google sign-in a teacher sees and manages only the labs they own or were
added to as a co-teacher (`lab_teachers`), and only the sessions, review
timelines, replays, live views and competition boards of those labs. Lists
leave the rest out; a direct link answers 403 with `X-Refusal: not-yours`, and
the teacher screens show the message without signing out.

- Admins (`STUDENTIDE_ADMINS`, or made admin on `#/teach/people`), the admin
  token and dev mode see every lab.
- Labs made before ownership have no owner and are visible to admins only.
  An admin hands one over in the lab's **Teachers** panel ("Hand over").
- The owner (or an admin) shares a lab with co-teachers by college address.
  Co-teachers can do everything the owner can except change the sharing;
  student addresses are refused. Only admins change the owner.
- Sessions outside any lab (practice tasks) are admin-only.
- A student's baseline still uses all their lab sessions, whoever's lab they
  were in, so a session's evidence is the same for every viewer.

The Review tab opens on **Lab sessions**: one row per lab per day (a class
meeting) with its time, students and how many are worth a conversation; a row
opens that class's sessions student by student (`#/review/l/<lab>/<day>`).
"Every session in one list" (`#/review/all`) keeps the flat list.

## API (admin token)

| Method | Path | |
| --- | --- | --- |
| GET / POST | `/api/teach/labs` | list with counts / create `{title, description}` |
| GET / PATCH / DELETE | `/api/teach/labs/{id}` | detail with questions, roster, progress / `{title?, description?, status?, everyone?}` / delete (409 once recorded) |
| POST | `/api/teach/labs/{id}/questions` | `{title, prompt, starter_code, sample_input}` |
| PUT | `/api/teach/labs/{id}/order` | `{question_ids}` |
| PUT | `/api/teach/labs/{id}/roster` | `{student_ids, everyone}` |
| PUT | `/api/teach/labs/{id}/teachers` | `{co_teachers, owner_email?}` share; owner change is admin-only |
| PATCH / DELETE | `/api/teach/questions/{id}` | edit / remove (409 once recorded) |
| GET | `/api/teach/students` | students who have signed in |

Student side (no token): `GET /api/students/{id}/labs` returns open labs
assigned to that student with their own progress per question.

## Demo and tests

`python -m studentide.seed` now adds two labs: *Lab 5: Strings and
dictionaries* (open, assigned to DEMO01 to DEMO06, holding their assessed
sessions) and a draft *Lab 6*, both without an owner (admins only in Google
mode). Backend tests: `backend/tests/test_teach.py`, ownership in
`backend/tests/test_ownership.py` (browser check: `frontend/e2e/ownership.mjs`).
Browser check with screenshots: `node frontend/e2e/teach.mjs <dir> [light|dark]`
(teacher builds and opens a lab, a new student answers question 1, the test
reads the session back and checks its lab, question and events).

## Tests, languages and platform questions

Questions can carry optional tests (an ungraded Check for students; required
only in competitions), labs have a subject and a programming language, and
questions can be picked by topic and difficulty from Codeforces and CodeChef
(through the openly licensed CodeContests dataset, with tests), Exercism and
MBPP, or linked from LeetCode and HackerRank. See
[question-sources.md](question-sources.md).

While a lab is open, **Watch live** on its page opens the live class view; see [live.md](live.md).

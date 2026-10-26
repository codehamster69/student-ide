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

Students see their open labs above the practice tasks after consent. Picking
a question opens the editor with its starter code and sample input.

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

Research API: `GET /api/sessions?lab_id=...`; the export includes the same
fields. The review timeline titles lab sessions by their question.

## API (admin token)

| Method | Path | |
| --- | --- | --- |
| GET / POST | `/api/teach/labs` | list with counts / create `{title, description}` |
| GET / PATCH / DELETE | `/api/teach/labs/{id}` | detail with questions, roster, progress / `{title?, description?, status?, everyone?}` / delete (409 once recorded) |
| POST | `/api/teach/labs/{id}/questions` | `{title, prompt, starter_code, sample_input}` |
| PUT | `/api/teach/labs/{id}/order` | `{question_ids}` |
| PUT | `/api/teach/labs/{id}/roster` | `{student_ids, everyone}` |
| PATCH / DELETE | `/api/teach/questions/{id}` | edit / remove (409 once recorded) |
| GET | `/api/teach/students` | students who have signed in |

Student side (no token): `GET /api/students/{id}/labs` returns open labs
assigned to that student with their own progress per question.

## Demo and tests

`python -m studentide.seed` now adds two labs: *Lab 5: Strings and
dictionaries* (open, assigned to DEMO01 to DEMO06, holding their assessed
sessions) and a draft *Lab 6*. Backend tests: `backend/tests/test_teach.py`.
Browser check with screenshots: `node frontend/e2e/teach.mjs <dir> [light|dark]`
(teacher builds and opens a lab, a new student answers question 1, the test
reads the session back and checks its lab, question and events).

## Tests, languages and platform questions

Questions can carry optional tests (an ungraded Check for students; required
only in competitions), labs have a subject and a programming language, and
questions can be picked from Exercism (live) or linked from LeetCode,
HackerRank and CodeChef. See [question-sources.md](question-sources.md).

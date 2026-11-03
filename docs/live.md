# Live classroom view

Teachers can follow an open lab while it runs. Open **Live** in the teacher
area (`/#/live`), or **Watch live** on an open lab's settings page.

## What a teacher sees

**Class view** (`#/live/labs/<lab id>`), refreshed every 3 s, one card per
student on the roster (or everyone who started, for an "everyone" lab):

| Field | Meaning |
| --- | --- |
| State | Typing (edit in the last 20 s), Working (last 2 min), Quiet (longer), Other tab (the IDE window or tab is in the background), Not connected (the IDE stopped answering for 20 s), Finished, Left, Not started |
| Question | the question of the student's latest session in this lab |
| Activity | edits per 30 s over the last 10 minutes |
| Runs | how many, and the last run's error type if it failed |
| Tests | last Check result (labs with tests) |
| Pastes | paste count in the current session |
| Moments | "moments worth a conversation" the review timeline has found in this student's sessions of this lab, recomputed at most every 30 s; marked *new* when one appears while the page is open |

No code is shown in the class view.

**Editor view** (`#/live/sessions/<session id>`, refreshed every 2 s): a read-only
copy of the student's editor with their caret, lines changed in the last
few seconds tinted, recent runs with output, last test check and the
prompt. The server rebuilds the code from the edit events the recorder
already uploads every 2 s, applying only new events each time.

A teacher cannot type in a student's editor, and nothing from a live view
changes a mark or a competition score.

## Students are always told

- While a teacher has a student's editor open, that student's top bar shows
  **"<teacher name> is viewing your editor"** (the name from their Google
  account). While the lab's class view is open, students in the lab see a
  small **"Class view on"** pill.
- The IDE asks every 5 s (`GET /api/sessions/{id}/viewers`); the notice ends
  as soon as the teacher leaves the page, or within 12 s if their browser
  closes.
- Every view is logged in `live_views`: teacher, lab, session, student, and
  when it started and last refreshed. Consecutive refreshes are one row.
- The consent screen (version 2) says teachers can follow a lab live and open
  a read-only view of the editor, always announced by name. Students who
  agreed to the earlier text are asked again before their next session.

## Turning it down

`STUDENTIDE_LIVE` in the server environment:

| Value | Effect |
| --- | --- |
| `editor` (default) | class view and per-student editor view |
| `class` | class view only; no student code is ever shown live |
| `off` | no live viewing at all |

The consent screen follows the setting. Changing it does not ask students
again; bump `CONSENT_VERSION` in `backend/studentide/db.py` if the ethics
committee wants every student to re-read a changed text.

## Ethics

Live viewing goes beyond the original design (after-the-fact review only), so
it should be named in the ethics application: what is shown, that students
are told every time, that views are logged, and that it never feeds into
marks. If the committee prefers less, run with `STUDENTIDE_LIVE=class`.

## API

Teacher (teacher/admin account; admin token in dev mode):

    GET    /api/live/labs                        open labs, how many students are connected
    GET    /api/live/labs/{lab_id}               class view (also the view heartbeat)
    GET    /api/live/sessions/{session_id}       editor view (also the view heartbeat)
    DELETE /api/live/views?lab_id=|session_id=   the teacher left the page

Student: `GET /api/sessions/{session_id}/viewers` -> `{class_view, editor: [{name}], live}`.

Presence and the code cache are kept in memory, which suits the single
uvicorn worker the deployment runs; the viewing log is in the database.

End-to-end check with screenshots: `frontend/e2e/live.mjs`.

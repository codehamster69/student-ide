# Sandbox Labs: what students see

Where a student finds and works on Sandbox Labs. The catalogue and lab format are in
[sandbox-labs.md](sandbox-labs.md); the local runtime under it is in
[sandbox-runtime.md](sandbox-runtime.md).

## Home: "Sandbox labs"

`frontend/src/screens/SandboxLabs.tsx`, on the student home under the web labs.
`GET /api/sandbox/my/labs` gives one shelf per subject (colour, code, semester) with a card
per published lab: assignments, network ("Internet on", "Package sites only", "No internet"),
Assessed, due time, and, once grading is on the server, "n of m submitted" and "Closed".

- **Desktop app** (`window.studentDesktop` present): the card opens the lab. A lab with
  `min_desktop_version` above the app's version says "Update the app to open". The last opened
  lab is marked.
- **Website**: the same cards, not clickable, under "Open these in the Student IDE app" with a
  "Get the app" link from `/api/desktop/config` `download_url`. Labs run on the student's own
  machine, so there is no browser fallback (teachers have cloud previews; students do not).

## Lab workspace

`frontend/src/screens/SandboxLab.tsx` (App screen `sandbox`).

1. Opening: `GET /api/sandbox/my/labs/{id}` (statement, visible tests) and
   `studentDesktop.sandbox.openLab(id)` in parallel; `sandbox.progress` events drive a step line
   ("Getting the lab environment ready… → Starting your Linux instance… → Bringing back your files…").
   On failure the error and the failing setup-check rows are shown with their fixes, plus
   "your files are on the server, use another computer that passes the check".
2. Assignment rail: numbered chips with state (not started, in progress, submitted, all tests
   pass, n of m pass, grading…), `Ctrl/Cmd+1…9` to switch. Visited assignments stay mounted, so
   each keeps its editor and shell.
3. Files (the assignment folder via `sandbox.listFiles`, build outputs hidden), an editor
   (`FileEditor` + the recorder; saves with `sandbox.writeFile` 0.7 s after typing stops; the
   runtime syncs to the server), and a note when files were restored or a conflict copy was kept.
4. Right panel: Statement (with a one-time "How this lab works" card), Output, Tests (local Check
   of visible tests, "n more checked by your teacher"), Grade (server grade once submitted), stdin.
5. Terminal: xterm.js on `studentDesktop.terminal` in the assignment folder; "New shell" after
   `exit`. When a command ends the file list and the open file are refreshed.
6. Run (`Ctrl/Cmd+Enter`), Check, Submit (a confirm dialog; `sandbox.submit`, then the grade is
   polled from `GET /api/sandbox/my/labs/{lab}/submissions` while queued or grading).
7. Header: subject, environment, network, due, CPU and memory of the instance, a warning when the
   engine cannot enforce limits, and "Recorded for this lab".

## Recording

One opening is one sitting; each assignment visited is its own session:
`POST /api/sessions {student_id, sandbox_lab_id, assignment_id, sitting_id, client_meta}` (roster,
section, published and `opens_at` checked by `sandbox.py`). The row has `lab_id` = sandbox lab,
`question_id` = assignment, `context` NULL (study data) and `question_json.kind = "sandbox"` with
`main_file` and `language` from its extension.

| logged by | events |
|---|---|
| renderer, editor | `key`/`edit` with `path`, `snapshot` (start per file, periodic, run) with `path`, `cursor`, `clipboard`, `focus` |
| renderer, terminal | `key` with `surface` terminal / terminal-editor (+ `path` in vim/nano); pastes go to `terminal.paste` |
| renderer, rail | `focus {target: "question"}` out/in on switching, window focus |
| runtime (`sandbox.event`, by sessionKey) | `term_cmd`, `term_output`, `term_paste`, `run`, `pkg_install`, `net_conn` |

A file that changes on disk while open (vim, a formatter, git) is reloaded into the editor as an
edit with origin `reload`; the detector skips it like `reset`, so it is not counted as typing.

## Tests

`BASE=… TOKEN=… node frontend/e2e/sandbox-student.mjs [dir] [light|dark]` runs against a live
dev server with a stand-in bridge (same contract as `desktop/app`): website note, home, open,
type, terminal command, Run, Check, Submit, `Ctrl+2`, and then checks two sessions with one
sitting id holding editor, terminal and runtime events. The real runtime is covered by
`desktop/sandbox` (`npm run test:engine`). Backend: `tests/test_sandbox.py::test_session_per_sandbox_assignment`.

## Compared with other lab tools

See `thesis/plans/2026-11-08-sandbox-student-ux.md`.

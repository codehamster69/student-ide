# Architecture

One FastAPI process serves the API and the built React app from a single SQLite file.
Students write code in a CodeMirror editor that records every keystroke and edit; staff
author labs, watch them live, review sessions on a timeline, and run competitions.
Feature-level detail lives in the other files in `docs/`; this page is the map.

## Modules

### Backend (`backend/studentide/`)
| module | responsibility |
|---|---|
| `app.py` | `create_app` factory: student endpoints (sessions, events, run, check), research read API, mounts the routers below and `frontend/dist`. Endpoint list in its docstring. |
| `db.py` | SQLite schema and queries (students, sessions, events, runs, labs, questions, users…). Created on startup, no migration tool: new columns are added in code. |
| `schema.py` | Event schema v1 shared with `frontend/src/recorder.ts`; validates uploads. |
| `auth.py` | Dev mode (roll number) or Google mode (one college domain); roles from the address format plus admin overrides; `check_lab` decides who sees which sessions. |
| `teach.py` | Teacher authoring: labs, questions, rosters, ownership/sharing, sittings. |
| `compete.py`, `grading.py`, `similarity.py` | Timed competitions with leaderboard and hand-in; test cases; staff-only similar-submission check. |
| `live.py` | Live classroom view; students poll every 5 s, which doubles as presence. |
| `review.py` | Turns a recorded session into timeline evidence by running the frozen detector. |
| `learn.py` + `learn/<lang>/` | Always-open learning lab; lessons are Markdown files. |
| `attendance.py` | Roll Call integration: per-teacher keys, class groups, effective-participation rule, sends marks when a sitting/lab closes. |
| `runner.py`, `runner_service.py` | Compile/run student code (Python, C, C++, Java, JS) with limits; the service form runs in its own container. |
| `providers/` | Question sources (bundled CodeContests/Codeforces/LeetCode/original sets, live MBPP/Exercism, link-only platforms); `polyglot.py` adapts function-style questions to every language. |
| `workspaces.py` | Sandbox Labs: workspace snapshots (checked gzip tars) and setup recipes, so desktop work follows the student between machines. |
| `retention.py`, `backup.py` | Purge raw key timings after N days (consent promise); gzipped SQLite backups. |
| `replay.py`, `export.py` | Rebuild documents from edit events; load sessions for analysis. |
| `detector/` | Phase 2: habit features per 30 s window, per-student baseline, two-channel (identity/process) CUSUM, synthetic typists, synthetic evaluation. |
| `harness/` | Phase 4: labelled corpus, strict dev/test split by student, thesis detector vs baselines (scaled Manhattan, TypeNet-style LSTM, Nosi-style), LaTeX/CSV/PDF outputs. |

### Frontend (`frontend/src/`)
- `recorder.ts` + `capture.ts`: framework-free capture; buffers events and uploads batches.
- `editor/`: CodeMirror session, theme, resizable panes.
- `screens/`: student app (sign-in, consent, tasks, workspace, My attendance).
- `teach/`, `live/`, `review/`, `compete/`, `learn/`: staff and student areas, each with its own `api.ts`.
- `routes.ts`: every teacher-area hash route; `ui/`: design system (tokens, primitives, motion).

### Desktop (`desktop/`)
- `sandbox/` (`@studentide/sandbox`): local sandbox runtime, one Linux instance per (student, subject) through the
  docker/podman CLI; terminal, runs, workspace sync, setup check, schema v2 events. See `docs/sandbox-runtime.md`.

## Main data paths

**1. Recording a session.** Student signs in (`auth.py`) and accepts consent, opens a
lab question → `POST /api/sessions` creates a session tied to lab, question and sitting →
`recorder.ts` batches key, edit (with origin), clipboard, focus and snapshot events →
`POST /api/sessions/{id}/events` validates against `schema.py` and stores them in `events` →
Run/Check go through `runner.py` (or `STUDENTIDE_RUNNER_URL`) and are stored in `runs`/`checks`.

**2. Detection and review.** `review.py` loads a session's events → `detector/features.py`
builds windowed habit features (skipping `reset` edits) → `detector/detector.py` scores them
against the student's baseline with the config frozen in `thesis/evaluation/frozen-config.json`
→ the review timeline (`frontend/src/review/`) shows alarms with evidence and code replay.
Sessions with context `learn` or `preview` never become study data.

**3. Evaluation.** `harness dev` builds a corpus (synthetic, or recorded `--db` + labels),
tunes on dev students and freezes the config; `harness test` scores held-out students once,
appends to `test-ledger.jsonl`, and writes tables and graphs into `thesis/latex/`.

**4. Attendance.** A lab with attached Roll Call class groups opens per sitting; on close,
`attendance.py` computes effective participation (active minutes, typed characters, optional
run) from edit/run records only and `PUT`s one Roll Call session per group and day.

## External services
- **Google Identity**: sign-in tokens verified server-side with google-auth.
- **Roll Call** (`codehamsters/attendance`, Next.js on Vercel): `/api/v1` with the teacher's
  sync key; teacher linking via a shared link secret. See `docs/attendance.md`.
- **Question data**: Hugging Face datasets bundled as `providers/data/*.jsonl.gz` by
  `backend/scripts/`; MBPP and Exercism fetched live from GitHub.
- **Deployment**: Docker Compose on a GCP VM in India (`deploy/`): Caddy (HTTPS) → app,
  separate `runner` container, `backup` job. See `docs/deploy.md`.

## Key decisions
- **Python end to end**: logger, features and statistics share one language and data model.
- **CodeMirror 6**: every change is a transaction with an origin (typed, paste, undo…),
  exactly what authorship evidence needs.
- **SQLite**: one lab, one server; a single file is easy to back up and hand to analysis.
- **Two-channel CUSUM, not a classifier**: per-student baselines detect *change* of author
  with few labels; a flag starts a conversation, never a penalty.
- **Strict dev/test protocol with a ledger**: held-out results can't be tuned after the fact.
- **No webcam/screen capture**, raw key timings purged after a retention window.
- **Competitions always grade, labs don't**: effort counts in class, correctness in contests.
- **One branch per feature, one brain entry per step**: the thesis is written from `thesis/brain/`.

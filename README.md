# Student IDE

A free, open-source, self-hostable coding environment for college programming
labs. Students write, run and submit code in the browser or in a desktop app.
Teachers set labs, grade automatically and see how each submission was written.
It has been used by 271 students at IIIT Surat.

**What you get**

- **Browser editor** (CodeMirror 6) with runnable tasks, an always-open learning lab and
  timed contests, plus a large question bank: Codeforces, CodeChef and LeetCode-style
  problems with hidden tests, see [docs/question-sources.md](docs/question-sources.md).
- **Sandbox Labs**: each subject gets its own Linux environment, run locally in Docker or
  Podman by a desktop app that installs its own container engine. Students get files, a
  terminal and Run/Check/Submit.
- **Teacher tools**: labs, hidden-test auto-grading, gradebook, regrades, a live classroom
  view and lab attendance.
- **Authorship checks without proctoring**: it records how code is typed (key timing,
  edits, pastes, focus), never the webcam or screen. It flags a likely change of author
  partway through a session, and a flag only ever leads to a conversation, never a
  penalty. Raw keystrokes are deleted on a schedule.
- **One Docker image** behind Caddy with HTTPS, Google sign-in restricted to your college
  domain, an isolated code runner and backups, see [docs/deploy.md](docs/deploy.md).

**Use it at your college:** follow [docs/deploy.md](docs/deploy.md), or [Run it](#run-it)
below to try it locally. Issues and pull requests are welcome. MIT licensed.

## Research background

Student IDE began as the lab editor for the M.Tech thesis *"Who is at the keyboard?
Process-aware authorship continuity in programming assessment"* (IIIT Surat). The
detector, evaluation harness and thesis sources live in this repository too.

| phase | status |
|-------|--------|
| 1. Event-logging editor | done |
| 2. Feature extraction + CUSUM detector, synthetic data | done, see [docs/detector.md](docs/detector.md) |
| 3. Teacher timeline dashboard | done, see [docs/review.md](docs/review.md); labs and questions in [docs/teaching.md](docs/teaching.md) |
| 4. Evaluation harness | done on synthetic data, see [docs/evaluation.md](docs/evaluation.md) |
| 6. Sandbox Labs runtime (desktop) | local Linux instance per subject in Docker/Podman, terminal, runs, workspace sync, setup check, schema v2; see [docs/sandbox-runtime.md](docs/sandbox-runtime.md) |
| Sandbox Labs monitoring | file watcher (`fs_change`, `port_open`), 5-minute offline journal with signed hash-chained batches, review lanes and "appeared without typing", live terminal mirror, readiness board, consent v3, attendance; see [docs/sandbox-runtime.md](docs/sandbox-runtime.md) and [docs/review.md](docs/review.md) |
| Desktop app (Sandbox Labs) | Electron window on the site, browser sign-in, bridge for local labs, auto-update from GitHub Releases through the server (unsigned builds for now), public download page `#/download` picks the installer for the visitor's computer, see [docs/desktop.md](docs/desktop.md) |
| 5. College deployment (pilot) | ready to deploy: Google sign-in for @iiitsurat.ac.in, HTTPS, backups, see [docs/deploy.md](docs/deploy.md) |
| Sandbox Labs (teacher side) | subjects, environments, sandbox labs, shared library and capped "Try as a student" previews, server grading of submissions (hidden tests, gradebook, regrade), see [docs/sandbox-labs.md](docs/sandbox-labs.md); desktop app and local sandboxes in progress |
| Sandbox Labs (student side) | home shelf per subject; in the desktop app a lab workspace with files, editor, terminal, Run/Check/Submit and grade; website lists them with "Open in the Student IDE app"; see [docs/sandbox-student.md](docs/sandbox-student.md) |

## Stack

- **Backend**: Python 3.11+, FastAPI, SQLite (`backend/studentide`). Python keeps the
  logger, feature extraction and statistics in one language.
- **Frontend**: TypeScript, CodeMirror 6, Vite (`frontend/`). CodeMirror exposes every
  document change as a transaction with its origin (typed, pasted, undo, autocomplete…),
  which is exactly what the logger needs. The UI around the editor is React + Tailwind CSS
  + Motion, built on a shared design system in `frontend/src/ui/` (see its README) that the
  teacher dashboard will reuse. Event capture lives in framework-free `recorder.ts` and
  `capture.ts`.

## Run it

```bash
# backend
python -m venv .venv && . .venv/bin/activate
pip install -e 'backend[dev]'

# frontend (build once; the backend serves frontend/dist)
cd frontend && npm install && npm run build && cd ..

export STUDENTIDE_ADMIN_TOKEN=change-me      # enables the research read API
uvicorn studentide.app:create_app --factory --host 0.0.0.0 --port 8000
```

Open http://localhost:8000, enter a roll number, accept the consent notice, pick a task.
This is dev mode. For a real deployment (college Google sign-in, HTTPS, isolated
code runner, backups, raw-keystroke deletion) see [docs/deploy.md](docs/deploy.md).
For frontend development run `npm run dev` in `frontend/` (proxies `/api` to port 8000).

## What gets recorded

See [docs/event-schema.md](docs/event-schema.md). In short: key down/up with
high-resolution timestamps, every edit with its origin, clipboard paste/copy/cut,
cursor moves, runs with full output, editor/window/tab focus, and periodic code
snapshots, all per student and per session.

## Detector (phase 2)

```bash
pip install -e 'backend[analysis]'
python -m studentide.detector.synth --out synthetic/         # example sessions as JSONL
cd backend && python -m studentide.detector.evaluate --typists 60 --thesis ../thesis/latex
```

Simulated typists, 30-second habit features, per-student baselines and a
two-channel CUSUM switch detector. See [docs/detector.md](docs/detector.md).

## Evaluation harness (phase 4)

```bash
cd backend
python -m studentide.harness dev  --thesis ../thesis/latex   # design on dev students, freeze the config
python -m studentide.harness test --thesis ../thesis/latex   # score the held-out students once (logged)
```

Strict student-level dev/test split, the thesis detector against scaled
Manhattan, TypeNet-style and Nosi-style baselines, RQ1/RQ2/RQ4 tables and
graphs into `thesis/latex/`. Runs on recorded study data with `--db` and a
labels manifest. See [docs/evaluation.md](docs/evaluation.md).

## Tests

```bash
cd backend && pytest                    # API, schema, runner, replay, generator, features, detector
node frontend/e2e/record.mjs            # browser end-to-end (needs a running server)
node frontend/e2e/screenshots.mjs out/ light   # thesis screenshots of every screen (or dark)
```

## Caveats

- The code runner (`runner.py`) uses a timeout and resource limits but is not a
  security sandbox. Keep the server on the lab network, or run code in a container.
- Student login is just a roll number; the lab is supervised. Teacher auth comes with phase 3.

## Review timeline (phase 3)

```bash
python -m studentide.seed --db data/demo.sqlite3     # simulated students to look at
STUDENTIDE_DB=data/demo.sqlite3 STUDENTIDE_ADMIN_TOKEN=change-me uvicorn studentide.app:create_app --factory
```

Students also have an always-open learning lab (concept lessons with runnable examples and small exercises), see [docs/learning-lab.md](docs/learning-lab.md).

Sandbox Labs (`#/sandbox`): teachers create subjects with a Linux environment built from a tool checklist, labs of assignments with tests and a reference solution, share labs to a library, and try any lab in a short cloud preview. The lab wizard imports questions, sets up environments by hand in a terminal, sets grading and late policy, and keeps a history of mid-lab fixes with regrade and undo. Students run them in the desktop app. See [docs/sandbox-labs.md](docs/sandbox-labs.md).

Labs can mark attendance in Roll Call (the attendance site): attach class groups to a lab, and students who effectively took part are marked present in their own group when the lab closes. See [docs/attendance.md](docs/attendance.md).

The desktop app (Sandbox Labs) installs with no prerequisites: its installer sets up its own container engine (a WSL2 distro on Windows, a Lima VM on macOS, rootless Podman on Linux), pulls the lab images and checks a lab starts. See [docs/desktop-installer.md](docs/desktop-installer.md).

Open http://localhost:8000/#/review for the timeline and http://localhost:8000/#/teach to create labs and questions. Details in [docs/review.md](docs/review.md) and [docs/teaching.md](docs/teaching.md).

# Student IDE

The lab code editor for the M.Tech thesis *"Who is at the keyboard? Process-aware
authorship continuity in programming assessment"* (IIIT Surat).

It records how code gets written (key timing, edits, pastes, runs, focus changes),
never the webcam or screen, so that later stages can learn each student's own
habits and spot a likely change of author partway through a session. A flag only
ever leads to a conversation, never a penalty.

| phase | status |
|-------|--------|
| 1. Event-logging editor | done |
| 2. Feature extraction + CUSUM detector, synthetic data | done, see [docs/detector.md](docs/detector.md) |
| 3. Teacher timeline dashboard | planned |
| 4. Evaluation harness | planned |

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

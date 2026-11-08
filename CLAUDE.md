# Student IDE

Lab code editor for Rohan's M.Tech thesis (IIIT Surat): records *how* code is written
(key timing, edits with origin, pastes, runs, focus) to detect a mid-session change of
author. A flag only ever leads to a conversation. Architecture: see docs/ARCHITECTURE.md.

## Stack
- Backend: Python 3.11+ (Docker uses 3.12), FastAPI, SQLite, NumPy; google-auth for sign-in
- Frontend: TypeScript 7, React 18, CodeMirror 6, Vite 8, Tailwind CSS v4, Motion
- Deploy: one Docker image run three ways (app, code runner, backup) + Caddy, Compose on a GCP VM
- Thesis: LaTeX (latexmk + biber) in `thesis/latex/`

## Commands
```bash
python -m venv .venv && . .venv/bin/activate && pip install -e 'backend[dev]'   # [analysis] adds matplotlib
cd frontend && npm install && npm run build          # backend serves frontend/dist
npm run typecheck                                     # (in frontend/) tsc --noEmit
STUDENTIDE_ADMIN_TOKEN=change-me uvicorn studentide.app:create_app --factory --port 8000
npm run dev                                           # (in frontend/) Vite, proxies /api to :8000
cd backend && pytest -q                               # whole suite
cd backend && pytest -q tests/test_compete.py::test_lobby_then_live_then_scored   # one test
BASE=http://127.0.0.1:8000 TOKEN=change-me node frontend/e2e/record.mjs   # e2e, needs running server
node frontend/e2e/screenshots.mjs out/ light          # thesis screenshots (or dark)
python -m studentide.seed --db data/demo.sqlite3      # demo data for the review timeline
cd backend && python -m studentide.harness dev --thesis ../thesis/latex   # test = held-out, run once, logged
cd desktop/app && npm install && npm run build      # desktop shell; smoke: BASE=… GBASE=… xvfb-run -a node e2e/smoke.mjs
cd thesis/latex && latexmk -pdf main.tex              # thesis PDF into build/
cd desktop/installer && npm test                     # installer tests; npm run package -- --linux packages the app
```
No linter is configured; `tsc --noEmit` (part of `npm run build`) is the frontend check.

## Layout
- `backend/studentide/` FastAPI app; `app.py` is the HTTP API (endpoint list in its docstring)
- `backend/studentide/detector/` phase 2 features + two-channel CUSUM + synthetic typists
- `backend/studentide/harness/` phase 4 evaluation (dev/test split, baselines, LaTeX outputs)
- `backend/studentide/providers/` question sources; `data/*.jsonl.gz` and `data/sets/` are bundled
- `backend/studentide/learn/<lang>/` learning-lab lessons as Markdown files
- `backend/scripts/` one-off builders for bundled question data (`build_*.py`)
- `backend/tests/` pytest, one file per feature
- `frontend/src/` `recorder.ts` + `capture.ts` (framework-free event capture), `screens/` (student app),
  `teach/`, `live/`, `review/`, `compete/`, `learn/`, `sandbox/` (staff areas), `ui/` (design system, see its README)
- `desktop/sandbox/` Sandbox Labs runtime (Node+TS, no Electron): `npm test`; `SANDBOX_IT=1 npm run test:engine` needs Docker
- `frontend/e2e/*.mjs` Playwright scripts, one per feature, run against a live server
- `docs/` one doc per feature (detector, review, teaching, deploy, attendance…)
- `desktop/app/` Electron shell (`src/shared/contract.ts` = bridge contract, `src/main/modules/<ns>.ts` per namespace);
  `desktop/installer/`, `desktop/sandbox/` its engine and lab packages. See docs/desktop.md
- `desktop/installer/` one-click engine setup (WSL2 distro / Lima / Podman) + electron-builder packaging; see docs/desktop-installer.md
- `deploy/` Compose, Caddyfile, GCP startup script
- `thesis/` brain log, LaTeX, evaluation ledger, progress diagram, plans

## Conventions
- Routes: teacher-area hash URLs come only from `frontend/src/routes.ts` (`#/<area>/<collection>/<id>/<view>`);
  keep old links working by rewriting them there.
- Event schema lives in `backend/studentide/schema.py`; bump `SCHEMA_VERSION` on any payload change
  and update `docs/event-schema.md`.
- Every module opens with a docstring saying what it is for; keep that.
- UI uses semantic tokens (`bg-surface`, `text-muted`…) from `frontend/src/ui/tokens.css`, never raw colours,
  so light and dark both work.
- Study data stays clean: `sessions.context` marks non-study sessions (`learn`, `preview` from View as
  student) and edits with origin `reset` are skipped by the detector. Exclude any new non-study source too.
- Thesis log: each notable change adds `thesis/brain/entries/YYYY-MM-DD-NN-slug.md` (from `TEMPLATE.md`,
  append-only, `supersedes:` to reverse). Screenshots go to `thesis/latex/snapshots/`, TikZ to `flowcharts/`.
- After a PR, update `thesis/progress/STATUS.md` + `phase-diagram.html` when a phase step changes.
- Feature work also updates the matching `docs/*.md` and the README table.
- Branch from `origin/main`; one PR per feature.

## Gotchas
- Env: `STUDENTIDE_ADMIN_TOKEN` (research API; unset = disabled), `STUDENTIDE_DB` (default
  `data/studentide.sqlite3`), `STUDENTIDE_GOOGLE_CLIENT_ID` (set = Google mode, roll-number login off),
  `STUDENTIDE_ADMINS`, `STUDENTIDE_RUNNER_URL` (remote runner), `STUDENTIDE_LIVE` (editor|class|off),
  `STUDENTIDE_ROLLCALL_LINK_SECRET` + `STUDENTIDE_ATTENDANCE_URL` (Roll Call), `STUDENTIDE_PREVIEW_*` (Sandbox Labs
  previews; `STUDENTIDE_PREVIEW_DOCKER=1 STUDENTIDE_PREVIEW_BUILD_LOCAL=1` in dev). Full list in docs/deploy.md.
- Sandbox Labs: the lab definition `studentide.sandbox-lab/1` (docs/sandbox-labs.md) is a contract with `desktop/`;
  keep it additive. Previews are teachers only and never study data; students run labs locally.
- `harness/report.py` outputs under `thesis/latex/` (tables, graphs, ablations) are generated: rerun, don't edit.
- `harness test` is a once-only held-out run recorded in `thesis/evaluation/test-ledger.jsonl`; don't rerun casually.
- `thesis/evaluation/frozen-config.json` is the frozen detector config and is copied into the Docker image.
- `runner.py` has limits but is not a sandbox; in deployment code runs in the separate `runner` container.
- Cloud sessions: npm downloads can stall; `bun install` is a working fallback (bun.lock is kept).
- The e2e scripts need a running server with a built frontend and the same admin token.
- Roll Call (codehamsters/attendance) shares Google client, admins and link secret; change both sides together.

## Compact instructions
Keep: the feature/PR being built, schema or detector changes, which thesis brain entries and docs
were added, failing tests, and any study-data exclusion decisions.

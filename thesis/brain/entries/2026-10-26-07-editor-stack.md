---
date: 2026-10-26
type: decision
title: Editor stack is FastAPI + SQLite backend, TypeScript + CodeMirror 6 frontend
thesis-chapter: 04-system-design
---

## What happened

The phase 1 event-logging editor was built as a Python FastAPI service
(`backend/studentide`) storing everything in one SQLite file, with a
TypeScript single-page editor (`frontend/`) built on CodeMirror 6 and Vite.
The backend also runs students' Python code and serves the built frontend.

## Why

- **Python backend**: phases 2 and 4 (feature extraction, CUSUM, evaluation,
  fairness analysis) are numeric work that belongs in Python. Keeping the
  logger in the same language means one data model and one `pip install`.
- **SQLite**: about 80 students in supervised labs is a tiny write load;
  WAL mode copes. A single file is easy to back up, hand to analysis code
  and delete under the data-retention policy. Postgres can replace it later
  without changing the event schema.
- **CodeMirror 6 over Monaco**: every document change is a transaction with
  a `userEvent` origin (typed, pasted, dropped, undo, autocomplete,
  indent), so edits can be logged exactly and replayed. Monaco hides more of
  this and is much heavier.
- **Server-side runner** (subprocess with timeout and resource limits)
  rather than in-browser Pyodide: run results are recorded where the
  student cannot alter them, and lab machines need no large download.
  It is not a security sandbox; a container is needed before any use
  outside a trusted lab network.

## Evidence

`README.md`, `backend/studentide/app.py`, `backend/studentide/runner.py`,
`frontend/src/`. Architecture figure: `thesis/latex/flowcharts/editor-dataflow.tex`.

## Follow-ups

- Containerised runner (nsjail/Docker) before remote use (RQ3, phase 3 study).
- Teacher authentication arrives with the timeline dashboard (build step 3).

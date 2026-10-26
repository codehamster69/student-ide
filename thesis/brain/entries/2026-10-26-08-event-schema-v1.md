---
date: 2026-10-26
type: decision
title: Event schema v1 — what the editor records and at what precision
thesis-chapter: 04-system-design
---

## What happened

Fixed the first version of the event schema (`backend/studentide/schema.py`,
explained in `docs/event-schema.md`, and suitable for appendix
`A-event-schema.tex`). Every event has `seq` (per-session counter), `t`
(ms since session start, browser high-resolution clock, rounded to 1 µs),
`type` and a validated `data` payload. Types: `key` (down/up, physical
`code`, coarse class, modifiers), `edit` (CodeMirror origin + change
ranges), `clipboard` (paste/copy/cut with text), `cursor` (throttled to
10/s), `run` (link to full run record, error type), `snapshot` (full text
at start, every 30 s if changed, before each run, at end), `focus`
(editor/window/tab), `session_start`/`session_end`.

## Why

- **Key timing from `KeyboardEvent.timeStamp`**, not when our handler ran:
  this is the closest a browser gets to the hardware event and is what
  digraph latency and hold time need.
- **Physical `code`, not the character**: layout-independent, enough for
  digraph features, and the typed text is already in the edit stream.
- **Edits as change ranges with origin** let phase 2 tell typed from pasted
  from autocompleted code and rebuild the program at any moment (needed for
  AST build-order features). Snapshots are checkpoints, and replay is
  verified against them, so dropped events are detectable, not silent.
- **Client-assigned `seq` + idempotent upload**: lab Wi-Fi drops; the
  browser retries until acknowledged and the server ignores duplicates,
  so the record has no gaps or double counts.
- **Focus/visibility events**: switching away and returning to type fluently
  is the transcription signature (condition D, RQ2).
- Offsets are UTF-16 units, as in JavaScript; the Python replay matches.

## Evidence

Unit tests in `backend/tests/test_api.py` (idempotent ingest, per-event
validation, replay incl. emoji). Browser end-to-end check
`frontend/e2e/record.mjs`.

## Follow-ups

- Phase 2: delete raw `key` events once a student's baseline summary is
  built (promised on the consent screen).
- Bump `SCHEMA_VERSION` for any payload change.

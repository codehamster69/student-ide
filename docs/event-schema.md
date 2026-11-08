# Event schema (v1)

The editor records one stream of events per **session** (one student working
on one task in one sitting). Everything later in the pipeline (30-second
feature windows, baselines, CUSUM, the teacher timeline) is computed from
this stream, so it is kept small, append-only and versioned.

The source of truth is `backend/studentide/schema.py`; this page explains it.

## Storage

SQLite, one file (`data/studentide.sqlite3` by default, `STUDENTIDE_DB` to change).

| table      | one row per | key columns |
|------------|-------------|-------------|
| `students` | student     | `id` (roll number or pseudonym), `consented_at` |
| `sessions` | sitting     | `id`, `student_id`, `task_id`, `started_at`, `ended_at`, `end_reason`, `schema_version`, `client_meta` (browser, screen, timezone; `client`: `{kind: "web"}` or `{kind: "desktop", app_version, platform, arch, chrome, device, portable}` from the desktop app, see desktop.md), `lab_id`, `question_id`, `question_json` (the question as the student saw it; all three NULL for practice tasks) |
| `labs`, `questions`, `lab_students` | teacher authoring | a lab (title, instructions, status draft/open/closed, `everyone`), its ordered questions (title, prompt, starter code, sample input) and its roster of roll numbers. See [docs/teaching.md](teaching.md). |
| `events`   | event       | `(session_id, seq)` primary key, `t`, `type`, `data` (JSON), `received_at` |
| `runs`     | Run click   | full `code`, `stdin`, `stdout`, `stderr`, `exit_code`, `duration_ms`, `error_type` |

## Envelope

| field  | meaning |
|--------|---------|
| `seq`  | per-session counter from 0, assigned in the browser. Uploads are retried until acknowledged and the server ignores duplicate `seq`, so no event is stored twice. Gaps in `seq` mean lost events. |
| `t`    | milliseconds since the session started, from the browser's high-resolution monotonic clock (`performance.now()` / `KeyboardEvent.timeStamp`), microsecond-rounded. Use this, not server time, for timing features. |
| `type` | one of the types below |
| `data` | payload for that type |

`t` follows the browser's own event timestamps, so a key event can carry a `t`
a fraction of a millisecond earlier than the event before it in `seq`. Sort by
`seq` for causal order, by `t` for timing.

## Types

**`key`** — every physical key press and release inside the editor.
`action` (`down`/`up`), `code` (layout-independent `KeyboardEvent.code`, e.g. `KeyA`),
`cls` (letter, digit, space, enter, tab, punct, backspace, delete, nav, modifier, other),
`repeat`, and `shift`/`ctrl`/`alt`/`meta`. Hold time = up − down of the same `code`;
digraph latency = down(k₂) − down(k₁). The typed character is not stored here; the
`edit` stream has the text.

**`edit`** — each change to the document. `origin` is CodeMirror's user event
(`input.type`, `input.paste`, `input.drop`, `input.complete` (autocomplete), `delete.backward`,
`delete.forward`, `delete.selection`, `undo`, `redo`, `input.indent`, ...).
`changes` is a list of `[from, to, inserted]` in pre-edit coordinates,
`len_before` / `len_after` are the document lengths. Offsets are UTF-16 code units
(JavaScript's), so `replay.py` works in UTF-16 too.

**`clipboard`** — `paste`, `copy` or `cut` in the editor, with `length`, `lines` and the
`text` (first 20 000 characters, `truncated` flag). For a paste, the matching `edit`
with origin `input.paste` follows immediately.

**`cursor`** — selection moves that are not edits (clicks, arrow keys), at most one
per 100 ms: `anchor`, `head`, `line`.

**`run`** — the student ran the program: `run_id` (row in `runs`), `code_sha256`,
`exit_code` (null on timeout), `duration_ms`, `error_type` (`SyntaxError`,
`NameError`, `Timeout`, ... or null when it ran cleanly).

**`snapshot`** — full document text with `reason`: `start`, `periodic` (every 30 s if
changed), `run` (just before each run) and `end`. Replay checks itself against these.

**`focus`** — `target` `editor` / `window` / `page` (tab visibility) and `state` `in` / `out`. `question`
  (added 2026-10-27, still v1 as every older event stays valid): in a lab
  sitting, the student moved to another question (`out`) or came back to this
  one (`in`); see `docs/teaching.md`.
Long "out" gaps followed by a burst of fluent typing are the classic transcription signature.

**`session_start` / `session_end`** — `wall_clock_ms` anchors `t` to real time;
`session_end.reason` is `submit` (Finish button) or `pagehide` (tab closed).

## Reading the data

```python
from studentide.db import Database
from studentide.export import load_session
from studentide.replay import replay

db = Database("data/studentide.sqlite3")
events = load_session(db, session_id)
for ev, code_now in replay(events):
    ...  # code_now is the document right after ev
```

or export everything to JSONL: `python -m studentide.export --db data/studentide.sqlite3 --out export/`.

## Privacy notes

- No webcam, microphone or screen capture. Keys are logged only while the editor has focus.
- The consent screen states what is recorded; sessions cannot start without consent.
- Research read endpoints need a teacher account (Google mode) or `STUDENTIDE_ADMIN_TOKEN`
  (dev mode), and are off when neither is configured.
- Raw `key` events are deleted once due (a student's baseline sessions when the four
  baseline weeks end, any session after `STUDENTIDE_RAW_KEY_DAYS`, default 28) after the
  detector's window features are stored in `session_windows`; the session is stamped
  `keys_purged_at`. See `backend/studentide/retention.py` and [deploy.md](deploy.md).

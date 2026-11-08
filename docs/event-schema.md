# Event schema (v2)

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

### Version 2 (Sandbox Labs, desktop app)

Additive: every v1 batch is a valid v2 batch and the server accepts both
(`SUPPORTED_VERSIONS`). Built by `desktop/sandbox` (see
[sandbox-runtime.md](sandbox-runtime.md)) and logged by the same recorder.

- **`key.surface`** `editor` (default) / `terminal` (shell prompt) /
  `terminal-editor` (vim, nano… in the terminal, with **`key.path`** = the file).
  Only `editor` keys feed the detector's identity channel until terminal typing
  is tested on the dev split.
- **`edit.path`**, **`snapshot.path`**: the file in a multi-file workspace (null =
  the one document of a web session). The detector replays each file separately;
  `replay()` follows the main file (the first one seen) unless given a path.
- **`run.source`** `button` / `test` / `terminal` and **`run.command`**. A compile
  or run command typed in the terminal (`gcc`, `make`, `./main`, `python3 x.py`…)
  is logged as a `run` with `run_id` `t-…` (no row in `runs`), so the process
  channel counts it.
- **`term_cmd`** — a command line from the terminal's shell hooks: `term_id`,
  `phase` (`start` / `end`), `command`, `cwd`, and at `end` `exit_code` and
  `duration_ms`. Best effort: the student has sudo and can remove the hooks.
- **`term_output`** — per command: `bytes` written and an escape-free `tail` (2 KB).
- **`term_paste`** — a paste into the terminal: `length`, `lines`, `text` (20 000
  characters), `truncated`, `sha256`.
- **`pkg_install`** — a package command that succeeded: `manager` (apt, pip,
  npm, cargo, go, conda, gem), `action`, `packages`, `command`. Feeds the setup recipe.
- **`net_conn`** — the instance reached a new host through the registries-only
  proxy: `host`, `port`, `allowed`. Host names only, never contents.

### Version 3 (Sandbox Labs: watcher, signed batches)

Additive again (`SUPPORTED_VERSIONS = (1, 2, 3)`).

- **`fs_change`** — a file in an assignment folder changed and the app did not
  write it (the sidecar watcher, see [sandbox-runtime.md](sandbox-runtime.md)):
  `path`, `size`, `sha256`, `origin` (`terminal-editor` = saved from vim/nano,
  `terminal` = written by a command, `outside` = no command we could see),
  `command`, `deleted`, `binary`, and for text files `added` (the new lines,
  20 000 characters), `added_lines`, `removed_lines`, `diff` (8 KB), `truncated`.
  Editor scratch files (`.swp`, `4913`, `~` backups) are never reported.
- **`port_open`** — a program started or stopped listening: `port`, `process`, `open`.
- **Signed batches.** The desktop app wraps each batch as
  `{"signed": {"payload": "<json>", "sig": "<base64>", "device_id": "…"}}`, where
  the payload is `{session_id, batch_seq, prev_hash, wall_ms, mono_ms, offline_ms,
  events}`. The key is an Ed25519 key per install (`POST /api/devices`); the
  server checks the signature and that `prev_hash` is the previous batch's hash,
  and stores the batch row in `event_batches` with `problem` set to
  `bad_signature`, `chain_break`, `rewritten` or `other_device` when it does not
  check out. Events are never dropped for a problem; the review shows it as a
  record break. Web batches stay unsigned.

None of the v3 events feed the detector (see the thesis brain entry
`2026-11-08-13-sandbox-monitoring-detector-feed.md`); they feed the review's
evidence lanes.

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

# Review timeline (phase 3)

The teacher / interviewer screen. It shows, for one recorded session, where
the student's habits drifted from their own baseline, with the code replayed
at any moment. A highlighted moment is a reason for a conversation, never a
penalty, and the screen says so wherever a result is shown.

## Try it with demo data

```bash
pip install -e 'backend[dev]'
cd frontend && npm install && npm run build && cd ..
python -m studentide.seed --db data/demo.sqlite3          # 6 simulated students, 36 sessions, ~6 s
STUDENTIDE_DB=data/demo.sqlite3 STUDENTIDE_ADMIN_TOKEN=change-me \
  uvicorn studentide.app:create_app --factory --port 8000
```

Open http://localhost:8000/#/review and enter the token. The seed refuses an
existing file, so demo sessions never end up in a real database.

Screenshots for the thesis: `BASE=http://127.0.0.1:8000 TOKEN=change-me node frontend/e2e/review-screenshots.mjs <dir> [light|dark]`
(output in `thesis/latex/snapshots/review/`).

## How it works

| piece | file |
|-------|------|
| evidence for a session (channels, moments, events) | `backend/studentide/review.py` (`Reviewer`) |
| replay data (initial text, edits, key times) | `review.replay_data` |
| API (admin token) | `/api/review/{config,labs,students,sessions,sessions/{id},sessions/{id}/replay}`; teachers see only their own labs (see `docs/teaching.md`) in `app.py` |
| conversation outcomes | `PUT /api/review/sessions/{id}/outcome`, table `moment_outcomes` (`db.py`), `review.attach_outcomes`, `pilot.outcome_counts` |
| demo data | `backend/studentide/seed.py` |
| screens | `frontend/src/review/` (lazy-loaded at `#/review`) |

- **Baseline**: a student's sessions in the 28 days after their first one.
  At least 2 are needed before anything is scored. A baseline session is
  scored against the *other* baseline sessions and labelled as a baseline
  check.
- **Detector = the frozen evaluation config.** `load_settings()` reads
  `thesis/evaluation/frozen-config.json` (or `$STUDENTIDE_CONFIG`), so the
  screen runs exactly what the harness evaluated: each channel's window
  length (typing rhythm and key-pair timing 30 s, way of working 90 s), its
  CUSUM k, the key-pair channel, the population prior for short baselines
  and the thresholds h calibrated on the dev students
  (`operating_point` in the config). Without the file it falls back to a
  built-in copy. `STUDENTIDE_H="identity=…,pairs=…,process=…"` overrides h,
  e.g. after calibrating on the class's real data. `GET /api/review/config`
  shows what is in force and where it came from.
- **Population parts from the class**: once 3 students have a baseline, the
  ICC feature weights, the key-pair vocabulary (the class's most-typed key
  pairs) and the population prior are fitted on every student's baseline
  sessions, just as the harness fits them on its training students. Before
  that: equal weights, the frozen vocabulary, no prior.
- **Lanes**: each channel's trace carries its own window grid
  (`start`/`end`/`window_s`), so the 90 s process lane and the 30 s typing
  lanes line up on one time axis.
- **Moments**: CUSUM restarts after an alarm, so a lasting change raises a
  chain of alarms where each starts at the previous one. `episodes()` merges
  a chain into one moment (estimated start, first alarm, last alarm).
- **Why this moment**: for each moment, the features of that channel that
  moved most between the estimated start and the first alarm, as the
  median over those windows vs the baseline centre, in the student's own
  spread units (the detector's own z), weighted like the detector.
- **Replay**: the browser applies the recorded edits itself (UTF-16 offsets
  match JavaScript string indices) with checkpoints every 200 edits; checked
  against all 524 stored snapshots of eight demo sessions with no mismatch.
- **Caching**: window features are cached in memory per session and event
  count, and warmed in a background thread at start-up when the token is
  set (36 demo sessions take ~6 s cold).

## Conversation outcomes

Teachers talk through review moments with students as part of teaching. After
that conversation, each moment card takes an optional one-tap note of how it
went: **Explained, own work**, **Had help**, **Copied** or **Not discussed**.
Tapping the chosen one again clears it.

- **Stored per moment**: table `moment_outcomes`, keyed by session, channel
  and the moment's estimated start (`switch_est`, rounded to 0.1 s), with who
  noted it and when. `GET /api/review/sessions/{id}` puts it on each moment as
  `outcome` (or null); notes whose moment is no longer shown (the detector
  config changed since) come back in `other_outcomes` rather than vanishing.
  `PUT /api/review/sessions/{id}/outcome` `{channel, start_s, outcome}` writes
  one (`outcome: null` clears it), with the same lab check as the timeline.
- **Staff-only**: only the review endpoints (teacher account or admin token)
  read or write it; nothing a student can call returns it, and the card says
  "Only staff see this".
- **Never detector input**: the detector reads events only, so a note cannot
  change any score, moment or threshold (`tests/test_outcomes.py` checks the
  timeline is identical before and after a note). Erasing a student, or a
  teacher's preview session, deletes its notes too.
- **For the thesis, descriptive only**: `python -m studentide.pilot` adds
  `outcomes` to its report, counts by outcome and by channel × outcome on the
  shared dev split (`harness.split.pilot_split`), plus how many notes were
  held out. `--summary REPORT --thesis ../thesis/latex` writes
  `tables/teacher-outcomes.tex`. These are what teachers recorded after a
  conversation, not labels of cheating, and the thesis reports them that way.
- **Consent**: the consent screen and the student guide say that after a conversation the
  instructor may note how it went, staff-only, never a mark, reported only as class-wide counts.
  Added without a `CONSENT_VERSION` bump (Rohan, 2026-11-25): it describes what follows a
  conversation the text already promised; teachers mention it in class.
- Browser check and screenshot: `BASE=… TOKEN=… node frontend/e2e/review-outcomes.mjs [thesis/latex/snapshots/review] [light|dark]`.

## Sandbox Lab sessions

Sandbox Labs appear in the Review tab's lab list (a box icon) for their subject's owner, teachers and
TAs, and for admins, the same as web labs for their owners (`auth.lab_ids` adds `db.sandbox_labs(email)`).

Sessions from the desktop app replay one file at a time (file tabs over the
editor) and add a collapsible **Terminal and files** section under the
timeline (`GET /api/review/sessions/{id}/sandbox`, `sandbox_review.py`):
terminal commands with exit code and output tail, saves from vim/nano (amber
when the keys typed in vim cannot account for the added text), files written
by a command or outside the app, ports, network and packages, offline gaps, and
record breaks (a batch whose signature or chain did not check out). Beside it,
the terminal as it stood at the playhead and **Appeared without typing**:
lines in the latest workspace snapshot or a submission that nothing we saw
explains (`evidence.py`: starter files, editor edits, terminal pastes and vim
saves backed by keys; lines of 6+ characters, files with 40+ such characters).
Same wording rule: something to ask about, not a verdict.

## Wording rules

- Never "flag", "alert", "cheating" or "suspicious" on screen. Say
  "moment worth a conversation" / "nothing stood out".
- Every moment carries suggested questions and the reminder that habits
  change for ordinary reasons (tiredness, a hard problem, a new keyboard,
  an injury) and that no mark follows from the screen.
- The outcome note words what happened in the conversation ("Had help"),
  never a verdict, and says it records the conversation, not a verdict.
- Simulated ground truth appears only for seeded sessions and only when the
  reviewer turns it on.

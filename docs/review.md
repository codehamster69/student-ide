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
| API (admin token) | `/api/review/{config,students,sessions,sessions/{id},sessions/{id}/replay}` in `app.py` |
| demo data | `backend/studentide/seed.py` |
| screens | `frontend/src/review/` (lazy-loaded at `#/review`) |

- **Baseline**: a student's sessions in the 28 days after their first one.
  At least 2 are needed before anything is scored. A baseline session is
  scored against the *other* baseline sessions and labelled as a baseline
  check. ICC feature weights are computed from every student's baseline
  once 3 students have one (equal weights before that).
- **Detector**: `fit_channels` + `detect_channels` from phase 2, W = 30 s.
  Thresholds default to the synthetic calibration
  (identity 5.25, process 16.5); override with
  `STUDENTIDE_H="identity=…,process=…"` once real calibration exists.
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

## Wording rules

- Never "flag", "alert", "cheating" or "suspicious" on screen. Say
  "moment worth a conversation" / "nothing stood out".
- Every moment carries suggested questions and the reminder that habits
  change for ordinary reasons (tiredness, a hard problem, a new keyboard,
  an injury) and that no mark follows from the screen.
- Simulated ground truth appears only for seeded sessions and only when the
  reviewer turns it on.

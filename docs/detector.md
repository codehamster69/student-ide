# Detector (phase 2)

Code: `backend/studentide/detector/`. It reads sessions in the editor's event
format (see [event-schema.md](event-schema.md)), so the same code runs on
synthetic and on real recordings.

| module | what it does |
|--------|--------------|
| `synth.py` | simulated typists and sessions for the five study conditions (A honest, B proxy, C takeover, D copying out, E paste) |
| `corpus.py` | the lab-style Python programs the simulated typists write |
| `features.py` | events → per-key streams (with replay, so comment keys are known) → habit features per window |
| `detector.py` | per-student baseline (summary stats only), feature weights, distance score, CUSUM, two channels |
| `evaluate.py` | the synthetic evaluation and ablations; writes tables and graphs into `thesis/latex/` |

## Use on recorded sessions

```python
from studentide.db import Database
from studentide.export import load_session
from studentide.detector.features import streams, window_features
from studentide.detector.detector import feature_weights, fit_channels, detect_channels

db = Database("data/studentide.sqlite3")
win = lambda sid: window_features(streams(load_session(db, sid)), 30)

# after the baseline weeks: windows of every student's honest sessions
baseline_windows = {student: [win(s) for s in sessions] for student, sessions in baseline_sessions.items()}
weights = feature_weights(baseline_windows)            # store with the baselines
models = {st: fit_channels(st, w, weights) for st, w in baseline_windows.items()}
# models[st]["identity"].to_json() is all that needs keeping; raw baseline keys can go

dets, alarms = detect_channels(models["PG25CS07"], win(todays_session), h={"identity": 5.25, "process": 16.5})
for alarm_s, est_switch_s, channel in alarms:
    ...  # evidence for the teacher timeline (phase 3)
```

`h` comes from calibration (`evaluate.py` picks it for at most 0.2 false
alarms per hour on calibration students); the values above are the synthetic
ones at 30 s windows and will change once real data exists.

## Design in short

- **Windows** of W seconds (30 by default); a window needs 20 code
  keystrokes to count, otherwise the detector state is left alone.
- **Comments apart**: keys typed while the caret is after a `#` (outside a
  string) are excluded from code features and get their own two features,
  because comment text is typed like retyping (Lueder et al., Nosi).
- **Features**: rhythm (digraph median, L-scale of log inter-key time, hold
  time), digraph groups (alternate/same hand, to/from space, shifted),
  pauses, revisions, build order (share of new code lines written above
  existing code, and block headers still without a body, both over the
  trailing 5 minutes), run rate, focus losses, paste share.
- **Baseline**: per feature median and 1.4826×MAD (floored), plus the
  student's own honest score level μ0, σ0 measured leave-one-session-out.
- **Two channels**: *identity* (rhythm + digraph, weighted by intraclass
  correlation across students, CUSUM k = 1) and *process* (everything else,
  equal weights, k = 0.5). A single combined score could not catch both
  takeovers and copying (see the ablation table).
- **CUSUM**: S_t = max(0, S_{t-1} + x_t − k), alarm at S_t > h, switch
  estimate = start of the window after the last S = 0; restart after an alarm.

## Synthetic results (seed 7, 60 typists, 30 min sessions, W = 30 s)

Test typists only (40). See `thesis/latex/tables/detection-by-condition.tex`
and `thesis/latex/ablations/` for everything.

| condition | detected | median delay | median switch-time error |
|-----------|----------|--------------|--------------------------|
| B full proxy (speed-matched) | 90% | 165 s | 0 s |
| C takeover (speed-matched) | 72% | 80 s | 29 s |
| C takeover (random partner) | 88% | 65 s | 31 s |
| D copying out | 80% | 405 s | 36 s |
| E paste | 78% | 502 s | 22 s |
| A honest | 0.42 false alarms per hour, 11% of sessions flagged | | |

These are simulated people. They show the pipeline works end to end and how
the settings trade off, not how it will do on students.

## Reproduce

```bash
pip install -e 'backend[analysis]'
cd backend
python -m studentide.detector.evaluate --typists 60 --seed 7 --thesis ../thesis/latex   # ~3 min
python -m studentide.detector.synth --out ../synthetic --typists 4                       # example JSONL
```

## Known gaps

- The generator types indentation with Tab; the real editor auto-indents and
  auto-closes brackets, so real `del_per_100` and digraphs around brackets will differ.
- Build order was first measured per edit, which was noisy (copying
  detection 50%); the line-level version gets 80%. Dropping it altogether
  gets 95% at slightly more false alarms, so decide on real data.
- Scaled Manhattan and TypeNet-style baselines, threshold calibration and short
  baselines are handled by the evaluation harness, see [evaluation.md](evaluation.md).

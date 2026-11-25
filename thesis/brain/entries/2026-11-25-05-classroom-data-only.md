---
date: 2026-11-25
type: decision
title: The thesis concludes from naturalistic classroom data only; takeovers are spliced from real sessions
thesis-chapter: 03-problem-and-rqs, 06-study-design, 07-10 (set-ups)
---

## What happened

Rohan (2026-11-25): "the students are not guinea pigs, we can't control the lab
environment ... we have to conclude our thesis with this type of data only." Any
session could be a first attempt, a re-attempt, on a lab PC or an own laptop, in a
lab or a competition, and some students may copy from an LLM. So the separate study
phases (survey, four baseline weeks, staged conditions A-E, mock remote interviews)
are dropped. He approved the new RQs and the splice-based evaluation by decision card.

Changes (this PR):

- **RQs** (ch 1, ch 3): RQ1 switch detection on spliced sessions, false alarms on real
  ones; RQ2 agreement of transcription measures with copying signs (no accuracy);
  RQ3 becomes transfer across devices (lab PC vs own laptop, a natural experiment)
  instead of remote interviews; RQ4 fairness by device class, OS, language, context,
  typing speed, plus precision at 1/100 and 1/500. Hypotheses H1-H4 stated.
- **Study design** (ch 6) rewritten: classroom-only stance, ethics (oral approval,
  written pending), setting (pilot table kept), study-data exclusions, baseline from
  the earliest M = 20 active minutes (device-aware option), splicing rules and limits,
  devices as natural experiment, weak copying labels, split by student and week with a
  disclosure, protocol, metrics, optional blind teacher review, threats to validity.
- **Harness**: `harness/splice.py` (stream- and window-level splicing, `add_splices`),
  `corpus.classroom_corpus()` (every study session, earliest-minutes baseline,
  `--by-device`, purged sessions scored from stored windows), `split.pilot_split()`
  and `PILOT_TEST_FROM`, `run.py --classroom --baseline-min --by-device`;
  `pilot.device_fingerprint/device_class` factored out for reuse. Tests:
  `backend/tests/test_splice.py` (8).
- Fixed a stray backspace byte in ch 4 (`\x08egin{figure}`) that broke the PDF build.

## Why

Without staging there is no ground truth, but two things are still known by
construction: a splice of student A's real session with student B's real typing on
the same question has a known switch time, and the devices students chose give a
within-student comparison. Real sessions give false alarms; since some may hide real
cheating, that rate is an upper bound and precision a lower bound, the safe direction
for a tool whose flags only start a conversation.

Alternatives considered: asking students to stage takeovers (rejected by Rohan: they
are a class, and staging changes the behaviour); treating copying signs as labels
(rejected: own-code pastes look the same, so RQ2 claims agreement only); pairing
partners across questions (rejected: the task would leak into the signal).

Splicing at the window level as well as the stream level matters because raw keys are
purged after 28 days; stored 30/90 s windows keep the thesis detector scorable. The
keystroke baselines (scaled Manhattan, TypeNet-style) need raw keys, so they are
compared on recent sessions only.

Known bias of splices: B continues B's own code (build order is B's document) and
there is no "read the other person's code" pause, which favours the process channel.
Ch 7 will report the identity channels alone too.

## Split (shared with the detector re-tune thread)

`pilot_split(student_id, started_at)`: test = 30% of students by the existing salted
hash (SALT student-ide/v1), plus every session from 2026-11-24 00:00 IST
(1795458600) for everyone. Dev = dev-hash students before that. The re-tune thread
applies it inside the container on the real student id. Disclosure: the first-look
aggregates (entry 01) covered all students before the split was fixed; nothing was
fitted on them.

## Evidence

- `backend/tests/test_splice.py`: splice correctness, roles, same-question partners,
  window splice for purged sessions, and a `dev` then `test` harness run on a small
  classroom DB (writes one ledger line in a temp folder).
- Smoke `dev --classroom` on 12 simulated students in a scratch DB: runs end to end.
- Thesis PDF builds (104 pages, no undefined references).

## Follow-ups

- Run `dev --classroom` on a copy of the live DB (dev split only), sweep
  `--baseline-min` and `--by-device`; then freeze and run `test` once.
- RQ2 weak-label analysis (agreement with copying signs, blocked outside pastes from
  the paste guard, PR #62) is not in `harness test` yet.
- RQ3 drift metrics (same/other device, two students) exist in `pilot.py`'s summary;
  move them into the harness for the test split.
- The live review still builds baselines from the first four lab weeks
  (`BASELINE_DAYS`); aligning it with "earliest M minutes" is for the re-tune thread.
- Ask a teacher for one hour of blind review of ~30 flags; otherwise RQ3/teacher
  review stays future work.
- Appendix B: attach the written confirmation of the oral approval when it comes.

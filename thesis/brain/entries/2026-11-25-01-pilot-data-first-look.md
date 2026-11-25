---
date: 2026-11-25
type: result
title: First look at the live pilot data; detector flags far too often on real classes
thesis-chapter: 06-study-design
---

## What happened

Rohan asked what the live sessions so far show. A thread took a disk snapshot
(`studentide-pre-20261125-analysis`) and ran an aggregates-only analysis inside the app
container. Only pseudonymous aggregates left the VM. The analysis is now
`backend/studentide/pilot.py`, documented in `docs/pilot-data.md`. The same PR keeps server
logs across deploys (`deploy/docker-compose.yml`, journald).

**Approval status.** Rohan reports oral institutional approval (Dean, HoD, faculty) for the
pilot, given on 2026-11-25 when asked. Written confirmation is still pending and goes in
appendix B. So the pilot data is used for analysis. Detector re-tuning treats it as
development data only, so the frozen held-out test protocol stays clean. The thesis should
say plainly what the approval covered: examiners usually expect a written ethics
committee (IEC) approval for human-subject data.

## Evidence

- **Volume.** 1,118 sessions, 281 students (305 accounts, 291 consented). 13 class days,
  27 Oct to 23 Nov. Lab 443 (171 students), competition 590 (125), practice 50, learning
  lab 35. C 608, Python 456. All web; the desktop app was never used.
- **Devices.** Windows 470, Linux 444, Android 111, Mac 84, iOS 9. Fingerprints: 618
  sessions lab-PC-like, 500 personal-like.
- **Session size.** Median 5 min, 256 events, 108 key presses.
- **Data quality is good.**
  - No events are missing outside the 28-day key purge (132 sessions purged).
  - The VM restart at 13:38 IST on 20 Nov hit 27 open lab sessions. Their recorders
    re-sent everything after ~100 s and nothing was lost.
  - 53 sessions have no end event (browser closed).
  - 1.5% of events in 285 sessions were logged out of time order, by a median of 3 ms.
    These are key events logged just after their edit, which is harmless.
  - 23 students' PCs had wall clocks 5.5 h off. Only server time is used, so this has no effect.
  - Sessions with no consent on file are all staff previews.
  - Phones (120 sessions) record no key events at all.
  - Server logs from before 25 Nov were lost, because each deploy recreates the containers
    (fixed).
- **Detector.**
  - 384 of 1,083 sessions had a ready baseline. Most students have one baseline session,
    and the median baseline holds 13 windows (~6 min of typing).
  - Of 157 ready sessions with typing, 61 raised an episode. In labs that is 7.5 per
    active hour (process 4.2, pairs 2.7, identity 0.24), against the 0.2 per hour target
    and 0.28 per hour on synthetic test data. Competitions raised 0 of 18.
  - Rates by device: other than the usual device 9.9/h vs usual 5.7/h; Windows 8.1/h,
    Mac 3.9/h, Linux 4.6/h.
  - Top evidence for process episodes: fill_in_frac (build order), up or down, in 42 of
    ~100 top-2 evidence items.
- **Copying signs.** 248 of 760 study sessions pasted; in 60, over half the inserted text
  was pasted. 97 had a big paste and 80 pasted within 60 s of returning to the window,
  117 sessions in all (97 students). Episode rate is 46% with signs vs 37% without.
  Typed-with-no-keys (auto-typer) appeared in 1 session.
- **Rhythm distance** (robust z, 5 features, median): same student 2.1, two students 2.9.
  The separation is real but overlaps a lot. The cross-device comparison is inconclusive
  (n=43, and the fingerprint then included browser version; fixed in pilot.py).

## Why it matters

The identity channel behaves on real data roughly as on synthetic data. The process
channel does not. Build order depends on the question, so a baseline of one or two
different questions gives a spread that a new question exceeds. The synthetic typists
never changed task difficulty this way. Phase 2 entry `2026-10-26` already noted that
dropping build order cost little on synthetic copying detection; real data now argues
for dropping or weakening it.

## Follow-ups

- Decision for Rohan: re-tune on pilot data as dev data (build order, a minimum baseline
  typing time, per-device or device-aware baselines). The frozen test config stays untouched.
- Labs should ask for a laptop or PC: phones give no rhythm data (RQ4 caveat).
- Run `pilot.py` within 28 days of a class if per-key statistics are wanted.
- Get the oral approval confirmed in writing (one email from the HoD or Dean is enough to cite) and attach it in appendix B.
- Rohan chose (decision card, 2026-11-25) to re-tune on pilot data as dev only; done in a separate thread.

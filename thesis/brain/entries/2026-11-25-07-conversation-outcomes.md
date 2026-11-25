---
date: 2026-11-25
type: decision
title: Teachers can note the outcome of the conversation about a review moment (staff-only, descriptive counts)
thesis-chapter: 06-study-design
---

## What happened

Each moment card on the review timeline now ends with an optional one-tap note,
"After talking with the student": *Explained, own work*, *Had help*, *Copied* or
*Not discussed*; tapping the chosen one again clears it. Stored per moment in the
new table `moment_outcomes` (session, channel, estimated start rounded to 0.1 s,
outcome, who, when), written by `PUT /api/review/sessions/{id}/outcome` with the
same lab check as the timeline, and attached to each episode as `outcome`.
`python -m studentide.pilot` adds `outcomes` to its report: counts by outcome and
by channel × outcome on the shared dev split (`harness.split.pilot_split`), plus
how many notes were held out; `--summary … --thesis` writes
`tables/teacher-outcomes.tex`. Stacked on PR #64 (it needs the pilot split and
ch. 6 from #61/#63/#64).

## Why

Rohan (2026-11-25, thesis-reframe thread): "a flag can be discussed because it
needs to be", and chose "Yes, add a one-tap outcome". Teachers hold these
conversations anyway, so a note of how they went costs one tap and adds no
procedure for students, in line with the classroom-only study design (no staged
sessions, no interviews). It gives the thesis a descriptive view of how moments
were used in class.

Choices:
- **Staff-only, never detector input.** Only review endpoints touch the table; the
  detector reads events, so a note cannot move a score, moment, threshold or split.
  A test checks the timeline is identical before and after a note.
- **Descriptive only.** A note is what a teacher recorded after a conversation, not
  a label: "own work" does not prove a false alarm, "had help"/"copied" does not
  confirm a switch of author, and which moments get discussed is the teacher's
  choice. So the counts are never used for precision/recall; that stays with
  splices and honest sessions.
- **Keyed by moment start, not an id.** Episodes are recomputed on every view; a
  re-tuned config may move or drop a moment. Notes that no longer match a shown
  moment come back as `other_outcomes` instead of vanishing.
- **Dev split only** in the aggregate, so the held-out sessions stay untouched.
- Erasing a student (and deleting preview sessions) deletes their notes.
- No `SCHEMA_VERSION` bump: not an event and not in the student's stream.

## Evidence

- `backend/tests/test_outcomes.py` (6 tests: note/replace/clear, detector unchanged,
  bad values and no-token 401, unmatched notes kept, erase, dev-split counts).
- `frontend/e2e/review-outcomes.mjs` passes light and dark on seeded data;
  screenshots `thesis/latex/snapshots/review/review-{light,dark}-08-moment-outcome.png`
  (fig:review-outcome, ch. 4).
- Ch. 6 `sec:teacher-review` rewritten (replaces the optional blind teacher review),
  table `tab:teacher-outcomes` (generated), new threat to validity.

## Follow-ups

- Consent text (Rohan approved 2026-11-25, same day): the consent screen and student
  guide now say the instructor may note how a conversation went, staff-only, never a
  mark, reported only as class-wide counts without names. No `CONSENT_VERSION` bump
  (web is v2, Sandbox v3, so a bump would re-ask everyone); teachers mention it in class.
- Run the pilot report on the VM once teachers have noted outcomes, then regenerate
  `tables/teacher-outcomes.tex`.

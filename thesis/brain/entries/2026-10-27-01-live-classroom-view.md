---
date: 2026-10-27
type: decision
title: Live classroom view for teachers, with a read-only editor view that students are always told about
thesis-chapter: 04-system-design
---

## What happened

Rohan asked whether teachers can see live what students are doing ("like a
monitoring tab"), and then whether teachers could open individual IDEs while
monitoring. Until now the design was after-the-fact only: the Review tab shows a
session's evidence timeline once it has data. PR #16 adds a **Live** tab:

- Class view per open lab: state (typing, working, quiet, other tab, not
  connected, finished), current question, edits per 30 s over 10 minutes, runs
  and last error, last test check, pastes, and the review timeline's moments in
  this lab so far. No code.
- Editor view per session: read-only code rebuilt on the server from edit
  events (incremental replay), the student's caret, recent runs, last check.
- Student side: the IDE polls who is watching every 5 s and shows "<teacher> is
  viewing your editor" or a "Class view on" pill. Every view is logged
  (`live_views`). Consent text bumped to version 2; earlier consents are asked
  again. `STUDENTIDE_LIVE=editor|class|off` narrows it.

## Why

- Live viewing changes what students consent to, and covert watching would
  undercut the project's stance that a highlighted moment leads to a
  conversation, never a penalty. Making every view visible to the student, by
  name, and logged keeps it a teaching tool (helping a stuck student) rather
  than surveillance.
- Rebuilding code from the existing edit stream means no new data is collected
  for the editor view; it only changes who can see it and when.
- The IDE's 5 s poll doubles as presence, so "quiet" (present, not typing) and
  "not connected" (tab closed) can be told apart without logging anything new
  into the research data.

## Open points

- The ethics application must name live viewing (what is shown, notices, log).
  If the committee prefers less, `STUDENTIDE_LIVE=class` keeps code private.
- A possible confound for the study: students who know they can be watched may
  type differently. Sessions could record whether an editor view happened
  (the log has it) so the analysis can exclude or compare them.
- Moments are summed over the student's sessions in this lab; a lab spanning
  several sittings would mix them.

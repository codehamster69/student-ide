---
date: 2026-11-25
type: decision
title: Thesis cleanup for submission: ch 4 trimmed to the method, appendices filled, M.Tech front matter
thesis-chapter: 04-system-design, appendices, frontmatter
---

## What happened

- Chapter 4 ("The Recording Editor", label `ch:system` kept) cut from about 8,400 to about
  2,600 words. Kept: architecture, what is logged and timing precision (the old TODO, now
  written), sessions/questions/sittings (needed for splicing), paste guard, consent + privacy +
  DPDP table, a new list of non-study sources (learn, preview, reset, competitions), deployment
  and sign-in, and the review timeline with conversation outcomes. Every label referenced from
  other chapters still exists.
- Teaching features (labs and question sources, competitions + similarity check, live view,
  learning lab, View as student, attendance, redesigns, desktop) moved to a new Appendix E
  (`app:features`, about 1,500 words, 7 figures). Dropped: licensing detail of each question
  source, the C fundamentals table, hand-in/resume/any-language mechanics, attendance key
  plumbing, per-redesign narrative. They remain in `docs/`.
- Appendix A (event schema) written; its payload table `tables/event-schema.tex` is generated
  from `schema.py` by `backend/scripts/build_schema_appendix.py`, and
  `tests/test_schema_appendix.py` fails when it goes stale.
- Appendix B (ethics and consent): oral approval from Dean, HoD and faculty with written
  confirmation pending; the full current consent text (v2 with the conversation-note sentences
  of 25 Nov, no re-consent), its version history, the live-view variants and the Sandbox v3
  additions.
- Old Appendix E (project progress, 26 Oct) removed: it described the staged-session study
  that was dropped (brain 2026-11-25-05). `thesis/progress/` still holds the live status.
- Front matter: added a Thesis Approval page (examiners, supervisor, HoD), date/place lines,
  a fuller declaration and certificate, a drafted acknowledgements page, more abbreviations,
  and List of Figures/Tables in the contents.

## Why

The supervisor and examiners read ch 4 for what the method depends on; 8,000 words of product
features buried that. No official IIIT Surat thesis template is public (searched 25 Nov: only
the M.Tech admission brochure), so the front matter follows the common Indian M.Tech order used
by IIT/IIIT guidelines. The schema table is generated so the appendix cannot drift from the code.

## Evidence

PDF builds with latexmk + biber, no undefined references or citations; 107 -> 96 pages.
Remaining overfull boxes are in ch 6, ch 12 (other threads) and the generated similarity table.

## Follow-ups

- Rohan to check with the department: official template or cover page, margins, whether an
  approval page and plagiarism report are required, and the institute logo for the title page.
- Personalise the acknowledgements draft.
- Attach the written approval to Appendix B when issued.

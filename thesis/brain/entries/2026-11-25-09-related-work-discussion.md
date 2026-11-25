---
date: 2026-11-25
type: decision
title: Related work (ch 2), discussion and limitations (ch 11) and the conclusion written from the pilot data
thesis-chapter: 02-background, 11-discussion, 12-conclusion
---

## What happened

Ch 2 grew from ~360 words / 20 references to ~3,400 words; the bibliography went from
19 to 81 entries. Ch 11 (was headings only) is now ~2,600 words, and the Conclusion
section of ch 12 is written (Future work untouched).

## Evidence

- Every new reference with a DOI was fetched from Crossref and the bib entry built from its
  metadata (56 entries); one wrong DOI from memory (Leinonen et al. 2016, ITiCSE) was caught
  and corrected to 10.1145/2899415.2899472. Six without DOI (two arXiv preprints plus Codex,
  PMLR, USENIX SOUPS, fairmlbook.org) were checked against arXiv / the publisher page. All
  existing DOIs resolve.
- Ch 2 covers keystroke dynamics and continuous authentication (scaled Manhattan, TypeNet,
  Buffalo/Clarkson data, Eberz/Sugrim evaluation critiques), CUSUM theory (Page, Lorden,
  Moustakides) and offline/Bayesian alternatives, programming-process analytics and
  keystrokes in CS education (Jadud ... ProgSnap2, Longi/Leinonen/Edwards/Hellas, writing
  research), contract cheating and proctoring, LLMs and generated-text detection, fairness
  (NIST FRVT, Gender Shades, base-rate fallacy), learning-analytics ethics and the law,
  plus a gap table (tab:rw-gap).
- Ch 11 uses only numbers already in ch 6-7, pilot-data.md and entries 2026-11-25-01/06/07:
  dev 64% splices caught at 1.59 FA/h, 450 s; 7.5 episodes/h first look; 9.9 vs 5.7 on
  less usual device; 84% own pastes; 45 splices, 2-3 cross-device; 10.7 active hours.
  New derived number: dev precision illustration from 64% caught and 29% of real sessions
  flagged = ~2% at 1/100, 0.4% at 1/500 (~45 honest flags per real one).
- Test-split numbers are red `\resultpending{...}` placeholders (macro via
  `\providecommand` in ch 11 and ch 12) for the final-evaluation thread to fill.

## Why

The discussion's main argument: real classwork drifts far more than simulated typing, no
operating point is free, copying needs its own evidence (paste origin), and at realistic
prevalence a flag can only start a conversation. Limitations name no ground truth, splices
as an approximation, the device confound, a modest short-session sample, one institution,
oral ethics approval with written confirmation pending, and out-of-scope attacks.

## Follow-ups

- Fill every `\resultpending` once the held-out test run is in ch 7-10, then delete the macro.
- Ch 1 still has a TODO for problem evidence; Newton 2018 and Bretag 2019 are now in the bib.

---
date: 2026-10-26
type: result
title: Nosi IDE paper read; details confirmed and design implications noted
thesis-chapter: 02-background, 05-features-and-detector, 08-rq2-composing-vs-transcribing
---

## What happened

Completes the follow-ups in `2026-10-26-06-citations-nosi-typenet.md`.
Rohan supplied the PDF of the Nosi IDE paper (Lueder et al., L@S '26,
Seoul, pp. 463–467, DOI 10.1145/3774398.3811574). Read in full; bib entry
corrected (author order Lueder, Zhao, Gray, Liu, Chatterjee, Zhang,
Nahodyl, Starner; pages added) and a related-work subsection drafted in
chapter 2. Also added Crossley et al. 2024 (EDM), which Nosi cites for
composition vs. transcription in essays.

What the paper actually says:

- **Feature:** L-scale (L-moment dispersion) of log(IAT). Pauses over
  5 minutes and IATs of exactly 0 are removed first. Log transform to stop
  fast typers looking artificially uniform.
- **Study:** N = 5, all authors, former TAs / proficient coders. A–B–B–A:
  code, scribe LLM solution, scribe another, code again, on one
  priority-queue problem. Subject-independent evaluation.
- **Results:** linear SVM on the 1-D feature, 100% leave-one-participant-
  out accuracy on whole sessions; about 80% with 150 s slices of active
  typing. Comment typing is sometimes misread as scribing.
- **Deployment:** Georgia Tech online grad AI course, ~1000 students; 48
  LLM-plagiarism cases found by replaying edit logs, none detectable by
  similarity tools.
- **System:** VS Code fork, LLM features off; encrypted assignments
  decrypted in memory; copy-out becomes an encrypted payload; pastes
  logged; no webcam/screen/OS surveillance; students get their key after
  the deadline to inspect what was logged.

## Why it matters for this thesis

- The deck's description (N = 5, IAT rhythm measure) is confirmed. Nosi
  detects **transcription**, not **author change**, and uses a
  population classifier, not a per-student baseline. That is the gap RQ1
  fills; RQ2 replicates Nosi at larger N with ordinary students.
- **Window length:** Nosi needs ~150 s of typing for ~80% with one
  feature. Our plan scores 30 s windows, so a single window will be
  noisy; CUSUM accumulating evidence across windows is what should make
  30 s workable. Worth an explicit window-size ablation.
- **Comment typing** is a known confound: consider separating comment vs.
  code keystrokes as a feature or filter.
- **Transparency idea worth borrowing:** letting students see exactly what
  was logged after the assessment fits our "conversation, not penalty"
  stance and the DPDP Act.
- L-scale of log(IAT) is cheap and robust; include it as one of our habit
  features, not only as the RQ2 baseline.

## Evidence

- `thesis/latex/bib/references.bib` (`lueder2026nosi`, `crossley2024plagiarism`)
- `thesis/latex/chapters/02-background.tex`, `08-rq2-composing-vs-transcribing.tex`
- The PDF itself is not committed (CC BY-NC-ND; cite by DOI).

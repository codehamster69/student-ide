---
date: 2026-10-30
type: plan
title: Sandbox Labs plan revision 3, teachers set up their own subjects and labs
thesis-chapter: 12-conclusion (future work), 04-system-design
supersedes: 2026-10-30-04-sandbox-labs-plan-revised.md
---

## What happened

Rohan asked (same day, PR #29) to "let teachers set up their subject and lab
as well, with ease of use", still as a plan only. Revision 3 of
`thesis/plans/2026-10-30-desktop-client.md` rewrites section 5 (faculty side),
adds faculty screens in 6.3, and updates decisions, migration, risks and
milestones. The figure gains the build service; chapter 12 mentions teacher
setup.

## Why

- **Teachers own subjects and labs; admin presets become a library.** Presets
  alone would not fit every course. Ownership, co-teachers and TAs reuse PR
  #19; rosters live once per subject and reuse the PR #14 address format
  (paste a roll range).
- **Environment builder with recipes.** Most teachers do not know Docker, so
  an environment is a base plus ticked tools, built off the VM by a build
  service (Cloud Build or GitHub Actions) with a smoke test and multi-arch
  output. A raw Dockerfile needs admin approval, to keep images small and
  safe. Environments are shared and versioned, so most teachers just reuse
  one.
- **Lab wizard (Basics, Assignments, Check, Publish).** Tests use the same
  JSON-line format as PR #25 or a test command; assignments can be imported
  from the existing question sources (PRs #13, #15, #20). The Check step runs
  tests against a private reference solution (must pass) and the starter
  (should fail), which catches the most common teacher mistake: a broken or
  over-strict test.
- **Preview without Docker.** "Try as a student" uses the cloud sandbox pool,
  so faculty never need Docker.
- **Safe mid-lab edits.** Statement/test fixes apply and re-grade; starter
  changes only reach students who have not started.
- **Targets**: blank to published lab under 15 minutes, preset to published
  under 3, checked with a timed usability test (D4).
- **Milestones**: D4 is now teacher setup (web-only, can start alongside D2);
  running a class moved to D4b.

## Evidence

- Plan revision 3: `thesis/plans/2026-10-30-desktop-client.md`, section 5.
- Figure: `thesis/latex/flowcharts/desktop-client.tex` (build service node).

## Follow-ups

- Rohan: which subjects get presets first; can teachers create subjects
  freely (suggested yes, admins approve only raw Dockerfiles); cloud seat
  budget; can IT install Docker or Podman in one lab room.

---
date: 2026-10-26
type: decision
title: Thesis folder, brain and LaTeX project set up
thesis-chapter: (meta)
---

## What happened

Created `thesis/` with two parts: `brain/` (this log) and `latex/` (the
thesis project with a chapter skeleton mapped to the RQs and study phases,
plus folders for snapshots, graphs, flowcharts, ablations, tables and the
bibliography). Rohan asked that events and everything else be tracked
from now on so the report and thesis can be written from them.

## Why

- **One file per brain entry,** not one big log file: several threads work
  in parallel, and they would all append to the end of the same file and
  conflict on every merge. Separate dated files sort the same way and never
  collide.
- **Append-only with `supersedes`:** the thesis needs to explain why a
  design changed, so the old reasoning has to survive.
- **Standard `report` class with an IIIT Surat-style front matter**
  (certificate, declaration, acknowledgements, abstract): no official
  institute template was available, so the front matter follows common
  Indian M.Tech conventions and is kept in `latex/frontmatter/` so it can
  be swapped for the official template later without touching chapters.
- **BibLaTeX + biber** for the bibliography, and TikZ for flowcharts, so
  diagrams are text, reviewable in PRs, and match the document fonts.
- Chapters are laid out by research question so each result has an
  obvious home from day one.

## Evidence

`thesis/README.md` documents the rule for other threads.

## Follow-ups

- Ask the guide / department for the official M.Tech thesis template and
  formatting rules, then swap `latex/frontmatter/`.
- Optionally add a CI job to build the PDF on every PR.

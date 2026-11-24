---
date: 2026-11-24
type: decision
title: Student IDE is renamed Scribelab, served at scribelab.hokora.xyz
thesis-chapter: 04-system-design
---

## What happened

Rohan asked for a rebrand: a new name with a small existing footprint, a logo,
a subdomain on hokora.xyz, the live site and the desktop app updated. The work is
stacked on the redesign PR stack (#55–#59) and replaces the rhythm-bar mark it added.

- Name: **Scribelab**. Logo ("Squiggle", picked by Rohan from three bolder options after he
  asked for a look that feels right to Gen Z students): a chunky hand-drawn "s" with a yellow
  text caret on a violet-pink-orange gradient; lowercase heavy wordmark with a gradient "lab".
  A first, quieter pen-nib mark was dropped. Options board: `snapshots/rebrand/scribelab-logo-options.png`.
  Sources: `frontend/src/ui/Logo.tsx`, `frontend/public/favicon.svg`,
  `desktop/installer/packaging/build/icon.{svg,png}` (electron-builder makes .ico/.icns).
- User-facing text in the web app, guides, desktop app, installer, docs and Roll Call
  (codehamsters/attendance#10) says Scribelab. Internal identifiers are unchanged:
  `studentide` packages and module, `STUDENTIDE_*` env vars, the database, the desktop
  appId, WSL distro, data folder, the `StudentIDE-Desktop` user agent, Roll Call's
  integration id `student-ide`, and the thesis title. The consent text never named the
  product, so it is untouched.
- DNS: A record `scribelab.hokora.xyz → 34.14.186.251` (Vercel, team codehamsters-projects).
  Caddy serves the new name; `STUDENTIDE_OLD_DOMAINS=studentide.hokora.xyz` sends browsers
  there with a 308 (same path) but still serves `/api/*` and the desktop user agent, because
  desktop apps from before the rename are locked to the old origin until they update.
- Desktop: default server is the new address, a saved old address is read as the new one,
  and the data folder keeps its old name so sign-in, settings and the unsent journal survive.

## Why

Round one (10 names, footprint by web search and GitHub repo counts) picked "Ductus"
(paleography's word for how a hand forms strokes). Rohan rejected it: a name should say
what the product is. Round two (8 names that say code lab / editor for students) gave
Scribelab the smallest footprint: no exact-match product or company, 4 GitHub repos.
"Lab" says where students write code; "scribe" is the writer, the thesis question.
Rejected: Penlab (Georgia Tech lab, MATLAB package), Labtrace (lab-tracking products,
reads as surveillance), Typelab, CodeInk, Codeprint, Handcode (existing coding products).

Keeping identifiers internal avoids a database or schema change and keeps study data,
Roll Call's API contract and installed desktop apps working.

## Evidence

- Snapshots: `thesis/latex/snapshots/rebrand/` (login light, task list light, editor dark,
  app icon, mark SVG).
- Backend suite 424 passed, 1 skipped; frontend build, desktop build and installer tests
  (23) pass. Caddyfile validated with Caddy 2.8.4 and exercised locally: old host gives
  308 to the new host for a browser, 200 for the desktop user agent and for `/api`.

## Follow-ups

- Rohan: add the new origin to the Google OAuth client, update the GitHub Actions variable
  `STUDENTIDE_URL`, approve a `desktop-v*` release tag for the renamed app.
- A trademark search (Indian TM registry) before anything is printed.

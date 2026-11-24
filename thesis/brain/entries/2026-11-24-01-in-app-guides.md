---
date: 2026-11-24
type: event
title: In-app student and teacher guides written as Markdown pages
thesis-chapter: 04-system-design
---

## What happened

Added 20 Markdown pages under `frontend/src/guide/pages/student/` (9) and
`frontend/src/guide/pages/teacher/` (11) for the in-app Help centre of the UI
redesign. Each has `title`, `summary`, `order`, `keywords` frontmatter. Content
comes from `docs/*.md` and the screens (consent, workspace, setup), no app code.
Pages link to each other by slug (`[Attendance](attendance)`).

## Why

Students and teachers need plain-language guidance inside the app, in one place
that the redesigned UI can render. The consent text is not rewritten: the
student page "What we record" explains it and points back to the consent screen
as the text agreed to. Every page keeps the rule that a flag only leads to a
conversation, never a penalty.

## Evidence

`frontend/src/guide/pages/**`. No behaviour changed.

## Follow-ups

The redesign thread renders the pages and resolves the relative slug links.
Re-check wording if the consent text or attendance rule changes.

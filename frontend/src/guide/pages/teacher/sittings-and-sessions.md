---
title: Sittings and sessions
summary: How a lab visit is recorded: one sitting, one session per question, and how work carries over between visits.
order: 4
keywords: [sitting, session, question, resume, finish, focus, recording, lab day, baseline]
---

## The words

- A **sitting** is one visit to a lab, from **Start lab** or **Continue lab** to **Finish lab**.
- A **session** is the recording of one question inside a sitting. Each question a student opens gets its own session, and all the sessions of the sitting are linked together.

So a session is still one question. The review timeline, code replay, Check and live view all work per question.

## What happens inside a sitting

- Moving to another question marks the first as "out" and the other as "in". The detector does not count it as looking away, and a gap that spans a switch is not treated as a pause.
- **Finish lab** ends every session of the sitting. Questions with code different from the starter are recorded as submitted; untouched ones as left.
- Coming back later starts a new sitting. Each question opens with the code the student left. The new session's start snapshot holds that code, so replay starts from it.
- Competitions do the same each time a student returns to the board and opens a question again.

## Baselines

A student's **baseline** is built from the sessions in the 28 days after their first one, and a session is scored only when there are at least two baseline sessions to compare with. Competition sessions are kept apart; see [Review timeline](review-timeline).

## What is never study data

Learning-lab practice and View as student previews are excluded from baselines, the detector, review, the live view and the research export.

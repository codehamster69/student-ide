---
title: Review timeline
summary: How to read a session's timeline: baselines, the three channels, moments worth a conversation, evidence and code replay.
order: 6
keywords: [review, timeline, moments, evidence, baseline, channels, typing rhythm, key-pair, way of working, flag, conversation, replay, cusum]
---

**A highlighted moment is a reason for a conversation, never a penalty.** It is not proof of anything, and no mark follows from the screen. Habits change for ordinary reasons: tiredness, a hard problem, a new keyboard, an injury.

## Finding a session

**Review** opens on **Lab sessions**: one row per lab per day (a class meeting) with its time, its students and how many are worth a conversation. A row opens that class student by student. **Every session in one list** shows the flat list. You see only the labs you own or share.

## How a session is judged

The recorder logs key timing, edits, pastes, runs and focus. Each student's own **baseline** is built from their sessions in the 28 days after their first one. Nothing is scored until there are at least two baseline sessions. A baseline session is compared with the *other* baseline sessions and labelled a baseline check, to show how much the student naturally varies.

A session is cut into short windows and each is compared with the student's own baseline by a CUSUM detector, which accumulates small, consistent drifts so one odd window does not trigger. Settings are the frozen ones used in the evaluation.

## The three channels

| Channel | What it watches |
| --- | --- |
| **Typing rhythm** | Speed and rhythm of typing |
| **Key-pair timing** | How fast this student types particular pairs of keys |
| **Way of working** | Pauses, revisions, the order code is built in, run rate, focus changes, paste share |

Each channel is a lane on the timeline. The detector keeps typing rhythm and way of working as separate channels because they answer different questions: a different typist shows mostly in rhythm and key pairs, while copied code shows mostly in how the work is done.

## Moments and evidence

Consecutive alarms are merged into one **moment** with an estimated start and end. Each moment card lists the features that moved most, in the student's own spread, and **suggested questions** to ask. Select a moment to jump the replay to it.

Other things on the timeline: pastes, runs that worked or failed, and focus changes. The **code replay** rebuilds the code at any point from the recorded edits.

The banner at the top says one of: *Not scored yet*, *Baseline week*, *Nothing stood out*, or *N moments worth a conversation*.

## Competition sessions

Competitions are timed, so they are measured separately: a competition session is compared only with the student's sessions from their *other* competitions (and, in any-language competitions, the same language when possible), and is not scored until there are at least two. Lab baselines leave competition sessions out.

## Sandbox Lab sessions

Sandbox sessions replay one file at a time and add a **Terminal and files** section: commands with exit codes, vim/nano saves, files written by commands, packages, network names, offline gaps, and **Appeared without typing** (lines in a snapshot that nothing recorded explains). The same rule applies: something to ask about, not a verdict.

## Wording

The app says "moment worth a conversation" and "nothing stood out", never an accusation. Please do the same when you talk to a student.

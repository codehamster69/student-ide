---
title: Attendance
summary: Link Roll Call, attach class groups, open for the performing group, and understand the present rule.
order: 9
keywords: [attendance, roll call, class groups, key, present, 10 minutes, 40 characters, override, send, next group, my attendance]
---

Student IDE can mark lab attendance in **Roll Call**, the attendance register.

## Set up once

In **Getting started**, press **Set up Roll Call for me**. It makes your own register (a key only you have). From then on **Open Roll Call** opens it already signed in. **Show key** lets you sign in by hand elsewhere. If you already use Roll Call, choose **I already use Roll Call** and paste your key from Roll Call settings. **Make a new key** moves the whole register to a new key and retires the old one.

## Per lab

1. **Attach class groups.** In the lab, *Class groups and attendance* → *Attach class groups*: tick groups from Roll Call or create one. Their students join the lab's roster. A lab can have several groups.
2. **Open for the performing group.** *Open* asks which group is performing; tick the group in the room. Only those groups' students see the lab until it closes or you move on. Students on no attached roster are not restricted.
3. **Next group or close.** *Next group* ends the sitting, sends attendance for its groups only and starts the next group's sitting, so G1 on Monday and G2 on Thursday can share one lab without G2 being marked absent on Monday. Closing sends the last sitting. Groups with nobody working that day are never sent.
4. **Check first** on the **Attendance** page: each student's mark and its reason; tap a mark to override; **Send to Roll Call**.

Roll Call rosters must build the same ids as the college address (`ug23cs001@…` is `UG23CS001`).

## Who counts as present

Per student and lab day:

| Measure | Default |
| --- | --- |
| Active minutes (an edit, Run or Check) | at least 10 |
| Typed characters (pastes, drops and Reset don't count) | at least 40 |
| Run or Check at least once | off |

Each lab has its own **Rule** on the attendance page. Sandbox Labs count the same way, with terminal keys counting as typed characters. Learning-lab practice and View as student never count. **The detector is never consulted**: a moment worth a conversation does not change attendance.

## What students see

Students get **My attendance** in their header, which opens Roll Call showing only their own marks, read-only.

## Shared computers

In Roll Call, Settings → *Sign out* forgets the key and the records in that browser.

---
title: Sandbox Labs
summary: Create subjects and environments, build labs with the wizard, preview as a student, grade submissions and share to the library.
order: 8
keywords: [sandbox, subject, environment, lab wizard, assignment, preview, gradebook, library, grading, late policy, docker, desktop, class board]
---

Sandbox Labs give students a Linux environment, a terminal and tested assignments. Students run them on their own computers in the desktop app (the cloud is only for your previews). Open **Sandbox** in the teacher area.

## Subjects

A **subject** is a course (code, title, semester, colour). It holds your labs, an **environment**, its people (co-teachers edit; TAs view) and an optional roster with sections. You can copy a subject with its labs as drafts for next semester. Admins see everything.

## Environments

An environment is a recipe for a Linux image: a base (Python, C/C++, Java, Linux, Node, databases), tools from a checklist, extra apt, pip or npm packages and an optional setup script. You never write a Dockerfile. Saving a new version queues a build; images are built off the main server and the page shows the state (queued, building, ready, failed). **Build now** starts a queued build and **Try again** re-queues a failed one. A raw Dockerfile needs admin approval.

**Set up by hand** starts a fresh instance of the environment with a terminal. Run the commands you need and the page writes the matching recipe script live, keeping only commands that change the machine; edit and save to build a new version. Use `tee` rather than vim or nano, which are not captured.

Environments belong to their author; a **shared** one can be used by every teacher.

## The lab wizard

A lab moves through steps: **Basics** (title, statement, network, assessed or not, opens and due times), **Assignments**, **Check**, **Publish**, **History**, **Submissions** and **Class** (the last two once published).

- **Assignments.** Each has a statement, starter files, the files to open, a Run command, tests and an optional reference solution. Tests are either input/output pairs fed to the Run command, or a command whose exit code decides (`make test`, `pytest -q`). Hidden tests never leave the server. Use **Import a question** to bring a question from the question sources, or copy an assignment from another lab.
- **Check.** Uses a preview to confirm the reference solution passes every test and the starter fails at least one.
- **Publish.** Choose a grading mode (tests; tests then manual adjustment; or manual), a late policy (closed, accept, or a penalty per day up to a maximum) and see **What students will see** first. Assessed labs never get open internet.
- **History.** Changes made after publishing, each with a plain sentence and an Undo. After a save the wizard says what students will notice: statement and test fixes reach them at once, test changes regrade submissions, and new starter files reach only students who have not opened that assignment.

## Try as a student

**Try as a student** starts a short-lived cloud preview of the lab for you only. Previews are capped (a few seats at once, one per teacher, idle stop after 15 minutes, 60 minutes at most) and never have open internet. A preview is never study data.

## Running the class

**Class** shows a readiness board before the lab ("48 of 52 machines ready", with the setup check's reason for any that are not) and, during the lab, who is typing, which assignment, the running command and counts. Tiles open the live editor with a terminal mirror. This is never study data.

## Gradebook

**Submissions** is a table of students × assignments with filters (not submitted, failing a test, all passed), attempt counts and a side panel with every test, hidden ones in full. Open **How it was written** for the review timeline, **Regrade** one or all after fixing a test, and download a CSV. Submissions are graded one at a time in a fresh container with no network.

## Library

**Share** puts a snapshot of a lab in the library, with a summary, topics and difficulty. Anyone can **Use** one: it becomes an independent copy in your subject. **Withdraw** removes your entry.

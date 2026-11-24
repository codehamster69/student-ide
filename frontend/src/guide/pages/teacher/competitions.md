---
title: Competitions
summary: Run a graded, timed class competition: setup, scoring, hand-in at the bell, the live board and the similar-submissions check.
order: 7
keywords: [competition, leaderboard, board, clock, start, end, hand-in, scoring, similar submissions, projector, any language, grace]
---

A competition is a lab with the clock and a leaderboard. **Correctness is always graded here**: every question needs at least one test before the clock can start, and only passing tests earn points.

## Set one up

1. **New competition** in Labs: title, instructions, the clock in minutes (empty means no clock; you end it) and what students see on the board.
2. Add questions as for a lab (write them or import them) with tests. The *Competition* card lists questions still missing tests.
3. Assign the class and set the status to **Open**. Students see a gold card and enter the lobby, where they pick the name shown on the board.
4. **Start the clock.** Questions appear for everyone at once.

For an open contest, set the language to **Any language**: students pick C, C++, Java, JavaScript or Python for each question, and tests are shared across languages.

## Scoring

Per question a student's best submission counts: 100 × passed ÷ total, plus up to 50 speed points when every test passes and there is a clock, scaled by how much of the *planned* time was left. A wrong submission costs nothing and ending early never shrinks a bonus already earned. Badges (*First to solve*, *Fastest on Qn*, *Solved them all*, *Most bugs fixed*) let more of the class stand out.

## Board settings for students

| Setting | Students see |
| --- | --- |
| Top 10 (default) | Top ten and their own place |
| Everyone | The whole class ranked |
| Reveal at end | Only their own score until the end |

## The live board

Open the board from the lab page (the **Leaderboard** button). **Present** goes full screen and hides roll numbers, for the projector. **End now** stops submissions early. The podium shows at the end. The full board with roll numbers is for the owner, co-teachers and admins.

## Hand-in when time runs out

Nobody loses points for forgotten submissions. When the clock ends, or you press **End now**, students' editors stop and send their last edits. After a 20-second grace period the server rebuilds each student's code per question from the edits it received and grades it as a submission made at the end (marked *At the bell*). A question counts as worked on if the code is not empty and differs from the starter. Until grading finishes, students and the board say final standings are coming.

## Similar submissions

**Similar submissions** (from the competition panel or the board) compares students' last submissions per question and language, ignoring names, layout, comments and literals, and masking starter code and stretches shared by half the class. Pairs are listed with a score and a side-by-side view showing typed versus pasted characters and links to each session's timeline.

It is a pointer for a conversation, never a verdict: it never says "copied", students never see it and it changes no score. A hand translation between languages is not detected.

## What a competition never uses

The leaderboard reads nothing from the review timeline or detector. A moment worth a conversation can never cost anyone a place.

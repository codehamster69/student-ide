# Student side of Sandbox Labs against other lab tools (2026-11-08)

Rohan asked for a seamless, easy-to-understand student flow, checked against similar tools
("C Lab" and the like). No single product called "C Lab" turned up; the closest are hosted
coding labs (Constructor Coding Lab, uCertify CodingLAB, Cengage Coding Labs, Turing's Craft
CodeLab), plus the tools universities use for the same job: Moodle VPL, CodeGrade, Replit
Teams and GitHub Classroom + Codespaces. Sources at the end; Replit and GitHub Classroom are
from general knowledge, not checked today.

| Step | Typical tools | Student IDE now |
|---|---|---|
| Setup | Hosted labs and VPL: nothing to install, runs in a jail server. Codespaces: cloud VM per repo. | Desktop app + local engine (one-click installer). If the engine fails, the lab shows the failing setup-check rows with a fix each, and says the files follow you to another machine. Trade-off chosen for full Linux per student at no server cost. |
| Finding work | LMS assignment list; Classroom: one repo per assignment. | Home shelf per subject, cards with assignments, network, Assessed, due, progress and Closed; "Last opened" mark. On the website the same list says "Open in the Student IDE app". |
| Opening | Instant (hosted) or a minute (Codespaces build). | Step line from the runtime ("Getting the environment… Starting… Bringing back your files…"); the first start downloads the image, later starts take seconds. |
| Files and editor | VPL: file list + editor, autosave. Replit: file tree, tabs. | File list of the assignment folder, CodeMirror editor, autosave into the instance, restore/conflict note. |
| Terminal | VPL 4.4: xterm.js text mode; Codespaces/Replit: full shell. | xterm.js shell in the assignment folder with sudo, one per assignment, "New shell" after exit. |
| Run / test | VPL: Run, Debug, Evaluate buttons; CodeGrade: AutoTest with continuous feedback. | Run (Ctrl+Enter) with stdin, Check (visible tests, local), "n more checked by your teacher". |
| Submit and feedback | CodeGrade: AutoTest tab, inline comments; Classroom: autograding check on the repo; VPL: grade from tests. | Submit dialog, then a Grade tab polled from the server (all tests, hidden ones by name), rail chip turns to pass / n of m. |
| Orientation | VPL shows the available actions on the activity page. | One-time "How this lab works" card (edit, Run/Check, terminal, Submit); keyboard hints on the rail. |
| Honesty about monitoring | Mostly silent. | "Recorded for this lab" always in the header. |

## What we took from them

1. Actions up front, as in VPL: Run, Check and Submit sit on the editor bar, with shortcuts.
2. Continuous feedback, as in CodeGrade: local Check any time, server grade after Submit, chips
   on the rail and progress on the home card.
3. One place per assignment, as in GitHub Classroom: each assignment has its own folder, shell,
   session and submission.
4. Fail with a fix, not a stack trace: setup-check rows instead of an engine error.

## Not yet

Inline teacher comments on a submission (CodeGrade), a debugger UI (VPL Debug), several
terminal tabs, port preview for web labs, a reconnect pill (journal thread), and Vim mode
(P2 thread's shared `editor/vim.ts`).

## Sources

- VPL: https://vpl.dis.ulpgc.es/documentation/latest/introduction.html,
  https://moodle.org/plugins/mod_vpl/4.3.0/36717, RWTH guide
  https://help.itc.rwth-aachen.de/en/service/8d9eb2f36eea4fcaa9abd0e1ca008b22/article/590f183f7aae4fc985bae1e64bf69024/
- CodeGrade: https://docs.codegra.de/user/autotest/student-experience.html,
  https://docs.codegra.de/user/autotest/continuous-feedback.html, https://docs.codegra.de/user/codeviewer.html
- Hosted labs: https://constructor.tech/learning/coding-lab, https://ciw.ucertify.com/products/coding-lab.html,
  https://help.cengage.com/mindtap/mt-student/mindtap/coding-labs-complete-assignment.html,
  https://www.dgp.toronto.edu/~jdeber/aps105h/201201/codelab.html

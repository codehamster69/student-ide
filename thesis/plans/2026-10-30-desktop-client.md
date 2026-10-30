# Plan: Sandbox Labs, a portable desktop client with local Docker

Status: **plan, not started** (2026-10-30, revision 2). Brain entries:
[`2026-10-30-03-desktop-client-plan`](../brain/entries/2026-10-30-03-desktop-client-plan.md) (first draft) and
[`2026-10-30-04-sandbox-labs-plan-revised`](../brain/entries/2026-10-30-04-sandbox-labs-plan-revised.md) (this revision).
Figure: [`latex/flowcharts/desktop-client.tex`](../latex/flowcharts/desktop-client.tex).

Revision 2 follows Rohan's answers to the first draft's open questions:

| Question | Rohan's answer | What changed in the plan |
| --- | --- | --- |
| Which subjects need a terminal? | It is a separate, new feature: **preset labs, all with terminal access** | Sandbox Labs is its own product side with a preset lab catalogue; the terminal is always on; existing web labs and competitions stay as they are. |
| Lab PCs or own laptops? | **Keep it portable** in case a lab PC does not work | Portable builds (no installer, no admin), work follows the student between machines, and a capped cloud sandbox as the last fallback. |
| Must labs work offline? | No, **online is required** for submissions and the rest | Offline mode dropped; only a short reconnect buffer remains. |
| Allow vim/nano? | **Yes** | Terminal editors in every image, a Vim mode in our own editor, and terminal-editor typing logged as its own surface. |
| UX | **Best possible** | Section 6 is expanded into concrete screens, motion specs and performance budgets. |

## 1. What we are building

Rohan saw a desktop lab tool that starts a private Docker sandbox on the
student's own machine for each lab, with an Ubuntu terminal, a file editor,
persistent edits and submission. We take the idea, not the product, and design
our own around what the thesis needs.

**Sandbox Labs** is a new part of Student IDE, next to the existing web labs
and competitions:

- A **catalogue of preset labs** grouped by subject (C programming, Data
  Structures, Operating Systems, Linux and shell, Networks, DBMS, Python).
  Each lab is a set of **assignments** with starter files, a statement,
  tests, and a pinned Linux image with the subject's toolchain.
- Every lab opens in a **private Linux sandbox on the student's machine**
  with a **terminal, a file tree and our editor**. Edits persist; work can be
  submitted and is graded on the server.
- **Monitoring keeps working.** Keystrokes, pastes, edits, runs, focus,
  terminal commands and files changed outside the editor stream to the
  server; the CUSUM detector, live view and review timeline keep working.
  A flag still only starts a conversation.
- **Compute moves to the student's machine.** Sixty live Linux shells on the
  college VM would cost far more than today's short runs; local Docker is
  what makes a terminal per student affordable.

What does not change: existing web labs, competitions, the detector, the
review and the server as the source of truth. Faculty keep working in the
browser.

## 2. Decisions at a glance

| Question | Decision | Main reason |
| --- | --- | --- |
| Shell | **Electron** | Same Chromium as the web app, so keystroke timestamps mean the same thing in both and the recorder is shared code. Tauri's engine differs per OS (WebView2, WebKitGTK, WKWebView), a confound for RQ1 and RQ3. |
| Distribution | **Portable builds** (Windows portable `.exe`, Linux AppImage, macOS `.app` in a zip) plus an optional installer | Runs from Downloads or a USB stick without admin rights. |
| UI code | Reuse `frontend/` (React, CodeMirror 6, Motion) | One design system for web and desktop. |
| Sandbox | One container per (student, lab); one folder per assignment | Instant assignment switching; assignments still separate sessions. |
| Where work lives | Server: event log, plus a **workspace snapshot** per assignment | Work follows the student to any machine; the server can check files against the evidence. |
| Where code runs | Local Docker or Podman first; **capped cloud sandbox** as last resort | "The lab PC doesn't work" must never block a student. |
| Terminal | Always on, every lab | Rohan's call: all preset labs have terminal access. |
| Terminal editors | vim and nano in every image; Vim keys in our editor too | Rohan's call; our editor's Vim mode keeps most typing in the best-logged surface. |
| Network | **Online required**; a short reconnect buffer only | Submissions, live view and grading need it. |
| Submission | Graded on the server runner from the uploaded workspace | An untrusted client cannot fake a grade. |
| Tamper resistance | Visible, not impossible: signed builds, signed hash-chained batches, evidence checks at submission | A student owns their machine; honest framing beats false promises. |
| Faculty | Web app: catalogue, assignment to classes, readiness, live terminal mirror, review | Faculty do not need Docker. |

## 3. Architecture

```
 Student machine (portable app)                                         College VM
 ┌───────────────────────────────────────────────────────────┐        ┌──────────────────────────────┐
 │ Electron                                                   │        │ Caddy → App + API             │
 │  renderer (sandboxed): React UI, CodeMirror, xterm.js      │ HTTPS  │  catalogue, sessions, events  │
 │   └ recorder (same code as web) ─► main: journal, signer ──┼───────►│  workspace store, live view   │
 │  main: Docker/Podman client, auth, updater, workspace sync │        │  detector + review (unchanged)│
 │        │ Docker API (socket / named pipe)                   │        │  runner: grades submissions   │
 │  ┌─────▼────────────────────────────────────────────────┐  │        │  cloud sandbox pool (capped,  │
 │  │ lab container sid-<student>-<lab>                     │  │        │  fallback only)               │
 │  │  /workspace/<assignment>/ … (named volume)            │  │        └──────────────────────────────┘
 │  │  no network, non-root, caps dropped, cpu/mem/pids     │  │
 │  │  shell hooks + file watcher → events                  │  │
 │  └───────────────────────────────────────────────────────┘  │
 └───────────────────────────────────────────────────────────┘
```

The same picture as TikZ is in `latex/flowcharts/desktop-client.tex`.

### 3.1 Electron, not Tauri

Tauri gives a ~10 MB app instead of ~100 MB and uses less RAM. It loses on the
one thing the thesis cannot give up: **measurement consistency**. Students
build baselines in the browser (Chrome on lab PCs) and will also work in the
desktop app; Electron runs the same Chromium, so `KeyboardEvent.timeStamp`,
key repeat and IME behave as in the web app. Electron also has mature pieces
for the rest: `node-pty`/Docker exec streams, `dockerode`, `safeStorage`,
code signing, auto-update, and fuses for hardening. A D0 spike checks timing
parity (scripted typing through a hardware-level injector in both) and RAM
on a lab PC before we commit.

### 3.2 Portable, and work that follows the student

"Portable" has three layers. The first two are fully solvable; the third is
not, and the plan is honest about it.

1. **The app is portable.** No installer, no admin rights: Windows portable
   `.exe` (or a zip), Linux AppImage, macOS `.app`. Settings and caches go in
   the user's profile (or next to the app with a `--portable` flag on a USB
   stick). An installer exists too, for students who prefer one.
2. **The work is portable.** Nothing important lives only on one machine.
   The server holds the event log and a **workspace snapshot** for every
   assignment (the question folder as a compressed tarball, size-capped at
   5 MB, uploaded about 10 s after the last change, on every Run and on
   Submit). Opening the lab on another machine restores the latest snapshot.
   The student can switch from a broken lab PC to their laptop mid-lab and
   carry on from where they were; terminal scrollback does not move.
3. **The sandbox needs a container runtime, which is not portable.** Docker
   or Podman must be installed once on each machine, which on Windows needs
   admin rights and WSL2. So the app picks the best available engine, in
   this order, and shows which one it is using:

   | Engine | When | Notes |
   | --- | --- | --- |
   | Docker Desktop / Docker Engine | Installed and running | Default. Free for education use. |
   | Podman (Desktop or rootless) | Installed | Same API; rootless on Linux avoids the root-equivalent `docker` group. |
   | **Cloud sandbox** | No local engine works | Same image on the college VM (or a second small VM), one container per student, **capped** (e.g. 10 seats per lab, idle after 15 min). Costs VM compute, so it is a safety net, not a mode. Faculty see who is on it. |

   The Lab doctor (section 6.2) makes this choice visible and fixable.

### 3.3 The lab image and container

- **One image per subject**, e.g. `studentide/lab-c:2026.1`, built from one
  Ubuntu LTS base with the subject's tools (gcc, make, gdb, valgrind, python3,
  sqlite3, iproute2 for networking labs as needed) and **vim, nano and
  tmux**. Multi-arch (amd64 + arm64). Pinned by digest in the lab
  definition; hosted on our own registry (Artifact Registry asia-south1 or
  GHCR) to avoid Docker Hub limits; images pulled the day before a lab.
- **One container per (student, lab)** named `sid-<student>-<lab>`, created
  on first open, stopped on app close or after idle, removed when the lab is
  archived. Restart takes about a second.
- **Workspace is a named volume**, one folder per assignment. Not a bind
  mount: faster on Windows/WSL, and the files are not in the student's
  Documents folder.
- **Locked down like today's VM runner**: `--network none` (a lab may opt
  into an apt/pip mirror), non-root user, `cap_drop ALL`,
  `no-new-privileges`, read-only root with tmpfs and the workspace writable,
  CPU, memory and pids limits.

### 3.4 Assignments and persistent state

The sitting model of PR #17 carries over: opening a lab is one sitting, each
assignment visited is its own session linked by `sitting_id`, and switching
logs `focus {target: "question"}` out and in. So the detector and review need
no change for switching.

Each assignment keeps, independently:

| State | Where it lives |
| --- | --- |
| Files (all of them, not just one) | Volume, plus the server's workspace snapshot; the editor's edit log on the server |
| Open files, cursor, scroll, folds, undo | Renderer memory while open; local store across restarts |
| Terminal: its own shell in the assignment folder, cwd, scrollback | Kept alive while the lab is open; last 5,000 lines on disk |
| Last run output, stdin, test results | Local store; submissions and runs on the server |

Switching between assignments is instant because nothing reloads: each
assignment's editor and terminal stay mounted (hidden), only the visible one
renders.

## 4. Monitoring

### 4.1 Editor: unchanged

The recorder is the same file as the web app's, so `key`, `edit`,
`clipboard`, `cursor`, `snapshot`, `focus` and `session_*` events are
identical and the detector keeps its frozen config. The editor gains
multi-file tabs; each edit carries its file path (additive field).

**Vim mode in our editor.** Since vim is allowed, the editor offers Vim key
bindings (CodeMirror's vim extension) as a setting. A student who likes vim
can stay in the editor, where every edit is logged at full detail, instead
of moving to vim in the terminal, where we see far less. Normal-mode
commands are key events like any other; the edits they cause are edit
events as usual.

### 4.2 Terminal and terminal editors (event schema v2, additive)

| Event | When | Content |
| --- | --- | --- |
| `key` with `surface` | Every key down/up anywhere | `editor`, `terminal` (shell prompt) or `terminal-editor` (vim/nano in the foreground, with the file). Same fields as editor keys. |
| `term_cmd` | Each command the shell runs | Command line, cwd, start, exit code, duration, from shell hooks (bash `PROMPT_COMMAND` + `DEBUG` trap emitting OSC 133-style marks, read from the PTY stream). |
| `term_paste` | Paste into the terminal | Text, length and hash, like editor pastes. |
| `fs_change` | A workspace file changes **not** through our editor | Path, size, hash, diff against the last known text, and the command that was running (`vim main.c`, `cat > main.c`, `git checkout`). |
| `term_output` | Per command | Bytes written and a clipped tail. |

How the client knows vim is in the foreground: the shell hook reports the
command start (`vim main.c`) and its end; between the two, terminal keys are
tagged `terminal-editor` with the file. Each save shows up as an
`fs_change` with a diff, so the review can replay a vim session save by save.

What is weaker for vim and nano: we see every key and its timing, and the
file at each save, but not each character edit in between. The review says
so in plain words on that lane.

**Detector.** Shell-prompt typing (short commands, many Enters) is a
different distribution from coding, so `terminal` keys are recorded but kept
out of the identity channel until tested. `terminal-editor` keys are code
typing mixed with vim commands; they are a candidate for the identity
channel, tested on the dev split with the same protocol as the key-pair
channel (PR #10). `term_cmd` compiles and runs count as runs for the process
channel. `fs_change` diffs without matching typing feed the same evidence
lane as large pastes.

### 4.3 Online required, with a short reconnect buffer

- Every event is appended to a per-session journal file by the main process
  before it is acknowledged (fsync every 500 ms), then uploaded in batches;
  `(session_id, seq)` keeps retries idempotent.
- If the connection drops, the student keeps typing for up to **5 minutes**
  with a calm "Reconnecting…" pill; events catch up when it returns. After
  5 minutes the workspace turns read-only with a clear message, until the
  connection is back. Submitting needs a live connection.
- Live view shows "offline since 10:42"; the review timeline shows the gap
  as a gap, never as a flag.
- Each batch carries wall and monotonic clocks; the server records receive
  time, so skew and delays are visible.

### 4.4 Tamper resistance

A student controls their own machine, so the client cannot be tamper-proof.
The aim is that tampering is **expensive and visible**.

| Threat | Counter |
| --- | --- |
| Modified app sends fake events | Code-signed builds; Electron fuses (ASAR integrity, no `RunAsNode`, no `NODE_OPTIONS`), devtools off; server refuses clients below a minimum version. |
| Events dropped, reordered or edited | Per-install keypair in the OS keychain (`safeStorage`) registered at sign-in; every batch signed and carrying the hash of the previous batch. Breaks are shown in the review. |
| Code appears without being typed | At every workspace upload and at Submit the server checks each file against the evidence: editor edits, `terminal-editor` keys with `fs_change` saves, pastes. Content with no supporting evidence is marked "appeared without typing" on the timeline. |
| Files edited from the host (`docker cp`, exec from outside) | The in-container watcher reports them as `fs_change` with no foreground command, shown as "changed outside the app". |
| Grades faked locally | Submissions are graded on the server runner from the uploaded workspace. Local tests are practice. |
| Someone else types, in person or by remote desktop | The detector's job, and the reason the thesis exists. |
| Scripted typing (AutoHotkey, xdotool) | Machine-regular timing; the identity channel is built to notice a different "typist". |

What the client deliberately does **not** do: no screen capture, no webcam,
no list of other apps, no files outside the lab workspace, no keys outside
the app window. Consent v3 explains the terminal logging, workspace
snapshots and the local container before the first Sandbox Lab.

## 5. Faculty side (web app)

1. **Catalogue.** Admins and faculty manage preset labs: subject, image
   version, assignments (statement, starter files, visible and hidden tests,
   time estimate, difficulty). Labs are versioned; a running class keeps the
   version it started with.
2. **Assign to classes.** Pick a lab, a class roster, open and due times,
   live or self-paced. Self-paced labs are how "hosting labs" works: students
   open them whenever, on any machine.
3. **Readiness board** before a live lab: each student's app version,
   engine (Docker, Podman, cloud), image pulled, online now. "48 of 52 ready"
   with the four names and their one-line problem.
4. **Live view** with a read-only terminal mirror next to the editor mirror,
   students always told who is watching (PR #16 rule).
5. **Submissions**: per assignment, tests passed, the submitted files, and a
   link to the session's timeline.
6. **Review timeline** gains lanes: terminal commands, vim saves, files
   changed outside the app, offline gaps, chain breaks. Same evidence style
   as now: moments, not verdicts.
7. **Teacher preview** in the desktop app: open any lab as a student would,
   in a throwaway container, to test the image and starter files.
8. **Cloud sandbox seats**: who is using one, and why (the doctor's
   diagnosis), so IT can fix that PC.

## 6. UX: students and faculty

### 6.1 Principles

- **Calm by default, motion with meaning.** Motion shows where things came
  from (card → workspace, assignment chip → assignment), what changed
  (Run → output, submit → result) and progress (sandbox setup). Durations
  120 to 240 ms, spring easing, one motion system in `frontend/src/ui`
  shared by student and faculty screens.
- **Never move what the student is typing into.** No layout shift in the
  editor or terminal; motion lives in the chrome around them.
- **Motion must not change keystroke timing.** Only compositor properties
  (`transform`, `opacity`), nothing animating on the main thread during
  typing, and a CI benchmark that types a scripted text with and without
  animations and checks recorded inter-key intervals agree within 1 ms.
- **Every wait tells a story.** No bare spinners: setup, pulls, compiles and
  uploads each say what is happening and how long is left.
- **Every error has one next step**, written as a button, not a code.
- **Keyboard first**: everything reachable without the mouse, a command
  palette, visible focus rings.
- Light and dark themes, Inter for UI and JetBrains Mono for code,
  WCAG AA contrast, `prefers-reduced-motion` respected (motion becomes fades).
- **Performance budgets**: app ready in under 2 s from launch, assignment
  switch under 100 ms, key-to-glyph latency under 16 ms, terminal echo under
  30 ms, 60 fps for all transitions on a 4 GB lab PC.

### 6.2 Student screens

1. **Sign-in.** One button, "Continue with your college Google account",
   opens the system browser (PKCE, loopback); the window gently pulls back
   into focus when sign-in completes.
2. **Lab doctor** (first run, and any time from the menu). Checklist rows
   animate from a soft pulse to a tick: Signed in · Container engine found ·
   Engine running · Disk space · Images ready. A failed row expands with one
   plain sentence and one button ("Start Docker Desktop", "Show me how
   (2 min)", "Use a cloud sandbox for now"). Image pulls show a progress ring
   with MB and time left; they keep going in the background.
3. **Home.** Subject shelves (horizontal rows) of lab cards, each with the
   subject colour, a progress ring (assignments submitted / total), due time
   and a status chip: *Live now* (gentle pulse), *Due Fri*, *Submitted*.
   A "Continue where you left off" hero card at the top resumes the last
   assignment in one click. Search and filters by subject.
4. **Opening a lab.** The card expands into the workspace (shared-element
   transition) while the sandbox starts behind it. A thin step line under
   the header reads "Starting sandbox → Restoring your files → Ready" and
   fades away when done; on a warm start it is under a second and barely
   shows.
5. **Workspace.**
   - Left: **assignment rail**, numbered chips with state (not started,
     in progress, tests passing, submitted). `Ctrl+1…9`, `Ctrl+Tab`,
     `Ctrl+K` palette. Switching slides content a few pixels in the
     direction of travel; the rail's highlight glides to the new chip.
   - Next to it, a collapsible **file tree** for the assignment folder.
   - Centre: **editor** with file tabs; Vim mode toggle in the status bar.
   - Right (collapsible): **statement** with examples and a "Tests" tab.
   - Bottom dock: **Terminal**, **Output**, **Tests**. Height remembered per
     assignment; `Ctrl+Backquote` toggles the terminal. Multiple terminal tabs per
     assignment.
   - **Status bar**: recording dot ("Recorded for this lab"), who is watching,
     connection, engine (Docker / Podman / Cloud), sandbox CPU and memory
     mini bars, last saved.
6. **Run and test.** Run morphs into a progress ring while compiling; output
   slides up; compiler errors underline the line and appear in a problems
   list. Tests show as rows that fill green or red one by one, with a diff
   view for failures.
7. **Submit.** A sheet slides up: files included, tests passed locally,
   "graded on the server". After submission the grade arrives with a short,
   restrained confirmation (a check that draws itself), and the rail chip
   turns to *Submitted*. Resubmission is allowed until the due time; history
   is kept.
8. **Connection loss.** A small pill "Reconnecting… your work is safe"
   with a countdown only in the last minute before read-only.
9. **Switching machines.** Opening the same lab elsewhere shows "Restored
   from your last save 2 min ago" with the machine name.

### 6.3 Faculty screens

1. **Catalogue**: subject shelves like the student Home, with an editor for
   assignments (statement preview side by side, starter files, tests with a
   "run in a sandbox" button).
2. **Class lab page**: a header with the clock and counts, the readiness
   board as a grid of student tiles that animate into place as students
   connect, ticks filling in live; tiles sort by attention (not ready,
   offline, on cloud).
3. **Live view**: the grid becomes a live class view; clicking a tile opens
   the student's editor and terminal mirror side by side in a panel that
   slides over without leaving the grid.
4. **Submissions table**: tests passed per assignment, sortable, with a
   heat strip per student; a row opens the files and the timeline.
5. **Timeline**: existing review page with the new lanes collapsed by
   default; hovering a lane expands it smoothly.

## 7. Migration and fit with the current app

Nothing existing is switched off or changed in behaviour.

1. **Catalogue backend**: tables for subjects, preset labs, assignments,
   images, class assignments and workspace snapshots. Sessions for Sandbox
   Labs reuse the `sessions` table with `kind: "sandbox"` and the sitting id,
   so the detector and review work unchanged.
2. **Shared frontend** with a small `Runtime` interface (`prepareLab`, `run`,
   `test`, `terminal`, `files`); the web app keeps today's behaviour.
3. **`desktop/` Electron app** bundles the frontend build and talks to the
   same API with a bearer token.
4. **Schema v2**, additive only: `key.surface`, `edit.path`, `term_cmd`,
   `term_paste`, `fs_change`, `term_output`. v1 recordings stay valid; the
   detector ignores what it does not know.
5. **Session start** records `client: web | desktop`, app version, engine
   and a hashed device id, so analysis can separate devices (RQ3) and the
   review can say "new device" as context.
6. **Cloud sandbox pool** on the VM: same images, capped seats, idle stop.

## 8. Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Lab PCs have no Docker, students lack admin rights | High | Ask IT to install Docker or Podman on the lab image once; portable app on any laptop that has it; capped cloud sandbox for the rest. |
| Windows needs WSL2 and BIOS virtualization | High on old PCs | Lab doctor detects and explains; cloud sandbox fallback. |
| Cloud fallback overused, VM cost grows | Medium | Cap seats per lab, idle stop, readiness board shows who and why so PCs get fixed. |
| Low-RAM PCs (4 GB) | Medium | Small images, one running container, idle stop; measured in D0. |
| Image pulls saturate campus internet at 9 am | Medium | Pre-pull the day before; regional registry; optional LAN mirror. |
| Apple Silicon / ARM laptops | Medium | Multi-arch images. |
| Vim usage hides fine-grained edits | Medium | Vim mode in our editor; `terminal-editor` keys and save diffs; review states the limit. |
| Workspace snapshots grow large (binaries, core dumps) | Medium | 5 MB cap, ignore build outputs (`a.out`, `*.o`, `core`), configurable per lab. |
| Local client tampering | Certain to be tried | Section 4.4; grading on the server; evidence check at submission. |
| Device change confounds baselines | Medium | Same engine (Electron); device recorded per session; RQ3 analyses by device. |
| Ethics: terminal and workspace data are new | Certain | Consent v3 before any pilot; raw keys purged after baseline as today. |

## 9. Milestones

Each milestone ends with something Rohan can try, and adds a brain entry and
thesis material as usual.

| # | Milestone | Done when |
| --- | --- | --- |
| D0 | **Spike** (~1 week): Electron loads the frontend, finds Docker or Podman, opens a terminal in a C container; timing parity browser vs Electron; RAM on a lab PC; portable build runs without admin | Go/no-go note in the brain with the numbers |
| D1 | **Catalogue + one lab end to end**: catalogue tables, one C lab with 3 assignments, portable app, sign-in, sandbox per lab, file tree, editor, terminal, local Run/tests | A student does the lab in the app and its sessions show in the review like web sessions |
| D2 | **Submit and sync**: workspace snapshots, restore on another machine, server grading, signed hash-chained batches, reconnect buffer, min version, auto-update | Switch laptops mid-lab and carry on; submit and see the grade |
| D3 | **Terminal monitoring**: shell hooks, `terminal-editor` detection, file watcher, schema v2, evidence check at submission, consent v3, review lanes, Vim mode in the editor | A vim edit and a `cat > main.c` both appear correctly on the timeline |
| D4 | **Faculty**: catalogue editor, assign to classes, readiness board, live terminal mirror, submissions table, teacher preview | A teacher runs a live Sandbox Lab from the browser end to end |
| D5 | **Fallback + UX polish**: cloud sandbox pool, Lab doctor, full motion pass on all screens, reduced motion, performance budgets and keystroke benchmark in CI | Usability test with 5 students and 2 faculty; budgets and benchmark green |
| D6 | **Pilot**: one real C lab with a class | VM CPU, cloud seat use and feedback logged; next labs chosen |

D1 to D3 are the core; D4 and D5 can overlap with D3.

## 10. Still open

1. Which subjects and labs should the first catalogue hold (we suggest
   C programming first, then Linux and shell)?
2. How many cloud fallback seats is the VM budget comfortable with?
3. Can IT install Docker or Podman on one lab room's PCs for the pilot?

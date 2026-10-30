# Plan: Student IDE desktop client with local Docker labs

Status: **plan, not started** (2026-10-30). Brain entry:
[`2026-10-30-03-desktop-client-plan`](../brain/entries/2026-10-30-03-desktop-client-plan.md).
Figure: [`latex/flowcharts/desktop-client.tex`](../latex/flowcharts/desktop-client.tex).

## 1. What we want and why

Rohan saw a desktop lab tool that starts a private Docker sandbox on the
student's own machine for each lab, with an Ubuntu terminal, a file editor,
persistent edits and submission. We take the idea, not the product: this plan
designs our own client around what the thesis needs.

What we want from a desktop client:

1. **Real environments.** A terminal and a full Linux toolchain per lab
   (gcc, make, gdb, valgrind, Python, shell utilities), which a web Run button
   cannot give. Subjects like OS, networks or DBMS labs become possible.
2. **Compute moves to the student's machine.** Today every Run and Check is a
   process on the college VM's runner container. Running that is cheap; what
   would *not* be cheap is giving 60 students a live terminal each on the VM.
   Local Docker is what makes terminals affordable, more than it saves on
   today's runs.
3. **Monitoring keeps working.** Keystrokes, pastes, edits, runs and focus
   changes still stream to the server, the CUSUM detector and review timeline
   still work, and the terminal becomes a new, logged surface.
4. **Switching questions is instant** and each question keeps its whole state
   (code, undo, cursor, terminal, last output).
5. **A polished, calm, motion-rich UI** for students and faculty.

What does not change: the server stays the source of truth for sessions,
events, grading, the detector and the review. A flag still only starts a
conversation. Faculty keep working in the browser.

## 2. Decisions at a glance

| Question | Recommendation | Main reason |
| --- | --- | --- |
| Shell | **Electron**, not Tauri | Same Chromium as the web app, so keystroke timestamps mean the same thing on both; Tauri uses a different web engine per OS (WebView2, WebKitGTK, WKWebView). |
| UI code | Reuse `frontend/` (React, CodeMirror 6, Motion) behind a `Runtime` adapter | One codebase for web and desktop; web stays the fallback. |
| Sandbox | One container per student per lab, one folder per question | Fast switching (no container start per question); questions still isolated by folder and session. |
| Where code lives | Server is the truth (edit log + snapshots); the local volume is a working copy | Local files can be tampered with; the server's replay cannot. |
| Runs and Checks | Local for practice; competitions and graded labs graded on the server at hand-in | Untrusted client cannot fake a grade; server grades only once per hand-in. |
| Terminal | xterm.js on a `docker exec` shell, logged with key timing, commands and file changes outside the editor | Terminal becomes evidence like the editor, not a blind spot. |
| Offline | Durable local journal, upload later; a live/proctored lab needs the network | Wi-Fi drops should not lose data, but live view needs a connection. |
| Tamper resistance | Detectable, not impossible: signed builds, signed hash-chained batches, server replay checks | A student owns their machine; honest framing is better than false promises. |
| Faculty | Stay on the web app; desktop has an optional teacher preview mode | Faculty do not need Docker to run a class. |

## 3. Architecture

```
 Student machine                                                     College VM (unchanged core)
 ┌──────────────────────────────────────────────────────────┐       ┌──────────────────────────┐
 │ Electron app                                              │       │ Caddy → App + API         │
 │  renderer (sandboxed): React UI, CodeMirror, xterm.js     │ HTTPS │  sessions, events, labs   │
 │   └ recorder (same as web) ──► main: durable journal ─────┼──────►│  detector, review, live   │
 │  main process: Docker client, auth, updater, signer       │       │  runner (hand-in grading) │
 │        │ Docker API (socket / named pipe)                  │       └──────────────────────────┘
 │  ┌─────▼───────────────────────────────────────────────┐ │
 │  │ Docker: lab container sid-<student>-<lab>            │ │
 │  │  /workspace/q1 … /workspace/qN  (named volume)       │ │
 │  │  no network, non-root, caps dropped, cpu/mem/pids    │ │
 │  │  shell hooks + file watcher → events                 │ │
 │  └──────────────────────────────────────────────────────┘ │
 └──────────────────────────────────────────────────────────┘
```

The same picture as TikZ is in `latex/flowcharts/desktop-client.tex`.

### 3.1 Electron vs Tauri

Tauri gives a 10 MB install instead of about 100 MB and lower memory, which is
attractive on old lab PCs. It loses on the one thing the thesis cannot give
up: **measurement consistency**. Students will build baselines in the browser
(Chrome on lab PCs) and may later work in the desktop app. Electron runs the
same Chromium, so `KeyboardEvent.timeStamp`, key repeat and IME behaviour are
the same as in the web app, and the recorder code is literally shared. With
Tauri the engine differs by OS, and any timing difference becomes a confound
in RQ1 and RQ3. Electron also has mature pieces for the rest: `node-pty` /
Docker exec streams, `dockerode`, `safeStorage` for secrets, code signing,
auto-update, and fuses for hardening.

A one-week spike verifies this (milestone D0): type the same scripted text
through both the browser and the Electron build with a hardware-level key
injector, compare inter-key interval distributions.

### 3.2 The `Runtime` adapter

The web app today calls `/api/sessions/{id}/run` and `/check`. We put that
behind an interface so the same UI runs in both places:

```ts
interface Runtime {
  kind: "server" | "local";
  prepareLab(lab): AsyncIterable<SetupStep>;        // pull image, create container, sync files
  run(question, code, stdin): Promise<RunResult>;   // local: docker exec; server: today's endpoint
  check(question, code): Promise<CheckResult>;      // practice only when local
  terminal?(question): TerminalHandle;              // local only
  files?(question): FileTree;                       // local only (multi-file questions later)
}
```

`ServerRuntime` wraps today's endpoints, so the web app behaves exactly as now.
`LocalRuntime` lives in the Electron main process and is reached through a
narrow `contextBridge` API. Labs gain an `environment` field: `web`, `local`
or `either`, so a teacher decides per lab.

### 3.3 The lab container

- **Image per subject**, e.g. `studentide/lab-c:2026.1`, `lab-python`,
  `lab-linux` (OS lab), built from one Ubuntu LTS base, multi-arch
  (amd64 + arm64 for Apple Silicon laptops), pinned by digest in the lab
  definition so every student in a lab has the same toolchain. Hosted on our
  own registry (Artifact Registry in asia-south1, or GHCR) to avoid Docker
  Hub rate limits; a lab-room mirror can be added later.
- **One container per (student, lab)**, named `sid-<student>-<lab>`,
  created on first open, stopped when the app closes or after idle, removed
  when the lab closes. Starting a stopped container takes about a second, so
  reopening a lab is fast.
- **Workspace is a named volume**, one folder per question
  (`/workspace/q3-linked-list/`). Named volume, not a bind mount: faster on
  Windows/WSL, and files are not sitting in the student's Documents folder.
- **Locked down the same way as the VM runner today**: `--network none` by
  default (a lab can opt into a package mirror), non-root user, `cap_drop ALL`,
  `no-new-privileges`, read-only root, tmpfs `/tmp` with `exec`, memory, CPU
  and pids limits. The runner's 5 s / 256 MB limits apply to Run; the
  terminal has wider limits since students may run servers or long jobs.

### 3.4 Persistent state per question

Each question keeps, independently:

| State | Where it lives |
| --- | --- |
| Code | Server (edit log + snapshots, resume code as today) and the volume |
| Undo history, cursor, scroll, folds | Renderer memory for open tabs; local store across restarts |
| Terminal (shell, cwd, scrollback) | One `tmux`-free shell per question started in its folder; scrollback kept in the renderer, last 5,000 lines on disk |
| Last run output, stdin, Check result | Local store, plus runs/checks on the server |

Reopening a lab on another machine: the server's resume code fills the
volume, so code follows the student; terminal history does not (by design).

The "one session per question, linked by a sitting id" model (PR #17) stays.
Switching still logs `focus {target: "question"}` out and in, so the detector
and review need no change for switching.

## 4. Monitoring in a local client

### 4.1 Editor events: unchanged

The recorder is the same file as on the web, so `key`, `edit`, `clipboard`,
`cursor`, `snapshot`, `focus` and `session_*` events are identical. The
detector keeps its features and its frozen config.

### 4.2 Runs

A local Run produces a `run` event as today. Because there is no server-side
`runs` row, the client also posts the run record (`code`, `stdin`, clipped
`stdout`/`stderr`, exit code, duration) to a new `POST /api/sessions/{id}/runs`
with `where: "local"`. The server stores it as untrusted context; the review
shows it as a local run. Run frequency still feeds the process channel.

### 4.3 Terminal logging (schema v2, additive)

The terminal is the new surface. What we log:

| Event | When | Content |
| --- | --- | --- |
| `key` with `surface: "terminal"` | Every key down/up in xterm.js | Same as editor keys (code, class, timing). No characters for typed text beyond what the command line already shows. |
| `term_cmd` | Each command the shell runs | Command line, cwd, start time, exit code, duration, from shell integration hooks (bash `PROMPT_COMMAND` + `DEBUG` trap emitting OSC 133-style marks, read by the client from the PTY stream). |
| `term_paste` | Paste into the terminal | Length and hash, plus the text for the review, like editor pastes. |
| `fs_change` | A file in the question folder changes **not** through our editor | Path, size, hash and a diff against the last known text, with the command that was running (e.g. `cat > main.c`, `sed -i`, `git checkout`). |
| `term_output` | Per command | Bytes written and a clipped tail, not the whole stream. |

`fs_change` matters most. Code that appears through the terminal, from a
`docker cp` on the host, or from any other route is shown on the timeline
like a paste: "code changed outside the editor". A small watcher inside the
container (`inotifywait` on `/workspace`) reports changes; every change the
editor itself made is tagged with its hash so the client can tell the two
apart.

Terminal editors (vim, nano) are left out of the default images. A teacher
can allow them per lab; then edits made in them arrive as `fs_change` plus
terminal key timing, which is weaker evidence than editor edits, and the
review says so.

**Detector.** Terminal key timing is a different distribution from coding
(short commands, many Enter keys), so at first it is recorded but **not** mixed
into the identity channel. Once there is data, a separate terminal digraph
baseline can be tried as an extra channel on the dev split (same protocol as
the key-pair channel in PR #10). `term_cmd` compile/run commands count as runs
for the process channel. `fs_change` outside the editor feeds the same
evidence lane as large pastes.

### 4.4 Offline buffering

- The renderer hands every event to the main process at once; the main
  process appends it to a **journal file per session** (append-only, fsync
  every 500 ms) before acknowledging. A crash or power cut loses at most
  half a second.
- An uploader drains the journal in batches with exponential backoff.
  `(session_id, seq)` is already idempotent, so retries are safe.
- Opening a lab needs the network once (sign-in, lab bundle, session ids for
  every question are issued at sitting start). After that a student can keep
  working offline; events upload when the network returns.
- Labs marked **live** (proctored, competitions) show a clear banner when
  offline and the teacher's live view shows "offline since 10:42". A gap is
  shown on the timeline as a gap, never as a flag.
- Each batch carries the client's wall clock and monotonic clock; the server
  records receive time, so clock skew and long delays are visible.
- Competition hand-in at time end (PR #21) is decided by the server clock; a
  student who is offline at the end gets the code from events that reached
  the server, which is the rule today.

### 4.5 Tamper resistance

A student controls their own machine, so a local client can never be made
tamper-proof. The aim is that tampering is **expensive and visible**, and the
evidence the detector relies on stays checkable on the server.

| Threat | Counter |
| --- | --- |
| Modified app sends fake events | Code-signed builds; Electron fuses (ASAR integrity, no `RunAsNode`, no `NODE_OPTIONS`, devtools off); server refuses clients below a minimum version. |
| Events dropped, reordered or edited after the fact | Each install has a keypair in the OS keychain (`safeStorage`), registered on sign-in; every batch is signed and carries the hash of the previous batch. Breaks in the chain are shown in the review. |
| Code injected without typing | Server already replays edits; it checks that replayed code equals snapshots, runs and hand-ins, and that inserted characters roughly match key downs. Text without keys looks like a paste, which is exactly how the timeline treats it. |
| Files edited from the host (`docker cp`, exec) | `fs_change` events from the in-container watcher; hand-in uses the server's replayed code, not the volume. |
| Grades faked locally | Graded work is graded on the server runner at hand-in. Local Check is practice only. |
| Someone else types, in person or by remote desktop | Unchanged: this is the detector's job, and the reason the thesis exists. |
| Scripted typing (AutoHotkey, xdotool) | Produces machine-regular timing; the identity channel is built to notice a different "typist". |

What the client deliberately does **not** do: no screen capture, no webcam,
no list of other running apps, no files outside the lab workspace, no
keystrokes outside the app window. This keeps the ethics position of the web
app; the consent text (v3) spells out the terminal logging and the local
container.

## 5. Student experience

### 5.1 First run: "Lab doctor"

A friendly check screen instead of an error:

1. Sign in with Google (system browser, PKCE loopback, same
   `@iiitsurat.ac.in` rule as the web app).
2. Checks: Docker installed? Running? Enough disk (images ~400 MB to 1 GB)?
   Virtualization on (Windows)? Each check is a row that animates from
   spinner to tick or to a one-line fix ("Start Docker Desktop" button,
   link to a 2-minute guide).
3. Pre-pulls the images for the student's enrolled labs in the background
   with a progress ring.
4. If Docker cannot work, it says so plainly and offers **"Use the web
   version for this lab"** when the lab allows `web`.

### 5.2 Home

A grid of lab cards coloured by subject, each with a progress ring
(questions attempted / total), due time and status (Open, Live now, Closed).
"Live now" cards pulse gently. Opening a card plays a shared-element
transition: the card expands into the workspace while the container boots
behind it, with a short narrative instead of a spinner: "Preparing your C
lab… starting sandbox… restoring your code… ready".

### 5.3 Workspace

- **Question rail** on the left: numbered chips with state (not started,
  in progress, ran, checks passing). `Ctrl+1…9`, `Ctrl+Tab` and a command
  palette (`Ctrl+K`) switch questions. Switching is instant because nothing
  reloads: each question's editor and terminal stay mounted (hidden), and the
  content slides a few pixels in the direction of travel.
- **Editor** centre, **terminal and output** in a bottom dock with tabs
  (Terminal, Output, Tests). The dock remembers its height per question.
- **Status bar**: recording dot ("Recording for this lab"), who is watching
  (as in PR #16), connection state, sandbox state (CPU/memory mini bars),
  and unsent events if offline.
- **Run** morphs into a progress ring while compiling, then the output panel
  slides up; compile errors underline the line in the editor.
- **Hand-in** opens a calm review sheet: each question with its status and a
  final confirmation; after hand-in the card on Home shows a checkmark
  animation once.

### 5.4 Motion and visual design principles

- **Motion explains, never decorates**: transitions show where things came
  from (card → workspace, chip → question), state changes (run → output) and
  progress (setup steps). 120 to 240 ms, spring easing, one motion system in
  `frontend/src/ui` shared by student and faculty screens.
- **Never move what the student is typing into.** No layout shift in the
  editor or terminal; motion is only in the chrome around them.
- **Animations must not distort keystroke timing.** Only `transform` and
  `opacity` (compositor), no main-thread animation during typing, and a CI
  benchmark that types a scripted text with and without animations running
  and checks the recorded inter-key intervals match within 1 ms. This is a
  thesis requirement as much as a UX one.
- Respect `prefers-reduced-motion`; light and dark themes; Inter for UI,
  JetBrains Mono for code; WCAG AA contrast; full keyboard use with visible
  focus rings.

## 6. Faculty side

Faculty stay in the web app (no Docker needed) with these additions:

1. **Lab environment**: when creating a lab, pick *Browser*, *Desktop
   sandbox* or *Either*, and a subject image (C, Python, Linux shell, …),
   with per-lab switches: terminal on/off, terminal editors allowed,
   package mirror allowed, live (needs network).
2. **Class readiness board** before a lab: each student's client version,
   Docker health, images pulled, online now. A teacher sees "48 of 52 ready"
   before the lab starts, not 20 minutes in.
3. **Live view** gains a read-only terminal mirror next to the editor
   mirror, with the same "student sees who is watching" rule.
4. **Review timeline** gains lanes: terminal commands, files changed outside
   the editor, offline gaps and chain breaks, local vs server runs. Each
   lane uses the existing evidence style (moments, not verdicts).
5. **Teacher preview** (desktop app, optional): open a lab as a student
   would, in a throwaway container, to test starter code and the image.
6. Image catalogue managed by admins (versions, sizes, toolchains), so
   teachers pick, not build, images.

The faculty UI uses the same motion system: the class grid animates tiles
into place as students connect, readiness ticks fill in live, timeline lanes
expand smoothly on hover.

## 7. Migration from the web app

Nothing is switched off. Steps, each shippable on its own:

1. Extract the `Runtime` adapter in `frontend/`; web keeps `ServerRuntime`
   (no behaviour change, existing e2e tests must pass unchanged).
2. Add `desktop/` (Electron) that bundles the same frontend build and talks
   to the same API with a bearer token instead of a cookie.
3. Add the `environment` field to labs (default `web`, so existing labs are
   untouched) and the local-run upload endpoint.
4. Bump the event schema to v2 with only additive types (`term_cmd`,
   `term_paste`, `fs_change`, `term_output`, `key.surface`); v1 recordings
   remain valid, the detector ignores what it does not know.
5. Session start records `client: web | desktop`, client version and a hashed
   device id, so analysis can separate devices (important for RQ3) and the
   review can say "new device" as context.
6. Pilot one lab as `either`; compare VM CPU, run counts and student
   feedback before making any lab `local` only.

## 8. Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Lab PCs have no Docker and students lack admin rights | High | Ask IT to install Docker (or Podman) on lab images once; until then those labs stay `web`. |
| Windows needs WSL2 and BIOS virtualization; Hyper-V conflicts | High on old PCs | Lab doctor detects it and explains; fallback to web. |
| Low-RAM PCs (4 GB) struggle with Docker Desktop + Electron | Medium | Small images, one running container at a time, idle stop; measure in D0. |
| Docker Desktop licensing | Low | Free for education use; Podman Desktop and Rancher Desktop as free alternatives (the client talks the Docker API, which both provide). |
| On Linux, the `docker` group is root-equivalent | Medium | Prefer rootless Docker or Podman on lab machines; document for IT. |
| Image pulls on 60 PCs at 9 am saturate campus internet | Medium | Pre-pull the day before; regional registry; optional LAN mirror. |
| Students on Apple Silicon or ARM laptops | Medium | Multi-arch images. |
| Local client tampering | Certain to be tried | Section 4.5; graded work graded on the server. |
| Device change confounds keystroke baselines | Medium | Same engine (Electron); record client and device per session; analyse by device in RQ3. |
| Two clients to maintain | Medium | One frontend; desktop adds only the runtime, terminal and journal. |
| Ethics: terminal logging is new data | Certain | Consent v3 before any desktop pilot; same retention (raw keys purged after baseline). |

## 9. Milestones

Each milestone ends with something Rohan can try, and adds a brain entry and
thesis material as usual.

| # | Milestone | Done when |
| --- | --- | --- |
| D0 | **Spike** (about 1 week): Electron shell loads the frontend, detects Docker, runs C in a container; timing parity test browser vs Electron; RAM measured on a lab PC | Timing distributions match within measurement error; a go/no-go note in the brain |
| D1 | **Local runs**: `Runtime` adapter, `desktop/` app, Google sign-in, lab container per lab with question folders, local Run/Check, `environment` field | A student does a full C lab in the desktop app and the review looks identical to a web session |
| D2 | **Reliable stream**: durable journal, offline mode, signed hash-chained batches, minimum client version, auto-update | Pull the network cable for 10 minutes mid-lab: nothing lost, review shows the gap |
| D3 | **Terminal**: xterm.js, shell integration, file watcher, schema v2, consent v3, review lanes | A command-line edit to `main.c` shows up as "changed outside the editor" on the timeline |
| D4 | **Faculty**: environment picker, image catalogue, readiness board, live terminal mirror, teacher preview | A teacher runs a desktop lab from the browser end to end |
| D5 | **UI and motion pass**: Lab doctor, Home, workspace, hand-in, faculty screens; reduced-motion; keystroke-latency benchmark in CI | Usability test with 5 students and 2 faculty; benchmark green |
| D6 | **Pilot**: one real lab as `either` | VM CPU and run counts compared; feedback logged; decide which labs go `local` |

D1 to D3 are the core; D4 and D5 can overlap with D3.

## 10. Open questions for Rohan

1. Which subjects need a real terminal first (only C programming, or an OS /
   Linux lab too)?
2. Will labs run on college lab PCs (which OS, can IT install Docker?) or on
   students' own laptops?
3. Must labs work offline, or is the campus network reliable enough that
   "needs network" is acceptable for all labs?
4. Should terminal editors like vim be allowed in some labs?

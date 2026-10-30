# Plan: Sandbox Labs, a portable desktop client with local Docker

Status: **plan, not started** (2026-10-30, revision 4). Brain entries:
[`2026-10-30-03-desktop-client-plan`](../brain/entries/2026-10-30-03-desktop-client-plan.md) (first draft),
[`2026-10-30-04-sandbox-labs-plan-revised`](../brain/entries/2026-10-30-04-sandbox-labs-plan-revised.md) (revision 2),
[`2026-10-30-05-teacher-setup-plan`](../brain/entries/2026-10-30-05-teacher-setup-plan.md) (revision 3: teachers set up subjects and labs) and
[`2026-10-30-06-whole-instance-plan`](../brain/entries/2026-10-30-06-whole-instance-plan.md) (revision 4: a whole instance for any subject).
Figure: [`latex/flowcharts/desktop-client.tex`](../latex/flowcharts/desktop-client.tex).

Revision 2 follows Rohan's answers to the first draft's open questions:

| Question | Rohan's answer | What changed in the plan |
| --- | --- | --- |
| Which subjects need a terminal? | It is a separate, new feature: **preset labs, all with terminal access** | Sandbox Labs is its own product side with a preset lab catalogue; the terminal is always on; existing web labs and competitions stay as they are. |
| Lab PCs or own laptops? | **Keep it portable** in case a lab PC does not work | Portable builds (no installer, no admin), work follows the student between machines. (A cloud fallback for students was later dropped: cloud instances are for teacher previews only.) |
| Must labs work offline? | No, **online is required** for submissions and the rest | Offline mode dropped; only a short reconnect buffer remains. |
| Allow vim/nano? | **Yes** | Terminal editors in every image, a Vim mode in our own editor, and terminal-editor typing logged as its own surface. |
| UX | **Best possible** | Section 6 is expanded into concrete screens, motion specs and performance budgets. |
| (revision 3) | **Teachers set up their own subjects and labs, easily** | Section 5 is new: subjects, an environment builder without Docker knowledge, a lab wizard, tests checked against a reference solution, preview in a cloud sandbox, publish to classes, and a shared library. Admin presets become starting points, not the only labs. |
| (revision 4) | **Versatile for all subjects; users may install any tech stack, since they get a whole instance** | Section 3.5 is new: each student gets a persistent Linux instance per subject with sudo, internet for installs, services and ports. Teachers choose a network mode per lab (open, registries only, off). Monitoring moves to a sidecar the student cannot switch off, and installs are logged. |

## 1. What we are building

Rohan saw a desktop lab tool that starts a private Docker sandbox on the
student's own machine for each lab, with an Ubuntu terminal, a file editor,
persistent edits and submission. We take the idea, not the product, and design
our own around what the thesis needs.

**Sandbox Labs** is a new part of Student IDE, next to the existing web labs
and competitions:

- **Subjects and labs that teachers set up themselves**, in a few minutes
  and without knowing Docker: a teacher creates a subject (e.g. "CS201 Data
  Structures"), picks or builds its environment from a checklist, and adds
  labs of **assignments** with starter files, a statement and tests. There
  are **no admin preset labs** (Rohan, 2026-10-30): the shared library holds
  only labs teachers choose to share, and starter environments cover the
  common subjects.
- Every lab opens in a **whole Linux instance on the student's machine**
  (sudo, internet for installs, services, ports) with a **terminal, a file
  tree and our editor**, so any subject's stack fits: C, Java, Python and
  ML, web, databases, compilers, networking, DevOps. Edits persist; work can be
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
| Distribution | **One installer per OS that also installs its own container engine** (Podman in a small WSL distro or VM), plus a portable build for machines already set up | Rohan's call (2026-10-30): no prerequisites for students. |
| UI code | Reuse `frontend/` (React, CodeMirror 6, Motion) | One design system for web and desktop. |
| Sandbox | **A whole instance per (student, subject)**: persistent, sudo, any package manager; one folder per lab and assignment | Rohan's call: versatile for every subject. Installs survive across the subject's labs. |
| Network | Per lab: **open** (default for practice), **registries only** (package mirrors, for assessed labs), **off** | Installing needs the internet, but an assessed lab should not reach every website. |
| Monitoring inside a root-capable instance | Watcher and command capture in a **sidecar container** the student cannot stop; key timing stays in the app | With sudo, anything inside the instance can be switched off by the student. |
| Where work lives | Server: event log, plus a **workspace snapshot** per assignment | Work follows the student to any machine; the server can check files against the evidence. |
| Where code runs | **Always on the student's machine** (Docker or Podman); cloud instances only for **teacher previews** (Rohan, 2026-10-30) | Keeps VM compute low. A student whose machine cannot run the sandbox moves to one that can, and their work follows them. |
| Terminal | Always on, every lab | Rohan's call: every Sandbox Lab has terminal access. |
| Terminal editors | vim and nano in every image; Vim keys in our editor too | Rohan's call; our editor's Vim mode keeps most typing in the best-logged surface. |
| App connectivity | **Online required**; a short reconnect buffer only | Submissions, live view and grading need it. |
| Submission | Graded on the server runner from the uploaded workspace | An untrusted client cannot fake a grade. |
| Tamper resistance | Visible, not impossible: signed builds, signed hash-chained batches, evidence checks at submission | A student owns their machine; honest framing beats false promises. |
| Faculty | Web app: catalogue, assignment to classes, readiness, live terminal mirror, review | Faculty do not need Docker. |
| Who makes labs | **Teachers**, per subject, created freely; no admin presets; admins only approve raw Dockerfiles | Rohan's call (2026-10-30); presets alone would not fit every course. |
| Environments | Built from a **recipe** (base + ticked tools) by a build service; raw Dockerfile only with admin approval | Teachers never need to know Docker; images stay small, safe and cached. |
| Checking a lab before students see it | Reference solution must pass every test, starter must fail; preview in a **cloud sandbox** | A teacher without Docker can still try the lab exactly as students will. |

## 3. Architecture

```
 Student machine (portable app)                                         College VM
 ┌───────────────────────────────────────────────────────────┐        ┌──────────────────────────────┐
 │ Electron                                                   │        │ Caddy → App + API             │
 │  renderer (sandboxed): React UI, CodeMirror, xterm.js      │ HTTPS  │  catalogue, sessions, events  │
 │   └ recorder (same code as web) ─► main: journal, signer ──┼───────►│  workspace store, live view   │
 │  main: Docker/Podman client, auth, updater, workspace sync │        │  detector + review (unchanged)│
 │        │ Docker API (socket / named pipe)                   │        │  runner: grades submissions   │
 │  ┌─────▼────────────────────────────────────────────────┐  │        │  preview instances for        │
 │  │ instance sid-<student>-<subject> + monitor sidecar    │  │        │  teachers only                │
 │  │  ~/labs/<lab>/<assignment>/ … (named volume)          │  │        └──────────────────────────────┘
 │  │  sudo, installs via proxy, ports, cpu/mem/disk limits │  │
 │  │  sidecar: file watcher, processes, proxy → events     │  │
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
3. **The sandbox needs a container runtime, so the installer brings its
   own** (Rohan, 2026-10-30: install the dependencies instead of asking for
   prerequisites). The **Student IDE installer** sets up everything in one
   run; no separate Docker install. See section 3.6. If Docker or Podman is
   already there, the app can use it instead:

   | Engine | When | Notes |
   | --- | --- | --- |
   | **Bundled engine** (our installer) | Default | Podman inside a small VM we ship; see 3.6. |
   | Docker Desktop / Docker Engine | Already installed | Used if the student or IT prefers it. |
   | Podman (Desktop or rootless) | Already installed | Same API. |

   The portable build still exists for machines where the engine is
   already set up (e.g. lab PCs prepared once with the installer).

   There is **no cloud fallback for students** (Rohan, 2026-10-30): every
   cloud instance would be the VM compute this design exists to save. If no
   local engine works, the Lab doctor (section 6.2) says why, how to fix it,
   and suggests moving to a machine that works; since files sync through
   the server, the student loses nothing by switching. Cloud instances exist
   only for **teacher previews** ("Try as a student", section 5.3): a few
   seats, idle stop after 15 minutes, registries-only network.

### 3.6 One installer that brings its own engine

Students should not have to install Docker first. The installer sets up a
private container engine for Student IDE alone, on each OS:

| OS | What the installer does | Admin rights | Restart |
| --- | --- | --- | --- |
| **Windows 10/11** | Turns on WSL2 if it is off (`wsl --install --no-distribution`), then imports **our own tiny WSL distro** (`StudentIDE`, ~150 MB, Podman inside) and points the app at it. No Docker Desktop. | Once, only if WSL2 is off | Once, only if WSL2 was just turned on; the installer resumes by itself after the reboot |
| **macOS** (Intel and Apple Silicon) | Ships a small Linux VM using Apple's Virtualization framework (via Lima, Apache 2.0) with Podman inside, stored in the user's Library. | No | No |
| **Linux** | Installs Podman from the distro's packages (rootless), or, without sudo, unpacks static rootless Podman into the user's home when the system allows user namespaces. | Only for the package route | No |

Why Podman and our own VM, not Docker Desktop: Podman and Lima are Apache
2.0, so we may ship them inside our installer; Docker Desktop cannot be
redistributed that way and asks the student to accept its own licence.
Rootless Podman also means the sandbox never runs as root on the host.

**What the installer cannot fix**, and how it handles each:

- **Virtualization switched off in the BIOS/UEFI** (common on lab PCs).
  Software cannot turn it on. The installer detects it before anything
  else and shows a short, illustrated guide for the student or IT; on lab
  PCs, IT does it once for the whole room.
- **No admin rights on Windows with WSL2 off.** The installer stops early
  with "Ask IT to run this once" and a one-page note for IT; once WSL2 is
  on, students install without admin.
- **Very old or 4 GB machines.** The installer measures RAM and disk and
  warns honestly before installing.

**Install experience**: one window, three animated steps ("Checking your
PC" → "Setting up the Linux engine" → "Downloading your subjects"), a
time-left estimate, and a single reboot prompt only when Windows needs it.
Images for the student's enrolled subjects download in the background
after sign-in. Updates to the app, the engine and images arrive silently;
uninstalling removes the engine and its disk image cleanly.

**For lab rooms**: the same installer has a silent mode
(`StudentIDE-Setup.exe /S /allusers`) so IT can push it to every PC with
their usual tools, after turning on virtualization once.

### 3.3 The lab image and container

- **One image per environment**, e.g. `studentide/env-c-ds:3`, built from
  one Ubuntu LTS base by the environment builder (section 5.2) with the
  subject's tools (gcc, make, gdb, valgrind, python3, sqlite3, iproute2 for
  networking labs as needed) and always **vim, nano and tmux**. Multi-arch (amd64 + arm64). Pinned by digest in the lab
  definition; hosted on our own registry (Artifact Registry asia-south1 or
  GHCR) to avoid Docker Hub limits; images pulled the day before a lab.
- **One instance per (student, subject)** named `sid-<student>-<subject>`
  (section 3.5), created on first open, stopped on app close or after idle,
  kept for the semester. Restart takes about a second.
- **Workspace is a named volume**, one folder per lab and assignment
  (`/home/student/labs/<lab>/<assignment>/`). Not a bind
  mount: faster on Windows/WSL, and the files are not in the student's
  Documents folder.
- **Isolated from the host, open inside** (section 3.5): sudo and a
  writable root inside the instance, but never `--privileged`, no host
  mounts other than the volumes, user namespaces (rootless Podman or Docker
  `userns-remap`) where available, and CPU, memory, disk and pids limits.

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

### 3.5 A whole instance, for any subject

Each student gets a full Linux machine per subject, not a locked-down
runner, so the same app serves every subject without us predicting its
stack.

**What students (and teachers) can do inside**

- `sudo apt install`, `pip`, `npm`, `cargo`, `go install`, `sdkman`, `conda`,
  downloading tarballs, cloning repos: any tech stack.
- Run **services**: MySQL, PostgreSQL, MongoDB, Redis, Nginx, a Flask or
  Spring server, Jupyter. Services keep running while the lab is open.
- **Ports**: a port a program opens inside (e.g. 3000, 8080, 8888) is
  detected and offered as a one-click preview in an in-app browser tab, or
  forwarded to `localhost` on the host. Web development and Jupyter work as
  on a normal machine.
- **Debugging and systems work**: gdb and strace (`SYS_PTRACE`), processes,
  signals, threads, pipes, shared memory, file systems in user space.
  Networking labs get `NET_ADMIN`/`NET_RAW` inside their own network
  namespace (ping, tcpdump, iptables, socket programming).
- **Multi-machine labs** (later): a lab can define several instances on a
  private network (client/server, a small cluster), from the same recipe.

**Persistence**

- The instance's root filesystem and home are kept for the semester, so a
  tool installed in week 2 is there in week 10. A "Reset instance" button
  rebuilds it from the subject's environment while keeping lab files.
- **Moving machines**: lab files come back from the server's workspace
  snapshots (section 3.2). Installed packages are too big to sync, so the
  app records every install command (from the command log) as the
  student's **setup recipe** and replays it on the new machine: "Restoring
  your setup: installing 4 packages…". The student can view and edit the
  recipe.

**Network modes (per lab, set by the teacher)**

| Mode | What works | Default for |
| --- | --- | --- |
| Open | Full internet | Practice labs and projects only; **not available for assessed labs** (decided 2026-10-30) |
| Registries only | apt, pip, npm, Maven, crates, Go proxy, GitHub releases through a small filtering proxy started next to the instance | Assessed labs |
| Off | Nothing outside the instance | Exams, competitions |

In every mode, traffic leaves through that proxy, which logs host names
(not contents) so the review can say "downloaded from pypi.org" or "visited
github.com". Open mode is honest about what it allows: a student could
fetch a solution, which is why assessed labs default to registries only and
why the evidence check (section 4.4) matters more than the network rule.
**Decided (Rohan, 2026-10-30):** assessed labs can use registries only or
off, never open.

**Resources**: defaults of 2 CPUs, 2 GB RAM and a 10 GB disk per instance,
raised per subject (ML or Java stacks need more), shown live in the status
bar. One instance runs at a time; others stop.

**Limits, stated plainly**: no GPU (CUDA labs need a cloud GPU later),
no Android emulator or other nested VMs, no Windows-only tools, no kernel
modules (OS labs use user space or a VM image instead), GUI programs only
through a later noVNC window. Docker-in-Docker is off by default; a DevOps
subject can enable it with Sysbox or rootless Podman inside, where the host
supports it.

**Teachers get the same instance.** "Set up by hand" in the environment
builder (section 5.2) opens a fresh instance; the teacher installs what the
subject needs in a terminal, and the commands become the environment's
recipe, which the build service turns into an image. Nobody has to write a
Dockerfile.

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
| `pkg_install` | A package manager installs or removes something | Manager (apt, pip, npm, …), packages and versions, from the command log and the package databases. Feeds the setup recipe. |
| `net_conn` | The instance reaches a new host through the proxy | Host name, port, mode decision (allowed or blocked); no contents. |
| `port_open` / `service` | A program starts listening, or a service starts or stops | Port, process name. |

**Where the capture runs.** With sudo, a student can switch off anything
inside the instance, including shell hooks. So:

- **Key timing** never depends on the instance: it is captured in the app
  (xterm.js and the editor), as before.
- The **file watcher, package and process observer and the network proxy**
  run in a **sidecar container** next to the instance. It mounts the
  workspace read-only and sees the instance's processes through a shared
  PID namespace; root inside the instance cannot stop it.
- **Shell hooks** stay for rich command lines, but are best-effort: the
  sidecar also sees every process started (`execve` via the shared PID
  namespace), and when hooks go quiet while processes keep running, the
  review notes "command logging stopped at 10:42".

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
| Monitoring switched off from inside (root in the instance) | Capture lives in the app and the sidecar; silenced shell hooks are visible. |
| Solutions downloaded (open network) | Proxy logs hosts; downloaded or generated files with no typing behind them are "appeared without typing"; assessed labs default to registries only. |
| Files edited from the host (`docker cp`, exec from outside) | The sidecar watcher reports them as `fs_change` with no foreground command, shown as "changed outside the app". |
| Grades faked locally | Submissions are graded on the server runner from the uploaded workspace. Local tests are practice. |
| Someone else types, in person or by remote desktop | The detector's job, and the reason the thesis exists. |
| Scripted typing (AutoHotkey, xdotool) | Machine-regular timing; the identity channel is built to notice a different "typist". |

What the client deliberately does **not** do: no screen capture, no webcam,
no list of other apps, no files outside the lab workspace, no keys outside
the app window. Consent v3 explains the terminal logging, workspace
snapshots and the local container before the first Sandbox Lab.

## 5. Faculty side (web app)

Teachers set up their own subjects and labs. The goal is that a teacher who
has never used Docker can go from nothing to a published lab in **under 15
minutes**, and from a lab a colleague shared to a published lab in
**under 3**. **Teachers create subjects freely**, with no admin approval
(Rohan, 2026-10-30).

### 5.1 Subjects

A subject is the home for a course's labs.

- **Create in one screen**: name, course code, semester, colour/icon
  (auto-suggested from the name), and the environment (5.2). Everything else
  has a sensible default.
- **People**: owner, co-teachers and TAs, reusing lab ownership from PR #19
  (owner and co-teachers edit, TAs view and help in live labs, admins see
  all).
- **Roster once per subject**, used by every lab in it: paste email
  addresses, paste a roll range ("UG24CS001 to UG24CS060", expanded with the
  address format from PR #14), or upload a CSV. Sections (A, B) are optional
  tags so one lab can open for one section only.
- **Copy a subject from last semester** with all its labs, unpublished.

### 5.2 Environment builder (no Docker knowledge needed)

An environment is the Linux toolbox a subject's labs run in.

1. **Pick a base**: C and C++, Python, Java, Linux and shell, Web (Node),
   Databases. Each shows what it includes and its size.
2. **Tick extra tools** from a searchable list (gdb, valgrind, make, cmake,
   strace, sqlite3, postgresql-client, numpy, pandas, pytest, junit, …).
   Each row shows its size; a live total keeps images small.
3. **Optional extras**: pip/apt packages by name (checked against an
   allowlist mirror), a setup script for files every lab needs. A **raw
   Dockerfile** is available too, but goes to an admin for approval.
4. **Build**: a build service (Cloud Build or GitHub Actions to our
   registry, never on the student-facing VM) builds amd64 and arm64 images,
   runs a smoke test (compile hello world, open a shell, check every ticked
   tool), and reports back. The teacher sees a progress line ("Installing
   gdb… 1 min left") and gets a notification when it is ready.
5. **Versions**: changing an environment builds a new version; running labs
   keep the version they started with until the teacher moves them.

Or **set up by hand**: open a fresh instance, install everything in its
terminal as on any Linux machine, try it, and press "Save as environment".
The recorded install commands become the recipe (shown for review and
editable), and the build service builds it reproducibly. Teachers can mix
both: tick the common tools, then add the rest by hand.

Starter environments cover every common subject: C/C++ and DSA, Java
(JDK, Maven, Gradle), Python and data science (Jupyter, numpy, pandas,
scikit-learn), web (Node, npm, a database), DBMS (MySQL, PostgreSQL,
MongoDB clients and servers), compiler design (flex, bison, LLVM), OS and
systems (gdb, strace, valgrind, perf), networks (iproute2, tcpdump,
netcat, Wireshark CLI), DevOps (git, Docker via Podman, Terraform CLI).

Environments are shared: any teacher can reuse "C with gdb and valgrind"
instead of building their own, so most teachers never open the builder.
Students start from the subject's environment and may install more on top
(section 3.5); the subject's environment is what grading uses.

### 5.3 Lab wizard

Four steps with a progress rail; drafts autosave, so a teacher can stop at
any point.

1. **Basics**: title, subject (environment comes from it, can be changed),
   short description, estimated time.
2. **Assignments**, each with:
   - **Statement** in Markdown with live preview, images by paste or drop.
   - **Starter files**: a small file tree; drag in files or a zip, or
     write them in the same editor students use.
   - **Tests**, in the simplest form that works:
     *input/output pairs* in a table (same JSON-line tests as PR #25, so
     every language works), or a *test command* (`make test`, `pytest`)
     whose exit code decides, each marked visible or hidden, with weights.
   - **Reference solution** (optional, strongly suggested): kept private.
   - **Import** instead of writing: from the existing question sources
     (Student IDE sets, Codeforces/CodeChef, MBPP; PRs #13, #15, #20), from
     another lab, from a zip, or from a public Git repo folder.
3. **Check**: the server runs every test against the reference solution
   (all must pass) and the starter (should fail), in the lab's environment,
   and lists problems in plain words ("Assignment 3: test 4 fails on your
   solution — expected `5`, got `5\n`"; "Assignment 2 has no hidden tests").
   **Try as a student** opens the lab in a cloud sandbox in the browser (or
   locally in the desktop app), exactly as a student would see it.
4. **Publish**: pick sections, open and due times, live or self-paced,
   network mode (open, registries only, off; section 3.5),
   grading (tests only, tests plus manual, or manual), late policy. A
   summary card shows what students will see before the final button.

### 5.4 Library

- **No admin presets** (Rohan, 2026-10-30). The library starts empty and
  grows from what teachers share; an empty library shows "Start blank" and
  "Copy last semester" instead.
- **Share to library**: a teacher can publish their lab for colleagues
  (statements, starters and tests; solutions only to teachers). Copies are
  independent, with a "based on" link and an optional "update available".
- Search by subject, topic, language and difficulty.

### 5.5 Editing a lab students already started

Fixing a typo or a wrong test mid-lab is common, so it must be safe:
statement and test fixes apply at once and re-grade existing submissions
(students get a quiet note); starter-file changes ask whether to update
students who have **not started** that assignment (those who started keep
their work). Every change is versioned and shown on the lab's history.

### 5.6 Running a class

1. **Readiness board** before a live lab: each student's app version,
   engine (Docker or Podman), image pulled, online now. "48 of 52 ready"
   with the four names and their one-line problem.
2. **Live view** with a read-only terminal mirror next to the editor mirror,
   students always told who is watching (PR #16 rule).
3. **Submissions**: per assignment, tests passed, the submitted files, and a
   link to the session's timeline; manual marks and comments when the lab
   uses them; export to CSV.
4. **Review timeline** gains lanes: terminal commands, vim saves, files
   changed outside the app, offline gaps, chain breaks. Same evidence style
   as now: moments, not verdicts.
5. **Machines that cannot run the sandbox**: each one with the doctor's
   diagnosis, so IT can fix that PC before the next lab.

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
   plain sentence and one button ("Restart the engine", "Show me how
   (2 min)", "Open on another machine"). Image pulls show a progress ring
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
     connection, engine (Docker / Podman), sandbox CPU and memory
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

1. **My subjects**: subject cards like the student Home, each with its labs,
   next live lab and a "New lab" button; an empty state with three big
   choices: *Start from the library*, *Copy last semester*, *Start blank*.
2. **Environment builder**: base cards that lift on hover, a tool checklist
   with sizes and a live size meter, and a build progress line that turns
   into a ready badge with a small, satisfying settle animation.
3. **Lab wizard**: a left progress rail (Basics, Assignments, Check,
   Publish) whose marker glides between steps; assignments as reorderable
   cards (drag to reorder with spring physics); statement and preview side
   by side; tests as an editable table that grows a row when you tab out of
   the last one. The Check step runs tests as rows that fill green or red one
   by one, with each problem linked to the field that fixes it.
4. **Library**: searchable shelves with a preview drawer that slides in;
   "Use this lab" copies it into the chosen subject and opens the wizard at
   step 2.
5. **Class lab page**: a header with the clock and counts, the readiness
   board as a grid of student tiles that animate into place as students
   connect, ticks filling in live; tiles sort by attention (not ready,
   offline, machine problem).
6. **Live view**: the grid becomes a live class view; clicking a tile opens
   the student's editor and terminal mirror side by side in a panel that
   slides over without leaving the grid.
7. **Submissions table**: tests passed per assignment, sortable, with a
   heat strip per student; a row opens the files and the timeline.
8. **Timeline**: existing review page with the new lanes collapsed by
   default; hovering a lane expands it smoothly.

## 7. Migration and fit with the current app

Nothing existing is switched off or changed in behaviour.

1. **Catalogue backend**: tables for subjects (with people and roster),
   environments (recipe, versions, image digests, build status), sandbox
   labs and versions, assignments (statement, starter files, tests,
   private solution), library entries, class publications and workspace
   snapshots. Ownership and co-teachers reuse the PR #19 checks; rosters
   reuse the PR #14 address rules. Sessions for Sandbox
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
6. **Teacher preview pool** on the VM: same images, a few seats, idle stop;
   teachers only.
7. **Build service** outside the VM (Cloud Build or GitHub Actions) that
   turns recipes into images in our registry.

## 8. Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Lab PCs have no Docker, students lack admin rights | High | Our installer brings its own engine; on Windows only turning on WSL2 needs admin, once (IT can push the silent installer); portable app on any laptop that has it; Lab doctor tells the student to switch machines, work follows them. |
| Windows needs WSL2 and BIOS virtualization | High on old PCs | Installer turns on WSL2 itself; BIOS virtualization cannot be turned on by software, so it is detected first with a guide for the student or IT. |
| Shipping and updating our own engine | Medium | Podman and Lima are maintained upstream; we pin versions, update silently, and test on Windows 10, 11, macOS and Ubuntu in CI. |
| A student has no working machine at all | Low to medium | Lab PCs prepared by IT are the guarantee; teacher can extend the due time. No cloud fallback by design. |
| Teacher previews grow VM cost | Low | A few seats, idle stop, teachers only. |
| Low-RAM PCs (4 GB) | Medium | Small images, one running container, idle stop; measured in D0. |
| Image pulls saturate campus internet at 9 am | Medium | Pre-pull the day before; regional registry; optional LAN mirror. |
| Apple Silicon / ARM laptops | Medium | Multi-arch images. |
| Vim usage hides fine-grained edits | Medium | Vim mode in our editor; `terminal-editor` keys and save diffs; review states the limit. |
| Workspace snapshots grow large (binaries, core dumps) | Medium | 5 MB cap, ignore build outputs (`a.out`, `*.o`, `core`), configurable per lab. |
| Local client tampering | Certain to be tried | Section 4.4; grading on the server; evidence check at submission. |
| Device change confounds baselines | Medium | Same engine (Electron); device recorded per session; RQ3 analyses by device. |
| Teachers write broken or leaky tests | Medium | Check step against the reference solution and starter; hidden tests never sent to clients. |
| Environments bloat or multiply | Medium | Recipes, size meter, shared environments, admin approval for raw Dockerfiles, unused versions pruned. |
| Image builds fail or are slow | Medium | Build off the VM, smoke tests, readable error, previous version stays usable. |
| Teacher setup still feels hard | Medium | Starter environments, shared labs, copy last semester, usability test with 2 teachers timed against the 15 min / 3 min targets. |
| Students break their own instance (rm -rf, broken packages) | High | "Reset instance" keeps lab files and replays the setup recipe; files are on the server anyway. |
| Heavy stacks (Java IDE servers, ML libraries) on 4 GB PCs | Medium | Per-subject resource defaults, one running instance; heaviest subjects run on lab PCs prepared for them. |
| Root in a container on the student's laptop | Medium | Never privileged; user namespaces or rootless Podman; only listed capabilities; the risk is to the student's own machine, which consent explains. |
| Open network makes fetching solutions easy | High in open mode | Registries-only default for assessed labs, host log, evidence check at submission. |
| Grading differs from the student's instance | Medium | Grading runs in the subject's environment plus the student's setup recipe restricted to registry packages; teachers see which packages a submission needed. |
| Teacher preview instances can reach the internet | Low | Registries-only network, small limits. |
| Ethics: terminal, workspace, install and host-name data are new | Certain | Consent v3 before any pilot; raw keys purged after baseline as today. |

## 9. Milestones

Each milestone ends with something Rohan can try, and adds a brain entry and
thesis material as usual.

| # | Milestone | Done when |
| --- | --- | --- |
| D0 | **Spike** (~1–2 weeks): installer prototype that sets up the bundled engine on Windows (WSL2 distro) and macOS (Lima VM); Electron loads the frontend, finds the engine, opens a terminal in a C container; timing parity browser vs Electron; RAM on a lab PC; portable build runs without admin | Go/no-go note in the brain with the numbers |
| D1 | **One lab end to end**: subject and lab tables, one C environment and one C lab with 3 assignments (seeded by hand), portable app, sign-in, instance per subject, file tree, editor, terminal, local Run/tests | A student does the lab in the app and its sessions show in the review like web sessions |
| D2 | **Submit and sync**: workspace snapshots, restore on another machine, server grading, signed hash-chained batches, reconnect buffer, min version, auto-update | Switch laptops mid-lab and carry on; submit and see the grade |
| D3 | **Terminal monitoring and whole instance**: sudo instance per subject, ports preview, setup recipe replay, network modes with the proxy, sidecar watcher and process observer, shell hooks, `terminal-editor` detection, schema v2 (incl. `pkg_install`, `net_conn`, `port_open`), evidence check at submission, consent v3, review lanes, Vim mode in the editor | A vim edit and a `cat > main.c` both appear correctly on the timeline; a student installs Postgres and a Node server, previews it, moves machines and gets the same setup back |
| D4 | **Teacher setup**: subjects with roster and people, environment builder with build service, lab wizard with Check and cloud-sandbox preview, publish to sections, shared library, safe mid-lab edits | A teacher who has not seen the app before sets up a subject and publishes a lab in under 15 minutes |
| D4b | **Running a class**: readiness board, live terminal mirror, submissions table with manual marks and export | A teacher runs a live Sandbox Lab from the browser end to end |
| D5 | **UX polish**: Lab doctor, full motion pass on all screens, reduced motion, performance budgets and keystroke benchmark in CI | Usability test with 5 students and 2 faculty; budgets and benchmark green |
| D6 | **Pilot**: one real C lab with a class | VM CPU, machines that failed the doctor and feedback logged; next labs chosen |

D1 to D3 are the student core; D4 can start alongside D2 since it is web-only; D4b and D5 overlap with D3.

## 10. Still open

Decided on 2026-10-30: teachers create subjects freely; no preset labs;
cloud instances for teacher previews only, no student fallback.

1. Can IT turn on virtualization (BIOS) and run our installer once on one lab room's PCs for the pilot?

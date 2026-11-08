# Sandbox Labs: the local sandbox runtime

The part of the desktop app that runs a student's lab on their own machine:
one Linux instance per (student, subject) in Docker or Podman, the in-app
terminal, the Run button and local tests, workspace snapshots that let work
follow the student to another machine, the setup check ("Lab doctor"), and
the terminal and run events the detector and review read. Plan:
`thesis/plans/2026-10-30-desktop-client.md` (sections 3.2 to 3.6, 4.2).

Code: `desktop/sandbox/` (package `@studentide/sandbox`, plain Node +
TypeScript, no Electron import, no native modules) and
`backend/studentide/workspaces.py` (snapshot and recipe storage). The shell
(`desktop/app`, see [desktop.md](desktop.md)) calls `registerSandboxIpc(ctx)` from
`desktop/app/src/main/modules/sandbox.ts` with the engine saved in `<userData>/engine.json`,
and stops instances on quit (`DesktopModule.dispose`; contract version 2);
the installer calls `setupCheck(engine)`. The catalogue and lab definitions
(`studentide.sandbox-lab/1`) are in [sandbox-labs.md](sandbox-labs.md).

| file | what it does |
|---|---|
| `engine.ts` | runs the engine CLI from the installer's `engine.json` (`cli` argv prefix, `dockerHost`, `env`); Docker and Podman share every subcommand used |
| `instance.ts` | create/start/stop/reset/destroy, limits, network modes, file access, starter files |
| `hooks.ts`, `marks.ts` | shell hooks injected as root on every start; parser for their marks |
| `terminal.ts` | `exec -i` + a PTY made inside the container by `script`; term events, vim/nano detection |
| `run.ts` | Run button and local tests, same result shape as `runner.py`, compares as `grading.py` |
| `workspace.ts`, `recipe.ts` | snapshot/restore and server sync; the setup recipe |
| `doctor.ts` | the setup check, with plain-language reasons and fixes |
| `registries.ts`, `netlog.ts`, `images/sidproxy/` | "registries only" proxy sidecar and its `net_conn` events |
| `desktop.ts`, `api.ts` | the `sandbox.*` / `terminal.*` IPC methods and their types |

## Instance

`sid-<student>-<subject>` (names from the lab definition, `{student}` = the
lower-cased roll number), home on the named volume `sidv-…`, kept for the
semester. Started with `--init … sleep infinity` as user `student`:

- **Isolated from the host, open inside**: sudo and a writable root, never
  `--privileged`, no host network or host mounts, `--cap-drop ALL` plus
  Docker's defaults minus `MKNOD`/`NET_RAW`, plus `SYS_PTRACE` for gdb
  (`NET_ADMIN`/`NET_RAW` only for networking labs). One `--cap-add` per
  capability (Docker refuses a comma list). The hostname is the subject code
  and resolves to 127.0.0.1, so sudo does not stall.
- **Limits** from the lab's `resources` (default 2 CPUs, 2 GB, 512 pids):
  `--cpus --memory --memory-swap --pids-limit`. Where the engine cannot set
  them (rootless on cgroup v1, the WSL distro without systemd) the instance
  runs without and `limitsEnforced` is false; the setup check warns. Disk is
  measured (`stats`) rather than enforced, because `--storage-opt size`
  needs xfs project quotas.
- **One running instance**: starting one stops the student's others; an
  idle instance stops after 30 minutes; the app stops all on quit.
- **Changed environment** (new image digest, limits, network): the container
  is recreated, the volume stays, and the setup recipe is replayed.
- **Reset instance**: same, on request.

### Network modes

| mode | how |
|---|---|
| `off` | `--network none` |
| `registries` | the instance sits only on an `--internal` network shared with a proxy sidecar (`sidproxy-…`, tinyproxy) that is also on the default network; `http(s)_proxy` points at it, apt and sudo are configured to keep it. The allowlist is `registries.ts` (apt, PyPI, conda, npm, Maven, Gradle, crates, Go, GitHub releases). Every host seen becomes one `net_conn` event per decision. |
| `open` | the engine's default network (never for assessed labs) |

## Terminal

One shell per assignment, started in its workdir. `exec -i` carries the
bytes and util-linux `script` inside the container gives bash a real PTY, so
the host needs no `node-pty`; resize runs `stty -F <pty>` in the container.
The runtime writes `/etc/studentide/bashrc` (sourced after the student's own
`.bashrc`) whose `PS0` and `PROMPT_COMMAND` print OSC 6973 marks with the
command line, cwd and exit code. The client strips them before xterm.js sees
them. The student has sudo and can remove the hooks; that is expected: key
timing comes from the app, and silent hooks are visible (`hooksQuietMs`).

While `vim`/`nano`/… is in the foreground, `terminal.surface` tells the
renderer to tag keys `terminal-editor` with the file. Scrollback (5,000
lines) stays on the machine.

## Runs and tests

The Run button runs the assignment's `run` command with `bash -lc` in its
workdir, with stdin, `timeout -s KILL` inside the container and 64 KB output.
`error_type` is `Timeout`, `OutOfMemory`, `NonZeroExit` or null. Local tests
run the visible tests only (practice); grades come from the server. A Check
logs one `run` event, not one per test case.

## Work that follows the student

- **Snapshots**: the assignment folder as a gzipped tar without build outputs
  (`a.out`, `*.o`, `*.class`, `node_modules`, `__pycache__`, `.venv`, …),
  at most 5 MB, uploaded 10 s after the last change (editor save or a
  terminal command ending), on every Run (reason `run`) and on Submit
  (`submit`). The version id is a content hash over paths and file hashes
  that leaves out the same files, so a restored folder hashes the same.
- **Opening a lab**: a folder that does not exist yet is restored from the
  server or, for a new assignment, seeded with the starter files. If both
  this machine and the server changed since the last sync, the server copy
  wins and the local folder is kept beside it as `<workdir>.local-<time>`:
  nothing is lost silently.
- **Setup recipe**: each package command that succeeded in the terminal
  (`apt install`, `pip install`, `npm i -g`, `cargo/go install`, `conda`,
  `gem`) is stored as typed, per subject, and replayed on a new instance
  ("Restoring your setup: …").
- **Server** (`workspaces.py`): `GET/PUT /api/workspaces/{lab}/{assignment}[/meta]`
  and `GET/PUT /api/workspaces/recipes/{subject}`, `?student_id=` like other
  student routes (Google mode: only yourself). Uploads are checked (real
  gzip tar, relative paths, no links out or device files, size and count
  caps); the newest 5 snapshots are kept plus every Submit.

## Setup check

`setupCheck(engine, {image?, quick?})` returns
`{ ok, checks: [{ id, ok, message, fix?, severity }] }`; `ok` is false only
for errors. CLI: `node desktop/sandbox/bin/sandbox-doctor.mjs --engine engine.json`.

| id | checks |
|---|---|
| `host.arch`, `host.memory`, `host.disk` | 64-bit, at least 6 GB (error under 3.5), 12 GB free disk (error under 4) |
| `engine.cli`, `engine.running`, `engine.version`, `engine.linux` | the program exists, the engine answers, Docker ≥ 20.10 / Podman ≥ 4, Linux containers |
| `engine.limits` | limits possible (rootless cgroup v1 warns) |
| `engine.pull`, `engine.run`, `engine.volume`, `engine.network` | an image downloads, a container runs, a volume and an internal network can be made |

Known failure texts are explained (`explain()`): virtualization off in the
BIOS, WSL2 missing, Docker installed but not running, Podman service down, no
permission on the socket, disk full, registry unreachable. Every error ends
with "use another machine that passes this check: your files follow you"
(there is no cloud fallback for students).

## Events (schema v2)

See [event-schema.md](event-schema.md). The runtime builds `{type, data}`;
the renderer's recorder adds `seq` and `t` and logs it into the session of
`sessionKey` (`<lab id>/<assignment id>`): `term_cmd` (start/end),
`term_output`, `term_paste`, `run` (`source` button/test/terminal; compile
and run commands typed in the terminal count as runs), `pkg_install`,
`net_conn`. The detector keeps terminal keys out of the identity channel.

## Tests

```bash
cd desktop/sandbox && bun install   # or npm install
npm run typecheck && npm test       # unit tests, no engine needed
docker build -t studentide-dev-base:test images/dev-base
docker build -t ghcr.io/codehamster69/studentide-sidproxy:1 images/sidproxy
SANDBOX_IT=1 SANDBOX_IT_NET=1 npm run test:engine   # real engine; SANDBOX_CLI=podman for Podman
```

The engine test does a whole lab through `registerSandboxIpc` against a fake
server: open, starter files, failing then passing tests, editor save, Run,
terminal commands, a paste, a vim session, a package command, Submit; then a
"second machine" (instance and volume deleted, fresh app data) gets the files
back and the setup recipe replayed. It also checks the time and memory limits
and the three network modes.

## File watcher (sidecar)

`watcher.ts` starts `sidwatch-<instance>` next to each running instance: the
same image, `--pid container:<instance> --network none`, the workspace volume
mounted read-only, all capabilities dropped except `DAC_READ_SEARCH` and
`SYS_PTRACE`. A POSIX `sh` loop (works on busybox) prints a baseline and then
one line per changed or deleted file and per listening port (from
`/proc/1/net/tcp*`). Busybox only has whole-second mtimes, so each round
compares against the stamp from two rounds ago; a change is reported within
about 2 s.

`FsWatch` turns lines into `fs_change` and `port_open` events (schema v3). The
app's own saves are announced first (`expect`) and not reported again. The
origin comes from the terminal's foreground: vim/nano (also for a save in the
3 s after it exits, since `:wq` saves and quits at once), a command, the Run or
Check button's command, or `outside`. Text files get a line diff
(`textdiff.ts`). If the watcher cannot start the lab still runs and the review
says files were not watched.

## Offline journal and signed batches

`journal.ts` (used by the app's `journal` namespace, see [desktop.md](desktop.md))
keeps every batch the recorder flushes in a JSONL file per session, fsynced
every 500 ms, and sends them in order as signed, hash-chained batches
([event-schema.md](event-schema.md), v3). It survives restarts. While the
server cannot be reached the student keeps working for 5 minutes; after that
the editor and terminal turn read-only until the connection is back (the pill
in the lab header says so) and nothing is lost. Each batch carries how long it
was offline, which the review shows as a gap, never as a moment.

## Presence

The app reports its version, platform, engine, setup check result and open
lab to `POST /api/sandbox/presence` every 60 s and after a setup check or
opening a lab. That feeds the teacher's readiness board
([sandbox-labs.md](sandbox-labs.md)).

## Not yet (later milestones)

Port preview, update channel and code signing. Images are not published yet:
the `sandbox-images` workflow builds the proxy image for amd64 and arm64.

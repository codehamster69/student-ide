---
date: 2026-11-08
type: result
title: Local sandbox runtime for Sandbox Labs (instances, terminal, runs, workspace sync, setup check, schema v2)
thesis-chapter: 12-conclusion
---

## What happened

Workstream 2 of the Sandbox Labs desktop app (plan `thesis/plans/2026-10-30-desktop-client.md`),
built in parallel with the shell (#37), installer (#38) and catalogue threads.

- `desktop/sandbox/` (`@studentide/sandbox`): one Linux instance per (student, subject) in Docker or
  Podman, driven through the engine CLI from the installer's `engine.json`; limits, three network
  modes (off / registries-only proxy sidecar / open), terminal with shell hooks, Run and local tests,
  workspace snapshots and setup-recipe replay, setup check, and the IPC methods for the shell.
- `backend/studentide/workspaces.py`: snapshot and recipe storage, uploads validated.
- Event schema v2 (additive, server accepts v1 and v2): `key.surface/path`, `edit.path`,
  `snapshot.path`, `run.source/command`, `term_cmd`, `term_output`, `term_paste`, `pkg_install`, `net_conn`.
- Detector: terminal keys kept out of the identity channel; each file of a multi-file workspace
  replayed separately; terminal compile/run commands count as runs. v1 recordings give identical features.

## Why

- **CLI, not the Docker API or node-pty**: on Windows the installer's engine is reached only as
  `wsl.exe -d StudentIDE -- podman`; the CLI is the one interface every engine route shares, and a
  PTY made inside the container by `script` avoids a native module in Electron.
- **Hooks injected at start, not baked into images**: environments built from a raw Dockerfile get
  the same monitoring, and the catalogue's images stay plain.
- **tinyproxy sidecar on an internal network** for registries-only labs: the instance has no other
  route out, so the rule holds even with root inside; the proxy log gives host names without contents.
- **Terminal keys out of identity** until tested: shell typing (short commands, many Enters) is a
  different distribution from coding (plan 4.2); recording them now keeps that test possible.
- **Server copy wins on conflict, local kept beside it** (`<workdir>.local-<time>`): a student
  switching machines never loses work silently.

## Evidence

- `desktop/sandbox`: 17 unit tests; 4 engine tests on Docker 29 (a whole lab through the IPC layer,
  then a "second machine" restores files and replays the recipe; time and memory limits; network
  modes: off blocks all, registries allows archive.ubuntu.com/pypi.org and refuses example.com with 403).
- Backend: `pytest -q` 354 passed (14 new in `test_workspaces.py`).
- Setup check on the dev engine: all 10 checks pass; a missing engine and "Docker not running" are
  explained with fixes.

## Follow-ups

- Sidecar file watcher / process observer (`fs_change`, `port_open`), port preview: milestone D3.
- Test `terminal-editor` keys for the identity channel on the dev split (as the key-pair channel, PR #10).
- Measure the runtime on Podman in the WSL distro and Lima once the installer builds them; limits may
  not apply without systemd there (setup check warns).
- Publish the proxy image (`sandbox-images` workflow) before the first pilot.

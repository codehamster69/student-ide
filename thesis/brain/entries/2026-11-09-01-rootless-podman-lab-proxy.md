---
date: 2026-11-09
type: issue
title: Sandbox labs with the "registries" network failed on rootless Podman (Mac VM); proxy now joins via bridge
thesis-chapter: 04-system-design
---

## What happened

The first real sandbox lab on the Mac engine (Lima VM, rootless Podman 5.6.2) failed to
open: `"pasta" is not supported: invalid network mode`. The registries-only proxy sidecar
was created on rootless Podman's default network (pasta) and then attached to the lab's
internal network, which rootless Podman refuses. Putting it on `bridge` fixed the attach,
but the internal network's DNS server then shadowed the outside one, so the proxy could not
resolve registry hosts.

Fix (`desktop/sandbox/src/instance.ts`): the proxy is created on `bridge`. On Podman, the
internal network is created with `--disable-dns`, the proxy is attached at a fixed address
(.254 of the subnet), and the lab gets `--add-host sidproxy:<ip>`. Docker keeps the alias.

## Why

A static address survives the proxy being recreated, and it avoids depending on pasta's
169.254.1.1 forwarder or on a hard-coded public DNS server, which campus networks often
block. The CI integration test runs on Docker only, which is why it never saw this.

## Evidence

Mac, 2026-11-09, test lab `slab_325bec76a3` through `registerSandboxIpc`: openLab 1.8 s, Run
printed `hello from the sandbox`, the terminal ran as `student` with Python 3.12.3, pip
downloaded `six` through the proxy, PyPI returned 200, example.com was refused, and direct
egress could not resolve.

## Follow-ups

- Run the sandbox integration test on Podman in CI too (rootless, pasta default).

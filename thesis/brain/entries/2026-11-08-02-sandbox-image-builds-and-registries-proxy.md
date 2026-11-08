---
date: 2026-11-08
type: event
title: Sandbox Labs environment images built in CI; previews get a registries-only network
thesis-chapter: 12-conclusion (sec:desktop-client), 04-system-design
---

## What happened

Follow-up to 2026-11-08-01, on the same PR (codehamster69/student-ide#40), after Rohan's "do it":

- `backend/studentide/sandbox_build.py` + `.github/workflows/sandbox-images.yml`: every 10 minutes a
  GitHub Actions job asks the server for queued environment versions, builds each recipe's Dockerfile for
  amd64 + arm64 with buildx, pushes it to GHCR, smoke-tests it (student user, sudo, bash, tar, script,
  editors, git, curl) and reports the digest or the failure log. A version stuck in `building` for 2 h is
  handed out again.
- All environments are tags of one GHCR package, `studentide-env:<env>-<version>`, made public once.
- `backend/studentide/registry_proxy.py` + Compose `preview-proxy` and internal network `previews`:
  previews of "registries" labs can reach only package registries (CONNECT/HTTP to an allowlist, 403
  otherwise, host names logged), the same list as the desktop runtime's `registries.ts`; a test keeps
  them equal. Sudoers keeps the proxy variables so `sudo apt` works.

## Why

Without built images, labs fall back to a local build on every student laptop (slow, needs the network
in the lab). Building in CI keeps the student-facing VM small and away from untrusted build steps.
Previews need registries so a teacher can try "pip install" steps the way a student would, while the
cloud never gives the open internet.

## Evidence

- `backend/tests/test_registry_proxy.py` (allowlist, refusals, CONNECT tunnel, HTTP forwarding, host
  list parity), `test_sandbox.py` (stale build requeue, build script against the real endpoints with
  Docker faked). Full suite green.
- Not yet run for real: the GitHub job (needs the secret and variable set) and the proxy on the VM.

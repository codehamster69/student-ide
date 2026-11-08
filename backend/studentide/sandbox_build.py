"""The Sandbox Labs build service: turns queued environment recipes into images.

Runs outside the student-facing VM (a GitHub Actions job, see
.github/workflows/sandbox-env-images.yml, or any machine with Docker buildx). It
asks the server what to build, builds and pushes each image, smoke-tests it,
and reports the digest back (sandbox.py, /api/sandbox/builds). Standard library
only, so CI needs no install.

    STUDENTIDE_BUILD_TOKEN=… python backend/studentide/sandbox_build.py --server https://studentide.example.in
    … --no-push      build for this machine only and report the local image id (dev)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

LOG_TAIL = 8000
# What every image must have (sandbox.COMMON_APT; the desktop runtime needs tar, script, bash).
SMOKE = "id -un | grep -qx student && sudo -n true && command -v bash tar script vim nano tmux git curl >/dev/null"


def call(server: str, token: str, method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(server.rstrip("/") + path, method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"x-build-token": token, "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def sh(args: list[str], stdin: str | None = None, timeout: int = 3600) -> tuple[int, str]:
    p = subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)


def build(job: dict, push: bool, platforms: str) -> tuple[str | None, str]:
    """-> (digest or None, log)."""
    image = job["image"]
    with tempfile.TemporaryDirectory() as ctx:
        with open(os.path.join(ctx, "Dockerfile"), "w") as f:
            f.write(job["dockerfile"])
        meta = os.path.join(ctx, "meta.json")
        args = ["docker", "buildx", "build", "--progress", "plain", "-t", image, "--metadata-file", meta]
        args += ["--platform", platforms, "--push"] if push else ["--load"]
        code, out = sh([*args, ctx])
        if code != 0:
            return None, out
        if push:
            with open(meta) as f:
                digest = json.load(f).get("containerimage.digest")
            ref = f"{image.rsplit(':', 1)[0]}@{digest}"
        else:
            _, digest = sh(["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=60)
            digest, ref = digest.strip(), image
    code, smoke = sh(["docker", "run", "--rm", "--entrypoint", "bash", ref, "-lc", SMOKE], timeout=600)
    if code != 0:
        return None, out + "\n--- smoke test failed (student user, sudo, bash, tar, script, vim, nano, tmux, git, curl)\n" + smoke
    return digest, out


def run_once(server: str, token: str, push: bool, platforms: str) -> int:
    jobs = call(server, token, "GET", "/api/sandbox/builds")
    for job in jobs:
        path = f"/api/sandbox/builds/{job['environment_id']}/{job['version']}"
        print(f"building {job['image']}", flush=True)
        call(server, token, "POST", path, {"status": "building"})
        try:
            digest, log = build(job, push, platforms)
        except Exception as e:  # report, then carry on with the next one
            digest, log = None, f"{type(e).__name__}: {e}"
        if digest:
            call(server, token, "POST", path, {"status": "ready", "digest": digest, "log": log[-LOG_TAIL:]})
            print(f"  ready {digest}", flush=True)
        else:
            call(server, token, "POST", path, {"status": "failed", "log": log[-LOG_TAIL:]})
            print("  failed:\n" + log[-2000:], flush=True)
    return len(jobs)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build queued Sandbox Labs environment images.")
    ap.add_argument("--server", default=os.environ.get("STUDENTIDE_URL"), required="STUDENTIDE_URL" not in os.environ)
    ap.add_argument("--no-push", action="store_true", help="build for this machine only (dev)")
    ap.add_argument("--platforms", default="linux/amd64,linux/arm64")
    a = ap.parse_args()
    token = os.environ.get("STUDENTIDE_BUILD_TOKEN")
    if not token:
        sys.exit("set STUDENTIDE_BUILD_TOKEN")
    n = run_once(a.server, token, not a.no_push, a.platforms)
    print(f"{n} image(s) processed")


if __name__ == "__main__":
    main()

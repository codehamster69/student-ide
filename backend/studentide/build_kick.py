"""Start the Sandbox Labs image build as soon as a version is queued.

The build service is a GitHub Actions workflow (sandbox-env-images.yml). Its
"every 10 minutes" schedule is best effort: GitHub delays and drops scheduled
runs, and in practice it ran every 6 to 8 hours, so a new environment version
sat at "Queued to build" for hours. With $STUDENTIDE_BUILD_DISPATCH_TOKEN set (a
fine-grained token with Actions: read and write on $STUDENTIDE_BUILD_REPO,
default codehamster69/student-ide) the server asks GitHub to run the workflow
now, through workflow_dispatch. The schedule stays as the fallback.

kick() never blocks or raises: it posts from a background thread, skips repeats
within a few seconds (GitHub keeps one pending run, which builds everything
queued), and logs a failure.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request

WORKFLOW = "sandbox-env-images.yml"
GAP_S = 5
log = logging.getLogger(__name__)
_lock = threading.Lock()
_last = 0.0


def enabled() -> bool:
    return bool(os.environ.get("STUDENTIDE_BUILD_DISPATCH_TOKEN", "").strip())


def _post(repo: str, token: str, ref: str) -> None:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW}/dispatches", method="POST",
        data=json.dumps({"ref": ref}).encode(),
        headers={"authorization": f"Bearer {token}", "accept": "application/vnd.github+json",
                 "x-github-api-version": "2022-11-28", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20):
            pass
    except Exception as e:  # the schedule still picks the job up later
        log.warning("could not start the image build workflow: %s", e)


def kick(force: bool = False) -> bool:
    """Ask GitHub to run the build workflow. -> whether a request was sent."""
    global _last
    token = os.environ.get("STUDENTIDE_BUILD_DISPATCH_TOKEN", "").strip()
    if not token:
        return False
    with _lock:
        if not force and time.monotonic() - _last < GAP_S:
            return False
        _last = time.monotonic()
    repo = os.environ.get("STUDENTIDE_BUILD_REPO", "").strip() or "codehamster69/student-ide"
    ref = os.environ.get("STUDENTIDE_BUILD_REF", "").strip() or "main"
    threading.Thread(target=_post, args=(repo, token, ref), daemon=True).start()
    return True

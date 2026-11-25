"""Server side of the desktop app (desktop/app): its config and browser sign-in.

The desktop app shows this server's web app in its own window, so every other
endpoint is shared with the browser. Two things are desktop-only:

* GET /api/desktop/config: the oldest app version this server accepts and where
  to get a new one ($STUDENTIDE_DESKTOP_MIN_VERSION, $STUDENTIDE_DESKTOP_DOWNLOAD_URL).
  The app checks it at start and every few minutes and, at a safe point (no lab
  open), shows an update page that installs the new version (desktop/app
  src/main/modules/updates.ts). `updates` says whether this server serves the
  auto-update feed (desktop_updates.py).

* Mandatory updates (VersionPolicy). With the feed on, the newest published
  release is also the minimum version, so no student keeps using an old app
  ($STUDENTIDE_DESKTOP_REQUIRE_LATEST=0 turns that off and leaves only the fixed
  minimum). An outdated app (User-Agent "StudentIDE-Desktop/<version>") may finish
  the work it has open: events, runs, checks and submissions still go through. It
  can't start new work: creating a session and joining a competition answer 426
  with code "desktop_update_required", and the web app then asks the shell to update.
  When GitHub can't be reached the fixed minimum still holds and nobody is locked out.

* Browser sign-in handoff (Google mode). Google refuses sign-in inside embedded
  browsers, so the app opens #/desktop/signin in the system browser (RFC 8252,
  loopback redirect with PKCE):
    POST /api/auth/desktop/grant     {challenge}        signed-in browser -> {code, expires_in}
    POST /api/auth/desktop/exchange  {code, verifier}   the app -> {cookie: {name, value, expires_at}, me}
  `challenge` is base64url(SHA-256(verifier)). A code lives 2 minutes, works once,
  and only for whoever holds the verifier, which never leaves the app. Only code
  hashes are stored. The grant needs the session cookie, which is SameSite=Lax, so
  another site cannot mint codes with it. Dev mode needs no handoff (roll numbers
  work in the app window) and answers 404.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
import time
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .auth import COOKIE, Auth
from .db import Database

CODE_TTL_S = 120
B64URL = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
DESKTOP_UA = re.compile(r"StudentIDE-Desktop/(\d+(?:\.\d+){0,2})")
# Requests that start new work; an outdated app is refused these (426) and nothing else.
NEW_WORK = re.compile(r"^/api/(sessions|competitions/[^/]+/join)/?$")
RETRY_S = 60  # after GitHub fails, keep the fixed minimum this long before asking again

SCHEMA = """
CREATE TABLE IF NOT EXISTS desktop_grants (
    code_sha256  TEXT PRIMARY KEY,
    challenge    TEXT NOT NULL,
    email        TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    created_at   REAL NOT NULL,
    expires_at   REAL NOT NULL
);
"""


class GrantIn(BaseModel):
    challenge: str = Field(min_length=43, max_length=128)


class ExchangeIn(BaseModel):
    code: str = Field(min_length=16, max_length=128)
    verifier: str = Field(min_length=43, max_length=128)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def challenge_of(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def version_key(v: str) -> tuple[int, int, int]:
    """(major, minor, patch) for comparing; a pre-release suffix is ignored, as in the app."""
    nums = [int(x) if x.isdigit() else 0 for x in v.split("-")[0].split(".")[:3]]
    return tuple(nums + [0] * (3 - len(nums)))  # type: ignore[return-value]


class VersionPolicy:
    """Which desktop app versions this server still accepts (see the module docstring)."""

    def __init__(self, releases=None, clock: Callable[[], float] = time.time):
        self.releases, self.clock = releases, clock
        self._failed_at = -RETRY_S

    def require_latest(self) -> bool:
        return self.releases is not None and os.environ.get("STUDENTIDE_DESKTOP_REQUIRE_LATEST", "1") != "0"

    def latest(self) -> str | None:
        """The newest published version, or None (feed off, nothing released, GitHub down)."""
        if self.releases is None or self.clock() - self._failed_at < RETRY_S:
            return None
        try:
            tag = self.releases.latest().get("tag_name", "")
        except Exception:  # GitHub down or no release yet: the fixed minimum still holds
            self._failed_at = self.clock()
            return None
        v = tag.removeprefix("desktop-v")
        return v if DESKTOP_UA.match(f"StudentIDE-Desktop/{v}") else None

    def min_version(self) -> str | None:
        fixed = os.environ.get("STUDENTIDE_DESKTOP_MIN_VERSION") or None
        latest = self.latest() if self.require_latest() else None
        options = [v for v in (fixed, latest) if v]
        return max(options, key=version_key) if options else None

    def outdated(self, user_agent: str) -> str | None:
        """The minimum version when this User-Agent is a desktop app older than it, else None."""
        m = DESKTOP_UA.search(user_agent or "")
        if not m:
            return None
        need = self.min_version()
        return need if need and version_key(m.group(1)) < version_key(need) else None

    def middleware(self):
        async def gate(request: Request, call_next):
            if request.method == "POST" and NEW_WORK.match(request.url.path):
                need = self.outdated(request.headers.get("user-agent", ""))
                if need:
                    return JSONResponse(status_code=426, content={
                        "detail": f"Update Scribelab to {need} to start new work. Your saved work is safe.",
                        "code": "desktop_update_required", "min_version": need})
            return await call_next(request)
        return gate


def router(db: Database, auth: Auth, me_json: Callable[[dict], dict], updates: bool = False,
           policy: VersionPolicy | None = None) -> APIRouter:
    policy = policy or VersionPolicy()
    with db.connect() as conn:
        conn.executescript(SCHEMA)
    r = APIRouter()

    @r.get("/api/desktop/config")
    def config() -> dict:
        return {
            "min_version": policy.min_version(),
            "latest": policy.latest(),
            # the newest release is mandatory (VersionPolicy); false = only min_version holds
            "require_latest": policy.require_latest(),
            # with updates on, the newest installer from GitHub Releases (desktop_updates.py)
            "download_url": os.environ.get("STUDENTIDE_DESKTOP_DOWNLOAD_URL") or ("/api/desktop/download" if updates else None),
            "updates": updates,
            "sign_in": "browser" if auth.cfg.google else "in-app",
        }

    def google_only():
        if not auth.cfg.google:
            raise HTTPException(404, "desktop sign-in is only needed with Google sign-in; use the roll number screen")

    @r.post("/api/auth/desktop/grant")
    def grant(body: GrantIn, request: Request) -> dict:
        google_only()
        user = auth.current(request)
        if user is None:
            raise HTTPException(401, "sign in first")
        if not B64URL.match(body.challenge):
            raise HTTPException(422, "bad challenge")
        code = secrets.token_urlsafe(32)
        now = time.time()
        with db.connect() as conn:
            conn.execute("DELETE FROM desktop_grants WHERE expires_at < ?", (now,))
            conn.execute("INSERT INTO desktop_grants(code_sha256, challenge, email, created_at, expires_at) VALUES (?,?,?,?,?)",
                         (_sha(code), body.challenge, user["email"], now, now + CODE_TTL_S))
        return {"code": code, "expires_in": CODE_TTL_S}

    @r.post("/api/auth/desktop/exchange")
    def exchange(body: ExchangeIn) -> dict:
        google_only()
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM desktop_grants WHERE code_sha256 = ?", (_sha(body.code),)).fetchone()
            if row is not None:  # one use, whatever happens next
                conn.execute("DELETE FROM desktop_grants WHERE code_sha256 = ?", (row["code_sha256"],))
        if row is None or row["expires_at"] < time.time():
            raise HTTPException(400, "this sign-in code has expired; sign in again")
        if not secrets.compare_digest(challenge_of(body.verifier), row["challenge"]):
            raise HTTPException(400, "this sign-in code belongs to another app")
        user = auth.get_user(row["email"])
        if user is None:
            raise HTTPException(400, "unknown account")
        token, expires = auth.new_session(user["email"])
        return {"cookie": {"name": COOKIE, "value": token, "expires_at": int(expires)}, "me": me_json(user)}

    return r

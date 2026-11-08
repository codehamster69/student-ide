"""Server side of the desktop app (desktop/app): its config and browser sign-in.

The desktop app shows this server's web app in its own window, so every other
endpoint is shared with the browser. Two things are desktop-only:

* GET /api/desktop/config: the oldest app version this server accepts and where
  to get a new one ($STUDENTIDE_DESKTOP_MIN_VERSION, $STUDENTIDE_DESKTOP_DOWNLOAD_URL).
  The app checks it before loading and shows an update page when it is too old.
  `updates` says whether this server serves the auto-update feed (desktop_updates.py).

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
from pydantic import BaseModel, Field

from .auth import COOKIE, Auth
from .db import Database

CODE_TTL_S = 120
B64URL = re.compile(r"^[A-Za-z0-9_-]{43,128}$")

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


def router(db: Database, auth: Auth, me_json: Callable[[dict], dict], updates: bool = False) -> APIRouter:
    with db.connect() as conn:
        conn.executescript(SCHEMA)
    r = APIRouter()

    @r.get("/api/desktop/config")
    def config() -> dict:
        return {
            "min_version": os.environ.get("STUDENTIDE_DESKTOP_MIN_VERSION") or None,
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

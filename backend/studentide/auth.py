"""Sign-in for a real deployment: Google accounts of one college only.

Two modes, picked by the environment:

* **Google mode** ($STUDENTIDE_GOOGLE_CLIENT_ID is set). The browser gets a
  Google ID token with Google Identity Services and posts it to
  /api/auth/google. The server checks the token's signature, audience and
  expiry, that the address is verified and that it belongs to
  $STUDENTIDE_ALLOWED_DOMAIN (default iiitsurat.ac.in, matched on both the
  Workspace `hd` claim and the address). It then sets an HttpOnly session
  cookie. Every student endpoint acts only for the signed-in student, and the
  teacher endpoints need a teacher or admin account.

* **Dev mode** (no client id): the phase 1 behaviour, kept for local work, the
  test suite and staged study sessions in a supervised lab. Students type a
  roll number, teacher screens use $STUDENTIDE_ADMIN_TOKEN.

Roles come from the college's address format. A student address is
<ug|pg><year><branch><roll>@domain, e.g. PG25CS07@iiitsurat.ac.in; the whole
local part, upper-cased, is the student id (the roll digits alone repeat
across years and branches). Any other address on the domain is a teacher.
$STUDENTIDE_ADMINS (comma-separated addresses) are always admins, and an admin
can set anyone's role by hand (TAs, odd addresses), which then sticks over the
pattern. $STUDENTIDE_BRANCH_CODES ("cs,ec,ccs") narrows the branch part; when
unset any 2-4 letters match, so a student of a branch nobody listed is never
mistaken for a teacher.

In Google mode $STUDENTIDE_ADMIN_TOKEN still works for scripts if set; leave
it unset in production.

Lab ownership: a teacher sees and manages only the labs (and competitions) they
made or were added to as a co-teacher, and only the sessions, review
timelines, live views and results recorded in those labs. Admins, the admin
token and dev mode see everything. A lab with no owner (made before ownership
existed) is visible to admins only until an admin hands it to a teacher.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException, Request, Response

from .db import Database

COOKIE = "studentide_session"
ROLES = ("student", "teacher", "admin")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    email         TEXT PRIMARY KEY,          -- lower-case Google address
    name          TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL CHECK (role IN ('student', 'teacher', 'admin')),
    role_source   TEXT NOT NULL DEFAULT 'pattern',  -- 'pattern', 'admin' (set by hand) or 'env' ($STUDENTIDE_ADMINS)
    student_id    TEXT UNIQUE,               -- id used in sessions and rosters, e.g. PG25CS07
    program       TEXT,                      -- UG / PG, parsed from a student address
    year          INTEGER,                   -- admission year, e.g. 2025
    branch        TEXT,                      -- e.g. CS
    roll          TEXT,                      -- roll digits, e.g. 07
    created_at    REAL NOT NULL,
    last_login_at REAL
);

-- Only the SHA-256 of the cookie value is stored, so a copy of the database
-- cannot be used to sign in.
CREATE TABLE IF NOT EXISTS auth_sessions (
    token_sha256  TEXT PRIMARY KEY,
    email         TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    created_at    REAL NOT NULL,
    expires_at    REAL NOT NULL
);
"""


@dataclass
class Config:
    client_id: str | None
    domain: str = "iiitsurat.ac.in"
    admins: frozenset[str] = frozenset()
    branch_codes: tuple[str, ...] = ()  # empty = any 2-4 letters
    admin_token: str | None = None
    session_days: float = 7.0
    secure_cookie: bool = True

    @property
    def google(self) -> bool:
        return bool(self.client_id)

    @classmethod
    def from_env(cls, admin_token: str | None = None) -> "Config":
        env = os.environ.get
        return cls(
            client_id=env("STUDENTIDE_GOOGLE_CLIENT_ID") or None,
            domain=(env("STUDENTIDE_ALLOWED_DOMAIN") or "iiitsurat.ac.in").lower().lstrip("@"),
            admins=frozenset(a.strip().lower() for a in (env("STUDENTIDE_ADMINS") or "").split(",") if a.strip()),
            branch_codes=tuple(b.strip().lower() for b in (env("STUDENTIDE_BRANCH_CODES") or "").split(",") if b.strip()),
            admin_token=admin_token if admin_token is not None else env("STUDENTIDE_ADMIN_TOKEN"),
            session_days=float(env("STUDENTIDE_SESSION_DAYS") or 7),
            secure_cookie=(env("STUDENTIDE_COOKIE_SECURE") or "1") != "0",
        )

    def student_pattern(self) -> re.Pattern:
        branch = "|".join(sorted(map(re.escape, self.branch_codes), key=len, reverse=True)) or "[a-z]{2,4}"
        return re.compile(rf"^(ug|pg)(\d{{2}})({branch})(\d{{1,4}})$", re.I)


def not_yours(detail: str) -> HTTPException:
    """403 for a lab the teacher may not touch. The header tells the browser it
    is not a sign-in problem, so it shows the message instead of signing out."""
    return HTTPException(403, detail, headers={"X-Refusal": "not-yours"})


@dataclass(frozen=True)
class Teacher:
    """Who is asking on a teacher endpoint. `email` is None for the admin token and dev mode."""
    email: str | None
    admin: bool


def parse_address(email: str, cfg: Config) -> dict:
    """Role and student fields from an address on the college domain."""
    local = email.split("@", 1)[0]
    m = cfg.student_pattern().match(local)
    if m:
        program, yy, branch, roll = m.groups()
        return {"role": "student", "student_id": local.upper(), "program": program.upper(),
                "year": 2000 + int(yy), "branch": branch.upper(), "roll": roll}
    # Teachers get an id too, so they can try the student editor themselves.
    sid = re.sub(r"[^A-Za-z0-9_-]", "_", local)[:32].upper()
    return {"role": "teacher", "student_id": sid, "program": None, "year": None, "branch": None, "roll": None}


def roster_id(raw: str, cfg: Config) -> str:
    """A roster entry typed by a teacher: a student id or a full address."""
    raw = raw.strip()
    if cfg.google:
        if "@" in raw:
            raw = raw.split("@", 1)[0]
        raw = raw.upper()
    return raw


def google_verifier(client_id: str) -> Callable[[str], dict]:
    """Checks a Google ID token (signature against Google's published keys,
    issuer, audience, expiry) and returns its claims."""
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    transport = g_requests.Request()

    def verify(credential: str) -> dict:
        return id_token.verify_oauth2_token(credential, transport, client_id)
    return verify


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Auth:
    def __init__(self, db: Database, cfg: Config, verify: Callable[[str], dict] | None = None):
        self.db, self.cfg = db, cfg
        self._verify = verify
        with db.connect() as conn:
            conn.executescript(SCHEMA)

    # -- accounts

    def verify(self, credential: str) -> dict:
        if self._verify is None:
            self._verify = google_verifier(self.cfg.client_id)
        try:
            claims = self._verify(credential)
        except Exception:
            raise HTTPException(401, "Google sign-in could not be verified, please try again")
        email = str(claims.get("email", "")).lower()
        domain = self.cfg.domain
        if not claims.get("email_verified") or claims.get("hd", "").lower() != domain or not email.endswith("@" + domain):
            raise HTTPException(403, f"Sign in with your @{domain} account")
        return claims | {"email": email}

    def upsert_user(self, email: str, name: str = "") -> dict:
        """Create or refresh the account at sign-in. A role set by an admin sticks;
        otherwise the role follows the address pattern."""
        email = email.lower()
        parsed = parse_address(email, self.cfg)
        now = time.time()
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            role, source = parsed["role"], "pattern"
            if row is not None and row["role_source"] == "admin":
                role, source = row["role"], "admin"
            if email in self.cfg.admins:
                role, source = "admin", "env"
            fields = {k: parsed[k] for k in ("student_id", "program", "year", "branch", "roll")}
            if row is None:
                conn.execute(
                    """INSERT INTO users(email, name, role, role_source, student_id, program, year, branch, roll,
                                         created_at, last_login_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (email, name, role, source, *fields.values(), now, now))
            else:
                conn.execute(
                    """UPDATE users SET name = COALESCE(NULLIF(?, ''), name), role = ?, role_source = ?, student_id = ?,
                       program = ?, year = ?, branch = ?, roll = ?, last_login_at = ? WHERE email = ?""",
                    (name, role, source, *fields.values(), now, email))
        self.db.get_or_create_student(parsed["student_id"])
        return self.get_user(email)

    def get_user(self, email: str) -> dict | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict]:
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY role DESC, email")]

    def set_role(self, email: str, role: str, by: str) -> dict:
        """Admin override. An address not seen yet is created, so a teacher can
        be set up before their first sign-in."""
        email = email.strip().lower()
        if role not in ROLES:
            raise HTTPException(400, f"role must be one of {', '.join(ROLES)}")
        if not email.endswith("@" + self.cfg.domain) or email.count("@") != 1:
            raise HTTPException(400, f"only @{self.cfg.domain} addresses can have accounts")
        if email in self.cfg.admins:
            raise HTTPException(409, "this address is an admin through STUDENTIDE_ADMINS")
        if email == by and role != "admin":
            raise HTTPException(409, "you cannot remove your own admin role")
        if self.get_user(email) is None:
            self.upsert_user(email)
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET role = ?, role_source = 'admin' WHERE email = ?", (role, email))
            if role == "student":  # sign out a demoted teacher everywhere
                conn.execute("DELETE FROM auth_sessions WHERE email = ?", (email,))
        return self.get_user(email)

    def reset_role(self, email: str) -> dict:
        """Drop the override: the role follows the address pattern again."""
        email = email.strip().lower()
        if self.get_user(email) is None:
            raise HTTPException(404, "unknown account")
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET role_source = 'pattern' WHERE email = ?", (email,))
        return self.upsert_user(email)

    # -- cookie sessions

    def new_session(self, email: str) -> tuple[str, float]:
        """A fresh session token and its expiry (unix seconds); only its hash is stored."""
        token = secrets.token_urlsafe(32)
        now = time.time()
        expires = now + self.cfg.session_days * 86400
        with self.db.connect() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now,))
            conn.execute("INSERT INTO auth_sessions(token_sha256, email, created_at, expires_at) VALUES (?,?,?,?)",
                         (_sha(token), email, now, expires))
        return token, expires

    def sign_in(self, response: Response, email: str) -> None:
        token, expires = self.new_session(email)
        response.set_cookie(COOKIE, token, max_age=int(expires - time.time()), httponly=True,
                            secure=self.cfg.secure_cookie, samesite="lax", path="/")

    def sign_out(self, request: Request, response: Response) -> None:
        token = request.cookies.get(COOKIE)
        if token:
            with self.db.connect() as conn:
                conn.execute("DELETE FROM auth_sessions WHERE token_sha256 = ?", (_sha(token),))
        response.delete_cookie(COOKIE, path="/")

    def current(self, request: Request) -> dict | None:
        token = request.cookies.get(COOKIE)
        if not token:
            return None
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT u.* FROM auth_sessions a JOIN users u ON u.email = a.email
                   WHERE a.token_sha256 = ? AND a.expires_at > ?""", (_sha(token), time.time())).fetchone()
        return dict(row) if row else None

    # -- guards

    def token_ok(self, request: Request) -> bool:
        tok = self.cfg.admin_token
        return bool(tok) and secrets.compare_digest(request.headers.get("x-admin-token", ""), tok)

    def require_teacher(self, request: Request) -> None:
        """Dependency for every teacher / research endpoint."""
        if self.token_ok(request):
            return
        if not self.cfg.google:
            if not self.cfg.admin_token:
                raise HTTPException(403, "research endpoints are disabled: set STUDENTIDE_ADMIN_TOKEN")
            raise HTTPException(401, "bad admin token")
        user = self.current(request)
        if user is None:
            raise HTTPException(401, "sign in first")
        if user["role"] not in ("teacher", "admin"):
            raise HTTPException(403, "this needs a teacher account")

    def teacher(self, request: Request) -> Teacher:
        """The teacher behind a request that already passed require_teacher."""
        if self.token_ok(request) or not self.cfg.google:
            return Teacher(None, True)
        user = self.current(request)
        if user is None or user["role"] not in ("teacher", "admin"):
            raise HTTPException(403, "this needs a teacher account")
        return Teacher(user["email"], user["role"] == "admin")

    def lab_ids(self, request: Request) -> set[str] | None:
        """Labs this teacher may see; None = all (admins)."""
        t = self.teacher(request)
        return None if t.admin else self.db.teacher_lab_ids(t.email)

    def check_lab(self, request: Request, lab_id: str | None) -> Teacher:
        """403 unless the lab is the teacher's own or shared with them (a Sandbox Lab: its
        subject's owner, teachers and TAs). A session outside any lab (practice tasks) is for admins only."""
        t = self.teacher(request)
        if not t.admin and (lab_id is None or (lab_id not in self.db.teacher_lab_ids(t.email)
                                               and not self.db.sandbox_lab_teacher(lab_id, t.email))):
            raise not_yours("this lab belongs to another teacher" if lab_id else "only admins see practice sessions")
        return t

    def require_admin(self, request: Request) -> dict:
        user = self.current(request) if self.cfg.google else None
        if user is None or user["role"] != "admin":
            raise HTTPException(403, "this needs an admin account")
        return user

    def own_student(self, request: Request, student_id: str) -> None:
        """In Google mode a student endpoint acts only for the signed-in student."""
        if not self.cfg.google:
            return
        user = self.current(request)
        if user is None:
            raise HTTPException(401, "sign in first")
        if user["student_id"] != student_id:
            raise HTTPException(403, "you can only act as yourself")

    def previewer(self, request: Request) -> Teacher | None:
        """The teacher or admin behind a student-endpoint request made from
        "View as student", else None. Google mode: a signed-in staff account
        (staff have their own student id, so own_student lets them through).
        Dev mode: the admin token sent with the request. Students can never
        claim this, so their sessions can't be hidden from the study."""
        if self.token_ok(request):
            return Teacher(None, True)
        if not self.cfg.google:
            return None
        user = self.current(request)
        if user is None or user["role"] not in ("teacher", "admin"):
            return None
        return Teacher(user["email"], user["role"] == "admin")

    def preview_lab_ids(self, t: Teacher) -> set[str] | None:
        """Labs a previewing teacher sees as a student would: their own and
        shared labs; None = all (admins)."""
        return None if t.admin else self.db.teacher_lab_ids(t.email)

    def own_session(self, request: Request, session_row) -> None:
        self.own_student(request, session_row["student_id"])

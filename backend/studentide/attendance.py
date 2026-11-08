"""Attendance from labs, through Roll Call (the attendance site, codehamsters/attendance).

Keys. Student IDE makes each teacher's Roll Call sync key (or the teacher pastes
one they already use) and keeps it on the server. "Open Roll Call" asks Roll Call
for a one-time sign-in link, so the teacher lands there signed in; the key itself
can be shown to its owner to sign in by hand. Each key is its own Roll Call
workspace, so a teacher sees only their own register. Each student gets a
student key (st_...), granted through every teacher whose class groups list
them, which opens only their own marks on Roll Call's read-only My attendance.

A lab can then
attach one or more Roll Call class groups (pick existing ones or create one
here). When the lab ends, every student who *effectively participated* is
marked present in their own class group's register, one Roll Call session per
class group and lab day; everyone else on that class's roster is absent.

Effective participation (per student, per lab day; thresholds per lab):

    active minutes  >= min_active_minutes (default 10)
                       distinct wall-clock minutes with an edit, a Run or a Check
    typed chars     >= min_typed_chars (default 40)
                       characters typed into the editor; pastes, drops and Reset don't count.
                       In a Sandbox Lab, characters typed in the lab's terminal (the prompt,
                       vim, nano) count too (Rohan, 2026-11-08): printable key presses there,
                       since terminal input has no edit events
    runs + checks   >= 1, only when require_run is set (default off)

Sandbox Labs (desktop app, sandbox.py) use the same rule and Roll Call class groups; their
sessions carry the sandbox lab id in sessions.lab_id. Active minutes there also count terminal
commands, terminal typing and the app's Run/Check presses (their `run` events: the desktop
runs locally, so there are no runs/checks rows). Terminal typing is read from key events, so
a sandbox lab day should be sent before retention.py purges raw keys (closing the lab sends it).

Only the lab's own sessions count: learning-lab practice (context 'learn') and
staff "View as student" previews (context 'preview') never do. Only edit, run
and check records are used, never key timings, so this works after retention.py
has purged raw keys and is unrelated to the detector: a flag never changes
attendance.

    GET    /api/teach/attendance                    this teacher's Roll Call connection
    POST   /api/teach/attendance/key                make this teacher's key (a new Roll Call workspace), if none yet
    GET    /api/teach/attendance/key                show it, to sign in to Roll Call by hand
    POST   /api/teach/attendance/key/rotate         replace the key: same register under a new key; the old key stops working
    GET    /api/teach/attendance/registers          admins: every teacher's Roll Call register (never the keys)
    POST   /api/teach/attendance/registers/{email}/open   admins: one-time link into that register, full access; logged
    POST   /api/teach/attendance/open               {url}: one-time link that opens Roll Call signed in (makes the key first)
    PUT    /api/teach/attendance                    {sync_key}  use an existing Roll Call key instead (checked first)
    DELETE /api/teach/attendance                    disconnect
    GET    /api/teach/attendance/labs               per lab: attached class groups and lab days sent
    GET    /api/teach/attendance/classes            the teacher's Roll Call class groups (?every=1: admins, every teacher's)
    POST   /api/teach/attendance/classes            {branch, section, group, groups: [{prefix, start, end, digits, exclude}]}
    GET    /api/teach/attendance/subjects           Roll Call subjects (for the lab's subject picker)
    POST   /api/teach/attendance/subjects           {name, code}
    GET    /api/teach/labs/{id}/classes             attached class groups, rule, lab days and what was sent
    PUT    /api/teach/labs/{id}/classes             {class_ids, add_to_roster}  attach / detach
    PUT    /api/teach/labs/{id}/attendance/rule     {min_active_minutes, min_typed_chars, require_run, auto_send}
    GET    /api/teach/labs/{id}/attendance?day=     preview: who would be marked present, and why
    POST   /api/teach/labs/{id}/attendance          {day, overrides: {student: "P"|"A"}}  send to Roll Call

    GET    /api/attendance/{student}                {enabled}: is this student in any attached class group
    POST   /api/attendance/{student}/open           {url, key}: grants their key, then a one-time link to My attendance

One lab can serve several groups on different days (G1 on Monday, G2 on
Tuesday): a group none of whose students worked in the lab on a day is not
sent for that day, so G2 isn't marked absent on G1's day. Overriding a mark in
that group sends it anyway (e.g. the whole group skipped the lab).

Sittings. Opening a lab (PATCH status=open, performing=[class ids]) starts a
sitting for the groups performing now; while it is open, students of the lab's
other groups can't work in it (db.labs_for_student). Sending performing again
while open switches to the next group: the previous sitting ends and its
attendance is sent, for its groups only. Closing ends the last one the same way.

Closing a lab (PATCH status=closed) sends every lab day not sent yet, if the
lab has class groups and auto_send is on. Sending again replaces the same Roll
Call sessions (their ids are derived from lab + class + day), never duplicates.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .db import Database

SCHEMA = """
-- A teacher's Roll Call connection. The sync key is the teacher's whole Roll
-- Call workspace, so it never leaves the server and is never sent to a browser.
CREATE TABLE IF NOT EXISTS attendance_links (
    email         TEXT PRIMARY KEY,          -- '' = dev mode / admin token
    sync_key      TEXT NOT NULL,
    connected_at  REAL NOT NULL,
    checked_at    REAL,
    issued        INTEGER NOT NULL DEFAULT 0 -- 1 = made by Student IDE, 0 = pasted by the teacher
);

-- Every time an admin opened another teacher's Roll Call register.
CREATE TABLE IF NOT EXISTS attendance_admin_opens (
    at            REAL NOT NULL,
    admin         TEXT NOT NULL,
    teacher       TEXT NOT NULL
);

-- A student's key for Roll Call's read-only My attendance (st_...). Roll Call
-- only ever sees its sha256, granted per teacher workspace.
CREATE TABLE IF NOT EXISTS student_keys (
    student_id    TEXT PRIMARY KEY,
    key           TEXT NOT NULL,
    created_at    REAL NOT NULL
) WITHOUT ROWID;

-- lab_classes and lab_runs live in db.py (labs_for_student reads them).

-- lab_id is a web lab (labs) or a Sandbox Lab (sbx_labs), so these tables carry no
-- foreign key; Database.delete_lab clears them (older databases are rebuilt once, below).
CREATE TABLE IF NOT EXISTS lab_attendance (
    lab_id        TEXT PRIMARY KEY,
    rule_json     TEXT NOT NULL,
    auto_send     INTEGER NOT NULL DEFAULT 1  -- send on closing the lab
);

-- One row per lab day and class group sent to Roll Call (the latest send).
CREATE TABLE IF NOT EXISTS attendance_sent (
    lab_id        TEXT NOT NULL,
    day           TEXT NOT NULL,             -- yyyy-mm-dd in STUDENTIDE_TIMEZONE
    class_id      TEXT NOT NULL,
    rollcall_id   TEXT NOT NULL,             -- Roll Call session uuid
    sent_at       REAL NOT NULL,
    sent_by       TEXT NOT NULL,
    how           TEXT NOT NULL,             -- 'teacher' or 'lab closed'
    present       INTEGER NOT NULL,
    total         INTEGER NOT NULL,
    marks_json    TEXT NOT NULL,
    overrides_json TEXT NOT NULL DEFAULT '{}',
    error         TEXT,                      -- set when the last try failed (marks_json = what was attempted)
    PRIMARY KEY (lab_id, day, class_id)
) WITHOUT ROWID;
"""

DEFAULT_RULE = {"min_active_minutes": 10, "min_typed_chars": 40, "require_run": False}
COUNTED_CONTEXT = None  # sessions.context: NULL = a real lab session (not 'learn', not 'preview')
NOT_TYPED = ("input.paste", "input.drop")
TYPED_KEY = ("letter", "digit", "space", "punct")  # a printable key press (terminal typing, Sandbox Labs)


def sandbox_lab(db: Database, lab_id: str) -> dict | None:
    """A Sandbox Lab as attendance needs it ({id, title, subject, subject_id}), or None."""
    with db.connect() as conn:
        try:
            row = conn.execute("""SELECT l.id, l.title, l.subject_id, s.title AS subject_title, s.code AS subject_code
                                  FROM sbx_labs l JOIN sbx_subjects s ON s.id = l.subject_id WHERE l.id = ?""", (lab_id,)).fetchone()
        except Exception:  # sandbox tables not created (sandbox router not mounted)
            return None
    if row is None:
        return None
    subject = f"{row['subject_code']} {row['subject_title']}".strip() if row["subject_code"] else row["subject_title"]
    return {"id": row["id"], "title": row["title"], "subject": subject, "subject_id": row["subject_id"], "kind": "sandbox"}


def any_lab(db: Database, lab_id: str):
    """A web lab (labs table) or a Sandbox Lab."""
    return db.get_lab(lab_id) or sandbox_lab(db, lab_id)


ANY_LAB_TABLES = ("lab_classes", "lab_attendance", "attendance_sent")


def _drop_lab_fk(db: Database) -> None:
    """Databases from before Sandbox Labs had attendance: rebuild the tables whose lab_id
    referenced labs(id), without that foreign key (SQLite cannot drop one in place)."""
    conn = sqlite3.connect(db.path, timeout=10)
    try:
        for table in ANY_LAB_TABLES:
            row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
            if row is None or "REFERENCES labs(id)" not in row[0]:
                continue
            new_sql = re.sub(r"\s*REFERENCES labs\(id\) ON DELETE CASCADE", "", row[0]).replace(f"CREATE TABLE {table}", f"CREATE TABLE {table}__new", 1)
            conn.execute("PRAGMA foreign_keys=OFF")
            with conn:
                conn.execute(new_sql)
                conn.execute(f"INSERT INTO {table}__new SELECT * FROM {table}")
                conn.execute(f"DROP TABLE {table}")
                conn.execute(f"ALTER TABLE {table}__new RENAME TO {table}")
    finally:
        conn.close()


def ensure_schema(db: Database) -> None:
    _drop_lab_fk(db)
    with db.connect() as conn:
        conn.executescript(SCHEMA)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(attendance_links)")}
        if "issued" not in cols:  # databases from before keys were made here
            conn.execute("ALTER TABLE attendance_links ADD COLUMN issued INTEGER NOT NULL DEFAULT 0")


def login_link(out: dict) -> str:
    """Roll Call's one-time sign-in link, on the address this server knows Roll Call by."""
    return f"{rollcall_url()}/login#code={out['code']}"


def new_teacher_key() -> str:
    return secrets.token_urlsafe(30)  # 40 characters, Roll Call's key format


def new_student_key() -> str:
    return "st_" + secrets.token_urlsafe(30)


def timezone() -> ZoneInfo:
    return ZoneInfo(os.environ.get("STUDENTIDE_TIMEZONE") or "Asia/Kolkata")


def rollcall_url() -> str:
    return (os.environ.get("STUDENTIDE_ATTENDANCE_URL") or "https://attendance.hokora.xyz").rstrip("/")


# Roll Call client ------------------------------------------------------------

class RollCallError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


# (method, url, sync key, json body or None) -> (http status, parsed json)
Transport = Callable[[str, str, str, dict | None], tuple[int, object]]


LINK = "link:"  # "key" of a server-to-server link call: the shared secret, not a sync key


def key_header(key: str) -> dict[str, str]:
    """A student key goes in x-student-key, a teacher's sync key as a bearer token,
    and a link call carries the shared link secret."""
    if key.startswith(LINK):
        return {"x-link-secret": key[len(LINK):]}
    return {"x-student-key": key} if key.startswith("st_") else {"Authorization": f"Bearer {key}"}


def link_secret() -> str:
    """$STUDENTIDE_ROLLCALL_LINK_SECRET, the same as Roll Call's LINK_SECRET: lets both
    apps keep one register per teacher (Roll Call's Google sign-in opens it too)."""
    s = (os.environ.get("STUDENTIDE_ROLLCALL_LINK_SECRET") or "").strip()
    return s if len(s) >= 16 else ""


def urllib_transport(method: str, url: str, key: str, body: dict | None) -> tuple[int, object]:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={**key_header(key), "Content-Type": "application/json",
                                          "User-Agent": "studentide-attendance"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except ValueError:
            return e.code, None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RollCallError(f"Roll Call is not reachable ({getattr(e, 'reason', e)})", 502) from e


@dataclass
class RollCall:
    key: str
    base: str
    transport: Transport

    def call(self, method: str, path: str, body: dict | None = None):
        status, data = self.transport(method, self.base + path, self.key, body)
        if status == 401:
            raise RollCallError("Roll Call did not accept this sync key", 400)
        if status == 410:
            raise RollCallError("This Roll Call key was replaced in Roll Call. Paste the new key under "
                                "Getting started → I already use Roll Call.", 409)
        if status >= 400:
            msg = data.get("error") if isinstance(data, dict) else None
            raise RollCallError(f"Roll Call said: {msg or f'error {status}'}", 502 if status >= 500 else 400)
        return data


# Participation ---------------------------------------------------------------

class Rule(BaseModel):
    min_active_minutes: int = Field(default=10, ge=0, le=600)
    min_typed_chars: int = Field(default=40, ge=0, le=100_000)
    require_run: bool = False


def describe(rule: dict) -> str:
    parts = [f"at least {rule['min_active_minutes']} active minutes", f"{rule['min_typed_chars']} typed characters"]
    if rule["require_run"]:
        parts.append("one run or Check")
    return "Present = " + ", ".join(parts[:-1]) + " and " + parts[-1] + " in the lab"


def _session_spans(db: Database, lab_id: str) -> list:
    """Each counted session of the lab with the first and last moment of an edit (or, in a
    Sandbox Lab, a terminal command, Run or file change), in server seconds, from the events
    index alone: no event bodies are read."""
    with db.connect() as conn:
        return conn.execute("""SELECT s.id, s.student_id, s.started_at,
                                      s.started_at + MIN(e.t) / 1000.0 AS first, s.started_at + MAX(e.t) / 1000.0 AS last
                               FROM sessions s JOIN events e ON e.session_id = s.id AND e.type IN ('edit', 'term_cmd', 'run', 'fs_change')
                               WHERE s.lab_id = ? AND s.context IS NULL GROUP BY s.id""", (lab_id,)).fetchall()


def _days_between(first: float, last: float, tz) -> set[str]:
    a, b = datetime.fromtimestamp(first, tz).date(), datetime.fromtimestamp(last, tz).date()
    return {(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)}


def lab_days(db: Database, lab_id: str) -> list[str]:
    """The days with activity in the lab, newest first, cheaply: from edit times
    and runs/Checks, without reading each edit (a busy lab has 100k+ of them)."""
    tz = timezone()
    days: set[str] = set()
    for s in _session_spans(db, lab_id):
        days |= _days_between(s["first"], s["last"], tz)
    with db.connect() as conn:
        for r in conn.execute("""SELECT r.created_at FROM runs r JOIN sessions s ON s.id = r.session_id
                                 WHERE s.lab_id = ? AND s.context IS NULL
                                 UNION ALL
                                 SELECT c.created_at FROM checks c JOIN sessions s ON s.id = c.session_id
                                 WHERE s.lab_id = ? AND s.context IS NULL""", (lab_id, lab_id)):
            days.add(datetime.fromtimestamp(r["created_at"], tz).date().isoformat())
    return sorted(days, reverse=True)


def lab_activity(db: Database, lab_id: str, day: str | None = None) -> dict[str, dict[str, dict]]:
    """day -> student -> evidence, from the lab's counted sessions. With `day`,
    only sessions that had edits that day are read (and only that day is kept)."""
    tz = timezone()
    out: dict[str, dict[str, dict]] = {}

    def ev(day: str, student: str) -> dict:
        return out.setdefault(day, {}).setdefault(student, {
            "minutes": set(), "typed": 0, "pasted": 0, "runs": 0, "checks": 0, "sessions": set(), "first": None, "last": None})

    def touch(e: dict, ts: float) -> None:
        e["minutes"].add(int(ts // 60))
        e["first"] = ts if e["first"] is None else min(e["first"], ts)
        e["last"] = ts if e["last"] is None else max(e["last"], ts)

    day_of = lambda ts: datetime.fromtimestamp(ts, tz).date().isoformat()
    with db.connect() as conn:
        sessions = conn.execute("SELECT id, student_id, started_at FROM sessions WHERE lab_id = ? AND context IS NULL",
                                (lab_id,)).fetchall()
    if day is not None:
        spans = {x["id"]: x for x in _session_spans(db, lab_id)}
        reading = [s for s in sessions if s["id"] in spans and day in _days_between(spans[s["id"]]["first"], spans[s["id"]]["last"], tz)]
    else:
        reading = sessions
    with db.connect() as conn:
        # runs and Checks as the server recorded them (the client's "run" events are left out: same presses)
        runs = conn.execute("""SELECT r.session_id, r.created_at, 'runs' AS kind FROM runs r JOIN sessions s ON s.id = r.session_id
                               WHERE s.lab_id = ? AND s.context IS NULL
                               UNION ALL
                               SELECT c.session_id, c.created_at, 'checks' FROM checks c JOIN sessions s ON s.id = c.session_id
                               WHERE s.lab_id = ? AND s.context IS NULL""", (lab_id, lab_id)).fetchall()
    by_id = {s["id"]: s for s in sessions}
    for s in reading:
        for e in db.iter_events(s["id"], types=("edit", "key", "term_cmd", "run", "fs_change")):
            ts = s["started_at"] + e["t"] / 1000.0
            d = e["data"]
            if e["type"] == "key":
                # Sandbox Labs: terminal typing (prompt, vim, nano) counts; editor keys are already counted as edits
                if d.get("surface", "editor") == "editor" or d.get("action") != "down" or d.get("repeat") \
                        or d.get("cls") not in TYPED_KEY or d.get("ctrl") or d.get("meta"):
                    continue
                x = ev(day_of(ts), s["student_id"])
                x["sessions"].add(s["id"])
                touch(x, ts)
                x["typed"] += 1
                continue
            if e["type"] != "edit":
                x = ev(day_of(ts), s["student_id"])
                x["sessions"].add(s["id"])
                touch(x, ts)
                if e["type"] == "run" and d.get("source") in ("button", "terminal"):
                    x["runs"] += 1  # desktop runs are local: no row in the runs table
                elif e["type"] == "run" and d.get("source") == "test":
                    x["checks"] += 1
                continue
            x = ev(day_of(ts), s["student_id"])
            x["sessions"].add(s["id"])
            touch(x, ts)
            origin = d.get("origin", "")
            n = sum(len(c[2]) for c in e["data"].get("changes", []))
            if origin.startswith("input") and origin not in NOT_TYPED:  # "reset"/"reload" are not input: never typed
                x["typed"] += n
            elif origin in NOT_TYPED:
                x["pasted"] += n
    for c in runs:
        s = by_id[c["session_id"]]
        x = ev(day_of(c["created_at"]), s["student_id"])
        x[c["kind"]] += 1
        touch(x, c["created_at"])
    return {day: out[day]} if day is not None and day in out else ({} if day is not None else out)


def judge(e: dict | None, rule: dict) -> dict:
    """Evidence -> {present, reason, ...numbers} for one student and day."""
    if e is None:
        return {"present": False, "reason": "no activity in this lab", "active_minutes": 0, "typed": 0, "pasted": 0,
                "runs": 0, "first": None, "last": None}
    active, runs = len(e["minutes"]), e["runs"] + e["checks"]
    short = []
    if active < rule["min_active_minutes"]:
        short.append(f"{active} of {rule['min_active_minutes']} active minutes")
    if e["typed"] < rule["min_typed_chars"]:
        short.append(f"{e['typed']} of {rule['min_typed_chars']} typed characters")
    if rule["require_run"] and runs < 1:
        short.append("never ran or checked code")
    did = f"{active} active min, {e['typed']} typed chars, {runs} run{'s' if runs != 1 else ''}"
    return {"present": not short, "reason": did if not short else "only " + "; ".join(short),
            "active_minutes": active, "typed": e["typed"], "pasted": e["pasted"], "runs": runs,
            "first": e["first"], "last": e["last"]}


# Router ----------------------------------------------------------------------

class LinkIn(BaseModel):
    sync_key: str = Field(min_length=32, max_length=128, pattern=r"^\s*[A-Za-z0-9_-]+\s*$")


class GroupIn(BaseModel):
    prefix: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9/_-]+$")
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    digits: int = Field(ge=1, le=8)
    exclude: list[int] = Field(default_factory=list, max_length=5000)


class ClassIn(BaseModel):
    branch: str = Field(min_length=1, max_length=80)
    section: str = Field(min_length=1, max_length=16)
    group: str = Field(default="", max_length=16)
    groups: list[GroupIn] = Field(min_length=1, max_length=8)


class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    code: str = Field(default="", max_length=24)


class AttachIn(BaseModel):
    class_ids: list[str] = Field(default_factory=list, max_length=20)
    add_to_roster: bool = True


class RuleIn(Rule):
    auto_send: bool = True


class SendIn(BaseModel):
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    overrides: dict[str, Literal["P", "A"]] = Field(default_factory=dict)


def router(db: Database, require_teacher: Callable, auth, transport: Transport | None = None) -> APIRouter:
    ensure_schema(db)
    send_http = transport or urllib_transport
    r = APIRouter(prefix="/api/teach", dependencies=[Depends(require_teacher)])

    def me(request: Request) -> str:
        return auth.teacher(request).email or ""

    def key_of(email: str) -> str | None:
        with db.connect() as conn:
            row = conn.execute("SELECT sync_key FROM attendance_links WHERE email = ?", (email,)).fetchone()
        return row["sync_key"] if row else None

    def client(email: str) -> RollCall:
        key = key_of(email)
        if key is None:
            raise HTTPException(409, "connect Roll Call first (Teach → Getting started)")
        return RollCall(key, rollcall_url(), send_http)

    def rc(fn):
        try:
            return fn()
        except RollCallError as e:
            raise HTTPException(e.status, str(e)) from e

    def lab_or_404(lab_id: str, request: Request):
        lab = db.get_lab(lab_id)
        if lab is not None:
            auth.check_lab(request, lab_id)
            return lab
        lab = sandbox_lab(db, lab_id)
        if lab is None:
            raise HTTPException(404, "unknown lab")
        auth.check_lab(request, lab_id)  # a Sandbox Lab: its subject's people (Auth.check_lab)
        return lab

    # connection -----------------------------------------------------------

    @r.get("/attendance")
    def connection(request: Request) -> dict:
        with db.connect() as conn:
            row = conn.execute("SELECT connected_at, checked_at, issued FROM attendance_links WHERE email = ?",
                               (me(request),)).fetchone()
        return {"connected": row is not None, "url": rollcall_url(),
                "connected_at": row["connected_at"] if row else None, "issued": bool(row and row["issued"]),
                "rule": DEFAULT_RULE, "timezone": str(timezone())}

    def link(email: str, key: str | None = None) -> str | None:
        """Roll Call's register for this address (made by Google sign-in there, or
        linked from here before); with `key`, records it as theirs when they have
        none. None when linking is off, the address is the dev register, or Roll
        Call is unreachable: Student IDE then works as before, on its own key."""
        secret = link_secret()
        if not secret or not email:
            return None
        try:
            status, data = send_http("POST", rollcall_url() + "/api/link/teacher", LINK + secret,
                                     {"email": email, **({"key": key} if key else {})})
        except RollCallError:
            return None
        return data.get("key") if status == 200 and isinstance(data, dict) else None

    def link_everyone() -> None:
        """Once per start: teachers whose keys were made before linking existed get
        linked, so their first Google sign-in in Roll Call opens the same register."""
        with db.connect() as conn:
            rows = conn.execute("SELECT email, sync_key FROM attendance_links WHERE email <> ''").fetchall()
        for row in rows:
            link(row["email"], row["sync_key"])

    if link_secret() and transport is None:
        threading.Thread(target=link_everyone, daemon=True, name="rollcall-link").start()

    def provision(email: str) -> str:
        """This teacher's key. With none yet: the register they already have in Roll
        Call (they signed in there with Google first), or else a new key, which is a
        new, empty Roll Call workspace."""
        key = key_of(email)
        if key is not None:
            return key
        key = link(email) or new_teacher_key()
        rc(lambda: RollCall(key, rollcall_url(), send_http).call("GET", "/api/v1"))  # checks it / creates the workspace
        key = link(email, key) or key
        now = time.time()
        with db.connect() as conn:
            conn.execute("""INSERT INTO attendance_links(email, sync_key, connected_at, checked_at, issued)
                            VALUES (?,?,?,?,1) ON CONFLICT(email) DO NOTHING""", (email, key, now, now))
        return key_of(email) or key

    @r.post("/attendance/key")
    def make_key(request: Request) -> dict:
        provision(me(request))
        return connection(request)

    @r.get("/attendance/key")
    def show_key(request: Request) -> dict:
        key = key_of(me(request))
        if key is None:
            raise HTTPException(404, "no Roll Call key yet: press Open Roll Call to make one")
        return {"sync_key": key, "login_url": rollcall_url() + "/login"}

    @r.post("/attendance/key/rotate")
    def rotate_key(request: Request) -> dict:
        """A new key for the same register: Roll Call moves every class, session,
        subject and student grant across and refuses the old key from then on.
        The old key is forgotten here."""
        email = me(request)
        old = key_of(email)
        if old is None:
            raise HTTPException(404, "no Roll Call key yet: press Open Roll Call to make one")
        new = new_teacher_key()
        # the new key itself too, so Roll Call's Google sign-in keeps opening this register
        moved = rc(lambda: RollCall(old, rollcall_url(), send_http).call(
            "POST", "/api/v1/rotate", {"new_workspace": hashlib.sha256(new.encode()).hexdigest(), "new_key": new}))
        now = time.time()
        with db.connect() as conn:
            conn.execute("UPDATE attendance_links SET sync_key = ?, issued = 1, checked_at = ? WHERE email = ?",
                         (new, now, email))
        return connection(request) | {"moved": (moved or {}).get("moved")}

    # admins: every register ---------------------------------------------------

    def admin_only(request: Request) -> str:
        t = auth.teacher(request)
        if not t.admin:
            raise HTTPException(403, "only admins open other teachers' registers")
        return t.email or ""

    @r.get("/attendance/registers")
    def registers(request: Request) -> list[dict]:
        admin_only(request)
        with db.connect() as conn:
            rows = conn.execute("""SELECT l.email, l.issued, l.connected_at,
                                          (SELECT COUNT(DISTINCT c.lab_id) FROM lab_classes c WHERE c.attached_by = l.email) AS labs,
                                          (SELECT MAX(at) FROM attendance_admin_opens o WHERE o.teacher = l.email) AS last_opened
                                   FROM attendance_links l ORDER BY l.email""").fetchall()
        return [dict(r) | {"issued": bool(r["issued"])} for r in rows]

    @r.post("/attendance/registers/{email}/open")
    def open_register(email: str, request: Request) -> dict:
        """Full access to a teacher's register for an admin (Rohan, 2026-11-03).
        Roll Call shows whose register it is; every open is logged here."""
        admin = admin_only(request)
        email = "" if email == "-" else email  # "-" = the dev-mode / admin-token register
        key = key_of(email)
        if key is None:
            raise HTTPException(404, "that teacher has not set up Roll Call")
        label = (f"{email}'s register" if email else "the shared register") + \
            (f", opened by admin {admin}" if admin else ", opened with the admin token")
        out = rc(lambda: RollCall(key, rollcall_url(), send_http).call("POST", "/api/v1/login-codes", {"label": label}))
        with db.connect() as conn:
            conn.execute("INSERT INTO attendance_admin_opens(at, admin, teacher) VALUES (?,?,?)", (time.time(), admin, email))
        return {"url": login_link(out)}

    @r.post("/attendance/open")
    def open_rollcall(request: Request) -> dict:
        email = me(request)
        key = provision(email)
        link(email, key)  # e.g. a key replaced before linking was on
        out = rc(lambda: RollCall(key, rollcall_url(), send_http).call("POST", "/api/v1/login-codes"))
        return {"url": login_link(out)}

    @r.put("/attendance")
    def connect(body: LinkIn, request: Request) -> dict:
        key = body.sync_key.strip()
        info = rc(lambda: RollCall(key, rollcall_url(), send_http).call("GET", "/api/v1"))
        now = time.time()
        with db.connect() as conn:
            conn.execute("""INSERT INTO attendance_links(email, sync_key, connected_at, checked_at, issued) VALUES (?,?,?,?,0)
                            ON CONFLICT(email) DO UPDATE SET sync_key = excluded.sync_key, connected_at = excluded.connected_at,
                            checked_at = excluded.checked_at, issued = 0""", (me(request), key, now, now))
        return connection(request) | {"workspace": info}

    @r.delete("/attendance")
    def disconnect(request: Request) -> dict:
        with db.connect() as conn:
            conn.execute("DELETE FROM attendance_links WHERE email = ?", (me(request),))
        return connection(request)

    @r.get("/attendance/labs")
    def per_lab(request: Request) -> dict:
        """lab id -> attached class labels and how many lab days were sent, for the labs this teacher sees."""
        ids = auth.lab_ids(request)
        out: dict[str, dict] = {}
        with db.connect() as conn:
            for row in conn.execute("SELECT lab_id, label FROM lab_classes ORDER BY label"):
                out.setdefault(row["lab_id"], {"classes": [], "days_sent": 0, "last_sent": None, "errors": 0})["classes"].append(row["label"])
            for row in conn.execute("""SELECT lab_id, COUNT(DISTINCT day) AS days, MAX(sent_at) AS last,
                                              SUM(error IS NOT NULL) AS errors FROM attendance_sent GROUP BY lab_id"""):
                d = out.setdefault(row["lab_id"], {"classes": [], "days_sent": 0, "last_sent": None, "errors": 0})
                d.update(days_sent=row["days"], last_sent=row["last"], errors=row["errors"])
        return {k: v for k, v in out.items() if ids is None or k in ids}

    def everyones_classes(request: Request) -> dict[str, dict]:
        """Admins: every connected teacher's Roll Call class groups, by id, each with
        its `owner` (whose register it is and whose key sends its attendance).
        A teacher whose Roll Call can't be reached is left out, not an error."""
        out: dict[str, dict] = {}
        with db.connect() as conn:
            rows = conn.execute("SELECT email, sync_key FROM attendance_links ORDER BY email").fetchall()
        for row in rows:
            try:
                got = RollCall(row["sync_key"], rollcall_url(), send_http).call("GET", "/api/v1/classes")
            except RollCallError:
                continue
            for c in got or []:
                out.setdefault(c["id"], c | {"owner": row["email"]})
        return out

    @r.get("/attendance/classes")
    def classes(request: Request, every: bool = False) -> list:
        """The teacher's Roll Call class groups; `?every=1` for an admin: every
        teacher's, each with `owner` (the admin's own first)."""
        if every and auth.teacher(request).admin:
            email = me(request)
            groups = list(everyones_classes(request).values())
            return sorted(groups, key=lambda c: (c["owner"] != email, c["owner"], c["label"]))
        return rc(lambda: client(me(request)).call("GET", "/api/v1/classes"))

    @r.post("/attendance/classes")
    def create_class(body: ClassIn, request: Request) -> dict:
        roster = {"groups": [g.model_dump() | {"prefix": g.prefix.upper()} for g in body.groups]}
        if any(g["end"] < g["start"] or g["end"] - g["start"] > 3000 for g in roster["groups"]):
            raise HTTPException(400, "each roll range needs From ≤ To, at most 3000 students")
        return rc(lambda: client(me(request)).call("POST", "/api/v1/classes", {
            "branch": body.branch.strip(), "section": body.section.strip().upper(), "group": body.group.strip().upper(),
            "roster": roster}))

    @r.get("/attendance/subjects")
    def subjects(request: Request) -> list:
        return rc(lambda: client(me(request)).call("GET", "/api/v1/subjects"))

    @r.post("/attendance/subjects")
    def create_subject(body: SubjectIn, request: Request) -> dict:
        return rc(lambda: client(me(request)).call("POST", "/api/v1/subjects", body.model_dump()))

    # a lab's class groups -------------------------------------------------

    def attached(lab_id: str) -> list[dict]:
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM lab_classes WHERE lab_id = ? ORDER BY label", (lab_id,)).fetchall()
        return [dict(r) | {"students": json.loads(r["students_json"])} for r in rows]

    def settings(lab_id: str) -> dict:
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM lab_attendance WHERE lab_id = ?", (lab_id,)).fetchone()
        rule = DEFAULT_RULE | (json.loads(row["rule_json"]) if row else {})
        return {"rule": rule, "auto_send": bool(row["auto_send"]) if row else True, "describe": describe(rule)}

    def sent(lab_id: str) -> list[dict]:
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM attendance_sent WHERE lab_id = ? ORDER BY day DESC", (lab_id,)).fetchall()
        return [{k: r[k] for k in ("day", "class_id", "rollcall_id", "sent_at", "sent_by", "how", "present", "total", "error")}
                for r in rows]

    def overview(lab_id: str) -> dict:
        days = lab_days(db, lab_id)
        return {"classes": [{k: c[k] for k in ("class_id", "label", "attached_by", "attached_at")} | {"n_students": len(c["students"])}
                            for c in attached(lab_id)],
                "days": days, "sent": sent(lab_id), "rollcall_url": rollcall_url(), **settings(lab_id),
                "sittings": runs(lab_id), "current": current_run(lab_id)}

    @r.get("/labs/{lab_id}/classes")
    def lab_classes(lab_id: str, request: Request) -> dict:
        lab_or_404(lab_id, request)
        return overview(lab_id)

    @r.put("/labs/{lab_id}/classes")
    def attach(lab_id: str, body: AttachIn, request: Request) -> dict:
        lab = lab_or_404(lab_id, request)
        email = me(request)
        want = list(dict.fromkeys(body.class_ids))
        have = {c["class_id"]: c for c in attached(lab_id)}
        mine = {c["id"]: c for c in rc(lambda: client(email).call("GET", "/api/v1/classes"))} if key_of(email) else {}
        # an admin may attach any teacher's group: it stays in that teacher's register
        others = everyones_classes(request) if auth.teacher(request).admin and set(want) - set(mine) - set(have) else {}
        rows = []
        for cid in want:
            c = mine.get(cid)
            o = others.get(cid)
            if c is not None:  # refresh from Roll Call: the roster may have changed
                rows.append((lab_id, cid, c["label"], json.dumps(sorted(s.upper() for s in c["students"])), email, time.time()))
            elif o is not None:
                rows.append((lab_id, cid, o["label"], json.dumps(sorted(s.upper() for s in o["students"])), o["owner"], time.time()))
            elif cid in have:  # a co-teacher's class: keep their copy
                h = have[cid]
                rows.append((lab_id, cid, h["label"], h["students_json"], h["attached_by"], h["attached_at"]))
            else:
                raise HTTPException(404, f"no class {cid} in your Roll Call")
        with db.connect() as conn:
            conn.execute("DELETE FROM lab_classes WHERE lab_id = ?", (lab_id,))
            conn.executemany("INSERT INTO lab_classes VALUES (?,?,?,?,?,?)", rows)
        # a Sandbox Lab's students come from its subject's sections (sandbox.py), not a lab roster
        if body.add_to_roster and rows and not isinstance(lab, dict):
            students = {s for row in rows for s in json.loads(row[3])}
            db.set_roster(lab_id, sorted(set(db.lab_roster(lab_id)) | students))
        return overview(lab_id)

    @r.put("/labs/{lab_id}/attendance/rule")
    def set_rule(lab_id: str, body: RuleIn, request: Request) -> dict:
        lab_or_404(lab_id, request)
        rule = Rule.model_validate(body.model_dump()).model_dump()
        with db.connect() as conn:
            conn.execute("""INSERT INTO lab_attendance(lab_id, rule_json, auto_send) VALUES (?,?,?)
                            ON CONFLICT(lab_id) DO UPDATE SET rule_json = excluded.rule_json, auto_send = excluded.auto_send""",
                         (lab_id, json.dumps(rule), int(body.auto_send)))
        return overview(lab_id)

    # preview and send -----------------------------------------------------

    # sittings: which groups perform in each opening of the lab ------------------

    def local_day(ts: float) -> str:
        return datetime.fromtimestamp(ts, timezone()).date().isoformat()

    def runs(lab_id: str) -> list[dict]:
        labels = {c["class_id"]: c["label"] for c in attached(lab_id)}
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM lab_runs WHERE lab_id = ? ORDER BY opened_at", (lab_id,)).fetchall()
        out = []
        for r in rows:
            ids = json.loads(r["class_ids"])
            out.append(dict(r) | {"class_ids": ids, "labels": [labels.get(i, "removed group") for i in ids]})
        return out

    def groups_on(lab_id: str, day: str) -> set[str] | None:
        """The groups that sat the lab on `day`; None = all attached (no sitting chose groups)."""
        that_day = [r for r in runs(lab_id) if local_day(r["opened_at"]) == day]
        if not that_day or any(not r["class_ids"] for r in that_day):
            return None
        return {i for r in that_day for i in r["class_ids"]}

    def current_run(lab_id: str) -> dict | None:
        return next((r for r in reversed(runs(lab_id)) if r["closed_at"] is None), None)

    class Sittings:
        """Called by teach.py's PATCH /labs/{id}: opening starts a sitting for the
        performing groups, switching groups or closing ends it and sends its
        attendance (if auto-send is on), for its groups only."""

        def check(self, lab_id: str, performing: list[str]) -> None:
            ids = {c["class_id"] for c in attached(lab_id)}
            unknown = [i for i in performing if i not in ids]
            if unknown:
                raise HTTPException(400, "performing groups must be attached to the lab first")

        def changed(self, lab_id: str, was: str, now: str, performing: list[str] | None, request: Request):
            cur = current_run(lab_id)
            sent = None
            if was == "open" and (now != "open" or performing is not None):
                if cur is not None:
                    sent = end_run(cur, request, send_it=now != "draft")
                elif now == "closed":
                    sent = on_closed(lab_id, request)
            elif now == "closed" and was != "closed":
                sent = on_closed(lab_id, request)
            if now == "open" and (was != "open" or performing is not None):
                with db.connect() as conn:
                    conn.execute("INSERT INTO lab_runs(id, lab_id, class_ids, opened_at, opened_by) VALUES (?,?,?,?,?)",
                                 ("run_" + uuid.uuid4().hex[:10], lab_id, json.dumps(sorted(set(performing or []))),
                                  time.time(), me(request)))
            return sent

    def end_run(run: dict, request: Request, send_it: bool = True) -> list[dict]:
        with db.connect() as conn:
            conn.execute("UPDATE lab_runs SET closed_at = ? WHERE id = ?", (time.time(), run["id"]))
        lab = any_lab(db, run["lab_id"])
        if not send_it or not settings(lab["id"])["auto_send"] or not attached(lab["id"]):
            return []
        day = local_day(run["opened_at"])
        if day not in lab_days(db, lab["id"]):
            return []
        groups = set(run["class_ids"]) or {c["class_id"] for c in attached(lab["id"])}
        groups -= {x["class_id"] for x in sent(lab["id"]) if x["day"] == day and not x["error"]}  # the teacher sent it already
        if not groups:
            return []
        try:
            return [send(lab, day, None, me(request), "lab closed", base(request), only=groups)]
        except HTTPException as e:  # e.g. nobody from the group worked in it
            return [{"day": day, "results": [], "error": e.detail}]

    def preview(lab_id: str, day: str | None, overrides: dict[str, str] | None = None) -> dict:
        days = lab_days(db, lab_id)
        day = day or (days[0] if days else datetime.now(timezone()).date().isoformat())
        today = lab_activity(db, lab_id, day).get(day, {})
        st = settings(lab_id)
        with db.connect() as conn:
            prev = {r["class_id"]: json.loads(r["overrides_json"]) for r in conn.execute(
                "SELECT class_id, overrides_json FROM attendance_sent WHERE lab_id = ? AND day = ?", (lab_id, day))}
        sent_rows = {s["class_id"]: s for s in sent(lab_id) if s["day"] == day}
        classes, in_a_class = [], set()
        performing = groups_on(lab_id, day)
        for c in attached(lab_id):
            if performing is not None and c["class_id"] not in performing:
                in_a_class.update(c["students"])  # another day's group: neither listed nor "in no class group"
                continue
            ov = (overrides if overrides is not None else prev.get(c["class_id"], {}))
            students = []
            for sid in c["students"]:
                j = judge(today.get(sid), st["rule"])
                o = ov.get(sid)
                students.append({"student_id": sid, **j, "auto": j["present"],
                                 "present": (o == "P") if o in ("P", "A") else j["present"], "override": o})
                in_a_class.add(sid)
            # nobody from this group worked in the lab that day (another group's sitting): not sent,
            # unless the teacher overrides a mark in it on purpose
            idle = not any(sid in today for sid in c["students"]) and not any(s["override"] for s in students)
            classes.append({"class_id": c["class_id"], "label": c["label"], "students": students,
                            "present": sum(s["present"] for s in students), "total": len(students),
                            "sent": sent_rows.get(c["class_id"]), "idle": idle})
        # active in the lab but on no attached roster: usually a prefix that doesn't match the college address
        outside = sorted(({"student_id": sid, **judge(e, st["rule"])} for sid, e in today.items() if sid not in in_a_class),
                         key=lambda x: x["student_id"])
        return {"day": day, "days": days, **st, "classes": classes, "not_in_any_class": outside,
                "sittings": [r for r in runs(lab_id) if local_day(r["opened_at"]) == day]}

    @r.get("/labs/{lab_id}/attendance")
    def get_preview(lab_id: str, request: Request, day: str | None = None) -> dict:
        lab_or_404(lab_id, request)
        return preview(lab_id, day)

    def send(lab, day: str, overrides: dict[str, str] | None, by: str, how: str, base_url: str,
             only: set[str] | None = None) -> dict:
        p = preview(lab["id"], day, overrides)
        if only is not None:
            p["classes"] = [c for c in p["classes"] if c["class_id"] in only]
        if not p["classes"]:
            raise HTTPException(409, "attach a class group first")
        if all(c["idle"] for c in p["classes"]):
            raise HTTPException(409, f"nobody from the attached class groups worked in this lab on {day}")
        firsts = [s["first"] for c in p["classes"] for s in c["students"] if s["present"] and s["first"]]
        lasts = [s["last"] for c in p["classes"] for s in c["students"] if s["present"] and s["last"]]
        hhmm = lambda ts: datetime.fromtimestamp(ts, timezone()).strftime("%H:%M")
        faculty = ((auth.get_user(by) or {}).get("name") or "") if by else ""
        results = []
        for c in p["classes"]:
            if c["idle"]:
                results.append({"class_id": c["class_id"], "label": c["label"], "skipped": True, "error": None,
                                "reason": "nobody from this group worked in the lab that day"})
                continue
            row = next(x for x in attached(lab["id"]) if x["class_id"] == c["class_id"])
            marks = {s["student_id"]: "P" if s["present"] else "A" for s in c["students"]}
            ov = {s["student_id"]: s["override"] for s in c["students"] if s["override"]}
            rid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"studentide:{lab['id']}:{c['class_id']}:{day}"))
            body = {"classId": c["class_id"], "subject": lab["subject"], "date": day,
                    "faculty": faculty,
                    "startTime": hhmm(min(firsts)) if firsts else "", "endTime": hhmm(max(lasts)) if lasts else "",
                    "marks": marks,
                    "source": {"app": "student-ide", "title": lab["title"], "url": f"{base_url}#/{'sandbox' if isinstance(lab, dict) and lab.get('kind') == 'sandbox' else 'teach'}/labs/{lab['id']}",
                               "rule": p["describe"]}}
            error = None
            try:
                key = key_of(row["attached_by"])
                if key is None:
                    raise RollCallError(f"{row['attached_by'] or 'the teacher who attached it'} is no longer connected to Roll Call", 409)
                RollCall(key, rollcall_url(), send_http).call("PUT", f"/api/v1/sessions/{rid}", body)
            except RollCallError as e:
                error = str(e)
            present = sum(m == "P" for m in marks.values())
            with db.connect() as conn:
                conn.execute("""INSERT OR REPLACE INTO attendance_sent
                                (lab_id, day, class_id, rollcall_id, sent_at, sent_by, how, present, total, marks_json, overrides_json, error)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                             (lab["id"], day, c["class_id"], rid, time.time(), by, how, present, len(marks),
                              json.dumps(marks), json.dumps(ov), error))
            results.append({"class_id": c["class_id"], "label": c["label"], "present": present, "total": len(marks),
                            "rollcall_id": rid, "error": error})
        return {"day": day, "results": results}

    def base(request: Request) -> str:
        return (os.environ.get("STUDENTIDE_PUBLIC_URL") or str(request.base_url)).rstrip("/") + "/"

    @r.post("/labs/{lab_id}/attendance")
    def post_send(lab_id: str, body: SendIn, request: Request) -> dict:
        lab = lab_or_404(lab_id, request)
        out = send(lab, body.day, body.overrides, me(request), "teacher", base(request))
        return out | {"preview": preview(lab_id, body.day)}

    def on_closed(lab_id: str, request: Request) -> list[dict]:
        """Called by teach.py when a lab is closed: send each lab day not sent yet."""
        st = settings(lab_id)
        if not st["auto_send"] or not attached(lab_id):
            return []
        done = {s["day"] for s in sent(lab_id) if not s["error"]}
        lab = any_lab(db, lab_id)
        return [send(lab, d, None, me(request), "lab closed", base(request))
                for d in sorted(lab_days(db, lab_id)) if d not in done]

    r.on_lab_closed = on_closed  # type: ignore[attr-defined]
    r.sittings = Sittings()  # type: ignore[attr-defined]
    r.student_router = student_router(db, auth, send_http)  # type: ignore[attr-defined]
    return r


def student_router(db: Database, auth, send_http: Transport) -> APIRouter:
    """My attendance for students: their own marks on Roll Call, read-only."""
    s = APIRouter(prefix="/api/attendance")

    def teachers_of(student: str) -> list[tuple[str, str]]:
        """(email, sync key) of every teacher whose attached class groups list this student."""
        like = f'%"{student}"%'
        with db.connect() as conn:
            rows = conn.execute("""SELECT DISTINCT l.email, l.sync_key FROM lab_classes c
                                   JOIN attendance_links l ON l.email = c.attached_by
                                   WHERE c.students_json LIKE ?""", (like,)).fetchall()
        return [(r["email"], r["sync_key"]) for r in rows]

    def key_for(student: str) -> str:
        with db.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO student_keys(student_id, key, created_at) VALUES (?,?,?)",
                         (student, new_student_key(), time.time()))
            return conn.execute("SELECT key FROM student_keys WHERE student_id = ?", (student,)).fetchone()["key"]

    def who(student_id: str, request: Request) -> str:
        auth.own_student(request, student_id)
        return student_id.strip().upper()

    @s.get("/{student_id}")
    def status(student_id: str, request: Request) -> dict:
        return {"enabled": bool(teachers_of(who(student_id, request))), "url": rollcall_url()}

    @s.post("/{student_id}/open")
    def open_mine(student_id: str, request: Request) -> dict:
        student = who(student_id, request)
        teachers = teachers_of(student)
        if not teachers:
            raise HTTPException(404, "none of your labs records attendance in Roll Call yet")
        key = key_for(student)
        viewer = hashlib.sha256(key.encode()).hexdigest()
        granted = 0
        for _, tkey in teachers:  # one teacher's Roll Call being down shouldn't hide the others
            try:
                RollCall(tkey, rollcall_url(), send_http).call("PUT", "/api/v1/viewers",
                                                                 {"student_id": student, "viewer_hash": viewer})
                granted += 1
            except RollCallError:
                pass
        if not granted:
            raise HTTPException(502, "Roll Call is not reachable right now")
        try:
            out = RollCall(key, rollcall_url(), send_http).call("POST", "/api/v1/login-codes")
        except RollCallError as e:
            raise HTTPException(e.status, str(e)) from e
        return {"url": login_link(out), "key": key, "teachers": granted}

    return s

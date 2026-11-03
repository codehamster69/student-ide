"""Attendance from labs, through Roll Call (the attendance site, codehamsters/attendance).

A teacher connects once by pasting their Roll Call sync key. A lab can then
attach one or more Roll Call class groups (pick existing ones or create one
here). When the lab ends, every student who *effectively participated* is
marked present in their own class group's register, one Roll Call session per
class group and lab day; everyone else on that class's roster is absent.

Effective participation (per student, per lab day; thresholds per lab):

    active minutes  >= min_active_minutes (default 10)
                       distinct wall-clock minutes with an edit, a Run or a Check
    typed chars     >= min_typed_chars (default 40)
                       characters typed into the editor; pastes, drops and Reset don't count
    runs + checks   >= 1, only when require_run is set (default off)

Only the lab's own sessions count: learning-lab practice (context 'learn') and
staff "View as student" previews (context 'preview') never do. Only edit, run
and check records are used, never key timings, so this works after retention.py
has purged raw keys and is unrelated to the detector: a flag never changes
attendance.

    GET    /api/teach/attendance                    this teacher's Roll Call connection
    PUT    /api/teach/attendance                    {sync_key}  connect (checked against Roll Call first)
    DELETE /api/teach/attendance                    disconnect
    GET    /api/teach/attendance/labs               per lab: attached class groups and lab days sent
    GET    /api/teach/attendance/classes            the teacher's Roll Call class groups
    POST   /api/teach/attendance/classes            {branch, section, group, groups: [{prefix, start, end, digits, exclude}]}
    GET    /api/teach/attendance/subjects           Roll Call subjects (for the lab's subject picker)
    POST   /api/teach/attendance/subjects           {name, code}
    GET    /api/teach/labs/{id}/classes             attached class groups, rule, lab days and what was sent
    PUT    /api/teach/labs/{id}/classes             {class_ids, add_to_roster}  attach / detach
    PUT    /api/teach/labs/{id}/attendance/rule     {min_active_minutes, min_typed_chars, require_run, auto_send}
    GET    /api/teach/labs/{id}/attendance?day=     preview: who would be marked present, and why
    POST   /api/teach/labs/{id}/attendance          {day, overrides: {student: "P"|"A"}}  send to Roll Call

Closing a lab (PATCH status=closed) sends every lab day not sent yet, if the
lab has class groups and auto_send is on. Sending again replaces the same Roll
Call sessions (their ids are derived from lab + class + day), never duplicates.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime
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
    checked_at    REAL
);

-- Roll Call class groups attached to a lab, with a copy of their student ids.
CREATE TABLE IF NOT EXISTS lab_classes (
    lab_id        TEXT NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    class_id      TEXT NOT NULL,             -- Roll Call class uuid
    label         TEXT NOT NULL,             -- "CSE · A · G1"
    students_json TEXT NOT NULL,             -- registration numbers on its roster, upper-case
    attached_by   TEXT NOT NULL,             -- whose Roll Call holds the class (sends go through their key)
    attached_at   REAL NOT NULL,
    PRIMARY KEY (lab_id, class_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS lab_attendance (
    lab_id        TEXT PRIMARY KEY REFERENCES labs(id) ON DELETE CASCADE,
    rule_json     TEXT NOT NULL,
    auto_send     INTEGER NOT NULL DEFAULT 1  -- send on closing the lab
);

-- One row per lab day and class group sent to Roll Call (the latest send).
CREATE TABLE IF NOT EXISTS attendance_sent (
    lab_id        TEXT NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
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


def ensure_schema(db: Database) -> None:
    with db.connect() as conn:
        conn.executescript(SCHEMA)


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


def urllib_transport(method: str, url: str, key: str, body: dict | None) -> tuple[int, object]:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
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


def lab_activity(db: Database, lab_id: str) -> dict[str, dict[str, dict]]:
    """day -> student -> evidence, from the lab's counted sessions."""
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
        # runs and Checks as the server recorded them (the client's "run" events are left out: same presses)
        runs = conn.execute("""SELECT r.session_id, r.created_at, 'runs' AS kind FROM runs r JOIN sessions s ON s.id = r.session_id
                               WHERE s.lab_id = ? AND s.context IS NULL
                               UNION ALL
                               SELECT c.session_id, c.created_at, 'checks' FROM checks c JOIN sessions s ON s.id = c.session_id
                               WHERE s.lab_id = ? AND s.context IS NULL""", (lab_id, lab_id)).fetchall()
    by_id = {s["id"]: s for s in sessions}
    for s in sessions:
        for e in db.iter_events(s["id"], types=("edit",)):
            ts = s["started_at"] + e["t"] / 1000.0
            x = ev(day_of(ts), s["student_id"])
            x["sessions"].add(s["id"])
            touch(x, ts)
            origin = e["data"].get("origin", "")
            n = sum(len(c[2]) for c in e["data"].get("changes", []))
            if origin.startswith("input") and origin not in NOT_TYPED:
                x["typed"] += n
            elif origin in NOT_TYPED:
                x["pasted"] += n
    for c in runs:
        s = by_id[c["session_id"]]
        x = ev(day_of(c["created_at"]), s["student_id"])
        x[c["kind"]] += 1
        touch(x, c["created_at"])
    return out


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
        if lab is None:
            raise HTTPException(404, "unknown lab")
        auth.check_lab(request, lab_id)
        return lab

    # connection -----------------------------------------------------------

    @r.get("/attendance")
    def connection(request: Request) -> dict:
        with db.connect() as conn:
            row = conn.execute("SELECT connected_at, checked_at FROM attendance_links WHERE email = ?",
                               (me(request),)).fetchone()
        return {"connected": row is not None, "url": rollcall_url(),
                "connected_at": row["connected_at"] if row else None, "rule": DEFAULT_RULE,
                "timezone": str(timezone())}

    @r.put("/attendance")
    def connect(body: LinkIn, request: Request) -> dict:
        key = body.sync_key.strip()
        info = rc(lambda: RollCall(key, rollcall_url(), send_http).call("GET", "/api/v1"))
        now = time.time()
        with db.connect() as conn:
            conn.execute("""INSERT INTO attendance_links(email, sync_key, connected_at, checked_at) VALUES (?,?,?,?)
                            ON CONFLICT(email) DO UPDATE SET sync_key = excluded.sync_key, connected_at = excluded.connected_at,
                            checked_at = excluded.checked_at""", (me(request), key, now, now))
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

    @r.get("/attendance/classes")
    def classes(request: Request) -> list:
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
        days = sorted(lab_activity(db, lab_id), reverse=True)
        return {"classes": [{k: c[k] for k in ("class_id", "label", "attached_by", "attached_at")} | {"n_students": len(c["students"])}
                            for c in attached(lab_id)],
                "days": days, "sent": sent(lab_id), "rollcall_url": rollcall_url(), **settings(lab_id)}

    @r.get("/labs/{lab_id}/classes")
    def lab_classes(lab_id: str, request: Request) -> dict:
        lab_or_404(lab_id, request)
        return overview(lab_id)

    @r.put("/labs/{lab_id}/classes")
    def attach(lab_id: str, body: AttachIn, request: Request) -> dict:
        lab_or_404(lab_id, request)
        email = me(request)
        want = list(dict.fromkeys(body.class_ids))
        have = {c["class_id"]: c for c in attached(lab_id)}
        mine = {c["id"]: c for c in rc(lambda: client(email).call("GET", "/api/v1/classes"))} if set(want) - set(have) or key_of(email) else {}
        rows = []
        for cid in want:
            c = mine.get(cid)
            if c is not None:  # refresh from Roll Call: the roster may have changed
                rows.append((lab_id, cid, c["label"], json.dumps(sorted(s.upper() for s in c["students"])), email, time.time()))
            elif cid in have:  # a co-teacher's class: keep their copy
                h = have[cid]
                rows.append((lab_id, cid, h["label"], h["students_json"], h["attached_by"], h["attached_at"]))
            else:
                raise HTTPException(404, f"no class {cid} in your Roll Call")
        with db.connect() as conn:
            conn.execute("DELETE FROM lab_classes WHERE lab_id = ?", (lab_id,))
            conn.executemany("INSERT INTO lab_classes VALUES (?,?,?,?,?,?)", rows)
        if body.add_to_roster and rows:
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

    def preview(lab_id: str, day: str | None, overrides: dict[str, str] | None = None) -> dict:
        activity = lab_activity(db, lab_id)
        days = sorted(activity, reverse=True)
        day = day or (days[0] if days else datetime.now(timezone()).date().isoformat())
        today = activity.get(day, {})
        st = settings(lab_id)
        with db.connect() as conn:
            prev = {r["class_id"]: json.loads(r["overrides_json"]) for r in conn.execute(
                "SELECT class_id, overrides_json FROM attendance_sent WHERE lab_id = ? AND day = ?", (lab_id, day))}
        sent_rows = {s["class_id"]: s for s in sent(lab_id) if s["day"] == day}
        classes, in_a_class = [], set()
        for c in attached(lab_id):
            ov = (overrides if overrides is not None else prev.get(c["class_id"], {}))
            students = []
            for sid in c["students"]:
                j = judge(today.get(sid), st["rule"])
                o = ov.get(sid)
                students.append({"student_id": sid, **j, "auto": j["present"],
                                 "present": (o == "P") if o in ("P", "A") else j["present"], "override": o})
                in_a_class.add(sid)
            classes.append({"class_id": c["class_id"], "label": c["label"], "students": students,
                            "present": sum(s["present"] for s in students), "total": len(students),
                            "sent": sent_rows.get(c["class_id"])})
        # active in the lab but on no attached roster: usually a prefix that doesn't match the college address
        outside = sorted(({"student_id": sid, **judge(e, st["rule"])} for sid, e in today.items() if sid not in in_a_class),
                         key=lambda x: x["student_id"])
        return {"day": day, "days": days, **st, "classes": classes, "not_in_any_class": outside}

    @r.get("/labs/{lab_id}/attendance")
    def get_preview(lab_id: str, request: Request, day: str | None = None) -> dict:
        lab_or_404(lab_id, request)
        return preview(lab_id, day)

    def send(lab, day: str, overrides: dict[str, str] | None, by: str, how: str, base_url: str) -> dict:
        p = preview(lab["id"], day, overrides)
        if not p["classes"]:
            raise HTTPException(409, "attach a class group first")
        firsts = [s["first"] for c in p["classes"] for s in c["students"] if s["present"] and s["first"]]
        lasts = [s["last"] for c in p["classes"] for s in c["students"] if s["present"] and s["last"]]
        hhmm = lambda ts: datetime.fromtimestamp(ts, timezone()).strftime("%H:%M")
        faculty = ((auth.get_user(by) or {}).get("name") or "") if by else ""
        results = []
        for c in p["classes"]:
            row = next(x for x in attached(lab["id"]) if x["class_id"] == c["class_id"])
            marks = {s["student_id"]: "P" if s["present"] else "A" for s in c["students"]}
            ov = {s["student_id"]: s["override"] for s in c["students"] if s["override"]}
            rid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"studentide:{lab['id']}:{c['class_id']}:{day}"))
            body = {"classId": c["class_id"], "subject": lab["subject"], "date": day,
                    "faculty": faculty,
                    "startTime": hhmm(min(firsts)) if firsts else "", "endTime": hhmm(max(lasts)) if lasts else "",
                    "marks": marks,
                    "source": {"app": "student-ide", "title": lab["title"], "url": f"{base_url}#/teach/labs/{lab['id']}",
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
        lab = db.get_lab(lab_id)
        return [send(lab, d, None, me(request), "lab closed", base(request))
                for d in sorted(lab_activity(db, lab_id)) if d not in done]

    r.on_lab_closed = on_closed  # type: ignore[attr-defined]
    return r

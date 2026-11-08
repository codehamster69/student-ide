"""Running a Sandbox Lab class: the readiness board and the live class grid (plan 5.6, 6.3 steps 5-6).

The desktop app reports its state about once a minute and whenever it runs
the setup check or opens a lab (desktop/sandbox/src/desktop.ts):

    POST /api/sandbox/presence?student_id=   {app_version, platform, engine, setup_ok, problems,
                                               images, lab_id?, instance?}

`problems` are the setup check's own plain-language failures (doctor.ts), so
the board can say *why* a machine is not ready and IT can fix that PC before
the lab. Teachers (the subject's people, as for the rest of the lab) read:

    GET /api/sandbox/labs/{lab_id}/class

one tile per student on the lab's roster: ready / not ready (with the one-line
reason) / app never seen, online now, and once the lab runs, the assignment
they are on, how recently they typed (editor or terminal), the command
running in their terminal and the counts the review lanes care about. Tiles
come sorted by attention: not ready, offline, then everyone else. Clicking a
tile opens the live editor view (live.py), which for Sandbox Labs adds the
read-only terminal mirror and the file being edited; the student is always
told, as with web labs.

This is never study data and never feeds the detector.
"""

from __future__ import annotations

import json
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .db import Database

SCHEMA = """
CREATE TABLE IF NOT EXISTS sbx_presence (
    student_id   TEXT PRIMARY KEY,
    updated_at   REAL NOT NULL,
    app_version  TEXT NOT NULL DEFAULT '',
    platform     TEXT NOT NULL DEFAULT '',
    engine       TEXT NOT NULL DEFAULT '',     -- docker | podman | wsl-podman | lima-podman | '' (none set up)
    setup_ok     INTEGER NOT NULL DEFAULT 0,
    problems_json TEXT NOT NULL DEFAULT '[]',  -- [{id, message, fix}] from the setup check
    images_json  TEXT NOT NULL DEFAULT '[]',   -- image refs present on the machine
    lab_id       TEXT,                         -- the Sandbox Lab open now, if any
    instance     TEXT NOT NULL DEFAULT ''      -- running | stopped | ''
);
"""

ONLINE_S = 150  # the app reports every 60 s; silent this long = offline
TYPING_S = 20


class Problem(BaseModel):
    id: str = Field(max_length=64)
    message: str = Field(max_length=300)
    fix: str | None = Field(default=None, max_length=300)


class PresenceIn(BaseModel):
    app_version: str = Field(default="", max_length=32)
    platform: str = Field(default="", max_length=32)
    engine: str = Field(default="", max_length=32)
    setup_ok: bool = False
    problems: list[Problem] = Field(default_factory=list, max_length=20)
    images: list[str] = Field(default_factory=list, max_length=50)
    lab_id: str | None = Field(default=None, max_length=64)
    instance: str = Field(default="", max_length=16)


def _version(v: str) -> tuple:
    out = []
    for part in (v or "0").split("-")[0].split("."):
        out.append(int(part) if part.isdigit() else 0)
    return tuple(out + [0] * (3 - len(out)))


def readiness(p, lab_image: str | None, min_version: str | None, now: float) -> tuple[str, str]:
    """(status, one-line reason) for one student's machine: ready | not_ready | unknown."""
    if p is None:
        return "unknown", "has not opened the Student IDE app yet"
    if min_version and _version(p["app_version"]) < _version(min_version):
        return "not_ready", f"app {p['app_version'] or 'too old'}: needs {min_version} or newer"
    problems = json.loads(p["problems_json"])
    if not p["engine"]:
        return "not_ready", "the lab engine is not set up (run the installer)"
    if not p["setup_ok"]:
        return "not_ready", problems[0]["message"] if problems else "the setup check failed"
    if lab_image and not any(i.split("@")[0] == lab_image.split("@")[0] or i == lab_image for i in json.loads(p["images_json"])):
        return "ready", "ready; the lab environment downloads when the lab opens"
    return "ready", "ready"


def router(db: Database, require_teacher, auth) -> tuple[APIRouter, APIRouter]:
    with db.connect() as conn:
        conn.executescript(SCHEMA)
    student = APIRouter(prefix="/api/sandbox")
    teacher = APIRouter(prefix="/api/sandbox", dependencies=[Depends(require_teacher)])

    def student_of(request: Request, student_id: str | None) -> str:
        """Google mode: only yourself; dev mode: ?student_id= (like the other student routes)."""
        if auth.cfg.google:
            user = auth.current(request)
            if user is None:
                raise HTTPException(401, "sign in first")
            return user["student_id"]
        if not student_id or not re.match(r"^[A-Za-z0-9_-]{1,32}$", student_id):
            raise HTTPException(400, "student_id is required in dev mode")
        return student_id

    @student.post("/presence")
    def presence(body: PresenceIn, request: Request, student_id: str | None = None) -> dict:
        sid = student_of(request, student_id)
        with db.connect() as conn:
            conn.execute("""INSERT OR REPLACE INTO sbx_presence VALUES (?,?,?,?,?,?,?,?,?,?)""",
                         (sid, time.time(), body.app_version, body.platform, body.engine, int(body.setup_ok),
                          json.dumps([p.model_dump() for p in body.problems]), json.dumps(body.images), body.lab_id, body.instance))
        return {"ok": True}

    @teacher.get("/labs/{lab_id}/class")
    def class_board(lab_id: str, request: Request) -> dict:
        auth.check_lab(request, lab_id)
        now = time.time()
        with db.connect() as conn:
            lab = conn.execute("SELECT * FROM sbx_labs WHERE id = ?", (lab_id,)).fetchone()
            if lab is None:
                raise HTTPException(404, "unknown lab")
            sections = json.loads(lab["sections_json"])
            roster = [r["student_id"] for r in conn.execute(
                "SELECT student_id, section FROM sbx_subject_students WHERE subject_id = ? ORDER BY student_id", (lab["subject_id"],))
                if not sections or r["section"] in sections]
            assignments = {a["id"]: a for a in conn.execute("SELECT id, title, position FROM sbx_assignments WHERE lab_id = ?", (lab_id,))}
            pres = {r["student_id"]: r for r in conn.execute(
                f"SELECT * FROM sbx_presence WHERE student_id IN ({','.join('?' * len(roster))})", roster)} if roster else {}
            sessions = conn.execute("""SELECT id, student_id, question_id, started_at, ended_at FROM sessions
                                       WHERE lab_id = ? AND context IS NULL ORDER BY started_at""", (lab_id,)).fetchall()
            subj = conn.execute("SELECT environment_id FROM sbx_subjects WHERE id = ?", (lab["subject_id"],)).fetchone()
            if lab["env_version"] is not None or not subj or not subj["environment_id"]:
                version = lab["env_version"]
            else:
                version = conn.execute("SELECT MAX(version) FROM sbx_env_versions WHERE environment_id = ?",
                                       (subj["environment_id"],)).fetchone()[0]
        from .sandbox import image_name  # the image students pull for this lab
        image = image_name(subj["environment_id"], version) if subj and subj["environment_id"] and version else None
        latest: dict[str, object] = {}
        for s in sessions:
            latest[s["student_id"]] = s
        stats = _activity(db, [s["id"] for s in latest.values()])
        tiles = []
        for st in sorted(set(roster) | set(latest)):
            p = pres.get(st)
            status, reason = readiness(p, image, lab["min_desktop_version"], now)
            online = bool(p and now - p["updated_at"] < ONLINE_S)
            s = latest.get(st)
            a = stats.get(s["id"], {}) if s else {}
            tile = {"student_id": st, "readiness": status, "reason": reason, "online": online,
                    "app_version": p["app_version"] if p else None, "engine": p["engine"] if p else None,
                    "platform": p["platform"] if p else None, "seen_at": p["updated_at"] if p else None,
                    "in_lab": bool(p and p["lab_id"] == lab_id and online),
                    "session_id": s["id"] if s else None, "assignment": assignments[s["question_id"]]["title"] if s and s["question_id"] in assignments else None,
                    "last_activity_at": a.get("last"), "typing": bool(a.get("last") and now - a["last"] < TYPING_S),
                    "running": a.get("running"), "commands": a.get("commands", 0), "saves": a.get("saves", 0),
                    "outside": a.get("outside", 0)}
            tiles.append(tile)
        order = {"not_ready": 0, "unknown": 1, "ready": 2}
        tiles.sort(key=lambda x: (order[x["readiness"]], not x["online"] and x["readiness"] == "ready", x["student_id"]))
        ready = sum(1 for x in tiles if x["readiness"] == "ready")
        return {"lab": {"id": lab["id"], "title": lab["title"], "status": lab["status"], "due_at": lab["due_at"]},
                "ready": ready, "total": len(tiles), "online": sum(1 for x in tiles if x["online"]),
                "in_lab": sum(1 for x in tiles if x["in_lab"]), "tiles": tiles, "now": now}

    return student, teacher


def _activity(db: Database, ids: list[str]) -> dict[str, dict]:
    """Per session: last activity (server seconds), the command running now, and lane counts."""
    out: dict[str, dict] = {}
    if not ids:
        return out
    with db.connect() as conn:
        starts = {r["id"]: r["started_at"] for r in conn.execute(
            f"SELECT id, started_at FROM sessions WHERE id IN ({','.join('?' * len(ids))})", ids)}
        for sid in ids:
            row = conn.execute("""SELECT MAX(t) FROM events WHERE session_id = ? AND type IN ('edit', 'key', 'term_cmd', 'fs_change')""",
                               (sid,)).fetchone()
            o = {"last": starts[sid] + row[0] / 1000 if row and row[0] is not None else None}
            cmds = conn.execute("""SELECT data FROM events WHERE session_id = ? AND type = 'term_cmd' ORDER BY seq DESC LIMIT 1""",
                                (sid,)).fetchone()
            if cmds:
                d = json.loads(cmds["data"])
                o["running"] = d["command"] if d["phase"] == "start" else None
            o["commands"] = conn.execute("SELECT COUNT(*) FROM events WHERE session_id = ? AND type = 'term_cmd' AND data LIKE '%\"phase\": \"end\"%'",
                                         (sid,)).fetchone()[0]
            for kind, like in (("saves", '%"origin": "terminal-editor"%'), ("outside", '%"origin": "outside"%')):
                o[kind] = conn.execute("SELECT COUNT(*) FROM events WHERE session_id = ? AND type = 'fs_change' AND data LIKE ?",
                                       (sid, like)).fetchone()[0]
            out[sid] = o
    return out

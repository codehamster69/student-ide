"""Live classroom view: what is happening in an open lab right now.

Two teacher views, both read-only:

* **Class view** (one lab): who is in a session, which question they are on,
  how recently they typed, whether the IDE tab is in front, their runs and
  test checks, and how many "moments worth a conversation" the review
  timeline has found so far. No code is shown here.
* **Editor view** (one session): the student's code as it stands now (rebuilt
  from the edit events the recorder already uploads every 2 s), the caret,
  their latest runs and checks.

Live viewing goes beyond after-the-fact review, so it is never silent. Every
teacher request is a heartbeat that is written to `live_views` (who looked at
which lab or session, from when to when), and the student's IDE polls
GET /api/sessions/{id}/viewers to show a banner while their editor or their
lab's class view is open. That poll is also the IDE's presence heartbeat: a
student whose page stopped polling shows as "not connected".

$STUDENTIDE_LIVE picks what is allowed: "editor" (default, both views),
"class" (class view only, no student code) or "off".

Teacher (teacher/admin account, or the admin token in dev mode):
    GET    /api/live/labs                              open labs with how many students are in now
    GET    /api/live/labs/{lab_id}                     one row per student
    GET    /api/live/sessions/{session_id}             the student's editor right now
    DELETE /api/live/views?lab_id=|session_id=         the teacher left the page (ends the banner at once)

Student:
    GET    /api/sessions/{session_id}/viewers          {class_view, editor: [{name}]}
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Request

from .db import Database
from .replay import ReplayError, apply_edit

Mode = Literal["off", "class", "editor"]

VIEW_TTL_S = 12        # a view without a heartbeat for this long has ended
PRESENCE_TTL_S = 20    # the IDE polls every 5 s; silent this long = not connected
TYPING_S = 20          # an edit this recent counts as typing now
IDLE_S = 120           # no edit for this long: idle
ACTIVITY_BINS = 20     # the activity strip: 20 x 30 s = the last 10 minutes
BIN_S = 30
MOMENTS_TTL_S = 30     # the detector works on 30 s windows; no point recomputing faster
OUTPUT_CHARS = 4000

SCHEMA = """
CREATE TABLE IF NOT EXISTS live_views (
    id            INTEGER PRIMARY KEY,
    viewer        TEXT NOT NULL,             -- teacher address, or 'admin-token' in dev mode
    viewer_name   TEXT NOT NULL DEFAULT '',
    lab_id        TEXT,                      -- class view: the lab
    session_id    TEXT,                      -- editor view: the session (NULL for a class view)
    student_id    TEXT,
    started_at    REAL NOT NULL,
    last_seen     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS live_views_by_session ON live_views(session_id, last_seen);
CREATE INDEX IF NOT EXISTS live_views_by_lab ON live_views(lab_id, last_seen);
"""


def ensure_schema(db: Database) -> None:
    with db.connect() as conn:
        conn.executescript(SCHEMA)


def mode_from_env() -> Mode:
    raw = (os.environ.get("STUDENTIDE_LIVE") or "editor").strip().lower()
    if raw not in ("off", "class", "editor"):
        raise ValueError("STUDENTIDE_LIVE must be off, class or editor")
    return raw  # type: ignore[return-value]


class Live:
    """In-memory state for one app process (the deployment runs one worker):
    student presence and the incremental code cache. Viewing itself is logged
    in the database so it outlives a restart."""

    def __init__(self, db: Database, mode: Mode):
        self.db = db
        self.mode = mode
        self._lock = threading.Lock()
        self._presence: dict[str, float] = {}                        # session id -> last IDE poll
        self._code: dict[str, tuple[int, str, int | None]] = {}      # session id -> (seq, text, caret)
        self._moments: dict[str, tuple[float, int, float | None]] = {}  # session id -> (computed at, n, last t)
        self._queue: queue.Queue = queue.Queue()
        self._queued: set[str] = set()
        self._worker: threading.Thread | None = None

    # -- presence

    def seen(self, session_id: str) -> None:
        with self._lock:
            self._presence[session_id] = time.time()

    def online(self, session_id: str, now: float) -> bool:
        with self._lock:
            return now - self._presence.get(session_id, 0) < PRESENCE_TTL_S

    # -- viewing log

    def heartbeat(self, viewer: tuple[str, str], *, lab_id: str | None, session_id: str | None = None,
                  student_id: str | None = None) -> None:
        """Extend this teacher's open view of the lab / session, or start a new one."""
        now = time.time()
        who, name = viewer
        target = "session_id = ?" if session_id else "session_id IS NULL AND lab_id = ?"
        with self.db.connect() as conn:
            row = conn.execute(f"SELECT id FROM live_views WHERE viewer = ? AND {target} AND last_seen > ? "
                               "ORDER BY last_seen DESC LIMIT 1",
                               (who, session_id or lab_id, now - VIEW_TTL_S)).fetchone()
            if row:
                conn.execute("UPDATE live_views SET last_seen = ? WHERE id = ?", (now, row[0]))
            else:
                conn.execute("""INSERT INTO live_views(viewer, viewer_name, lab_id, session_id, student_id, started_at, last_seen)
                                VALUES (?,?,?,?,?,?,?)""", (who, name, lab_id, session_id, student_id, now, now))

    def leave(self, viewer: tuple[str, str], *, lab_id: str | None, session_id: str | None) -> None:
        """Close the teacher's open view now instead of waiting for it to time out."""
        now = time.time()
        target = "session_id = ?" if session_id else "session_id IS NULL AND lab_id = ?"
        with self.db.connect() as conn:
            conn.execute(f"UPDATE live_views SET last_seen = ? WHERE viewer = ? AND {target} AND last_seen > ?",
                         (now - VIEW_TTL_S, viewer[0], session_id or lab_id, now - VIEW_TTL_S))

    def viewers(self, session_row) -> dict:
        """Who is looking at this session right now, for the student's banner."""
        cutoff = time.time() - VIEW_TTL_S
        with self.db.connect() as conn:
            editor = conn.execute("""SELECT viewer, MAX(viewer_name) AS name FROM live_views
                                     WHERE session_id = ? AND last_seen > ? GROUP BY viewer""",
                                  (session_row["id"], cutoff)).fetchall()
            klass = session_row["lab_id"] is not None and conn.execute(
                "SELECT 1 FROM live_views WHERE lab_id = ? AND session_id IS NULL AND last_seen > ? LIMIT 1",
                (session_row["lab_id"], cutoff)).fetchone() is not None
        return {"class_view": klass, "editor": [{"name": r["name"] or "Your teacher"} for r in editor]}

    def watched_sessions(self, lab_id: str) -> set[str]:
        cutoff = time.time() - VIEW_TTL_S
        with self.db.connect() as conn:
            return {r[0] for r in conn.execute(
                "SELECT DISTINCT session_id FROM live_views WHERE lab_id = ? AND session_id IS NOT NULL AND last_seen > ?",
                (lab_id, cutoff))}

    # -- the code as it stands

    def code(self, session_id: str) -> tuple[str, int | None]:
        """Current text and caret, applying only the edits that arrived since the last call."""
        with self._lock:
            seq, text, caret = self._code.get(session_id, (-1, None, None))
        try:
            text, caret, seq = self._advance(session_id, seq, text, caret)
        except ReplayError:  # out-of-order upload: start again from the first snapshot
            text, caret, seq = self._advance(session_id, -1, None, None)
        with self._lock:
            self._code[session_id] = (seq, text or "", caret)
        return text or "", caret

    def _advance(self, session_id: str, seq: int, text: str | None, caret: int | None):
        with self.db.connect() as conn:
            rows = conn.execute("""SELECT seq, type, data FROM events WHERE session_id = ? AND seq > ?
                                   AND type IN ('snapshot', 'edit', 'cursor') ORDER BY seq""", (session_id, seq)).fetchall()
        for r in rows:
            d = json.loads(r["data"])
            if r["type"] == "snapshot":
                text = d["text"]  # a snapshot is the truth at that point, also after a gap
            elif r["type"] == "edit" and text is not None:
                text = apply_edit(text, d)
                caret = _edit_caret(d, caret)
            elif r["type"] == "cursor":
                caret = d["head"]
            seq = r["seq"]
        return text, caret, seq

    # -- moments (the review timeline's episodes), recomputed at most every 30 s

    def moments(self, reviewer, session_id: str, now: float, ended: bool = False) -> tuple[int, float | None]:
        """Never runs the detector inside the teacher's poll: that took seconds
        per session and, with a class of them, froze the whole server. A stale
        or missing count is queued for one background thread and shown on a
        later poll."""
        with self._lock:
            hit = self._moments.get(session_id)
            if hit and (ended or now - hit[0] < MOMENTS_TTL_S):  # an ended session's count never changes
                return hit[1], hit[2]
            if session_id not in self._queued:
                self._queued.add(session_id)
                self._queue.put((reviewer, session_id))
            if self._worker is None:
                self._worker = threading.Thread(target=self._compute_moments, name="live-moments", daemon=True)
                self._worker.start()
        return (hit[1], hit[2]) if hit else (0, None)

    def moments_now(self, reviewer, session_id: str) -> tuple[int, float | None]:
        try:
            eps = reviewer.summary(session_id)["episodes"]
        except Exception:  # a session with too few events to window yet
            eps = []
        out = (len(eps), max((e["first_alarm"] for e in eps), default=None))
        with self._lock:
            self._moments[session_id] = (time.time(), *out)
        return out

    def _compute_moments(self) -> None:
        while True:
            reviewer, session_id = self._queue.get()
            try:
                self.moments_now(reviewer, session_id)
            finally:
                with self._lock:
                    self._queued.discard(session_id)


def _edit_caret(d: dict, caret: int | None) -> int | None:
    """Where the caret ends up after an edit: the end of the last inserted text."""
    ch = d.get("changes") or []
    if not ch:
        return caret
    frm, to, ins = ch[-1]
    shift = sum(len(t.encode("utf-16-le")) // 2 - (b - a) for a, b, t in ch[:-1])
    return frm + shift + len(ins.encode("utf-16-le")) // 2


def router(db: Database, require_teacher: Callable, auth, reviewer, live: Live) -> APIRouter:
    r = APIRouter(prefix="/api/live", dependencies=[Depends(require_teacher)])

    def allowed(what: Mode) -> None:
        order = ("off", "class", "editor")
        if order.index(live.mode) < order.index(what):
            raise HTTPException(403, "the live editor view is turned off on this server" if what == "editor"
                                else "live viewing is turned off on this server")

    def viewer(request: Request) -> tuple[str, str]:
        user = auth.current(request) if auth.cfg.google else None
        if user:
            return user["email"], user["name"] or user["email"].split("@")[0]
        return "admin-token", "Your teacher"

    def lab_or_404(lab_id: str):
        lab = db.get_lab(lab_id)
        if lab is None:
            raise HTTPException(404, "unknown lab")
        return lab

    @r.get("/labs")
    def labs(request: Request) -> list[dict]:
        allowed("class")
        now = time.time()
        out = []
        for lab in db.list_labs(auth.lab_ids(request)):
            if lab["status"] != "open":
                continue
            open_ = [s for s in db.list_sessions(lab_id=lab["id"]) if s["ended_at"] is None]
            out.append({"id": lab["id"], "title": lab["title"], "kind": lab["kind"], "language": lab["language"],
                        "n_questions": lab["n_questions"], "n_roster": lab["n_roster"], "everyone": bool(lab["everyone"]),
                        "n_in_session": len({s["student_id"] for s in open_}),
                        "n_online": len({s["student_id"] for s in open_ if live.online(s["id"], now)})})
        return out

    @r.get("/labs/{lab_id}")
    def lab_view(lab_id: str, request: Request) -> dict:
        allowed("class")
        lab = lab_or_404(lab_id)
        auth.check_lab(request, lab_id)
        live.heartbeat(viewer(request), lab_id=lab_id)
        now = time.time()
        questions = {q["id"]: q for q in db.lab_questions(lab_id)}
        sessions = [s for s in db.list_sessions(lab_id=lab_id)]
        by_student: dict[str, list] = {}
        for s in sessions:
            by_student.setdefault(s["student_id"], []).append(s)
        students = sorted(set(db.lab_roster(lab_id)) | set(by_student))
        ids = [s["id"] for s in sessions]
        stats = _event_stats(db, ids, now)
        runs = _run_stats(db, ids)
        checks = _check_stats(db, ids)
        watched = live.watched_sessions(lab_id)

        rows = []
        for st in students:
            ss = by_student.get(st, [])
            cur = _current(ss, live, now)
            row = {"student_id": st, "state": "not_started", "session_id": None, "question_id": None,
                   "question_title": None, "position": None, "started_at": None, "last_edit_at": None,
                   "activity": [0] * ACTIVITY_BINS, "tab_away": False, "pastes": 0,
                   "runs": 0, "run_errors": 0, "last_run": None, "check": None,
                   "submitted": sorted({s["question_id"] for s in ss if s["end_reason"] == "submit"}),
                   "moments": 0, "last_moment_at": None, "moment_session_id": None, "watched": False}
            if cur is not None:
                es = stats.get(cur["id"], {})
                q = questions.get(cur["question_id"])
                n_moments, last_t, moment_sid = 0, None, None
                if sum(stats.get(s["id"], {}).get("n", 0) for s in ss):
                    for s in sorted(ss, key=lambda s: s["started_at"]):
                        n, t = live.moments(reviewer, s["id"], now, ended=s["ended_at"] is not None)
                        n_moments += n
                        if n:
                            moment_sid, last_t = s["id"], s["started_at"] + t
                row.update({
                    "session_id": cur["id"], "question_id": cur["question_id"],
                    "question_title": q["title"] if q else json.loads(cur["question_json"] or "{}").get("title"),
                    "position": q["position"] if q else None,
                    "started_at": cur["started_at"], "last_edit_at": es.get("last_edit"),
                    "activity": es.get("activity", [0] * ACTIVITY_BINS),
                    "tab_away": es.get("away", False), "pastes": es.get("pastes", 0),
                    "runs": runs.get(cur["id"], {}).get("n", 0), "run_errors": runs.get(cur["id"], {}).get("errors", 0),
                    "last_run": runs.get(cur["id"], {}).get("last"),
                    "check": checks.get(cur["id"]),
                    "moments": n_moments, "last_moment_at": last_t, "moment_session_id": moment_sid, "watched": cur["id"] in watched,
                    "state": _state(cur, es, live.online(cur["id"], now), now),
                })
            rows.append(row)
        return {"lab": {"id": lab["id"], "title": lab["title"], "kind": lab["kind"], "status": lab["status"],
                        "language": lab["language"]},
                "questions": [{"id": q["id"], "title": q["title"], "position": q["position"]} for q in questions.values()],
                "students": rows, "now": now, "editor_view": live.mode == "editor"}

    @r.get("/sessions/{session_id}")
    def editor_view(session_id: str, request: Request) -> dict:
        allowed("editor")
        s = db.get_session(session_id)
        if s is None:
            raise HTTPException(404, "unknown session")
        auth.check_lab(request, s["lab_id"])
        live.heartbeat(viewer(request), lab_id=s["lab_id"], session_id=session_id, student_id=s["student_id"])
        now = time.time()
        text, caret = live.code(session_id)
        es = _event_stats(db, [session_id], now).get(session_id, {})
        q = json.loads(s["question_json"]) if s["question_json"] else {}
        rs = [dict(x) for x in db.list_runs(session_id)][-5:]
        cs = [dict(x) for x in db.list_checks(session_id)]
        lab = db.get_lab(s["lab_id"]) if s["lab_id"] else None
        return {
            "session": {"id": s["id"], "student_id": s["student_id"], "lab_id": s["lab_id"],
                        "lab_title": lab["title"] if lab else None, "question_id": s["question_id"],
                        "question_title": q.get("title") or s["task_id"], "prompt": q.get("prompt", ""),
                        "source": {k: v for k, v in (q.get("source") or {}).items() if k in ("url", "live_prompt")} or None,
                        "language": q.get("language", "python"), "started_at": s["started_at"],
                        "ended_at": s["ended_at"], "end_reason": s["end_reason"]},
            "state": _state(s, es, live.online(session_id, now), now),
            "text": text, "caret": caret, "last_edit_at": es.get("last_edit"), "tab_away": es.get("away", False),
            "activity": es.get("activity", [0] * ACTIVITY_BINS),
            "runs": [{"created_at": x["created_at"], "exit_code": x["exit_code"], "error_type": x["error_type"],
                      "duration_ms": x["duration_ms"], "stdin": x["stdin"][:OUTPUT_CHARS],
                      "stdout": x["stdout"][:OUTPUT_CHARS], "stderr": x["stderr"][:OUTPUT_CHARS]} for x in reversed(rs)],
            "check": ({"passed": cs[-1]["passed"], "total": cs[-1]["total"], "created_at": cs[-1]["created_at"],
                       "best": max(c["passed"] for c in cs)} if cs else None),
            "now": now,
        }

    @r.delete("/views")
    def leave(request: Request, lab_id: str | None = None, session_id: str | None = None) -> dict:
        if not (lab_id or session_id):
            raise HTTPException(400, "lab_id or session_id")
        live.leave(viewer(request), lab_id=lab_id, session_id=session_id)
        return {"ok": True}

    return r


def _current(ss: list, live: Live, now: float):
    """The session the student is on now. In a lab sitting every question
    visited has its own open session, and only the one on screen polls
    /viewers, so prefer an open session that is polling, then the newest."""
    if not ss:
        return None
    open_ = [s for s in ss if s["ended_at"] is None and live.online(s["id"], now)]
    if open_:
        with live._lock:
            return max(open_, key=lambda s: live._presence.get(s["id"], 0))
    return max(ss, key=lambda s: s["started_at"])


def _state(s, es: dict, online: bool, now: float) -> str:
    if s["ended_at"] is not None:
        return "submitted" if s["end_reason"] == "submit" else "left"
    if not online:
        return "offline"
    if es.get("away"):
        return "away"
    last = es.get("last_edit")
    if last is not None and now - last < TYPING_S:
        return "typing"
    if last is None or now - last >= IDLE_S:
        return "idle"
    return "active"


def _marks(n: int) -> str:
    return ",".join("?" * n)


def _event_stats(db: Database, ids: list[str], now: float) -> dict[str, dict]:
    """Per session: last edit (server clock), edits per 30 s over the last 10
    minutes, whether the tab or window is in the background, and paste count.
    Times are when the batch arrived, which is at most ~2 s after the keystroke."""
    if not ids:
        return {}
    out: dict[str, dict] = {i: {"activity": [0] * ACTIVITY_BINS, "n": 0} for i in ids}
    since = now - ACTIVITY_BINS * BIN_S
    with db.connect() as conn:
        for r in conn.execute(f"""SELECT session_id, COUNT(*) AS n,
                                         MAX(CASE WHEN type = 'edit' THEN received_at END) AS last_edit,
                                         SUM(type = 'clipboard' AND json_extract(data, '$.action') = 'paste') AS pastes
                                  FROM events WHERE session_id IN ({_marks(len(ids))}) GROUP BY session_id""", ids):
            out[r["session_id"]].update(n=r["n"], last_edit=r["last_edit"], pastes=r["pastes"] or 0)
        for r in conn.execute(f"""SELECT session_id, CAST((received_at - ?) / {BIN_S} AS INTEGER) AS b, COUNT(*) AS n
                                  FROM events WHERE session_id IN ({_marks(len(ids))}) AND type = 'edit' AND received_at >= ?
                                  GROUP BY 1, 2""", (since, *ids, since)):
            if 0 <= r["b"] < ACTIVITY_BINS:
                out[r["session_id"]]["activity"][r["b"]] = r["n"]
        # The latest window/page focus event says whether the IDE is in front.
        for r in conn.execute(f"""SELECT e.session_id, e.data FROM events e
                                  JOIN (SELECT session_id, MAX(seq) AS seq FROM events
                                        WHERE session_id IN ({_marks(len(ids))}) AND type = 'focus'
                                          AND json_extract(data, '$.target') IN ('window', 'page')
                                        GROUP BY session_id) m ON m.session_id = e.session_id AND m.seq = e.seq""", ids):
            out[r["session_id"]]["away"] = json.loads(r["data"]).get("state") == "out"
    return out


def _run_stats(db: Database, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    out: dict[str, dict] = {}
    with db.connect() as conn:
        for r in conn.execute(f"""SELECT session_id, created_at, exit_code, error_type FROM runs
                                  WHERE session_id IN ({_marks(len(ids))}) ORDER BY created_at""", ids):
            d = out.setdefault(r["session_id"], {"n": 0, "errors": 0, "last": None})
            d["n"] += 1
            d["errors"] += r["error_type"] is not None
            d["last"] = {"at": r["created_at"], "ok": r["error_type"] is None, "error_type": r["error_type"]}
    return out


def _check_stats(db: Database, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    out: dict[str, dict] = {}
    with db.connect() as conn:
        for r in conn.execute(f"""SELECT session_id, created_at, passed, total FROM checks
                                  WHERE session_id IN ({_marks(len(ids))}) ORDER BY created_at""", ids):
            prev = out.get(r["session_id"])
            out[r["session_id"]] = {"passed": r["passed"], "total": r["total"], "at": r["created_at"],
                                    "best": max(r["passed"], prev["best"] if prev else 0)}
    return out

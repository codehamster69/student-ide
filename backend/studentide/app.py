"""HTTP API for the lab editor.

Student-facing (no auth beyond a roll number, the lab is supervised):
    GET  /api/tasks
    POST /api/login                     {student_id}            -> consent status
    POST /api/consent                   {student_id}
    POST /api/sessions                  {student_id, task_id, client_meta}
    POST /api/sessions/{id}/events      {schema_version, events: [...]}
    POST /api/sessions/{id}/run         {code, stdin}

Research-facing (needs header X-Admin-Token = $STUDENTIDE_ADMIN_TOKEN;
disabled entirely when that variable is unset):
    GET  /api/sessions[?student_id=]
    GET  /api/sessions/{id}/events
    GET  /api/sessions/{id}/runs

Review timeline (phase 3, same token):
    GET  /api/review/config
    GET  /api/review/students
    GET  /api/review/sessions[?student_id=]   per-session summary + flags
    GET  /api/review/sessions/{id}            evidence timeline
    GET  /api/review/sessions/{id}/replay     edits + key times to rebuild the code

Run with:  uvicorn studentide.app:create_app --factory
(env STUDENTIDE_DB picks the database file)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from . import runner
from .db import Database
from .review import BASELINE_DAYS, CHANNEL_INFO, MIN_BASELINE, Reviewer, replay_data
from .schema import SCHEMA_VERSION, Event

STUDENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
TASKS: list[dict] = json.loads((Path(__file__).parent / "tasks.json").read_text(encoding="utf-8"))
TASK_IDS = {t["id"] for t in TASKS}
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class LoginIn(BaseModel):
    student_id: str


class SessionIn(BaseModel):
    student_id: str
    task_id: str
    client_meta: dict = Field(default_factory=dict)


class RunIn(BaseModel):
    code: str = Field(max_length=200_000)
    stdin: str = Field(default="", max_length=100_000)


def _student_id(raw: str) -> str:
    sid = raw.strip()
    if not STUDENT_ID.match(sid):
        raise HTTPException(400, "student id must be 1-32 letters, digits, '-' or '_'")
    return sid


def create_app(db_path: str | Path | None = None, admin_token: str | None = None, serve_frontend: bool = True) -> FastAPI:
    db = Database(db_path or os.environ.get("STUDENTIDE_DB", "data/studentide.sqlite3"))
    token = admin_token if admin_token is not None else os.environ.get("STUDENTIDE_ADMIN_TOKEN")
    app = FastAPI(title="Student IDE", version="0.1.0")
    app.state.db = db
    reviewer = Reviewer(db)
    app.state.reviewer = reviewer
    if token:
        threading.Thread(target=reviewer.warm, daemon=True).start()

    def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
        if not token:
            raise HTTPException(403, "research endpoints are disabled: set STUDENTIDE_ADMIN_TOKEN")
        if x_admin_token != token:
            raise HTTPException(401, "bad admin token")

    def live_session(session_id: str):
        row = db.get_session(session_id)
        if row is None:
            raise HTTPException(404, "unknown session")
        return row

    @app.get("/api/tasks")
    def tasks() -> list[dict]:
        return TASKS

    @app.post("/api/login")
    def login(body: LoginIn) -> dict:
        row = db.get_or_create_student(_student_id(body.student_id))
        return {"student_id": row["id"], "consented": row["consented_at"] is not None}

    @app.post("/api/consent")
    def consent(body: LoginIn) -> dict:
        sid = _student_id(body.student_id)
        db.get_or_create_student(sid)
        db.record_consent(sid)
        return {"student_id": sid, "consented": True}

    @app.post("/api/sessions")
    def start_session(body: SessionIn) -> dict:
        sid = _student_id(body.student_id)
        if body.task_id not in TASK_IDS:
            raise HTTPException(400, "unknown task")
        if db.get_or_create_student(sid)["consented_at"] is None:
            raise HTTPException(403, "consent required before recording")
        session_id = uuid.uuid4().hex
        db.create_session(session_id, sid, body.task_id, SCHEMA_VERSION, body.client_meta)
        return {"session_id": session_id, "schema_version": SCHEMA_VERSION}

    @app.post("/api/sessions/{session_id}/events")
    async def ingest(session_id: str, request: Request) -> dict:
        # Parsed by hand so navigator.sendBeacon (text/plain body) works on page close.
        live_session(session_id)
        try:
            body = json.loads(await request.body())
            raw_events = body["events"]
            if body.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION or not isinstance(raw_events, list):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise HTTPException(400, f"expected {{schema_version: {SCHEMA_VERSION}, events: [...]}}")
        if len(raw_events) > 5000:
            raise HTTPException(413, "batch too large")

        # Validate one by one: a single malformed event must not block the rest
        # (the client would otherwise retry the same batch forever).
        good, rejected = [], []
        for raw in raw_events:
            try:
                good.append(Event.model_validate(raw).model_dump())
            except ValidationError as e:
                seq = raw.get("seq") if isinstance(raw, dict) else None
                rejected.append({"seq": seq, "error": e.errors(include_url=False)[0]["msg"]})
        inserted = db.insert_events(session_id, good)
        for ev in good:
            if ev["type"] == "session_end":
                db.end_session(session_id, ev["data"].get("reason") or "end")
        return {"accepted": len(good), "inserted": inserted, "rejected": rejected, "max_seq": db.max_seq(session_id)}

    @app.post("/api/sessions/{session_id}/run")
    def run(session_id: str, body: RunIn) -> dict:
        live_session(session_id)
        res = runner.run_python(body.code, body.stdin)
        run_id = uuid.uuid4().hex
        db.insert_run({
            "id": run_id, "session_id": session_id, "created_at": time.time(),
            "code": body.code, "stdin": body.stdin, "stdout": res.stdout, "stderr": res.stderr,
            "exit_code": res.exit_code, "duration_ms": res.duration_ms, "error_type": res.error_type,
        })
        return {
            "run_id": run_id,
            "code_sha256": hashlib.sha256(body.code.encode()).hexdigest(),
            "stdout": res.stdout, "stderr": res.stderr,
            "exit_code": res.exit_code, "duration_ms": res.duration_ms, "error_type": res.error_type,
        }

    @app.get("/api/sessions", dependencies=[Depends(require_admin)])
    def sessions(student_id: str | None = None) -> list[dict]:
        out = []
        for r in db.list_sessions(student_id):
            d = dict(r)
            d["client_meta"] = json.loads(d["client_meta"])
            out.append(d)
        return out

    @app.get("/api/sessions/{session_id}/events", dependencies=[Depends(require_admin)])
    def session_events(session_id: str, type: str | None = None) -> list[dict]:
        live_session(session_id)
        return list(db.iter_events(session_id, tuple(type.split(",")) if type else None))

    @app.get("/api/sessions/{session_id}/runs", dependencies=[Depends(require_admin)])
    def session_runs(session_id: str) -> list[dict]:
        live_session(session_id)
        return [dict(r) for r in db.list_runs(session_id)]

    @app.get("/api/review/config", dependencies=[Depends(require_admin)])
    def review_config() -> dict:
        return {"h": reviewer.h, "window_s": reviewer.window_s, "baseline_days": BASELINE_DAYS,
                "min_baseline": MIN_BASELINE,
                "channels": {ch: {"label": l, "about": a} for ch, (l, a) in CHANNEL_INFO.items()}}

    @app.get("/api/review/students", dependencies=[Depends(require_admin)])
    def review_students() -> list[dict]:
        by_student: dict[str, list] = {}
        for r in db.list_sessions():
            by_student.setdefault(r["student_id"], []).append(dict(r))
        out = []
        for st, ss in sorted(by_student.items()):
            base = reviewer.baseline_ids(ss)
            out.append({"student_id": st, "n_sessions": len(ss), "n_baseline": len(base),
                         "baseline_ready": len(base) >= MIN_BASELINE,
                         "first": min(s["started_at"] for s in ss), "last": max(s["started_at"] for s in ss)})
        return out

    @app.get("/api/review/sessions", dependencies=[Depends(require_admin)])
    def review_sessions(student_id: str | None = None) -> list[dict]:
        return [reviewer.summary(r["id"]) for r in db.list_sessions(student_id)]

    @app.get("/api/review/sessions/{session_id}", dependencies=[Depends(require_admin)])
    def review_session(session_id: str) -> dict:
        live_session(session_id)
        return reviewer.review(session_id)

    @app.get("/api/review/sessions/{session_id}/replay", dependencies=[Depends(require_admin)])
    def review_replay(session_id: str) -> dict:
        live_session(session_id)
        return replay_data(db, session_id)

    if serve_frontend and FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    return app


"""HTTP API for the lab editor.

Student-facing (no auth beyond a roll number, the lab is supervised):
    GET  /api/tasks                                built-in practice tasks
    GET  /api/students/{id}/labs                   open labs assigned to this student
    POST /api/login                     {student_id}            -> consent status
    POST /api/consent                   {student_id}
    POST /api/sessions                  {student_id, task_id | question_id | lesson_id, client_meta, language?}
                                                   (language: any-language competitions, one session per language)
    POST /api/sessions/{id}/events      {schema_version, events: [...]}
    POST /api/sessions/{id}/run         {code, stdin}   in the lab's language (Python for practice tasks)
    POST /api/sessions/{id}/check       {code}          against the question's tests, if it has any
    GET  /api/live-prompt/{provider}/{ref}             a question's text when the browser can't fetch it
                                                       itself (LeetCode; kept in memory only, never stored)

Sign-in (see auth.py). With $STUDENTIDE_GOOGLE_CLIENT_ID set, students and
teachers sign in with their college Google account, /api/login is off and
every student endpoint acts only for the signed-in student:
    GET  /api/auth/config                          {mode: google | dev, client_id, domain}
    POST /api/auth/google               {credential}            -> account, sets the session cookie
    GET  /api/me                                   the signed-in account (401 if none)
    POST /api/auth/logout
    GET  /api/admin/users                          admins only
    PUT  /api/admin/users/{email}       {role}     admin override (TAs, odd addresses)
    DELETE /api/admin/users/{email}/role           drop the override

Research-facing (a teacher or admin account in Google mode; otherwise header
X-Admin-Token = $STUDENTIDE_ADMIN_TOKEN, disabled when that variable is unset).
A teacher sees only sessions recorded in their own or shared labs; admins, the
token and dev mode see everything (auth.Auth.check_lab):
    GET  /api/sessions[?student_id=&lab_id=]
    GET  /api/sessions/{id}/events
    GET  /api/sessions/{id}/runs
    GET  /api/sessions/{id}/checks

Live classroom view (same access, see live.py; $STUDENTIDE_LIVE = editor | class | off):
    GET  /api/live/labs, /api/live/labs/{lab_id}, /api/live/sessions/{id}
    GET  /api/sessions/{id}/viewers                student: who is watching now

Review timeline (phase 3, same access):
    GET  /api/review/config
    GET  /api/review/labs                     lab sessions: when they ran, students, moments
    GET  /api/review/students
    GET  /api/review/sessions[?student_id=&lab_id=]   per-session summary + flags (lab_id=practice: outside labs)
    GET  /api/review/sessions/{id}            evidence timeline
    GET  /api/review/sessions/{id}/replay     edits + key times to rebuild the code

Learning lab (always open, never reviewed; see learn.py):
    GET  /api/learn[?student_id=]                  tracks and lessons, with the student's progress
    GET  /api/learn/lessons/{track}/{slug}

Teacher authoring (same access): /api/teach/*, see teach.py.
Class competitions: /api/teach/competitions/*, /api/competitions/*,
POST /api/sessions/{id}/submit, see compete.py.

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

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from . import attendance, compete, grading, learn, live as live_mod, retention, runner, teach
from .auth import Auth, Config
from .db import CONSENT_VERSION, Database, has_consent
from .providers import PROVIDERS, ProviderError
from .review import BASELINE_DAYS, CHANNEL_INFO, MIN_BASELINE, Reviewer, replay_data
from .replay import ReplayError, final_text
from .schema import SCHEMA_VERSION, Event

PREVIEW = "preview"  # sessions.context of a teacher's "View as student" (see auth.previewer)
STUDENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
TASKS: list[dict] = json.loads((Path(__file__).parent / "tasks.json").read_text(encoding="utf-8"))
TASK_IDS = {t["id"] for t in TASKS}
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class LoginIn(BaseModel):
    student_id: str


class GoogleIn(BaseModel):
    credential: str = Field(max_length=8192)


class RoleIn(BaseModel):
    role: str


class SessionIn(BaseModel):
    student_id: str
    task_id: str | None = None      # a built-in practice task, or
    question_id: str | None = None  # a question from a lab the teacher assigned, or
    lesson_id: str | None = Field(default=None, max_length=200)  # a learning-lab lesson
    sitting_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,64}$")  # one opening of that lab
    language: str | None = None     # an any-language competition: the language the student picked for this question
    client_meta: dict = Field(default_factory=dict)


class RunIn(BaseModel):
    code: str = Field(max_length=200_000)
    stdin: str = Field(default="", max_length=100_000)


class CheckIn(BaseModel):
    code: str = Field(max_length=200_000)


def _student_id(raw: str) -> str:
    sid = raw.strip()
    if not STUDENT_ID.match(sid):
        raise HTTPException(400, "student id must be 1-32 letters, digits, '-' or '_'")
    return sid


def latest_code(db: Database, student_id: str, question_id: str, language: str | None = None) -> str | None:
    """The code of this student's most recent session on the question, rebuilt
    from its edits (or its last snapshot if events were lost); None if none.
    `language`: only sessions in that language count (an any-language competition
    keeps one session per language, and C code must not come back as Python)."""
    for row in db.previous_sessions(student_id, question_id):
        if language and row["question_json"] and json.loads(row["question_json"]).get("language", language) != language:
            continue
        events = list(db.iter_events(row["id"], ("snapshot", "edit")))
        if not events:
            continue
        try:
            return final_text(events)
        except ReplayError:
            snaps = [e["data"]["text"] for e in events if e["type"] == "snapshot"]
            if snaps:
                return snaps[-1]
    return None


def create_app(db_path: str | Path | None = None, admin_token: str | None = None, serve_frontend: bool = True,
               auth_config: Config | None = None, verify_google=None, live_mode: str | None = None,
               attendance_transport=None) -> FastAPI:
    """`auth_config` / `verify_google` replace the environment and Google's token check in tests,
    `attendance_transport` the HTTP calls to Roll Call (see attendance.Transport)."""
    db = Database(db_path or os.environ.get("STUDENTIDE_DB", "data/studentide.sqlite3"))
    cfg = auth_config or Config.from_env(admin_token)
    auth = Auth(db, cfg, verify_google)
    app = FastAPI(title="Student IDE", version="0.2.0")
    app.state.db = db
    app.state.auth = auth
    reviewer = Reviewer(db)
    app.state.reviewer = reviewer
    if cfg.admin_token or cfg.google:
        threading.Thread(target=reviewer.warm, daemon=True).start()
    retention.ensure_schema(db)
    live_mod.ensure_schema(db)
    live = live_mod.Live(db, live_mode or live_mod.mode_from_env())
    app.state.live = live
    retention.start_background(db, reviewer.settings)

    require_admin = auth.require_teacher  # every teacher / research endpoint

    def live_session(session_id: str, request: Request | None = None):
        """The session row; with `request`, only for the student who owns it."""
        row = db.get_session(session_id)
        if row is None:
            raise HTTPException(404, "unknown session")
        if request is not None:
            auth.own_session(request, row)
        return row

    @app.get("/api/tasks")
    def tasks() -> list[dict]:
        return TASKS

    @app.get("/api/live-prompt/{provider_id}/{ref}")
    def live_prompt(provider_id: str, ref: str, request: Request) -> dict:
        """Fallback for questions whose text the app may not store: the server
        fetches it from the same public source the browser tries first, holds it
        in memory for a while and passes it on. Signed-in users only."""
        if auth.cfg.google and auth.current(request) is None and not auth.token_ok(request):
            raise HTTPException(401, "sign in first")
        p = PROVIDERS.get(provider_id)
        if p is None or not hasattr(p, "live_text"):
            raise HTTPException(404, "this source has no live text")
        try:
            return {"text": p.live_text(ref)}
        except ProviderError as e:
            raise HTTPException(e.status, str(e)) from e

    # -- sign-in

    def me_json(user: dict) -> dict:
        st = db.get_or_create_student(user["student_id"])
        return {k: user[k] for k in ("email", "name", "role", "student_id", "program", "year", "branch", "roll")} | {
            "consented": has_consent(st)}

    @app.get("/api/auth/config")
    def auth_config_json() -> dict:
        return {"mode": "google" if cfg.google else "dev", "client_id": cfg.client_id, "domain": cfg.domain,
                "live": live.mode, "consent_version": CONSENT_VERSION}

    @app.post("/api/auth/google")
    def google_sign_in(body: GoogleIn, response: Response) -> dict:
        if not cfg.google:
            raise HTTPException(404, "Google sign-in is not configured on this server")
        claims = auth.verify(body.credential)
        user = auth.upsert_user(claims["email"], str(claims.get("name", "")))
        auth.sign_in(response, user["email"])
        return me_json(user)

    @app.get("/api/me")
    def me(request: Request) -> dict:
        user = auth.current(request)
        if user is None:
            raise HTTPException(401, "not signed in")
        return me_json(user)

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response) -> dict:
        auth.sign_out(request, response)
        return {"ok": True}

    @app.get("/api/admin/users")
    def admin_users(request: Request) -> list[dict]:
        auth.require_admin(request)
        return auth.list_users()

    @app.put("/api/admin/users/{email}")
    def admin_set_role(email: str, body: RoleIn, request: Request) -> dict:
        admin = auth.require_admin(request)
        return auth.set_role(email, body.role, admin["email"])

    @app.delete("/api/admin/users/{email}/role")
    def admin_reset_role(email: str, request: Request) -> dict:
        auth.require_admin(request)
        return auth.reset_role(email)

    # -- students

    @app.post("/api/login")
    def login(body: LoginIn) -> dict:
        if cfg.google:
            raise HTTPException(410, "sign in with your college Google account")
        row = db.get_or_create_student(_student_id(body.student_id))
        return {"student_id": row["id"], "consented": has_consent(row)}

    @app.post("/api/consent")
    def consent(body: LoginIn, request: Request) -> dict:
        sid = _student_id(body.student_id)
        auth.own_student(request, sid)
        db.get_or_create_student(sid)
        db.record_consent(sid)
        return {"student_id": sid, "consented": True}

    @app.post("/api/sessions")
    def start_session(body: SessionIn, request: Request) -> dict:
        sid = _student_id(body.student_id)
        auth.own_student(request, sid)
        # "View as student": a teacher's own and shared labs (drafts too), kept out of every study table
        staff = auth.previewer(request)
        question, context = None, None
        if body.lesson_id:
            lesson = learn.get_lesson(body.lesson_id)
            if lesson is None:
                raise HTTPException(404, "no such lesson")
            question, context = learn.snapshot(lesson), learn.CONTEXT
            task_id = lesson["id"]
        elif body.question_id:
            q = db.get_question(body.question_id)
            open_labs = db.preview_labs(auth.preview_lab_ids(staff)) if staff else db.labs_for_student(sid)
            if q is None or q["lab_id"] not in {l["id"] for l in open_labs}:
                raise HTTPException(403, "this question is not open for you")
            lab = db.get_lab(q["lab_id"])
            # The snapshot keeps everything the session ran against, hidden tests included.
            question = teach.question_json(q) | {"language": lab["language"], "subject": lab["subject"]}
            if lab["language"] == grading.ANY:
                # one session = one language: switching language opens another session (detector baselines stay per language)
                allowed = grading.question_languages(q)
                if body.language not in allowed:
                    raise HTTPException(400, f"pick one of: {', '.join(allowed)}")
                question = grading.for_language(question, body.language)
            task_id = q["id"]
        elif body.task_id in TASK_IDS:
            task_id = body.task_id
        else:
            raise HTTPException(400, "unknown task")
        if staff:
            context = PREVIEW
            db.get_or_create_student(sid)
            if question and question["lab_id"] and compete.get_comp(db, question["lab_id"]):
                raise HTTPException(403, "student view can't enter a competition: it would put you on the class board")
        elif not has_consent(db.get_or_create_student(sid)):
            raise HTTPException(403, "consent required before recording")
        if question and question["lab_id"] and not staff:
            compete.can_start_session(db, question["lab_id"], sid)
        # Coming back to a question (a later lab sitting, back from a competition's
        # board, or a lesson opened again) picks up the code where the student left it, in the same language.
        resume = latest_code(db, sid, question["id"], question["language"]) if question else None
        session_id = uuid.uuid4().hex
        db.create_session(session_id, sid, task_id, SCHEMA_VERSION, body.client_meta, question,
                          body.sitting_id if question else None, context)
        return {"session_id": session_id, "schema_version": SCHEMA_VERSION,
                "lab_id": question and question["lab_id"], "question_id": question and question["id"],
                "sitting_id": question and body.sitting_id, "resume_code": resume}

    @app.get("/api/students/{student_id}/labs")
    def my_labs(student_id: str, request: Request) -> list[dict]:
        sid = _student_id(student_id)
        auth.own_student(request, sid)
        staff = auth.previewer(request)
        return teach.student_labs(db, sid, db.preview_labs(auth.preview_lab_ids(staff)) if staff else None)

    @app.post("/api/sessions/{session_id}/events")
    async def ingest(session_id: str, request: Request) -> dict:
        # Parsed by hand so navigator.sendBeacon (text/plain body) works on page close.
        live_session(session_id, request)
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

    @app.get("/api/sessions/{session_id}/viewers")
    def viewers(session_id: str, request: Request) -> dict:
        """Polled by the student's IDE: who is watching live (shown as a banner). Also its presence heartbeat."""
        row = live_session(session_id, request)
        live.seen(session_id)
        return live.viewers(row) | {"live": live.mode}

    def snapshot(row) -> dict:
        """The question as the student saw it when the session started (empty for practice tasks)."""
        return json.loads(row["question_json"]) if row["question_json"] else {}

    @app.post("/api/sessions/{session_id}/run")
    def run(session_id: str, body: RunIn, request: Request) -> dict:
        row = live_session(session_id, request)
        res = runner.run(body.code, body.stdin, snapshot(row).get("language", "python"))
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

    @app.post("/api/sessions/{session_id}/check")
    def check(session_id: str, body: CheckIn, request: Request) -> dict:
        """Checks against the tests in the session's snapshot, so a question edited
        mid-session never changes what an open session is checked against."""
        q = snapshot(live_session(session_id, request))
        graded = grading.grade(q, body.code, q.get("language", "python")) if q else None
        if graded is None:
            raise HTTPException(409, "this question has no test cases")
        check_id = uuid.uuid4().hex
        db.insert_check(check_id, session_id, body.code, graded)
        return graded | {"check_id": check_id, "code_sha256": hashlib.sha256(body.code.encode()).hexdigest()}

    def teacher_session(session_id: str, request: Request):
        """A session row for a teacher endpoint: only from the teacher's own or shared labs."""
        row = live_session(session_id)
        auth.check_lab(request, row["lab_id"])
        return row

    def visible_sessions(request: Request, student_id: str | None = None, lab_id: str | None = None) -> list:
        """Sessions a teacher may see; lab_id 'practice' = sessions outside any lab (admins only)."""
        if lab_id:
            auth.check_lab(request, None if lab_id == "practice" else lab_id)
        rows = db.list_sessions(student_id, None if lab_id == "practice" else lab_id)
        if lab_id == "practice":
            rows = [r for r in rows if r["lab_id"] is None]
        ids = auth.lab_ids(request)
        return rows if ids is None else [r for r in rows if r["lab_id"] in ids]

    @app.get("/api/sessions", dependencies=[Depends(require_admin)])
    def sessions(request: Request, student_id: str | None = None, lab_id: str | None = None) -> list[dict]:
        out = []
        for r in visible_sessions(request, student_id, lab_id):
            d = dict(r)
            d["client_meta"] = json.loads(d["client_meta"])
            d["question_json"] = json.loads(d["question_json"]) if d["question_json"] else None
            out.append(d)
        return out

    @app.get("/api/sessions/{session_id}/events", dependencies=[Depends(require_admin)])
    def session_events(session_id: str, request: Request, type: str | None = None) -> list[dict]:
        teacher_session(session_id, request)
        return list(db.iter_events(session_id, tuple(type.split(",")) if type else None))

    @app.get("/api/sessions/{session_id}/runs", dependencies=[Depends(require_admin)])
    def session_runs(session_id: str, request: Request) -> list[dict]:
        teacher_session(session_id, request)
        return [dict(r) for r in db.list_runs(session_id)]

    @app.get("/api/sessions/{session_id}/checks", dependencies=[Depends(require_admin)])
    def session_checks(session_id: str, request: Request) -> list[dict]:
        teacher_session(session_id, request)
        return [dict(r) | {"results_json": json.loads(r["results_json"])} for r in db.list_checks(session_id)]

    @app.get("/api/review/config", dependencies=[Depends(require_admin)])
    def review_config() -> dict:
        st = reviewer.settings
        return {"h": reviewer.h, "window_s": reviewer.window_s, "baseline_days": BASELINE_DAYS,
                "min_baseline": MIN_BASELINE, "config_source": st.source, "prior_n": st.prior_n,
                "channels": {ch: {"label": l, "about": a, "window_s": st.window_s[ch], "k": st.k[ch]}
                             for ch, (l, a) in CHANNEL_INFO.items() if ch in st.channels}}

    @app.get("/api/review/students", dependencies=[Depends(require_admin)])
    def review_students(request: Request) -> list[dict]:
        ids = auth.lab_ids(request)
        by_student: dict[str, list] = {}
        for r in reviewer._sessions():  # tagged with context, so competitions stay out of the lab baseline
            by_student.setdefault(r["student_id"], []).append(r)
        out = []
        for st, ss in sorted(by_student.items()):
            seen = ss if ids is None else [s for s in ss if s["lab_id"] in ids]
            if not seen:
                continue
            # The baseline is the student's, built from all their lab sessions; a
            # teacher only sees the sessions from their own labs.
            base = reviewer.baseline_ids(ss)
            out.append({"student_id": st, "n_sessions": len(seen), "n_baseline": len(base),
                         "baseline_ready": len(base) >= MIN_BASELINE,
                         "first": min(s["started_at"] for s in seen), "last": max(s["started_at"] for s in seen)})
        return out

    @app.get("/api/review/labs", dependencies=[Depends(require_admin)])
    def review_labs(request: Request) -> list[dict]:
        """The Review tab's first screen: one row per lab session the teacher
        may see (when it ran, who came, how many moments), newest first."""
        by_lab: dict[str | None, list] = {}
        for r in visible_sessions(request):
            by_lab.setdefault(r["lab_id"], []).append(r)
        labs = {l["id"]: l for l in db.list_labs(auth.lab_ids(request))}
        out = []
        for lab_id, ss in by_lab.items():
            if lab_id is not None and lab_id not in labs:
                continue
            lab = labs.get(lab_id)
            sums = [reviewer.summary(s["id"]) for s in ss]
            out.append({
                "id": lab_id or "practice", "title": lab["title"] if lab else "Practice tasks",
                "kind": lab["kind"] if lab else "practice", "subject": lab["subject"] if lab else "",
                "status": lab["status"] if lab else None,
                "started_at": min(s["started_at"] for s in ss),
                "ended_at": max(x["started_at"] + x["duration_s"] for x in sums),
                # when each class sitting began, so the browser can show the days in local time
                "sittings_at": sorted({k: min(x["started_at"] for x in ss if (x["sitting_id"] or x["id"]) == k)
                                       for k in {s["sitting_id"] or s["id"] for s in ss}}.values()),
                "n_students": len({s["student_id"] for s in ss}), "n_sessions": len(ss),
                "n_assessed": sum(x["phase"] == "assessed" for x in sums),
                "n_with_moments": sum(bool(x["episodes"]) for x in sums),
                "students_with_moments": len({x["student_id"] for x in sums if x["episodes"]}),
            })
        return sorted(out, key=lambda d: d["started_at"], reverse=True)

    @app.get("/api/review/sessions", dependencies=[Depends(require_admin)])
    def review_sessions(request: Request, student_id: str | None = None, lab_id: str | None = None) -> list[dict]:
        return [reviewer.summary(r["id"]) for r in visible_sessions(request, student_id, lab_id)]

    @app.get("/api/review/sessions/{session_id}", dependencies=[Depends(require_admin)])
    def review_session(session_id: str, request: Request) -> dict:
        teacher_session(session_id, request)
        return reviewer.review(session_id)

    @app.get("/api/review/sessions/{session_id}/replay", dependencies=[Depends(require_admin)])
    def review_replay(session_id: str, request: Request) -> dict:
        teacher_session(session_id, request)
        return replay_data(db, session_id)

    app.include_router(learn.router(db, auth, _student_id))
    attendance_router = attendance.router(db, require_admin, auth, attendance_transport)
    app.include_router(attendance_router)
    app.include_router(teach.router(db, require_admin, auth, attendance_router.on_lab_closed))
    app.include_router(compete.router(db, require_admin, auth))
    app.include_router(live_mod.router(db, require_admin, auth, reviewer, live))

    if serve_frontend and FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    return app


"""Grading of Sandbox Lab submissions on the server.

A student's Submit in the desktop app uploads the assignment folder with
reason "submit" (workspaces.py). That snapshot becomes a submission here and is
queued; one grader thread takes the queue in order and, in a fresh container of
the lab's environment image (no network, small CPU/memory caps, started through
the preview driver, so in deployment through preview_service.py, the only
holder of the Docker socket), lays the starter files, then the student's files
over them, and runs every test of the assignment, hidden ones too. The
container is removed afterwards. One grading run at a time keeps the e2-medium
VM responsive next to the three teacher previews; a run takes the image start
plus the tests (usually 5-30 s).

What the student sees: status, passed/total and every visible test in full;
a hidden test shows only its name and whether it passed. Teachers see
everything, per student and assignment, and can regrade one submission or a
whole lab after fixing a test.

Student routes (desktop app; cookie in Google mode, ?student_id= in dev mode):
    GET  /api/sandbox/my/labs/{lab_id}/submissions   latest per assignment + attempts
    GET  /api/sandbox/my/submissions/{id}            one, for polling while it grades
Teacher routes (same access as the lab):
    GET  /api/sandbox/labs/{lab_id}/submissions      every rostered student x assignment
    GET  /api/sandbox/submissions/{id}               full results (hidden tests too)
    POST /api/sandbox/submissions/{id}/regrade
    POST /api/sandbox/labs/{lab_id}/regrade          the latest submission of every student

Snapshots hold text and binary files; only UTF-8 text files are laid into the
grading container (build outputs are already left out by the desktop app, and
the tests build from source). Grading uses the lab's image only, not packages
the student installed in their own instance, like any autograder.
"""

from __future__ import annotations

import gzip
import io
import json
import posixpath
import tarfile
import threading
import time
import uuid
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request

from .db import Database
from .previews import Driver, Limits, PreviewError, instance_spec, run_tests, starter_files
from .sandbox import Store, definition, late_policy

SCHEMA = """
CREATE TABLE IF NOT EXISTS sbx_submissions (
    id            TEXT PRIMARY KEY,           -- sub_ + 10 hex; the grading container is sbxp-<id>
    student_id    TEXT NOT NULL,
    lab_id        TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    snapshot_id   INTEGER NOT NULL,           -- workspace_snapshots.id (submits are never pruned)
    sha256        TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('queued', 'grading', 'graded', 'failed', 'no_tests')),
    passed        INTEGER,
    total         INTEGER,
    results_json  TEXT NOT NULL DEFAULT '[]', -- run_tests results, hidden tests included
    error         TEXT NOT NULL DEFAULT '',
    lab_version   INTEGER,                    -- the lab version the tests came from at grading time
    grades        INTEGER NOT NULL DEFAULT 0, -- times graded (> 1 = regraded)
    submitted_at  REAL NOT NULL,
    graded_at     REAL
);
CREATE INDEX IF NOT EXISTS sbx_submissions_by_lab ON sbx_submissions(lab_id, student_id, assignment_id, submitted_at);
CREATE INDEX IF NOT EXISTS sbx_submissions_queue ON sbx_submissions(status, submitted_at);
"""

GRADE_LIMITS = Limits(cpus=1.0, memory_mb=1024, pids=256)
MAX_TEXT_FILE = 2_000_000
NOT_SET_UP = "Grading is not set up on this server yet. Your work is saved; your teacher can grade it later."


def snapshot_files(data: bytes, workdir: str) -> list[dict]:
    """A workspace snapshot (gzip tar, already checked by workspaces.check_tarball)
    -> [{path, content, executable}] for its UTF-8 text files, placed under workdir."""
    out = []
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(data)), mode="r:") as tar:
        for m in tar.getmembers():
            if not m.isfile() or m.size > MAX_TEXT_FILE:
                continue
            name = posixpath.normpath(m.name[2:] if m.name.startswith("./") else m.name)
            if name.startswith(("/", "..")) or name == ".":
                continue
            try:
                content = tar.extractfile(m).read().decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                continue
            out.append({"path": posixpath.join(workdir, name), "content": content, "executable": bool(m.mode & 0o111)})
    return out


def for_student(results: list[dict]) -> list[dict]:
    """Hidden tests: name and pass only, so their inputs and outputs stay secret."""
    out = []
    for r in results:
        if r.get("hidden"):
            out.append({"name": r["name"], "hidden": True, "passed": r["passed"], "timed_out": r.get("timed_out", False)})
        else:
            out.append({k: v for k, v in r.items() if k != "stderr"} | {"stderr": (r.get("stderr") or "")[-2000:]})
    return out


class Grader:
    """The queue in sbx_submissions and the one thread that works through it."""

    def __init__(self, db: Database, store: Store, driver: Driver | None, clock: Callable[[], float] = time.time):
        self.db, self.store, self.driver, self.clock = db, store, driver, clock
        self.background = True  # tests grade inline instead
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return self.driver is not None

    def row(self, sub_id: str):
        return self.store.one("SELECT * FROM sbx_submissions WHERE id = ?", (sub_id,))

    def queued(self) -> int:
        return self.store.one("SELECT COUNT(*) n FROM sbx_submissions WHERE status IN ('queued', 'grading')")["n"]

    def submit(self, student_id: str, lab_id: str, assignment_id: str, snapshot_id: int, sha: str) -> str:
        sub_id = "sub_" + uuid.uuid4().hex[:10]
        status = "queued" if self.has_tests(lab_id, assignment_id) else "no_tests"  # also for labs graded by hand
        self.store.x("""INSERT INTO sbx_submissions (id, student_id, lab_id, assignment_id, snapshot_id, sha256, status,
                        error, submitted_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                     (sub_id, student_id, lab_id, assignment_id, snapshot_id, sha, status,
                      "" if self.enabled or status == "no_tests" else NOT_SET_UP, self.clock()))
        if status == "queued":
            self.kick()
        return sub_id

    def has_tests(self, lab_id: str, assignment_id: str) -> bool:
        lab = self.store.one("SELECT * FROM sbx_labs WHERE id = ?", (lab_id,))
        if lab is not None and "grading_mode" in lab.keys() and lab["grading_mode"] == "manual":
            return False
        a = self.store.one("SELECT tests_json FROM sbx_assignments WHERE id = ? AND lab_id = ?", (assignment_id, lab_id))
        t = json.loads(a["tests_json"] or "{}") if a else {}
        return bool(t.get("cases")) if t.get("kind", "io") == "io" else bool((t.get("command") or "").strip())

    def regrade(self, sub_ids: list[str]) -> int:
        n = 0
        for sid in sub_ids:
            row = self.row(sid)
            if row is None or row["status"] == "grading":
                continue
            status = "queued" if self.has_tests(row["lab_id"], row["assignment_id"]) else "no_tests"
            self.store.x("UPDATE sbx_submissions SET status = ?, error = ? WHERE id = ?",
                         (status, "" if self.enabled or status == "no_tests" else NOT_SET_UP, sid))
            n += status == "queued"
        if n:
            self.kick()
        return n

    def latest_ids(self, lab_id: str, assignment_id: str | None = None) -> list[str]:
        rows = self.store.q("""SELECT id FROM sbx_submissions s WHERE lab_id = ? AND (? IS NULL OR assignment_id = ?)
                               AND submitted_at = (SELECT MAX(submitted_at) FROM sbx_submissions t WHERE t.lab_id = s.lab_id
                               AND t.student_id = s.student_id AND t.assignment_id = s.assignment_id)""",
                            (lab_id, assignment_id, assignment_id))
        return [r["id"] for r in rows]

    def regrade_assignment(self, lab_id: str, assignment_id: str) -> int:
        """sandbox.py's on_tests_changed hook: the tests of a published lab changed."""
        return self.regrade(self.latest_ids(lab_id, assignment_id))

    # -- the worker

    def kick(self) -> None:
        if not self.enabled:
            return
        if not self.background:
            self.drain()
            return
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._loop, name="sandbox-grader", daemon=True)
                self.thread.start()
        self.wake.set()

    def _loop(self) -> None:
        while True:
            self.drain()
            self.wake.wait(60)
            self.wake.clear()

    def on_restart(self) -> None:
        """A run cut off by a restart goes back in the queue."""
        self.store.x("UPDATE sbx_submissions SET status = 'queued' WHERE status = 'grading'")
        if self.queued():
            self.kick()

    def drain(self) -> None:
        while True:
            with self.lock:
                row = self.store.one("SELECT * FROM sbx_submissions WHERE status = 'queued' ORDER BY submitted_at LIMIT 1")
                if row is None:
                    return
                self.store.x("UPDATE sbx_submissions SET status = 'grading' WHERE id = ?", (row["id"],))
            self.grade(row)

    def grade(self, row) -> None:
        container = f"sbxp-{row['id']}"
        try:
            lab = self.store.one("SELECT * FROM sbx_labs WHERE id = ?", (row["lab_id"],))
            if lab is None:
                raise PreviewError("the lab was deleted")
            d = definition(self.store, lab, student=False)
            a = next((a for a in d["assignments"] if a["id"] == row["assignment_id"]), None)
            if a is None:
                raise PreviewError("the assignment was deleted")
            if d["environment"] is None:
                raise PreviewError("the subject has no environment")
            with self.db.connect() as conn:
                snap = conn.execute("SELECT data FROM workspace_snapshots WHERE id = ?", (row["snapshot_id"],)).fetchone()
            if snap is None:
                raise PreviewError("the submitted snapshot is gone")
            files = {f["path"]: f for f in starter_files(a["workdir"], a["files"])}
            files |= {f["path"]: f for f in snapshot_files(bytes(snap["data"]), a["workdir"])}
            spec = instance_spec(self.store, container, lab, d, GRADE_LIMITS, network="off")
            try:
                self.driver.start(spec)
                self.driver.put_files(container, list(files.values()))
                res = run_tests(self.driver, container, a["workdir"], a["run"], a["tests"])
            finally:
                try:
                    self.driver.stop(container)
                except PreviewError:
                    pass
            self.store.x("""UPDATE sbx_submissions SET status = 'graded', passed = ?, total = ?, results_json = ?, error = '',
                            lab_version = ?, grades = grades + 1, graded_at = ? WHERE id = ?""",
                         (res["passed"], res["total"], json.dumps(res["results"]), lab["version"], self.clock(), row["id"]))
        except Exception as e:  # noqa: BLE001 - a failed run is recorded, the queue goes on
            msg = str(e) if isinstance(e, PreviewError) else f"grading failed ({type(e).__name__})"
            self.store.x("UPDATE sbx_submissions SET status = 'failed', error = ?, grades = grades + 1, graded_at = ? "
                         "WHERE id = ?", (msg[:1000], self.clock(), row["id"]))


def submission_json(row, student: bool, attempts: int | None = None, lab=None) -> dict:
    """`lab`: its row, to add the late policy's verdict (days late, score factor)."""
    results = json.loads(row["results_json"] or "[]")
    d = {"id": row["id"], "lab_id": row["lab_id"], "assignment_id": row["assignment_id"], "status": row["status"],
         "passed": row["passed"], "total": row["total"], "submitted_at": row["submitted_at"],
         "graded_at": row["graded_at"], "error": row["error"], "regraded": row["grades"] > 1,
         "results": for_student(results) if student else results}
    if not student:
        d |= {"student_id": row["student_id"], "sha256": row["sha256"], "lab_version": row["lab_version"]}
    if attempts is not None:
        d["attempts"] = attempts
    if lab is not None:
        late = late_policy(lab, row["submitted_at"])
        d["late"] = {"days": late["days_late"], "factor": late["factor"], "reason": late["reason"]}
    return d


def router(db: Database, require_teacher: Callable, auth, sandbox_router, driver: Driver | None,
           clock: Callable[[], float] = time.time) -> APIRouter:
    with db.connect() as conn:
        conn.executescript(SCHEMA)
    store: Store = sandbox_router.store
    grader = Grader(db, store, driver, clock)
    r = APIRouter(prefix="/api/sandbox", dependencies=[Depends(require_teacher)])
    open_r = APIRouter(prefix="/api/sandbox")

    def latest(lab_id: str, student_id: str | None = None) -> dict[tuple[str, str], tuple]:
        """(student, assignment) -> (latest row, attempts)."""
        rows = store.q("""SELECT * FROM sbx_submissions WHERE lab_id = ? AND (? IS NULL OR student_id = ?)
                          ORDER BY submitted_at""", (lab_id, student_id, student_id))
        out: dict[tuple[str, str], tuple] = {}
        for row in rows:
            k = (row["student_id"], row["assignment_id"])
            out[k] = (row, (out[k][1] if k in out else 0) + 1)
        return out

    def progress(student_id: str, lab_id: str) -> dict:
        got = latest(lab_id, student_id).values()
        return {"submitted": len(got),
                "passed_all": sum(1 for row, _ in got if row["status"] == "graded" and row["passed"] == row["total"])}

    def student_lab(request: Request, lab_id: str, student_id: str | None):
        sid = sandbox_router.student_of(request, student_id)
        if not any(l["id"] == lab_id for l in sandbox_router.visible_labs(sid, include_closed=True)):
            raise HTTPException(404, "this lab is not open for you")
        return sid

    @open_r.get("/my/labs/{lab_id}/submissions")
    def my_submissions(lab_id: str, request: Request, student_id: str | None = None) -> dict:
        sid = student_lab(request, lab_id, student_id)
        got = latest(lab_id, sid)
        lab = store.one("SELECT * FROM sbx_labs WHERE id = ?", (lab_id,))
        return {"grader": {"enabled": grader.enabled},
                "assignments": {a["id"]: (submission_json(got[(sid, a["id"])][0], True, got[(sid, a["id"])][1], lab)
                                          if (sid, a["id"]) in got else None) for a in store.assignments(lab_id)}}

    @open_r.get("/my/submissions/{sub_id}")
    def my_submission(sub_id: str, request: Request, student_id: str | None = None) -> dict:
        sid = sandbox_router.student_of(request, student_id)
        row = grader.row(sub_id)
        if row is None or row["student_id"] != sid:
            raise HTTPException(404, "unknown submission")
        lab = store.one("SELECT * FROM sbx_labs WHERE id = ?", (row["lab_id"],))
        return submission_json(row, True, lab=lab) | {"queue_ahead": queue_ahead(row)}

    def queue_ahead(row) -> int:
        if row["status"] != "queued":
            return 0
        return store.one("SELECT COUNT(*) n FROM sbx_submissions WHERE status IN ('queued', 'grading') AND submitted_at < ?",
                         (row["submitted_at"],))["n"]

    @r.get("/labs/{lab_id}/submissions")
    def lab_submissions(lab_id: str, request: Request) -> dict:
        lab = sandbox_router.lab_access(request, lab_id, write=False)
        assignments = [{"id": a["id"], "title": a["title"]} for a in store.assignments(lab_id)]
        got = latest(lab_id)
        sections = json.loads(lab["sections_json"])
        roster = [s for s in store.roster(lab["subject_id"]) if not sections or s["section"] in sections]
        ids = {s["id"] for s in roster} | {k[0] for k in got}  # a student taken off the roster keeps their row
        section = {s["id"]: s["section"] for s in roster}
        students = []
        for sid in sorted(ids):
            cells = {}
            for a in assignments:
                hit = got.get((sid, a["id"]))
                cells[a["id"]] = None if hit is None else submission_json(hit[0], False, hit[1], lab) | {
                    "session_id": session_for(sid, lab_id, a["id"])}
            students.append({"student_id": sid, "section": section.get(sid, ""), "on_roster": sid in section,
                             "assignments": cells})
        done = [c for s in students for c in s["assignments"].values() if c]
        return {"lab": {"id": lab["id"], "title": lab["title"], "due_at": lab["due_at"], "status": lab["status"]},
                "assignments": assignments, "students": students,
                "grader": {"enabled": grader.enabled, "queued": grader.queued()},
                "counts": {"students": len(students), "submitted": len(done),
                           "graded": sum(1 for c in done if c["status"] == "graded"),
                           "passed_all": sum(1 for c in done if c["status"] == "graded" and c["passed"] == c["total"])}}

    def session_for(student_id: str, lab_id: str, assignment_id: str) -> str | None:
        with db.connect() as conn:
            row = conn.execute("""SELECT id FROM sessions WHERE student_id = ? AND lab_id = ? AND question_id = ?
                                  ORDER BY started_at DESC LIMIT 1""", (student_id, lab_id, assignment_id)).fetchone()
        return row["id"] if row else None

    def teacher_row(request: Request, sub_id: str, write: bool):
        row = grader.row(sub_id)
        if row is None:
            raise HTTPException(404, "unknown submission")
        sandbox_router.lab_access(request, row["lab_id"], write=write)
        return row

    @r.get("/submissions/{sub_id}")
    def get_submission(sub_id: str, request: Request) -> dict:
        row = teacher_row(request, sub_id, write=False)
        with db.connect() as conn:
            n = conn.execute("SELECT COUNT(*) n FROM sbx_submissions WHERE lab_id = ? AND student_id = ? AND assignment_id = ?",
                             (row["lab_id"], row["student_id"], row["assignment_id"])).fetchone()["n"]
        lab = store.one("SELECT * FROM sbx_labs WHERE id = ?", (row["lab_id"],))
        return submission_json(row, False, n, lab) | {"session_id": session_for(row["student_id"], row["lab_id"], row["assignment_id"])}

    @r.post("/submissions/{sub_id}/regrade")
    def regrade_one(sub_id: str, request: Request) -> dict:
        teacher_row(request, sub_id, write=True)
        if not grader.enabled:
            raise HTTPException(503, NOT_SET_UP)
        grader.regrade([sub_id])
        return get_submission(sub_id, request)

    @r.post("/labs/{lab_id}/regrade")
    def regrade_lab(lab_id: str, request: Request) -> dict:
        sandbox_router.lab_access(request, lab_id, write=True)
        if not grader.enabled:
            raise HTTPException(503, NOT_SET_UP)
        return {"queued": grader.regrade(grader.latest_ids(lab_id))}

    sandbox_router.lab_progress = progress
    hooks = getattr(sandbox_router, "on_tests_changed", None)
    if isinstance(hooks, list):
        hooks.append(grader.regrade_assignment)
    r.grader = grader
    r.student_router = open_r
    return r

"""Workspace snapshots and setup recipes for Sandbox Labs (desktop app).

A student's assignment folder lives in a container on their own machine; so
the work can follow them to another machine, the desktop app uploads the
folder as a gzipped tarball (build outputs left out, at most 5 MB) about 10 s
after the last change, on every Run and on Submit, and restores the latest
one when the lab opens elsewhere. Packages installed in the instance are too
big to move, so the app also keeps the student's *setup recipe* (the package
commands that succeeded) per subject and replays it on a new machine.
Client: desktop/sandbox/src/workspace.ts. Plan: thesis/plans/2026-10-30-desktop-client.md 3.2/3.5.

Endpoints (student_id as a query parameter, like the other student routes;
in Google mode a student can only act as themselves):

    GET  /api/workspaces/{lab_id}/{assignment_id}/meta   latest snapshot's hash, size, time
    GET  /api/workspaces/{lab_id}/{assignment_id}        latest snapshot (application/gzip)
    PUT  /api/workspaces/{lab_id}/{assignment_id}        upload; headers X-Workspace-Sha256 (content
                                                         hash from the client), X-Workspace-Reason
                                                         (change | run | submit), X-Workspace-Parent
    GET  /api/workspaces/recipes/{subject_id}            the setup recipe {version, steps}
    PUT  /api/workspaces/recipes/{subject_id}

Ids are the catalogue's opaque strings (sandbox lab, assignment, subject). An
upload goes through the catalogue's `gate` (sandbox.py upload_gate): the lab
must be open for the student (published or closed, on the roster and section,
past opens_at) and hold the assignment, and a Submit must come before the due
time; backups after it are still kept so no work is lost. A kept Submit goes to
`on_submit` (submissions.py), which queues it for grading; the reply carries
that submission.
Every upload is checked before it is kept: a real gzip tar, relative paths
only, no links out of the folder or device files, bounded size and count. The
last KEEP snapshots of an assignment are kept, plus every Submit.
"""

from __future__ import annotations

import gzip
import io
import json
import posixpath
import re
import tarfile
import time
from typing import Callable

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .db import Database

MAX_SNAPSHOT = 5 * 1024 * 1024
MAX_UNPACKED = 64 * 1024 * 1024
MAX_MEMBERS = 5000
KEEP = 5
ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
REASONS = ("change", "run", "submit")

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    lab_id TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    sha256 TEXT NOT NULL,          -- client's content hash of the folder (path + file hashes)
    parent TEXT,                   -- hash this upload was based on, if the client knew one
    reason TEXT NOT NULL,
    size INTEGER NOT NULL,
    files INTEGER NOT NULL,
    created_at REAL NOT NULL,
    data BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS workspace_by_key ON workspace_snapshots(student_id, lab_id, assignment_id, id);
CREATE TABLE IF NOT EXISTS workspace_recipes (
    student_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    recipe_json TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (student_id, subject_id)
);
"""


class RecipeStep(BaseModel):
    model_config = ConfigDict(extra="ignore")
    manager: str = Field(max_length=16)
    action: str = Field(pattern="^(install|remove)$")
    packages: list[str] = Field(default_factory=list, max_length=200)
    command: str = Field(max_length=4096)
    cwd: str = Field(default="/home/student", max_length=1024)
    at: float = 0


class Recipe(BaseModel):
    version: int = 1
    steps: list[RecipeStep] = Field(default_factory=list, max_length=500)


def check_tarball(data: bytes) -> int:
    """Number of files in a valid snapshot; raises HTTPException(400) otherwise."""
    if len(data) > MAX_SNAPSHOT:
        raise HTTPException(413, f"snapshot is larger than {MAX_SNAPSHOT // (1024 * 1024)} MB")
    try:
        raw = gzip.decompress(data)
    except (OSError, EOFError) as e:
        raise HTTPException(400, "snapshot is not gzip data") from e
    if len(raw) > MAX_UNPACKED + 1024 * 1024:
        raise HTTPException(413, "snapshot unpacks to too much data")
    files = 0
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
            members = tar.getmembers()
    except tarfile.TarError as e:
        raise HTTPException(400, "snapshot is not a tar archive") from e
    if len(members) > MAX_MEMBERS:
        raise HTTPException(413, f"snapshot has more than {MAX_MEMBERS} entries")
    for m in members:
        name = m.name[2:] if m.name.startswith("./") else m.name
        parts = [p for p in name.split("/") if p not in ("", ".")]
        if name.startswith("/") or ".." in parts:
            raise HTTPException(400, f"snapshot path escapes the folder: {m.name}")
        if m.isdev() or m.isfifo():
            raise HTTPException(400, f"snapshot holds a device file: {m.name}")
        if m.issym() or m.islnk():
            target = m.linkname
            where = posixpath.normpath(posixpath.join(posixpath.dirname("/".join(parts)), target))
            if target.startswith("/") or where == ".." or where.startswith("../"):
                raise HTTPException(400, f"snapshot link points out of the folder: {m.name}")
        if m.isfile():
            files += 1
            total += m.size
    if total > MAX_UNPACKED:
        raise HTTPException(413, "snapshot unpacks to too much data")
    return files


def router(db: Database, auth, student_id_check: Callable[[str], str],
           gate: Callable[[str, str, str, str], object] | None = None,
           on_submit: Callable[[str, str, str, int, str], dict] | None = None) -> APIRouter:
    with db.connect() as conn:
        conn.executescript(SCHEMA)
    r = APIRouter(prefix="/api/workspaces")

    def who(request: Request, student_id: str) -> str:
        sid = student_id_check(student_id)
        auth.own_student(request, sid)
        return sid

    def ids(*vals: str) -> None:
        for v in vals:
            if not ID.match(v):
                raise HTTPException(400, "bad id")

    # recipes first, so "recipes" is never taken for a lab id
    @r.get("/recipes/{subject_id}")
    def get_recipe(subject_id: str, request: Request, student_id: str) -> dict:
        sid = who(request, student_id)
        ids(subject_id)
        with db.connect() as conn:
            row = conn.execute("SELECT recipe_json, updated_at FROM workspace_recipes WHERE student_id = ? AND subject_id = ?",
                               (sid, subject_id)).fetchone()
        if row is None:
            raise HTTPException(404, "no setup recipe yet")
        return json.loads(row["recipe_json"]) | {"updated_at": row["updated_at"]}

    @r.put("/recipes/{subject_id}")
    def put_recipe(subject_id: str, body: Recipe, request: Request, student_id: str) -> dict:
        sid = who(request, student_id)
        ids(subject_id)
        now = time.time()
        with db.connect() as conn:
            conn.execute("""INSERT INTO workspace_recipes (student_id, subject_id, recipe_json, updated_at) VALUES (?, ?, ?, ?)
                            ON CONFLICT(student_id, subject_id) DO UPDATE SET recipe_json = excluded.recipe_json,
                            updated_at = excluded.updated_at""", (sid, subject_id, body.model_dump_json(), now))
        return {"ok": True, "steps": len(body.steps), "updated_at": now}

    def latest(sid: str, lab_id: str, assignment_id: str, with_data: bool = False):
        cols = "sha256, parent, reason, size, files, created_at" + (", data" if with_data else "")
        with db.connect() as conn:
            return conn.execute(f"""SELECT {cols} FROM workspace_snapshots WHERE student_id = ? AND lab_id = ?
                                    AND assignment_id = ? ORDER BY id DESC LIMIT 1""", (sid, lab_id, assignment_id)).fetchone()

    @r.get("/{lab_id}/{assignment_id}/meta")
    def meta(lab_id: str, assignment_id: str, request: Request, student_id: str) -> dict:
        sid = who(request, student_id)
        ids(lab_id, assignment_id)
        row = latest(sid, lab_id, assignment_id)
        if row is None:
            raise HTTPException(404, "no snapshot yet")
        return dict(row)

    @r.get("/{lab_id}/{assignment_id}")
    def download(lab_id: str, assignment_id: str, request: Request, student_id: str) -> Response:
        sid = who(request, student_id)
        ids(lab_id, assignment_id)
        row = latest(sid, lab_id, assignment_id, with_data=True)
        if row is None:
            raise HTTPException(404, "no snapshot yet")
        return Response(bytes(row["data"]), media_type="application/gzip",
                        headers={"X-Workspace-Sha256": row["sha256"], "Cache-Control": "no-store"})

    @r.put("/{lab_id}/{assignment_id}")
    async def upload(lab_id: str, assignment_id: str, request: Request, student_id: str) -> dict:
        sid = who(request, student_id)
        ids(lab_id, assignment_id)
        sha = request.headers.get("x-workspace-sha256", "").lower()
        if not SHA.match(sha):
            raise HTTPException(400, "X-Workspace-Sha256 must be a sha256 hex digest")
        parent = request.headers.get("x-workspace-parent", "").lower() or None
        if parent is not None and not SHA.match(parent):
            raise HTTPException(400, "bad X-Workspace-Parent")
        reason = request.headers.get("x-workspace-reason", "change")
        if reason not in REASONS:
            raise HTTPException(400, f"X-Workspace-Reason must be one of {', '.join(REASONS)}")
        if gate is not None:
            gate(sid, lab_id, assignment_id, reason)
        body = bytearray()
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_SNAPSHOT:
                raise HTTPException(413, f"snapshot is larger than {MAX_SNAPSHOT // (1024 * 1024)} MB")
        data = bytes(body)
        files = check_tarball(data)
        now = time.time()
        db.get_or_create_student(sid)
        with db.connect() as conn:
            prev = conn.execute("""SELECT sha256 FROM workspace_snapshots WHERE student_id = ? AND lab_id = ? AND assignment_id = ?
                                   ORDER BY id DESC LIMIT 1""", (sid, lab_id, assignment_id)).fetchone()
            if prev is not None and prev["sha256"] == sha and reason != "submit":
                return {"sha256": sha, "size": len(data), "files": files, "created_at": now, "unchanged": True}
            snap_id = conn.execute("""INSERT INTO workspace_snapshots (student_id, lab_id, assignment_id, sha256, parent, reason,
                            size, files, created_at, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                   (sid, lab_id, assignment_id, sha, parent, reason, len(data), files, now, data)).lastrowid
            # keep the newest KEEP plus every submit
            conn.execute("""DELETE FROM workspace_snapshots WHERE student_id = ? AND lab_id = ? AND assignment_id = ?
                            AND reason != 'submit' AND id NOT IN (SELECT id FROM workspace_snapshots WHERE student_id = ?
                            AND lab_id = ? AND assignment_id = ? ORDER BY id DESC LIMIT ?)""",
                         (sid, lab_id, assignment_id, sid, lab_id, assignment_id, KEEP))
        out = {"sha256": sha, "size": len(data), "files": files, "created_at": now,
               "conflict": prev is not None and parent is not None and prev["sha256"] != parent}
        if reason == "submit" and on_submit is not None:
            out["submission"] = on_submit(sid, lab_id, assignment_id, snap_id, sha)
        return out

    return r

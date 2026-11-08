"""Sandbox Labs workspaces: snapshots go up and come back, bad archives are
refused, only the newest few (plus every Submit) are kept, recipes round-trip."""

import gzip
import hashlib
import io
import tarfile

import pytest
from fastapi.testclient import TestClient

from studentide import workspaces
from studentide.app import create_app

Q = {"student_id": "S1"}


def open_lab(path, students=("S1", "S2"), status="published", due_at=None) -> None:
    """Lab slab_1 with assignment asg_1, open to `students` (uploads are checked against the catalogue)."""
    import sqlite3
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO sbx_subjects (id, title, created_at, updated_at) VALUES ('sub_1', 'OS', 0, 0)")
        conn.executemany("INSERT INTO sbx_subject_students (subject_id, student_id) VALUES ('sub_1', ?)",
                         [(s,) for s in students])
        conn.execute("INSERT INTO sbx_labs (id, subject_id, title, status, due_at, created_at, updated_at) "
                     "VALUES ('slab_1', 'sub_1', 'Shell', ?, ?, 0, 0)", (status, due_at))
        conn.execute("INSERT INTO sbx_assignments (id, lab_id, position, title, created_at, updated_at) "
                     "VALUES ('asg_1', 'slab_1', 0, 'One', 0, 0)")


@pytest.fixture
def client(tmp_path):
    c = TestClient(create_app(tmp_path / "w.sqlite3", admin_token="t", serve_frontend=False))
    open_lab(tmp_path / "w.sqlite3")
    return c


def tgz(files: dict[str, bytes], links: dict[str, str] | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for name, target in (links or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)
    return gzip.compress(buf.getvalue())


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def put(c, data, h, reason="change", parent=None, lab="slab_1", asg="asg_1"):
    headers = {"X-Workspace-Sha256": h, "X-Workspace-Reason": reason, "Content-Type": "application/gzip"}
    if parent:
        headers["X-Workspace-Parent"] = parent
    return c.put(f"/api/workspaces/{lab}/{asg}", params=Q, content=data, headers=headers)


def test_upload_then_restore(client):
    assert client.get("/api/workspaces/slab_1/asg_1/meta", params=Q).status_code == 404
    data = tgz({"./main.c": b"int main(){}\n", "./lib/util.h": b"#pragma once\n"})
    r = put(client, data, sha("v1"))
    assert r.status_code == 200, r.text
    assert r.json()["files"] == 2
    meta = client.get("/api/workspaces/slab_1/asg_1/meta", params=Q).json()
    assert meta["sha256"] == sha("v1") and meta["size"] == len(data)
    got = client.get("/api/workspaces/slab_1/asg_1", params=Q)
    assert got.content == data and got.headers["x-workspace-sha256"] == sha("v1")
    # another student sees nothing
    assert client.get("/api/workspaces/slab_1/asg_1/meta", params={"student_id": "S2"}).status_code == 404


def test_same_content_is_not_stored_twice_and_conflict_is_reported(client):
    data = tgz({"a.txt": b"1"})
    put(client, data, sha("v1"))
    assert put(client, data, sha("v1")).json()["unchanged"] is True
    # an upload based on an older version than the server's latest is a conflict (kept, but reported)
    put(client, tgz({"a.txt": b"2"}), sha("v2"), parent=sha("v1"))
    r = put(client, tgz({"a.txt": b"3"}), sha("v3"), parent=sha("v1"))
    assert r.json()["conflict"] is True


@pytest.mark.parametrize("bad", [
    b"not gzip",
    gzip.compress(b"not a tar"),
    tgz({"../escape.txt": b"x"}),
    tgz({"/etc/passwd": b"x"}),
    tgz({"ok.txt": b"x"}, links={"evil": "../../etc/passwd"}),
    tgz({"ok.txt": b"x"}, links={"abs": "/etc/passwd"}),
])
def test_bad_archives_are_refused(client, bad):
    assert put(client, bad, sha("x")).status_code == 400


def test_links_inside_the_folder_are_fine(client):
    assert put(client, tgz({"src/a.c": b"x"}, links={"src/b.c": "a.c", "top": "src/a.c"}), sha("l")).status_code == 200


def test_size_and_header_checks(client, monkeypatch):
    monkeypatch.setattr(workspaces, "MAX_SNAPSHOT", 100)
    assert put(client, b"x" * 200, sha("big")).status_code == 413
    assert put(client, tgz({"a": b"1"}), "nothex").status_code == 400
    assert put(client, tgz({"a": b"1"}), sha("r"), reason="whatever").status_code == 400
    assert client.get("/api/workspaces/bad id!/x/meta", params=Q).status_code in (400, 404)


def test_keeps_newest_and_every_submit(client, tmp_path):
    put(client, tgz({"a": b"s"}), sha("submitted"), reason="submit")
    for i in range(workspaces.KEEP + 3):
        put(client, tgz({"a": str(i).encode()}), sha(f"v{i}"))
    with _db(tmp_path) as conn:
        rows = conn.execute("SELECT reason FROM workspace_snapshots").fetchall()
    assert len(rows) == workspaces.KEEP + 1
    assert sum(r["reason"] == "submit" for r in rows) == 1


def _db(tmp_path):
    from studentide.db import Database
    return Database(tmp_path / "w.sqlite3").connect()


def test_recipe_round_trip(client):
    assert client.get("/api/workspaces/recipes/subj_1", params=Q).status_code == 404
    recipe = {"version": 1, "steps": [{"manager": "apt", "action": "install", "packages": ["valgrind"],
                                       "command": "sudo apt install -y valgrind", "cwd": "/home/student", "at": 1}]}
    assert client.put("/api/workspaces/recipes/subj_1", params=Q, json=recipe).json()["steps"] == 1
    got = client.get("/api/workspaces/recipes/subj_1", params=Q).json()
    assert got["steps"][0]["packages"] == ["valgrind"]
    bad = {"version": 1, "steps": [{"manager": "apt", "action": "explode", "command": "x"}]}
    assert client.put("/api/workspaces/recipes/subj_1", params=Q, json=bad).status_code == 422


# ---- schema v2 (desktop sandbox events) ----

def _session(c):
    c.post("/api/consent", json={"student_id": "S1"})
    r = c.get("/api/tasks")
    return c.post("/api/sessions", json={"student_id": "S1", "task_id": r.json()[0]["id"], "client_meta": {}}).json()["session_id"]


def test_v1_and_v2_batches_are_accepted(client):
    sid = _session(client)
    v1 = {"schema_version": 1, "events": [{"seq": 0, "t": 0, "type": "snapshot", "data": {"reason": "start", "text": ""}}]}
    assert client.post(f"/api/sessions/{sid}/events", json=v1).status_code == 200
    v2 = {"schema_version": 2, "events": [
        {"seq": 1, "t": 5, "type": "key", "data": {"action": "down", "code": "KeyL", "cls": "letter", "surface": "terminal"}},
        {"seq": 2, "t": 6, "type": "term_cmd", "data": {"term_id": "t1", "phase": "start", "command": "ls", "cwd": "/home/student"}},
        {"seq": 3, "t": 9, "type": "term_cmd", "data": {"term_id": "t1", "phase": "end", "command": "ls", "cwd": "/home/student",
                                                        "exit_code": 0, "duration_ms": 3}},
        {"seq": 4, "t": 9, "type": "term_output", "data": {"term_id": "t1", "bytes": 8, "tail": "main.c\n"}},
        {"seq": 5, "t": 10, "type": "term_paste", "data": {"term_id": "t1", "length": 2, "lines": 1, "text": "ls", "sha256": "0" * 64}},
        {"seq": 6, "t": 11, "type": "pkg_install", "data": {"manager": "apt", "action": "install", "packages": ["gdb"], "command": "sudo apt install gdb"}},
        {"seq": 7, "t": 12, "type": "net_conn", "data": {"host": "pypi.org", "port": 443, "allowed": True}},
        {"seq": 8, "t": 13, "type": "run", "data": {"run_id": "t-x", "code_sha256": "a", "source": "terminal", "command": "gcc main.c"}},
        {"seq": 9, "t": 14, "type": "edit", "data": {"origin": "input.type", "changes": [[0, 0, "x"]], "len_before": 0, "len_after": 1, "path": "util.c"}},
    ]}
    r = client.post(f"/api/sessions/{sid}/events", json=v2)
    assert r.status_code == 200, r.text
    assert r.json()["rejected"] == [] and r.json()["accepted"] == 9
    assert client.post(f"/api/sessions/{sid}/events", json={"schema_version": 3, "events": []}).status_code == 400


def test_detector_ignores_terminal_keys_and_follows_files():
    from studentide.detector.features import streams
    from studentide.replay import final_text
    ev = [
        {"seq": 0, "t": 0, "type": "snapshot", "data": {"reason": "start", "text": "", "path": "main.c"}},
        {"seq": 1, "t": 10, "type": "key", "data": {"action": "down", "code": "KeyA", "cls": "letter"}},
        {"seq": 2, "t": 20, "type": "key", "data": {"action": "down", "code": "KeyB", "cls": "letter", "surface": "terminal"}},
        {"seq": 3, "t": 30, "type": "key", "data": {"action": "down", "code": "KeyC", "cls": "letter", "surface": "terminal-editor", "path": "a.c"}},
        {"seq": 4, "t": 40, "type": "edit", "data": {"origin": "input.type", "changes": [[0, 0, "ab"]], "len_before": 0, "len_after": 2, "path": "main.c"}},
        {"seq": 5, "t": 50, "type": "edit", "data": {"origin": "input.type", "changes": [[0, 0, "xyz"]], "len_before": 0, "len_after": 3, "path": "util.c"}},
        {"seq": 6, "t": 60, "type": "edit", "data": {"origin": "input.type", "changes": [[2, 2, "c"]], "len_before": 2, "len_after": 3, "path": "main.c"}},
        {"seq": 7, "t": 70, "type": "run", "data": {"run_id": "t-1", "code_sha256": "x", "source": "terminal", "command": "make"}},
    ]
    s = streams(ev)
    assert s.k_code == ["KeyA"]
    assert len(s.run_t) == 1
    assert final_text(ev) == "abc"  # the main file, not util.c


def test_uploads_are_checked_against_the_lab(tmp_path):
    import time
    path = tmp_path / "g.sqlite3"
    c = TestClient(create_app(path, admin_token="t", serve_frontend=False))
    open_lab(path, students=("S1",), due_at=time.time() - 3600)
    data = tgz({"./main.c": b"x"})
    # not on the roster, unknown lab, unknown assignment
    assert c.put("/api/workspaces/slab_1/asg_1", params={"student_id": "S9"}, content=data,
                 headers={"X-Workspace-Sha256": sha("a")}).status_code == 403
    assert put(c, data, sha("a"), lab="slab_2").status_code == 403
    assert put(c, data, sha("a"), asg="asg_9").status_code == 404
    # past the due time: backups are kept, Submit is refused with a reason
    assert put(c, data, sha("a")).status_code == 200
    late = put(c, data, sha("a"), reason="submit")
    assert late.status_code == 409 and "can no longer be submitted" in late.json()["detail"]
    # a draft lab takes nothing
    import sqlite3
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE sbx_labs SET status = 'draft', due_at = NULL")
    assert put(c, data, sha("b")).status_code == 403

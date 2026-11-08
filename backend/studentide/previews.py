"""Cloud preview instances: a teacher's "Try as a student" for a sandbox lab.

Students always run Sandbox Labs on their own machine. Teachers without the
desktop app can still try a lab exactly as a student would, in a small,
short-lived instance on the college VM. Previews are capped so they can't grow
VM cost: a few seats in total, one per teacher, an idle stop and a hard time
limit, small CPU/memory limits, and never the open internet (registries only
through the filtering proxy when one is configured, otherwise no network).

The containers are started by a driver:

    DockerDriver   the docker CLI on this machine (dev: STUDENTIDE_PREVIEW_DOCKER=1;
                   in deployment it runs inside preview_service.py, the only
                   container that holds the Docker socket)
    RemoteDriver   HTTP + WebSocket to preview_service (STUDENTIDE_PREVIEW_URL)
    FakeDriver     tests

Routes (teacher sign-in, like /api/teach):

    GET  /api/sandbox/previews                  mine (admins: all) + seats
    POST /api/sandbox/previews                  {lab_id}  start one (stops my older one)
    GET  /api/sandbox/previews/{id}             status, the lab definition, files
    POST /api/sandbox/previews/{id}/stop
    GET  /api/sandbox/previews/{id}/files       ?assignment_id=  [{path, size}] / ?path= one file
    PUT  /api/sandbox/previews/{id}/files       {path, content}
    POST /api/sandbox/previews/{id}/run         {assignment_id, stdin}
    POST /api/sandbox/previews/{id}/check       {assignment_id}  every test, hidden ones too
    POST /api/sandbox/previews/{id}/verify      reference solution must pass, starter should fail
    WS   /api/sandbox/previews/{id}/terminal?assignment_id=   shell as `student` in the workdir
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import posixpath
import shlex
import subprocess
import tarfile
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from . import grading
from .db import Database
from .sandbox import Store, definition, dockerfile

SCHEMA = """
CREATE TABLE IF NOT EXISTS sbx_previews (
    id            TEXT PRIMARY KEY,
    teacher_email TEXT NOT NULL,             -- '' = admin token / dev mode
    lab_id        TEXT NOT NULL,
    lab_version   INTEGER NOT NULL,
    container     TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('starting', 'running', 'stopped', 'failed')),
    error         TEXT NOT NULL DEFAULT '',
    started_at    REAL NOT NULL,
    last_active   REAL NOT NULL,
    stopped_at    REAL,
    stop_reason   TEXT                       -- 'teacher', 'idle', 'time limit', 'replaced', 'server restart'
);
CREATE INDEX IF NOT EXISTS sbx_previews_status ON sbx_previews(status, started_at);
"""

# Capability set shared with the desktop runtime (desktop/sandbox): enough for
# sudo, apt, gdb/strace and services, never --privileged.
CAPS = "CHOWN,DAC_OVERRIDE,FOWNER,FSETID,KILL,SETGID,SETUID,SETPCAP,NET_BIND_SERVICE,SYS_CHROOT,AUDIT_WRITE,SYS_PTRACE"
OUTPUT_LIMIT = 64_000


@dataclass(frozen=True)
class Limits:
    seats: int = 3                # previews running at once, all teachers together; 0 = previews off
    idle_s: float = 15 * 60       # stopped after this long without a request or a keystroke
    max_s: float = 60 * 60        # stopped after this long whatever happens
    cpus: float = 1.0             # per preview, at most (a lab may ask for less)
    memory_mb: int = 1024
    pids: int = 256

    @classmethod
    def from_env(cls) -> "Limits":
        env = os.environ.get
        return cls(seats=int(env("STUDENTIDE_PREVIEW_SEATS") or 3),
                   idle_s=float(env("STUDENTIDE_PREVIEW_IDLE_MIN") or 15) * 60,
                   max_s=float(env("STUDENTIDE_PREVIEW_MAX_MIN") or 60) * 60,
                   cpus=float(env("STUDENTIDE_PREVIEW_CPUS") or 1),
                   memory_mb=int(env("STUDENTIDE_PREVIEW_MEMORY_MB") or 1024))


class PreviewError(Exception):
    pass


class Driver(Protocol):
    def start(self, spec: dict) -> None: ...
    def put_files(self, container: str, files: list[dict]) -> None: ...
    def read_file(self, container: str, path: str) -> str: ...
    def list_files(self, container: str, folder: str) -> list[dict]: ...
    def exec(self, container: str, command: str, workdir: str, stdin: str = "", timeout_s: int = 10) -> dict: ...
    def stop(self, container: str) -> None: ...
    def stop_all(self) -> None: ...


def tar_of(files: list[dict]) -> bytes:
    """[{path (absolute), content, executable}] -> a tar owned by student (uid 1000),
    parent folders included, for `docker cp -a - container:/`."""
    buf, dirs = io.BytesIO(), set()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for f in files:
            rel = f["path"].lstrip("/")
            parts = rel.split("/")[:-1]
            for i in range(2, len(parts) + 1):  # /home/student/... : leave /home itself alone
                d = "/".join(parts[:i])
                if d not in dirs:
                    dirs.add(d)
                    info = tarfile.TarInfo(d)
                    info.type, info.mode, info.uid, info.gid, info.uname, info.gname = tarfile.DIRTYPE, 0o755, 1000, 1000, "student", "student"
                    info.mtime = time.time()
                    tar.addfile(info)
            data = f["content"].encode()
            info = tarfile.TarInfo(rel)
            info.size, info.mode = len(data), 0o755 if f.get("executable") else 0o644
            info.uid = info.gid = 1000
            info.uname = info.gname = "student"
            info.mtime = time.time()
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class DockerDriver:
    """Runs previews with the docker CLI. Network: "off" -> none; "registries" ->
    the internal network STUDENTIDE_PREVIEW_NETWORK with STUDENTIDE_PREVIEW_PROXY as
    HTTP(S)_PROXY (the registry allowlist proxy), or none when those aren't set."""

    LABEL = "studentide.preview=1"

    def __init__(self, docker: str = "docker"):
        self.docker = docker
        self.network = os.environ.get("STUDENTIDE_PREVIEW_NETWORK") or ""
        self.proxy = os.environ.get("STUDENTIDE_PREVIEW_PROXY") or ""
        self.build_local = os.environ.get("STUDENTIDE_PREVIEW_BUILD_LOCAL") == "1"

    def _run(self, args: list[str], input: bytes | None = None, timeout: float = 60) -> subprocess.CompletedProcess:
        try:
            return subprocess.run([self.docker, *args], input=input, capture_output=True, timeout=timeout)
        except FileNotFoundError:
            raise PreviewError("docker is not installed on the preview host")
        except subprocess.TimeoutExpired:
            raise PreviewError(f"docker {args[0]} took too long")

    def _ok(self, p: subprocess.CompletedProcess, what: str) -> str:
        if p.returncode != 0:
            raise PreviewError(f"{what}: {p.stderr.decode(errors='replace').strip()[-500:]}")
        return p.stdout.decode(errors="replace")

    def ensure_image(self, spec: dict) -> str:
        image, digest = spec["image"], spec.get("digest")
        ref = f"{image.split(':')[0]}@{digest}" if digest else image
        if self._run(["image", "inspect", ref], timeout=30).returncode == 0:
            return ref
        if digest or not self.build_local:
            p = self._run(["pull", "-q", ref], timeout=900)
            if p.returncode == 0:
                return ref
            if not self.build_local:
                raise PreviewError("the environment image is not built yet" if not digest else
                                   f"could not pull the image: {p.stderr.decode(errors='replace').strip()[-300:]}")
        self._ok(self._run(["build", "-q", "-t", image, "-"], input=spec["dockerfile"].encode(), timeout=1800),
                 "building the environment failed")
        return image

    def start(self, spec: dict) -> None:
        ref = self.ensure_image(spec)
        net = ["--network", "none"]
        env = []
        if spec["network"] == "registries" and self.network and self.proxy:
            net = ["--network", self.network]
            env = ["-e", f"HTTP_PROXY={self.proxy}", "-e", f"HTTPS_PROXY={self.proxy}",
                   "-e", f"http_proxy={self.proxy}", "-e", f"https_proxy={self.proxy}"]
        r = spec["resources"]
        args = ["run", "-d", "--init", "--name", spec["container"], "--hostname", spec["hostname"],
                "--user", "student", "-w", "/home/student",
                "--cpus", str(r["cpus"]), "--memory", f"{r['memory_mb']}m", "--memory-swap", f"{r['memory_mb']}m",
                "--pids-limit", str(r["pids"]), "--cap-drop", "ALL", *(a for c in CAPS.split(",") for a in ("--cap-add", c)),
                "--label", self.LABEL, "--label", f"studentide.lab={spec['lab_id']}", *net, *env,
                ref, "sleep", "infinity"]
        self._ok(self._run(args, timeout=120), "starting the preview failed")

    def put_files(self, container: str, files: list[dict]) -> None:
        if files:
            self._ok(self._run(["cp", "-a", "-", f"{container}:/"], input=tar_of(files)), "copying files failed")

    def read_file(self, container: str, path: str) -> str:
        p = self._run(["exec", "-u", "student", container, "head", "-c", "2000000", path], timeout=20)
        if p.returncode != 0:
            raise PreviewError("no such file")
        return p.stdout.decode(errors="replace")

    def list_files(self, container: str, folder: str) -> list[dict]:
        p = self._run(["exec", "-u", "student", container, "find", folder, "-maxdepth", "5", "-type", "f",
                       "-not", "-path", "*/.git/*", "-printf", "%P\\t%s\\n"], timeout=20)
        if p.returncode != 0:
            return []
        out = []
        for line in p.stdout.decode(errors="replace").splitlines()[:500]:
            path, _, size = line.partition("\t")
            out.append({"path": path, "size": int(size or 0)})
        return sorted(out, key=lambda f: f["path"])

    def exec(self, container: str, command: str, workdir: str, stdin: str = "", timeout_s: int = 10) -> dict:
        t0 = time.monotonic()
        p = self._run(["exec", "-i", "-u", "student", "-w", workdir, container,
                       "timeout", "-k", "2", str(timeout_s), "bash", "-lc", command],
                      input=stdin.encode(), timeout=timeout_s + 15)
        code = p.returncode
        return {"stdout": p.stdout.decode(errors="replace")[:OUTPUT_LIMIT],
                "stderr": p.stderr.decode(errors="replace")[:OUTPUT_LIMIT],
                "exit_code": code, "timed_out": code == 124, "duration_ms": round((time.monotonic() - t0) * 1000)}

    def stop(self, container: str) -> None:
        self._run(["rm", "-f", container], timeout=60)

    def stop_all(self) -> None:
        p = self._run(["ps", "-aq", "--filter", f"label={self.LABEL}"], timeout=30)
        ids = p.stdout.decode().split()
        if ids:
            self._run(["rm", "-f", *ids], timeout=120)

    def terminal_argv(self, container: str, workdir: str) -> list[str]:
        return [self.docker, "exec", "-it", "-u", "student", "-w", workdir, "-e", "TERM=xterm-256color",
                container, "bash", "-l"]


class RemoteDriver:
    """preview_service.py over HTTP; the shared STUDENTIDE_PREVIEW_TOKEN guards it."""

    def __init__(self, url: str, token: str):
        import requests
        self.url, self.http = url.rstrip("/"), requests.Session()
        self.http.headers["x-preview-token"] = token
        self.token = token

    def _call(self, path: str, body: dict, timeout: float = 60) -> dict:
        try:
            r = self.http.post(self.url + path, json=body, timeout=timeout)
        except Exception as e:
            raise PreviewError(f"the preview service is not reachable ({type(e).__name__})")
        if r.status_code != 200:
            raise PreviewError(r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith(
                "application/json") else r.text[:300])
        return r.json()

    def start(self, spec: dict) -> None:
        self._call("/start", spec, timeout=2000)

    def put_files(self, container: str, files: list[dict]) -> None:
        self._call("/put_files", {"container": container, "files": files})

    def read_file(self, container: str, path: str) -> str:
        return self._call("/read_file", {"container": container, "path": path})["content"]

    def list_files(self, container: str, folder: str) -> list[dict]:
        return self._call("/list_files", {"container": container, "folder": folder})["files"]

    def exec(self, container: str, command: str, workdir: str, stdin: str = "", timeout_s: int = 10) -> dict:
        return self._call("/exec", {"container": container, "command": command, "workdir": workdir,
                                    "stdin": stdin, "timeout_s": timeout_s}, timeout=timeout_s + 30)

    def stop(self, container: str) -> None:
        self._call("/stop", {"container": container})

    def stop_all(self) -> None:
        self._call("/stop_all", {})

    def terminal_url(self, container: str, workdir: str) -> str:
        from urllib.parse import urlencode
        base = self.url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{base}/terminal?{urlencode({'container': container, 'workdir': workdir})}"


class FakeDriver:
    """In-memory stand-in for tests: files in a dict, commands answered by `handler`."""

    def __init__(self, handler: Callable[[dict, str, str, str], dict] | None = None):
        self.containers: dict[str, dict] = {}
        self.handler = handler or (lambda files, cmd, wd, stdin: {"stdout": stdin, "stderr": "", "exit_code": 0})
        self.fail_start = ""

    def start(self, spec: dict) -> None:
        if self.fail_start:
            raise PreviewError(self.fail_start)
        self.containers[spec["container"]] = {"spec": spec, "files": {}}

    def _c(self, container: str) -> dict:
        if container not in self.containers:
            raise PreviewError("no such container")
        return self.containers[container]

    def put_files(self, container: str, files: list[dict]) -> None:
        for f in files:
            self._c(container)["files"][f["path"]] = f["content"]

    def read_file(self, container: str, path: str) -> str:
        files = self._c(container)["files"]
        if path not in files:
            raise PreviewError("no such file")
        return files[path]

    def list_files(self, container: str, folder: str) -> list[dict]:
        pre = folder.rstrip("/") + "/"
        return [{"path": p[len(pre):], "size": len(c)} for p, c in sorted(self._c(container)["files"].items())
                if p.startswith(pre)]

    def exec(self, container: str, command: str, workdir: str, stdin: str = "", timeout_s: int = 10) -> dict:
        out = self.handler(self._c(container)["files"], command, workdir, stdin)
        return {"stdout": "", "stderr": "", "exit_code": 0, "timed_out": False, "duration_ms": 1} | out

    def stop(self, container: str) -> None:
        self.containers.pop(container, None)

    def stop_all(self) -> None:
        self.containers.clear()


def driver_from_env() -> Driver | None:
    if os.environ.get("STUDENTIDE_PREVIEW_URL"):
        return RemoteDriver(os.environ["STUDENTIDE_PREVIEW_URL"], os.environ.get("STUDENTIDE_PREVIEW_TOKEN", ""))
    if os.environ.get("STUDENTIDE_PREVIEW_DOCKER") == "1":
        return DockerDriver()
    return None


# -- grading inside an instance


def run_tests(driver: Driver, container: str, workdir: str, run_cmd: str, tests: dict) -> dict:
    """Every test of an assignment (hidden ones too: only teachers call this)."""
    timeout = int(tests.get("timeout_s") or 10)
    if tests.get("kind") == "command":
        r = driver.exec(container, tests["command"], workdir, "", timeout)
        ok = r["exit_code"] == 0
        return {"passed": int(ok), "total": 1, "results": [{"name": tests["command"], "passed": ok,
                                                            "stdout": r["stdout"][-4000:], "stderr": r["stderr"][-4000:],
                                                            "timed_out": r["timed_out"]}]}
    results = []
    for i, case in enumerate(tests.get("cases") or []):
        r = driver.exec(container, run_cmd, workdir, case["stdin"], timeout)
        ok = r["exit_code"] == 0 and not r["timed_out"] and grading.outputs_match(r["stdout"], case["expected"],
                                                                                   case.get("compare", "text"))
        results.append({"name": case.get("name") or f"Test {i + 1}", "hidden": case.get("hidden", False), "passed": ok,
                        "stdin": case["stdin"], "expected": case["expected"], "got": r["stdout"][-4000:],
                        "stderr": r["stderr"][-2000:], "exit_code": r["exit_code"], "timed_out": r["timed_out"]})
    return {"passed": sum(r["passed"] for r in results), "total": len(results), "results": results}


def starter_files(workdir: str, files: list[dict]) -> list[dict]:
    return [{"path": posixpath.join(workdir, f["path"]), "content": f["content"], "executable": f.get("executable", False)}
            for f in files]


# -- manager + routes


class StartIn(BaseModel):
    lab_id: str


class FileIn(BaseModel):
    path: str = Field(min_length=1, max_length=400)
    content: str = Field(max_length=2_000_000)


class RunIn(BaseModel):
    assignment_id: str
    stdin: str = Field(default="", max_length=100_000)
    command: str | None = Field(default=None, max_length=2000)  # default: the assignment's Run command


class AssignmentRef(BaseModel):
    assignment_id: str


class Previews:
    """Seats, idle stop and time limit for preview instances, kept in sbx_previews."""

    def __init__(self, db: Database, store: Store, driver: Driver | None, limits: Limits | None = None,
                 clock: Callable[[], float] = time.time):
        self.db, self.store, self.driver = db, store, driver
        self.limits = limits or Limits.from_env()
        self.clock = clock
        self.lock = threading.Lock()
        self.background = True  # start containers on a thread (pulls can take minutes); tests turn it off
        with db.connect() as conn:
            conn.executescript(SCHEMA)

    @property
    def enabled(self) -> bool:
        return self.driver is not None and self.limits.seats > 0

    def row(self, pid: str):
        return self.store.one("SELECT * FROM sbx_previews WHERE id = ?", (pid,))

    def active(self) -> list:
        return self.store.q("SELECT * FROM sbx_previews WHERE status IN ('starting', 'running') ORDER BY started_at")

    def stop(self, pid: str, reason: str) -> None:
        row = self.row(pid)
        if row is None or row["status"] in ("stopped", "failed"):
            return
        self.store.x("UPDATE sbx_previews SET status = 'stopped', stopped_at = ?, stop_reason = ? WHERE id = ?",
                     (self.clock(), reason, pid))
        try:
            self.driver.stop(row["container"])
        except PreviewError:
            pass

    def reap(self) -> None:
        """Stop previews that went idle or reached the time limit."""
        now = self.clock()
        for p in self.active():
            if now - p["started_at"] > self.limits.max_s:
                self.stop(p["id"], "time limit")
            elif now - p["last_active"] > self.limits.idle_s:
                self.stop(p["id"], "idle")

    def on_restart(self) -> None:
        """Containers don't survive a server restart in a known state: clear them."""
        for p in self.active():
            self.store.x("UPDATE sbx_previews SET status = 'stopped', stopped_at = ?, stop_reason = 'server restart' "
                         "WHERE id = ?", (self.clock(), p["id"]))
        try:
            self.driver.stop_all()
        except PreviewError:
            pass

    def touch(self, pid: str) -> None:
        self.store.x("UPDATE sbx_previews SET last_active = ? WHERE id = ?", (self.clock(), pid))

    def seats(self) -> dict:
        active = self.active()
        frees = min((min(p["last_active"] + self.limits.idle_s, p["started_at"] + self.limits.max_s) for p in active),
                    default=None)
        return {"total": self.limits.seats, "used": len(active), "free": max(0, self.limits.seats - len(active)),
                "next_free_at": frees if len(active) >= self.limits.seats else None,
                "idle_minutes": self.limits.idle_s / 60, "max_minutes": self.limits.max_s / 60}

    def spec(self, pid: str, lab, d: dict) -> dict:
        env = d["environment"]
        r = env["resources"]
        subj = self.store.one("SELECT code, title FROM sbx_subjects WHERE id = ?", (lab["subject_id"],))
        recipe_row = self.store.env_version(env["id"], env["version"])
        return {
            "container": f"sbxp-{pid}", "lab_id": lab["id"], "image": env["image"], "digest": env["digest"],
            "dockerfile": dockerfile(env["id"], env["version"], json.loads(recipe_row["recipe_json"])),
            "hostname": (subj["code"] or "preview").lower()[:30] or "preview",
            "network": "off" if d["network"] == "off" else "registries",  # previews never get the open internet
            "resources": {"cpus": min(r["cpus"], self.limits.cpus), "memory_mb": min(r["memory_mb"], self.limits.memory_mb),
                          "pids": min(r["pids"], self.limits.pids)},
        }

    def start(self, lab, email: str) -> str:
        if not self.enabled:
            raise HTTPException(503, "Try as a student is not set up on this server (see docs/sandbox-labs.md)")
        d = definition(self.store, lab, student=False)
        if d["environment"] is None:
            raise HTTPException(409, "give the subject an environment first")
        if not d["assignments"]:
            raise HTTPException(409, "add an assignment first")
        with self.lock:
            self.reap()
            for p in self.active():
                if p["teacher_email"] == email:
                    self.stop(p["id"], "replaced")
            seats = self.seats()
            if seats["free"] <= 0:
                wait = max(1, round((seats["next_free_at"] - self.clock()) / 60)) if seats["next_free_at"] else None
                raise HTTPException(409, f"All {seats['total']} preview seats are in use"
                                         + (f"; one frees up in about {wait} min." if wait else "."))
            pid = "prv_" + uuid.uuid4().hex[:10]
            now = self.clock()
            self.store.x("INSERT INTO sbx_previews VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (pid, email, lab["id"], lab["version"], f"sbxp-{pid}", "starting", "", now, now, None, None))
        spec = self.spec(pid, lab, d)
        files = [f for a in d["assignments"] for f in starter_files(a["workdir"], a["files"])]
        if self.background:
            threading.Thread(target=self._boot, args=(pid, spec, files), daemon=True).start()
        else:
            self._boot(pid, spec, files)
        return pid

    def _boot(self, pid: str, spec: dict, files: list[dict]) -> None:
        try:
            self.driver.start(spec)
            self.driver.put_files(spec["container"], files)
        except PreviewError as e:
            self.store.x("UPDATE sbx_previews SET status = 'failed', error = ?, stopped_at = ? WHERE id = ?",
                         (str(e)[:1000], self.clock(), pid))
            try:
                self.driver.stop(spec["container"])
            except PreviewError:
                pass
            return
        row = self.row(pid)
        if row and row["status"] == "starting":
            self.store.x("UPDATE sbx_previews SET status = 'running', last_active = ? WHERE id = ?", (self.clock(), pid))
        else:  # stopped while it was starting
            self.driver.stop(spec["container"])


def router(db: Database, require_teacher: Callable, auth, sandbox_router, driver: Driver | None = None,
           limits: Limits | None = None, clock: Callable[[], float] = time.time) -> APIRouter:
    store: Store = sandbox_router.store
    pv = Previews(db, store, driver, limits, clock)
    r = APIRouter(prefix="/api/sandbox/previews", dependencies=[Depends(require_teacher)])
    ws_r = APIRouter(prefix="/api/sandbox/previews")

    def who(request) -> str:
        return auth.teacher(request).email or ""

    def preview_json(p) -> dict:
        d = dict(p)
        d["ends_at"] = min(p["last_active"] + pv.limits.idle_s, p["started_at"] + pv.limits.max_s)
        lab = store.one("SELECT title, subject_id FROM sbx_labs WHERE id = ?", (p["lab_id"],))
        d["lab_title"] = lab["title"] if lab else ""
        return d

    def mine(pid: str, request) -> dict:
        p = pv.row(pid)
        t = auth.teacher(request)
        if p is None or (not t.admin and p["teacher_email"] != (t.email or "")):
            raise HTTPException(404, "unknown preview")
        return p

    def running(pid: str, request) -> dict:
        pv.reap()
        p = mine(pid, request)
        if p["status"] != "running":
            raise HTTPException(409, "this preview is not running" + (f" ({p['stop_reason']})" if p["stop_reason"] else ""))
        pv.touch(pid)
        return p

    def lab_def(p, assignment_id: str | None = None):
        lab = store.one("SELECT * FROM sbx_labs WHERE id = ?", (p["lab_id"],))
        if lab is None:
            raise HTTPException(404, "the lab was deleted")
        d = definition(store, lab, student=False)
        if assignment_id is None:
            return d, None
        a = next((a for a in d["assignments"] if a["id"] == assignment_id), None)
        if a is None:
            raise HTTPException(404, "unknown assignment")
        return d, a

    def in_workdir(a: dict, path: str) -> str:
        full = posixpath.normpath(posixpath.join(a["workdir"], path))
        if not (full + "/").startswith(a["workdir"] + "/"):
            raise HTTPException(400, "files live in the assignment's folder")
        return full

    def call(fn, *args, **kw):
        try:
            return fn(*args, **kw)
        except PreviewError as e:
            raise HTTPException(502, str(e))

    @r.get("")
    def list_previews(request: Request) -> dict:
        pv.reap()
        t = auth.teacher(request)
        rows = pv.active() if t.admin else [p for p in pv.active() if p["teacher_email"] == (t.email or "")]
        return {"enabled": pv.enabled, "seats": pv.seats(), "previews": [preview_json(p) for p in rows]}

    @r.post("")
    def start(body: StartIn, request: Request) -> dict:
        lab = sandbox_router.lab_access(request, body.lab_id, write=False)
        pid = pv.start(lab, who(request))
        return get(pid, request)

    @r.get("/{pid}")
    def get(pid: str, request: Request) -> dict:
        pv.reap()
        p = mine(pid, request)
        d = preview_json(p)
        d["lab"] = lab_def(p)[0] if store.one("SELECT 1 FROM sbx_labs WHERE id = ?", (p["lab_id"],)) else None
        d["seats"] = pv.seats()
        return d

    @r.post("/{pid}/stop")
    def stop(pid: str, request: Request) -> dict:
        mine(pid, request)
        pv.stop(pid, "teacher")
        return preview_json(pv.row(pid))

    @r.get("/{pid}/files")
    def files(pid: str, request: Request, assignment_id: str, path: str | None = None) -> dict:
        p = running(pid, request)
        _, a = lab_def(p, assignment_id)
        if path is not None:
            return {"path": path, "content": call(pv.driver.read_file, p["container"], in_workdir(a, path))}
        return {"files": call(pv.driver.list_files, p["container"], a["workdir"])}

    @r.put("/{pid}/files")
    def put_file(pid: str, body: FileIn, request: Request, assignment_id: str) -> dict:
        p = running(pid, request)
        _, a = lab_def(p, assignment_id)
        call(pv.driver.put_files, p["container"], [{"path": in_workdir(a, body.path), "content": body.content}])
        return {"saved": body.path}

    @r.post("/{pid}/run")
    def run(pid: str, body: RunIn, request: Request) -> dict:
        p = running(pid, request)
        _, a = lab_def(p, body.assignment_id)
        cmd = body.command if body.command is not None else a["run"]
        if not cmd.strip():
            raise HTTPException(400, "this assignment has no Run command")
        return call(pv.driver.exec, p["container"], cmd, a["workdir"], body.stdin, int(a["tests"]["timeout_s"]))

    @r.post("/{pid}/check")
    def check(pid: str, body: AssignmentRef, request: Request) -> dict:
        p = running(pid, request)
        _, a = lab_def(p, body.assignment_id)
        return call(run_tests, pv.driver, p["container"], a["workdir"], a["run"], a["tests"])

    @r.post("/{pid}/verify")
    def verify(pid: str, request: Request) -> dict:
        """The lab wizard's Check step: in a scratch folder per assignment, the
        reference solution (laid over the starter) must pass every test and the
        starter alone should fail at least one."""
        p = running(pid, request)
        d, _ = lab_def(p)
        out = []
        for a in d["assignments"]:
            item = {"assignment_id": a["id"], "title": a["title"], "problems": []}
            t = a["tests"]
            n = len(t.get("cases") or []) if t["kind"] == "io" else 1
            if n == 0:
                item["problems"].append("No tests yet, so nothing can be checked.")
                out.append(item)
                continue
            if t["kind"] == "io" and not [c for c in t["cases"] if c["hidden"]]:
                item["problems"].append("No hidden tests: students can see every expected output.")
            for which, files in (("starter", a["files"]), ("solution", None)):
                if which == "solution":
                    if not a.get("solution_files"):
                        item["problems"].append("No reference solution, so the tests can't be checked against one.")
                        continue
                    sol = {f["path"]: f for f in a["files"]} | {f["path"]: f for f in a["solution_files"]}
                    files = list(sol.values())
                scratch = f"/tmp/verify/{a['id']}/{which}"
                call(pv.driver.exec, p["container"], f"rm -rf {shlex.quote(scratch)} && mkdir -p {shlex.quote(scratch)}",
                     "/tmp", "", 10)
                call(pv.driver.put_files, p["container"], starter_files(scratch, files))
                res = call(run_tests, pv.driver, p["container"], scratch, a["run"], t)
                item[which] = {"passed": res["passed"], "total": res["total"],
                               "failed": [x for x in res["results"] if not x["passed"]][:5]}
            if "solution" in item and item["solution"]["passed"] < item["solution"]["total"]:
                f = item["solution"]["failed"][0]
                got = repr(f.get("got", "")[:60]) if "got" in f else "a non-zero exit"
                item["problems"].append(f"{f['name']} fails on your solution: expected {f.get('expected', '')[:60]!r}, got {got}.")
            if "starter" in item and item["starter"]["passed"] == item["starter"]["total"]:
                item["problems"].append("The starter files already pass every test.")
            out.append(item)
        return {"assignments": out, "ok": all(not a["problems"] or all(
            pr.startswith(("No hidden", "No reference")) for pr in a["problems"]) for a in out)}

    @ws_r.websocket("/{pid}/terminal")
    async def terminal(ws: WebSocket, pid: str, assignment_id: str) -> None:
        try:
            auth.require_teacher(ws)
            p = running(pid, ws)
            _, a = lab_def(p, assignment_id)
        except HTTPException as e:
            await ws.close(code=4403 if e.status_code in (401, 403) else 4404, reason=str(e.detail)[:120])
            return
        await ws.accept()
        if isinstance(pv.driver, RemoteDriver):
            await _bridge_remote(ws, pv.driver.terminal_url(p["container"], a["workdir"]), pv.driver.token,
                                 lambda: pv.touch(pid))
        elif isinstance(pv.driver, DockerDriver):
            await pty_bridge(ws, pv.driver.terminal_argv(p["container"], a["workdir"]), lambda: pv.touch(pid))
        else:
            await ws.send_text("terminal is not available with this driver\r\n")
            await ws.close()

    r.previews = pv
    r.ws_router = ws_r
    return r


async def pty_bridge(ws: WebSocket, argv: list[str], on_input: Callable[[], None]) -> None:
    """A shell under a local pty <-> a browser terminal. Client messages are JSON:
    {"type": "input", "data": "..."} or {"type": "resize", "cols": n, "rows": n};
    the server sends the terminal's output as text."""
    import fcntl
    import pty
    import struct
    import termios

    master, slave = pty.openpty()
    proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, start_new_session=True, close_fds=True)
    os.close(slave)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    def readable() -> None:
        try:
            data = os.read(master, 65536)
        except OSError:
            data = b""
        queue.put_nowait(data or None)
        if not data:
            loop.remove_reader(master)

    loop.add_reader(master, readable)

    async def pump_out() -> None:
        while (data := await queue.get()) is not None:
            await ws.send_text(data.decode(errors="replace"))
        await ws.close()

    out_task = asyncio.create_task(pump_out())
    last_touch = 0.0
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            if msg.get("type") == "input":
                os.write(master, str(msg.get("data", "")).encode())
                if time.monotonic() - last_touch > 20:
                    last_touch = time.monotonic()
                    on_input()
            elif msg.get("type") == "resize":
                size = struct.pack("HHHH", int(msg.get("rows", 24)), int(msg.get("cols", 80)), 0, 0)
                fcntl.ioctl(master, termios.TIOCSWINSZ, size)
    except (WebSocketDisconnect, RuntimeError, ValueError, OSError):
        pass
    finally:
        out_task.cancel()
        try:
            loop.remove_reader(master)
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        os.close(master)


async def _bridge_remote(ws: WebSocket, url: str, token: str, on_input: Callable[[], None]) -> None:
    """Browser terminal <-> preview_service's terminal, message for message."""
    import websockets

    try:
        async with websockets.connect(url, additional_headers={"x-preview-token": token}, max_size=2**20) as up:
            async def down() -> None:
                async for m in up:
                    await ws.send_text(m if isinstance(m, str) else m.decode(errors="replace"))
                await ws.close()

            task = asyncio.create_task(down())
            last = 0.0
            try:
                while True:
                    m = await ws.receive_text()
                    await up.send(m)
                    if time.monotonic() - last > 20:
                        last = time.monotonic()
                        on_input()
            except (WebSocketDisconnect, RuntimeError):
                pass
            finally:
                task.cancel()
    except Exception as e:  # service down or refused: tell the teacher in the terminal
        try:
            await ws.send_text(f"\r\nThe preview terminal is not reachable ({type(e).__name__}).\r\n")
            await ws.close()
        except Exception:
            pass


def start_reaper(pv: Previews, every_s: float = 60) -> threading.Thread:
    """Background idle stop, so a closed browser tab doesn't hold a seat."""
    def loop() -> None:
        while True:
            time.sleep(every_s)
            try:
                pv.reap()
            except Exception:
                pass
    t = threading.Thread(target=loop, daemon=True, name="preview-reaper")
    t.start()
    return t

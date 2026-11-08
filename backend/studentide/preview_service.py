"""Teacher preview instances as their own small service, for deployments.

The only container that holds the Docker socket. The app never gets it: it
asks this service, over the internal network and with a shared token
($STUDENTIDE_PREVIEW_TOKEN), to start, stop and exec into preview
containers and the short-lived grading containers of submissions.py, and
proxies the terminal WebSocket to it (previews.RemoteDriver). Seats, idle
stop, the grading queue and who may open what are decided by the app; this
service only refuses containers that are not previews or grading runs.

    uvicorn studentide.preview_service:app --port 8002
"""

from __future__ import annotations

import os
import re
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket
from pydantic import BaseModel, Field

from .previews import DockerDriver, PreviewError, pty_bridge

app = FastAPI(title="Student IDE previews")
driver = DockerDriver()
# previews.Previews names every preview this way, submissions.Grader every grading run
CONTAINER = re.compile(r"^sbxp-(prv|sub)_[0-9a-f]{10}$")
PATH = re.compile(r"^/(home/student|tmp)(/[^\0]*)?$")


def token_ok(headers) -> bool:
    tok = os.environ.get("STUDENTIDE_PREVIEW_TOKEN", "")
    return bool(tok) and secrets.compare_digest(headers.get("x-preview-token", ""), tok)


def guard(request: Request) -> None:
    if not token_ok(request.headers):
        raise HTTPException(401, "bad preview token")


def check(container: str, *paths: str) -> None:
    if not CONTAINER.match(container):
        raise HTTPException(400, "not a preview container")
    for p in paths:
        if not PATH.match(p) or "/../" in p + "/":
            raise HTTPException(400, "path outside the preview's home")


def run(fn, *args):
    try:
        return fn(*args)
    except PreviewError as e:
        raise HTTPException(502, str(e))


class Resources(BaseModel):
    cpus: float = Field(gt=0, le=4)
    memory_mb: int = Field(ge=256, le=4096)
    pids: int = Field(ge=64, le=1024)


class Spec(BaseModel):
    container: str
    lab_id: str = Field(pattern=r"^slab_[0-9a-f]{10}$")
    image: str = Field(max_length=300)
    digest: str | None = None
    dockerfile: str = Field(max_length=60_000)
    hostname: str = Field(pattern=r"^[a-z0-9-]{1,30}$")
    network: str = Field(pattern=r"^(off|registries)$")
    resources: Resources


class Files(BaseModel):
    container: str
    files: list[dict] = Field(max_length=500)


class FileRef(BaseModel):
    container: str
    path: str = ""
    folder: str = ""


class Exec(BaseModel):
    container: str
    command: str = Field(max_length=5000)
    workdir: str
    stdin: str = Field(default="", max_length=200_000)
    timeout_s: int = Field(default=10, ge=1, le=300)


class Stop(BaseModel):
    container: str = ""


@app.post("/start", dependencies=[Depends(guard)])
def start(spec: Spec) -> dict:
    check(spec.container)
    run(driver.start, spec.model_dump())
    return {"ok": True}


@app.post("/put_files", dependencies=[Depends(guard)])
def put_files(body: Files) -> dict:
    check(body.container, *(str(f.get("path", "")) for f in body.files))
    run(driver.put_files, body.container, body.files)
    return {"ok": True}


@app.post("/read_file", dependencies=[Depends(guard)])
def read_file(body: FileRef) -> dict:
    check(body.container, body.path)
    return {"content": run(driver.read_file, body.container, body.path)}


@app.post("/list_files", dependencies=[Depends(guard)])
def list_files(body: FileRef) -> dict:
    check(body.container, body.folder)
    return {"files": run(driver.list_files, body.container, body.folder)}


@app.post("/exec", dependencies=[Depends(guard)])
def exec_(body: Exec) -> dict:
    check(body.container, body.workdir)
    return run(driver.exec, body.container, body.command, body.workdir, body.stdin, body.timeout_s)


@app.post("/stop", dependencies=[Depends(guard)])
def stop(body: Stop) -> dict:
    check(body.container)
    run(driver.stop, body.container)
    return {"ok": True}


@app.post("/stop_all", dependencies=[Depends(guard)])
def stop_all() -> dict:
    run(driver.stop_all)
    return {"ok": True}


@app.websocket("/terminal")
async def terminal(ws: WebSocket, container: str, workdir: str) -> None:
    if not token_ok(ws.headers):
        await ws.close(code=4401)
        return
    try:
        check(container, workdir)
    except HTTPException:
        await ws.close(code=4400)
        return
    await ws.accept()
    await pty_bridge(ws, driver.terminal_argv(container, workdir), lambda: None)


@app.get("/health")
def health() -> dict:
    p = driver._run(["version", "--format", "{{.Server.Version}}"], timeout=10)
    return {"ok": p.returncode == 0, "docker": p.stdout.decode().strip()}

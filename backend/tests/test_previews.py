"""Teacher "Try as a student" preview instances: seats, idle stop, time limit,
ownership, files, run/check/verify. A fake driver stands in for Docker; one
test uses real Docker when it is available."""

import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.auth import Config
from studentide.previews import DockerDriver, FakeDriver, Limits, tar_of

from test_auth import DOMAIN, fake_google, sign_in
from test_sandbox import ADMIN, MEERA, PRIYA, make_lab, make_subject


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def echo_program(files, cmd, workdir, stdin):
    """'Runs' main.c: prints its stdin if main.c says ECHO, else nothing."""
    if cmd.startswith("rm -rf"):
        return {}
    src = files.get(f"{workdir}/main.c", "")
    return {"stdout": stdin if "ECHO" in src else ""}


@pytest.fixture
def env(tmp_path):
    clock, driver = Clock(), FakeDriver(echo_program)
    cfg = Config(client_id="test-client", admins=frozenset({ADMIN}), secure_cookie=False)
    app = create_app(tmp_path / "p.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google,
                     preview_driver=driver, preview_limits=Limits(seats=2, idle_s=600, max_s=3600))
    app.state.previews.clock = clock
    app.state.previews.background = False
    return app, driver, clock


def lab_for(c):
    s = make_subject(c)
    return make_lab(c, s["id"])


def test_start_files_run_check(env):
    app, driver, clock = env
    priya = sign_in(app, PRIYA)
    lab = lab_for(priya)
    p = priya.post("/api/sandbox/previews", json={"lab_id": lab["id"]}).json()
    assert p["status"] == "running" and p["lab"]["id"] == lab["id"]
    spec = driver.containers[p["container"]]["spec"]
    assert spec["network"] == "registries" and spec["resources"] == {"cpus": 1.0, "memory_mb": 1024, "pids": 256}
    assert spec["hostname"] == "cs201" and "FROM ubuntu:24.04" in spec["dockerfile"]
    a = p["lab"]["assignments"][0]
    files = priya.get(f"/api/sandbox/previews/{p['id']}/files", params={"assignment_id": a["id"]}).json()["files"]
    assert [f["path"] for f in files] == ["Makefile", "main.c"]
    one = priya.get(f"/api/sandbox/previews/{p['id']}/files", params={"assignment_id": a["id"], "path": "main.c"})
    assert one.json()["content"].startswith("int main")
    bad = priya.get(f"/api/sandbox/previews/{p['id']}/files", params={"assignment_id": a["id"], "path": "../../etc/passwd"})
    assert bad.status_code == 400

    res = priya.post(f"/api/sandbox/previews/{p['id']}/check", json={"assignment_id": a["id"]}).json()
    assert (res["passed"], res["total"]) == (0, 2)
    priya.put(f"/api/sandbox/previews/{p['id']}/files", params={"assignment_id": a["id"]},
              json={"path": "main.c", "content": "// ECHO"})
    res = priya.post(f"/api/sandbox/previews/{p['id']}/check", json={"assignment_id": a["id"]}).json()
    assert (res["passed"], res["total"]) == (2, 2) and res["results"][1]["hidden"] is True
    out = priya.post(f"/api/sandbox/previews/{p['id']}/run", json={"assignment_id": a["id"], "stdin": "hi"}).json()
    assert out["stdout"] == "hi"


def test_verify_solution_and_starter(env):
    app, driver, clock = env
    priya = sign_in(app, PRIYA)
    lab = lab_for(priya)
    aid = lab["definition"]["assignments"][0]["id"]
    priya.patch(f"/api/sandbox/assignments/{aid}", json={"solution_files": [{"path": "main.c", "content": "// ECHO"}]})
    p = priya.post("/api/sandbox/previews", json={"lab_id": lab["id"]}).json()
    v = priya.post(f"/api/sandbox/previews/{p['id']}/verify").json()
    a = v["assignments"][0]
    assert v["ok"] and a["solution"] == {"passed": 2, "total": 2, "failed": []} and a["starter"]["passed"] == 0
    priya.patch(f"/api/sandbox/assignments/{aid}", json={"solution_files": [{"path": "main.c", "content": "wrong"}]})
    v = priya.post(f"/api/sandbox/previews/{p['id']}/verify").json()
    assert not v["ok"] and "fails on your solution" in v["assignments"][0]["problems"][0]


def test_seats_one_per_teacher_and_owner_only(env):
    app, driver, clock = env
    priya, meera, admin = sign_in(app, PRIYA), sign_in(app, MEERA), sign_in(app, ADMIN)
    lab = lab_for(priya)
    first = priya.post("/api/sandbox/previews", json={"lab_id": lab["id"]}).json()
    second = priya.post("/api/sandbox/previews", json={"lab_id": lab["id"]}).json()  # replaces the first
    assert priya.get(f"/api/sandbox/previews/{first['id']}").json()["stop_reason"] == "replaced"
    assert first["container"] not in driver.containers
    assert meera.post("/api/sandbox/previews", json={"lab_id": lab["id"]}).status_code == 403  # not her lab
    assert meera.get(f"/api/sandbox/previews/{second['id']}").status_code == 404
    mlab = lab_for(meera)
    assert meera.post("/api/sandbox/previews", json={"lab_id": mlab["id"]}).status_code == 200
    full = admin.post("/api/sandbox/previews", json={"lab_id": lab["id"]})
    assert full.status_code == 409 and "seats are in use" in full.json()["detail"]
    listing = admin.get("/api/sandbox/previews").json()
    assert listing["seats"]["used"] == 2 and listing["seats"]["free"] == 0 and len(listing["previews"]) == 2


def test_idle_stop_and_time_limit(env):
    app, driver, clock = env
    priya = sign_in(app, PRIYA)
    lab = lab_for(priya)
    p = priya.post("/api/sandbox/previews", json={"lab_id": lab["id"]}).json()
    aid = p["lab"]["assignments"][0]["id"]
    clock.t += 500
    assert priya.post(f"/api/sandbox/previews/{p['id']}/run", json={"assignment_id": aid}).status_code == 200  # activity
    clock.t += 500
    assert priya.get(f"/api/sandbox/previews/{p['id']}").json()["status"] == "running"
    clock.t += 700
    got = priya.get(f"/api/sandbox/previews/{p['id']}").json()
    assert got["status"] == "stopped" and got["stop_reason"] == "idle" and not driver.containers
    q = priya.post("/api/sandbox/previews", json={"lab_id": lab["id"]}).json()
    for _ in range(7):  # busy all along, still stopped at the hour
        clock.t += 550
        priya.post(f"/api/sandbox/previews/{q['id']}/run", json={"assignment_id": aid})
    assert priya.get(f"/api/sandbox/previews/{q['id']}").json()["stop_reason"] == "time limit"


def test_failed_start_and_disabled(env, tmp_path):
    app, driver, clock = env
    priya = sign_in(app, PRIYA)
    lab = lab_for(priya)
    driver.fail_start = "the environment image is not built yet"
    p = priya.post("/api/sandbox/previews", json={"lab_id": lab["id"]}).json()
    assert p["status"] == "failed" and "not built" in p["error"]
    assert priya.get("/api/sandbox/previews").json()["seats"]["used"] == 0
    off = create_app(tmp_path / "off.sqlite3", serve_frontend=False, admin_token="tok")
    c = TestClient(off)
    h = {"x-admin-token": "tok"}
    s = c.post("/api/sandbox/subjects", json={"title": "OS", "recipe": {"base": "linux"}}, headers=h).json()
    l = c.post(f"/api/sandbox/subjects/{s['id']}/labs", json={"title": "x"}, headers=h).json()
    c.post(f"/api/sandbox/labs/{l['id']}/assignments", json={"title": "a"}, headers=h)
    r = c.post("/api/sandbox/previews", json={"lab_id": l["id"]}, headers=h)
    assert r.status_code == 503 and c.get("/api/sandbox/previews", headers=h).json()["enabled"] is False


def test_off_network_lab_gets_no_network(env):
    app, driver, clock = env
    priya = sign_in(app, PRIYA)
    lab = lab_for(priya)
    priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"network": "off"})
    p = priya.post("/api/sandbox/previews", json={"lab_id": lab["id"]}).json()
    assert driver.containers[p["container"]]["spec"]["network"] == "off"


def test_tar_owned_by_student():
    import io
    import tarfile
    data = tar_of([{"path": "/home/student/labs/l/a/main.c", "content": "x", "executable": True}])
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        members = {m.name: m for m in t.getmembers()}
    assert set(members) == {"home/student", "home/student/labs", "home/student/labs/l", "home/student/labs/l/a",
                            "home/student/labs/l/a/main.c"}
    assert all(m.uid == 1000 for m in members.values()) and members["home/student/labs/l/a/main.c"].mode == 0o755


def docker_ready() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "image", "inspect", "ubuntu:24.04"], capture_output=True).returncode == 0


@pytest.mark.skipif(not docker_ready(), reason="needs Docker with ubuntu:24.04 pulled")
def test_real_docker_preview(tmp_path, monkeypatch):
    """End to end with Docker: build the environment locally, start, run a C
    program through make, check the tests, stop."""
    monkeypatch.setenv("STUDENTIDE_PREVIEW_BUILD_LOCAL", "1")
    app = create_app(tmp_path / "r.sqlite3", serve_frontend=False, admin_token="tok",
                     preview_driver=DockerDriver(), preview_limits=Limits(seats=1))
    app.state.previews.background = False
    c = TestClient(app)
    h = {"x-admin-token": "tok"}
    s = c.post("/api/sandbox/subjects", json={"title": "C", "code": "c101", "recipe": {"base": "c-cpp"}}, headers=h).json()
    lab = c.post(f"/api/sandbox/subjects/{s['id']}/labs", json={"title": "Echo"}, headers=h).json()
    lab = c.post(f"/api/sandbox/labs/{lab['id']}/assignments", headers=h, json={
        "title": "cat", "run": "make -s && ./main",
        "files": [{"path": "main.c", "content": "#include <stdio.h>\nint main(void){int c;while((c=getchar())!=EOF)putchar(c);}\n"},
                  {"path": "Makefile", "content": "main: main.c\n\tcc -O2 -o main main.c\n"}],
        "tests": {"cases": [{"stdin": "hello\n", "expected": "hello"}, {"stdin": "x", "expected": "y", "hidden": True}]}}).json()
    p = c.post("/api/sandbox/previews", json={"lab_id": lab["id"]}, headers=h).json()
    try:
        assert p["status"] == "running", p["error"]
        aid = p["lab"]["assignments"][0]["id"]
        res = c.post(f"/api/sandbox/previews/{p['id']}/check", json={"assignment_id": aid}, headers=h).json()
        assert (res["passed"], res["total"]) == (1, 2)
        who = c.post(f"/api/sandbox/previews/{p['id']}/run", headers=h,
                     json={"assignment_id": aid, "command": "id -un; hostname; sudo -n true && echo sudo; pwd"}).json()
        assert who["stdout"].split() == ["student", "c101", "sudo", p["lab"]["assignments"][0]["workdir"]]
        net = c.post(f"/api/sandbox/previews/{p['id']}/run", headers=h,
                     json={"assignment_id": aid, "command": "curl -sS -m 3 https://pypi.org >/dev/null; echo $?"}).json()
        assert net["stdout"].strip() != "0"  # no proxy configured: no network at all
    finally:
        c.post(f"/api/sandbox/previews/{p['id']}/stop", headers=h)
    assert subprocess.run(["docker", "inspect", p["container"]], capture_output=True).returncode != 0

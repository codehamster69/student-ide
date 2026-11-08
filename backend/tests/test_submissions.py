"""Sandbox Lab submissions: a Submit snapshot is queued and graded in a fresh
no-network container (hidden tests too); students see hidden tests as name +
pass only; teachers see every student x assignment and can regrade."""

import gzip
import hashlib
import io
import tarfile

import pytest

from studentide import preview_service
from studentide.app import create_app
from studentide.auth import Config
from studentide.previews import FakeDriver
from studentide.submissions import snapshot_files

from test_auth import DOMAIN, fake_google, sign_in
from test_previews import echo_program
from test_sandbox import ADMIN, MEERA, PRIYA, make_lab, make_subject

STUDENT = "pg25cs07@" + DOMAIN


def tgz(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(buf.getvalue())


def submit(c, lab_id, aid, main: bytes, reason="submit", sid="PG25CS07"):
    data = tgz({"./main.c": main, "./Makefile": b"main: main.c\n"})
    return c.put(f"/api/workspaces/{lab_id}/{aid}", params={"student_id": sid}, content=data, headers={
        "X-Workspace-Sha256": hashlib.sha256(main).hexdigest(), "X-Workspace-Reason": reason,
        "Content-Type": "application/gzip"})


def make_app(tmp_path, driver):
    cfg = Config(client_id="test-client", admins=frozenset({ADMIN}), secure_cookie=False)
    app = create_app(tmp_path / "g.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google,
                     preview_driver=driver)
    if driver is not None:
        app.state.grader.background = False
    return app


@pytest.fixture
def env(tmp_path):
    driver = FakeDriver(echo_program)
    app = make_app(tmp_path, driver)
    priya = sign_in(app, PRIYA)
    s = make_subject(priya)
    lab = make_lab(priya, s["id"], n=2)
    priya.put(f"/api/sandbox/subjects/{s['id']}/roster", json={"text": "A: PG25CS07, PG25CS08"})
    priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"status": "published"})
    aids = [a["id"] for a in priya.get(f"/api/sandbox/labs/{lab['id']}").json()["definition"]["assignments"]]
    return app, driver, priya, lab["id"], aids


def test_submit_is_graded_with_hidden_tests(env):
    app, driver, priya, lab_id, (a1, a2) = env
    student = sign_in(app, STUDENT)
    started = []
    real_start = driver.start
    driver.start = lambda spec: (started.append(spec), real_start(spec))
    r = submit(student, lab_id, a1, b"// ECHO")
    assert r.status_code == 200, r.text
    sub = r.json()["submission"]
    assert sub["status"] == "graded"  # tests grade inline; on the server the reply says "queued"
    got = student.get(f"/api/sandbox/my/submissions/{sub['id']}").json()
    assert (got["status"], got["passed"], got["total"]) == ("graded", 2, 2)
    visible, hidden = got["results"]
    assert visible["expected"] == "1\n" and visible["got"] == "1\n"
    assert hidden == {"name": "secret", "hidden": True, "passed": True, "timed_out": False}
    # a fresh container per run, no network, removed afterwards; the preview service accepts its name
    spec = started[0]
    assert spec["network"] == "off" and spec["container"] == f"sbxp-{sub['id']}"
    assert preview_service.CONTAINER.match(spec["container"]) and not driver.containers

    # a wrong answer: graded 0/2; latest per assignment with attempt counts
    submit(student, lab_id, a1, b"// nope")
    mine = student.get(f"/api/sandbox/my/labs/{lab_id}/submissions").json()
    assert mine["assignments"][a2] is None
    assert (mine["assignments"][a1]["passed"], mine["assignments"][a1]["attempts"]) == (0, 2)
    card = student.get("/api/sandbox/my/labs").json()[0]["labs"][0]
    assert (card["submitted"], card["passed_all"], card["closed"]) == (1, 0, False)

    # a change backup is not a submission
    assert "submission" not in submit(student, lab_id, a2, b"// ECHO", reason="change").json()


def test_teacher_table_and_regrade(env):
    app, driver, priya, lab_id, (a1, a2) = env
    student = sign_in(app, STUDENT)
    sub = submit(student, lab_id, a1, b"// nope").json()["submission"]
    table = priya.get(f"/api/sandbox/labs/{lab_id}/submissions").json()
    assert [s["student_id"] for s in table["students"]] == ["PG25CS07", "PG25CS08"]
    cell = table["students"][0]["assignments"][a1]
    assert cell["passed"] == 0 and cell["results"][1]["stdin"] == "2\n"  # teachers see hidden tests in full
    assert table["students"][1]["assignments"][a1] is None
    assert table["counts"] == {"students": 2, "submitted": 1, "graded": 1, "passed_all": 0}

    # the teacher fixes a test: regrade picks up the new expectation
    priya.patch(f"/api/sandbox/assignments/{a1}", json={"tests": {"kind": "io", "cases": [
        {"name": "one", "stdin": "", "expected": ""}]}})
    assert priya.post(f"/api/sandbox/labs/{lab_id}/regrade").json() == {"queued": 1}
    again = priya.get(f"/api/sandbox/submissions/{sub['id']}").json()
    assert (again["passed"], again["total"], again["regraded"]) == (1, 1, True)

    # other teachers and students can't see or regrade it
    meera = sign_in(app, MEERA)
    assert meera.get(f"/api/sandbox/labs/{lab_id}/submissions").status_code in (403, 404)
    assert meera.post(f"/api/sandbox/submissions/{sub['id']}/regrade").status_code in (403, 404)
    other = sign_in(app, "pg25cs08@" + DOMAIN)
    assert other.get(f"/api/sandbox/my/submissions/{sub['id']}").status_code == 404


def test_failures_are_recorded_and_queue_goes_on(env):
    app, driver, priya, lab_id, (a1, a2) = env
    student = sign_in(app, STUDENT)
    driver.fail_start = "could not pull the image"
    sub = submit(student, lab_id, a1, b"// ECHO").json()["submission"]
    got = student.get(f"/api/sandbox/my/submissions/{sub['id']}").json()
    assert got["status"] == "failed" and "pull" in got["error"]
    driver.fail_start = ""
    priya.post(f"/api/sandbox/submissions/{sub['id']}/regrade")
    assert student.get(f"/api/sandbox/my/submissions/{sub['id']}").json()["status"] == "graded"


def test_closed_lab_refuses_submit_but_shows_grades(env):
    app, driver, priya, lab_id, (a1, a2) = env
    student = sign_in(app, STUDENT)
    submit(student, lab_id, a1, b"// ECHO")
    priya.patch(f"/api/sandbox/labs/{lab_id}", json={"status": "closed"})
    late = submit(student, lab_id, a1, b"// ECHO")
    assert late.status_code == 409 and "closed" in late.json()["detail"]
    assert student.get(f"/api/sandbox/my/labs/{lab_id}").json()["closed"] is True
    assert student.get(f"/api/sandbox/my/labs/{lab_id}/submissions").json()["assignments"][a1]["passed"] == 2
    # but no new recorded session on a closed lab
    assert student.post("/api/sessions", json={"student_id": "PG25CS07", "sandbox_lab_id": lab_id,
                                               "assignment_id": a1}).status_code == 403


def test_no_grader_keeps_the_submission(tmp_path):
    app = make_app(tmp_path, None)
    priya = sign_in(app, PRIYA)
    s = make_subject(priya)
    lab = make_lab(priya, s["id"])
    priya.put(f"/api/sandbox/subjects/{s['id']}/roster", json={"text": "PG25CS07"})
    priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"status": "published"})
    aid = priya.get(f"/api/sandbox/labs/{lab['id']}").json()["definition"]["assignments"][0]["id"]
    sub = submit(sign_in(app, STUDENT), lab["id"], aid, b"x").json()["submission"]
    assert sub["status"] == "queued" and "not set up" in sub["error"]
    assert priya.post(f"/api/sandbox/submissions/{sub['id']}/regrade").status_code == 503


def test_snapshot_files_text_only():
    data = tgz({"./main.c": b"int x;", "./a.out": b"\x7fELF\xff\xfe", "./sub/notes.txt": "héllo".encode()})
    files = snapshot_files(data, "/home/student/labs/l/a")
    assert {f["path"]: f["content"] for f in files} == {"/home/student/labs/l/a/main.c": "int x;",
                                                       "/home/student/labs/l/a/sub/notes.txt": "héllo"}

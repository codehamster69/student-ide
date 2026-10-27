"""Deployments run student code in a separate runner service; the main
server's run and grading results must not change."""

import socket
import threading
import time

import pytest
import uvicorn

from studentide import grading, runner
from studentide.runner_service import app


@pytest.fixture(scope="module")
def runner_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(5)


def test_remote_run_matches_local(runner_url, monkeypatch):
    code = "a = int(input())\nprint(a * 2)\n"
    local = runner.run(code, "21\n")
    monkeypatch.setenv("STUDENTIDE_RUNNER_URL", runner_url)
    remote = runner.run(code, "21\n")
    assert (remote.stdout, remote.exit_code, remote.error_type) == (local.stdout, local.exit_code, local.error_type) == ("42\n", 0, None)
    assert runner.run("print(", "").error_type == "SyntaxError"


def test_remote_grading(runner_url, monkeypatch):
    q = {"tests": [{"name": "a", "stdin": "2\n", "expected": "4"}, {"name": "b", "stdin": "3\n", "expected": "9", "hidden": True}]}
    local = grading.grade(q, "n = int(input())\nprint(n * n)\n")
    monkeypatch.setenv("STUDENTIDE_RUNNER_URL", runner_url)
    remote = grading.grade(q, "n = int(input())\nprint(n * n)\n")
    assert remote["passed"] == local["passed"] == 2
    assert [r["passed"] for r in remote["results"]] == [r["passed"] for r in local["results"]]


def test_unreachable_runner_says_so(monkeypatch):
    monkeypatch.setenv("STUDENTIDE_RUNNER_URL", "http://127.0.0.1:9")
    r = runner.run("print(1)")
    assert r.error_type == "Unavailable" and "runner" in r.stderr


def test_program_that_cannot_start_is_reported(monkeypatch):
    """A scratch dir mounted noexec once made every C run a 500; now it is a normal failed run."""
    def refuse(*a, **k):
        raise PermissionError(13, "Permission denied")
    with runner.Program('#include <stdio.h>\nint main(){puts("hi");}', "c") as p:
        assert p.failed is None
        monkeypatch.setattr(runner.subprocess, "Popen", refuse)
        r = p.run()
    assert r.exit_code == 126 and "could not start" in r.stderr

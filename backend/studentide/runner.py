"""Runs a student's Python program and captures the result.

This is a lab-machine runner, not a security sandbox: it isolates the
interpreter (-I), uses a throwaway working directory, a wall-clock timeout
and, on Linux, CPU / memory / file-size limits. Before exposing the server
beyond a trusted lab network, run code inside a container (e.g. nsjail or
a locked-down Docker image) instead.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

TIMEOUT_S = 5.0
MAX_OUTPUT = 64 * 1024  # bytes kept per stream
MEMORY_LIMIT = 256 * 1024 * 1024

_ERROR_LINE = re.compile(r"^(\w+(?:Error|Exception|Interrupt|Exit)|\w+Warning)\b", re.M)


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int | None  # None when killed by the timeout
    duration_ms: float
    error_type: str | None


def _limits() -> None:  # runs in the child before exec
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (int(TIMEOUT_S) + 1, int(TIMEOUT_S) + 1))
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT * 16, MAX_OUTPUT * 16))
    os.setsid()


def _clip(b: bytes) -> str:
    s = b[:MAX_OUTPUT].decode("utf-8", errors="replace")
    return s + ("\n[output truncated]" if len(b) > MAX_OUTPUT else "")


def error_type_of(stderr: str, exit_code: int | None) -> str | None:
    """Name of the exception that ended the program, from the last traceback line."""
    if exit_code is None:
        return "Timeout"
    if exit_code == 0:
        return None
    found = _ERROR_LINE.findall(stderr)
    return found[-1] if found else f"Exit{exit_code}"


def run_python(code: str, stdin: str = "") -> RunResult:
    with tempfile.TemporaryDirectory(prefix="sid-run-") as work:
        path = os.path.join(work, "main.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        start = time.perf_counter()
        proc = subprocess.Popen(
            [sys.executable, "-I", path],
            cwd=work,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=_limits if sys.platform.startswith("linux") else None,
        )
        try:
            out, err = proc.communicate(stdin.encode(), timeout=TIMEOUT_S)
            exit_code: int | None = proc.returncode
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, 9)
            except (ProcessLookupError, PermissionError, AttributeError):
                proc.kill()
            out, err = proc.communicate()
            exit_code = None
            err += f"\nTimeout: program ran longer than {TIMEOUT_S:g}s and was stopped".encode()
        duration_ms = (time.perf_counter() - start) * 1000
    stderr = _clip(err)
    return RunResult(_clip(out), stderr, exit_code, duration_ms, error_type_of(stderr, exit_code))

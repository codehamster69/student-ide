"""Runs a student's program (Python, C, C++, Java or JavaScript) and captures
the result.

This is a lab-machine runner, not a security sandbox: it isolates the
interpreter (-I), uses a throwaway working directory, a wall-clock timeout
and, on Linux, CPU / memory / file-size limits. Before exposing the server
beyond a trusted lab network, run code inside a container (e.g. nsjail or
a locked-down Docker image) instead.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

TIMEOUT_S = 5.0
COMPILE_TIMEOUT_S = 20.0
MAX_OUTPUT = 64 * 1024  # bytes kept per stream
MEMORY_LIMIT = 256 * 1024 * 1024

_ERROR_LINE = re.compile(r"^(\w+(?:Error|Exception|Interrupt|Exit)|\w+Warning)\b", re.M)
# Java and JavaScript print "Exception in thread ... java.lang.Foo" / "TypeError: ..." mid-line.
_QUALIFIED_ERROR = re.compile(r"\b(?:[a-z]+\.)+([A-Z]\w*(?:Error|Exception))\b")
_JAVA_CLASS = re.compile(r"^\s*public\s+(?:final\s+)?class\s+([A-Za-z_]\w*)", re.M)
_ES_MODULE = re.compile(r"^\s*(?:import|export)\s", re.M)

# Languages a lab can be set to. `tool` is what must be on PATH for it to run.
LANGUAGES: dict[str, dict] = {
    "python": {"label": "Python 3", "tool": "python3", "file": "main.py"},
    "c": {"label": "C (gcc)", "tool": "gcc", "file": "main.c"},
    "cpp": {"label": "C++17 (g++)", "tool": "g++", "file": "main.cpp"},
    "java": {"label": "Java", "tool": "javac", "file": "Main.java"},
    "javascript": {"label": "JavaScript (Node)", "tool": "node", "file": "main.js"},
}


def available_languages() -> list[dict]:
    """Every language with whether this machine can actually run it."""
    return [{"id": k, "label": v["label"], "file": v["file"],
             "available": k == "python" or shutil.which(v["tool"]) is not None} for k, v in LANGUAGES.items()]


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int | None  # None when killed by the timeout
    duration_ms: float
    error_type: str | None


def _limits(cpu_s: float, memory: bool = True):
    def apply() -> None:  # runs in the child before exec
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_s) + 1, int(cpu_s) + 1))
        if memory:  # the JVM and V8 reserve far more address space than they use
            resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT * 16, MAX_OUTPUT * 16))
        os.setsid()
    return apply


def _clip(b: bytes) -> str:
    s = b[:MAX_OUTPUT].decode("utf-8", errors="replace")
    return s + ("\n[output truncated]" if len(b) > MAX_OUTPUT else "")


def error_type_of(stderr: str, exit_code: int | None) -> str | None:
    """Name of the exception that ended the program, from the last traceback line."""
    if exit_code is None:
        return "Timeout"
    if exit_code == 0:
        return None
    found = _ERROR_LINE.findall(stderr) or _QUALIFIED_ERROR.findall(stderr)
    return found[-1] if found else f"Exit{exit_code}"


def _exec(argv: list[str], work: str, stdin: str, env: dict, timeout: float, memory: bool = True):
    """Returns (stdout bytes, stderr bytes, exit code or None on timeout)."""
    proc = subprocess.Popen(
        argv, cwd=work, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        preexec_fn=_limits(timeout, memory) if sys.platform.startswith("linux") else None,
    )
    try:
        out, err = proc.communicate(stdin.encode(), timeout=timeout)
        return out, err, proc.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, 9)
        except (ProcessLookupError, PermissionError, AttributeError):
            proc.kill()
        out, err = proc.communicate()
        return out, err + f"\nTimeout: program ran longer than {timeout:g}s and was stopped".encode(), None


def _plan(language: str, code: str, work: str) -> tuple[list[str] | None, list[str], bool]:
    """Writes the source file; returns (compile argv or None, run argv, memory limit on?)."""
    if language == "java":
        m = _JAVA_CLASS.search(code)
        name = m.group(1) if m else "Main"
        path = os.path.join(work, f"{name}.java")
        compile_ = ["javac", "-encoding", "UTF-8", "-J-Xmx256m", path]
        run = ["java", "-Xmx256m", "-Xss64m", "-cp", work, name]
        memory = False
    elif language in ("c", "cpp"):
        path = os.path.join(work, LANGUAGES[language]["file"])
        exe = os.path.join(work, "main")
        compile_ = (["gcc", "-std=c11"] if language == "c" else ["g++", "-std=c++17"]) + ["-O2", "-o", exe, path, "-lm"]
        run, memory = [exe], True
    elif language == "javascript":
        # ES module syntax (import/export, as in Exercism stubs) needs .mjs; plain scripts keep require().
        path = os.path.join(work, "main.mjs" if _ES_MODULE.search(code) else "main.js")
        compile_, run, memory = None, ["node", "--max-old-space-size=256", path], False
    else:
        path = os.path.join(work, "main.py")
        compile_, run, memory = None, [sys.executable, "-I", path], True
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return compile_, run, memory


class Program:
    """A program written to a scratch directory and compiled once, so it can be
    run against many inputs (test cases) without recompiling.

        with Program(code, "cpp") as p:
            if p.failed: ...      # p.failed is a RunResult (CompileError / Unavailable)
            r = p.run("1 2\\n")
    """

    def __init__(self, code: str, language: str = "python"):
        if language not in LANGUAGES:
            raise ValueError(f"unsupported language: {language}")
        self.code, self.language = code, language
        self.failed: RunResult | None = None
        self.compile_ms = 0.0

    def __enter__(self) -> "Program":
        self._tmp = tempfile.TemporaryDirectory(prefix="sid-run-")
        self.work = self._tmp.name
        self.env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
                    "HOME": self.work, "LANG": "C.UTF-8"}
        compile_, self.argv, self.memory = _plan(self.language, self.code, self.work)
        tool = compile_[0] if compile_ else self.argv[0]
        if tool != sys.executable and shutil.which(tool) is None:
            self.failed = RunResult("", f"{LANGUAGES[self.language]['label']} is not installed on this server", 127, 0.0, "Unavailable")
        elif compile_ is not None:
            start = time.perf_counter()
            _, cerr, cexit = _exec(compile_, self.work, "", self.env, COMPILE_TIMEOUT_S, memory=False)
            self.compile_ms = (time.perf_counter() - start) * 1000
            if cexit != 0:
                self.failed = RunResult("", _clip(self._strip(cerr)), cexit, self.compile_ms,
                                        "Timeout" if cexit is None else "CompileError")
        return self

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()

    def _strip(self, b: bytes) -> bytes:  # compiler/runtime messages without the scratch path
        return b.replace(self.work.encode() + b"/", b"")

    def run(self, stdin: str = "") -> RunResult:
        if self.failed:
            return self.failed
        start = time.perf_counter()
        out, err, exit_code = _exec(self.argv, self.work, stdin, self.env, TIMEOUT_S, self.memory)
        duration_ms = (time.perf_counter() - start) * 1000
        stderr = _clip(self._strip(err))
        return RunResult(_clip(out), stderr, exit_code, duration_ms, error_type_of(stderr, exit_code))


def run(code: str, stdin: str = "", language: str = "python") -> RunResult:
    """Compile (when the language needs it) and run once. A compile failure comes
    back as error_type "CompileError" with the compiler's messages on stderr;
    duration_ms includes compile time, since that is what the student waited."""
    with Program(code, language) as p:
        r = p.run(stdin)
        if not p.failed:
            r.duration_ms += p.compile_ms
        return r


def run_python(code: str, stdin: str = "") -> RunResult:
    return run(code, stdin, "python")

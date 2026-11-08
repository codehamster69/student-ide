"""Sandbox Labs catalogue: subjects, environments, sandbox labs and their
assignments, the shared library, and the lab definition the desktop app runs.

Teachers create subjects freely (no approval), give each an environment (a
recipe of base + tools that the build service turns into a Linux image), add
labs of assignments, and may share a lab to the library for colleagues. There
are no preset labs: the library holds only what teachers share. Students run
every lab on their own machine; cloud instances (previews.py) are for teachers'
"Try as a student" only. Format and endpoints: docs/sandbox-labs.md.

Ownership follows web labs (PR #19): a subject's owner and co-teachers edit
it, TAs only view, admins see everything, only admins change the owner. A lab
belongs to its subject's people.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import time
import uuid
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from .auth import not_yours, roster_id
from .db import Database
from .grading import MAX_TESTS

FORMAT = "studentide.sandbox-lab/1"
Network = Literal["open", "registries", "off"]
Compare = Literal["text", "json", "tokens"]  # grading.outputs_match; "checker" is web-only

SCHEMA = """
CREATE TABLE IF NOT EXISTS sbx_environments (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    owner_email   TEXT,                       -- NULL = made with the admin token / dev mode
    shared        INTEGER NOT NULL DEFAULT 0, -- 1 = every teacher may use it (only the author edits)
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);
-- Each change to an environment is a new version; labs pin the version they run.
CREATE TABLE IF NOT EXISTS sbx_env_versions (
    environment_id TEXT NOT NULL REFERENCES sbx_environments(id) ON DELETE CASCADE,
    version       INTEGER NOT NULL,
    recipe_json   TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('needs_approval', 'queued', 'building', 'ready', 'failed')),
    digest        TEXT,                       -- sha256:… of the pushed image, set by the build service
    log           TEXT NOT NULL DEFAULT '',   -- last lines of the build, for the teacher
    approved_by   TEXT,                       -- raw Dockerfiles: the admin who allowed the build
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL,
    PRIMARY KEY (environment_id, version)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS sbx_subjects (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    code          TEXT NOT NULL DEFAULT '',   -- course code, e.g. CS201
    semester      TEXT NOT NULL DEFAULT '',   -- e.g. "Autumn 2026"
    color         TEXT NOT NULL DEFAULT '',   -- one of COLORS
    owner_email   TEXT,
    environment_id TEXT REFERENCES sbx_environments(id),
    copied_from   TEXT,                       -- subject this was copied from (last semester)
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sbx_subject_people (
    subject_id    TEXT NOT NULL REFERENCES sbx_subjects(id) ON DELETE CASCADE,
    email         TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('co_teacher', 'ta')),
    PRIMARY KEY (subject_id, email)
) WITHOUT ROWID;
-- No foreign key to students: roll numbers can be added before first sign-in.
CREATE TABLE IF NOT EXISTS sbx_subject_students (
    subject_id    TEXT NOT NULL REFERENCES sbx_subjects(id) ON DELETE CASCADE,
    student_id    TEXT NOT NULL,
    section       TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (subject_id, student_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS sbx_labs (
    id            TEXT PRIMARY KEY,
    subject_id    TEXT NOT NULL REFERENCES sbx_subjects(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'closed')),
    network       TEXT NOT NULL DEFAULT 'registries' CHECK (network IN ('open', 'registries', 'off')),
    assessed      INTEGER NOT NULL DEFAULT 1,  -- assessed labs can never use the open network
    sections_json TEXT NOT NULL DEFAULT '[]',  -- [] = the whole roster, else only these sections
    env_version   INTEGER,                     -- pinned at publish; NULL = the subject's newest
    opens_at      REAL,
    due_at        REAL,
    min_desktop_version TEXT,                  -- the app version this lab needs, if newer than any
    version       INTEGER NOT NULL DEFAULT 1,  -- bumps on every change; clients cache by (id, version)
    based_on      TEXT,                        -- library entry it was copied from
    based_on_version INTEGER,
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sbx_labs_by_subject ON sbx_labs(subject_id, created_at);
CREATE TABLE IF NOT EXISTS sbx_assignments (
    id            TEXT PRIMARY KEY,
    lab_id        TEXT NOT NULL REFERENCES sbx_labs(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    title         TEXT NOT NULL,
    statement     TEXT NOT NULL DEFAULT '',    -- Markdown
    files_json    TEXT NOT NULL DEFAULT '[]',  -- starter files [{path, content, executable}]
    open_json     TEXT NOT NULL DEFAULT '[]',  -- files the editor opens first
    run           TEXT NOT NULL DEFAULT '',    -- Run button command, in the workdir
    tests_json    TEXT NOT NULL DEFAULT '{}',  -- {kind, command, timeout_s, cases: [{name, stdin, expected, hidden, compare}]}
    solution_json TEXT NOT NULL DEFAULT '[]',  -- reference solution files; teachers and the server only
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sbx_assignments_by_lab ON sbx_assignments(lab_id, position);
-- A lab shared to the library: a snapshot, so later edits to the source don't
-- leak into colleagues' copies until the author shares again (version + 1).
CREATE TABLE IF NOT EXISTS sbx_library (
    id            TEXT PRIMARY KEY,
    lab_id        TEXT NOT NULL UNIQUE,
    shared_by     TEXT,
    title         TEXT NOT NULL,
    summary       TEXT NOT NULL DEFAULT '',
    subject_title TEXT NOT NULL DEFAULT '',
    topics_json   TEXT NOT NULL DEFAULT '[]',
    difficulty    TEXT NOT NULL DEFAULT '',
    base          TEXT NOT NULL DEFAULT '',    -- the environment's base, for search ("c-cpp")
    snapshot_json TEXT NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1,
    uses          INTEGER NOT NULL DEFAULT 0,
    shared_at     REAL NOT NULL,
    withdrawn_at  REAL
);
"""

COLORS = ("indigo", "teal", "amber", "rose", "sky", "violet", "emerald", "orange")

# Always in every image (the local runtime needs tar, script and bash).
COMMON_APT = ("sudo", "bash", "tar", "util-linux", "procps", "less", "vim", "nano", "tmux", "git", "curl",
              "ca-certificates", "locales", "man-db", "file", "unzip", "zip")

BASES: dict[str, dict] = {
    "c-cpp": {"label": "C and C++", "apt": ["build-essential", "gdb", "make"], "mb": 420,
              "includes": "gcc, g++, make, gdb"},
    "python": {"label": "Python", "apt": ["python3", "python3-pip", "python3-venv"], "mb": 260,
               "includes": "Python 3.12, pip, venv"},
    "java": {"label": "Java", "apt": ["openjdk-21-jdk-headless", "maven"], "mb": 610,
             "includes": "JDK 21, Maven"},
    "linux": {"label": "Linux and shell", "apt": ["man-db", "bc", "jq", "tree", "rsync"], "mb": 190,
              "includes": "bash, coreutils, jq, tree, man pages"},
    "web-node": {"label": "Web (Node)", "apt": ["nodejs", "npm"], "mb": 480,
                 "includes": "Node.js, npm"},
    "databases": {"label": "Databases", "apt": ["sqlite3", "postgresql", "postgresql-client", "mariadb-client"],
                  "mb": 520, "includes": "SQLite, PostgreSQL server and client, MariaDB client"},
}
BASE_MB = 150  # Ubuntu 24.04 plus COMMON_APT

TOOLS: list[dict] = [
    {"id": t[0], "label": t[1], "group": t[2], "mb": t[3], **t[4]} for t in (
        ("gdb", "gdb debugger", "C and C++", 30, {"apt": ["gdb"]}),
        ("valgrind", "Valgrind", "C and C++", 90, {"apt": ["valgrind"]}),
        ("make", "make", "C and C++", 2, {"apt": ["make"]}),
        ("cmake", "CMake", "C and C++", 45, {"apt": ["cmake"]}),
        ("clang", "Clang and clang-format", "C and C++", 380, {"apt": ["clang", "clang-format"]}),
        ("strace", "strace and ltrace", "Systems", 3, {"apt": ["strace", "ltrace"]}),
        ("perf", "perf", "Systems", 60, {"apt": ["linux-tools-generic"]}),
        ("flex-bison", "flex and bison", "Compilers", 6, {"apt": ["flex", "bison"]}),
        ("llvm", "LLVM", "Compilers", 300, {"apt": ["llvm"]}),
        ("python3", "Python 3", "Python", 60, {"apt": ["python3", "python3-pip", "python3-venv"]}),
        ("pytest", "pytest", "Python", 5, {"apt": ["python3-pip"], "pip": ["pytest"]}),
        ("numpy", "NumPy", "Python", 40, {"apt": ["python3-pip"], "pip": ["numpy"]}),
        ("pandas", "pandas", "Python", 70, {"apt": ["python3-pip"], "pip": ["pandas"]}),
        ("matplotlib", "Matplotlib", "Python", 50, {"apt": ["python3-pip"], "pip": ["matplotlib"]}),
        ("scikit-learn", "scikit-learn", "Python", 120, {"apt": ["python3-pip"], "pip": ["scikit-learn"]}),
        ("jupyter", "Jupyter", "Python", 150, {"apt": ["python3-pip"], "pip": ["jupyterlab"]}),
        ("jdk", "Java JDK 21", "Java", 330, {"apt": ["openjdk-21-jdk-headless"]}),
        ("maven", "Maven", "Java", 20, {"apt": ["maven"]}),
        ("gradle", "Gradle", "Java", 150, {"apt": ["gradle"]}),
        ("junit", "JUnit 5", "Java", 5, {"apt": ["junit5"]}),
        ("node", "Node.js and npm", "Web", 300, {"apt": ["nodejs", "npm"]}),
        ("typescript", "TypeScript", "Web", 25, {"apt": ["nodejs", "npm"], "npm": ["typescript"]}),
        ("sqlite3", "SQLite", "Databases", 3, {"apt": ["sqlite3"]}),
        ("postgres", "PostgreSQL server", "Databases", 60, {"apt": ["postgresql"]}),
        ("psql", "PostgreSQL client", "Databases", 15, {"apt": ["postgresql-client"]}),
        ("mariadb", "MariaDB / MySQL server", "Databases", 190, {"apt": ["mariadb-server"]}),
        ("mysql-client", "MariaDB / MySQL client", "Databases", 40, {"apt": ["mariadb-client"]}),
        ("redis", "Redis", "Databases", 10, {"apt": ["redis-server", "redis-tools"]}),
        ("iproute2", "iproute2 (ip, ss)", "Networks", 3, {"apt": ["iproute2"]}),
        ("ping", "ping and traceroute", "Networks", 2, {"apt": ["iputils-ping", "traceroute"]}),
        ("netcat", "netcat", "Networks", 1, {"apt": ["netcat-openbsd"]}),
        ("tcpdump", "tcpdump", "Networks", 3, {"apt": ["tcpdump"]}),
        ("tshark", "Wireshark CLI (tshark)", "Networks", 120, {"apt": ["tshark"]}),
        ("nginx", "nginx", "Web", 5, {"apt": ["nginx"]}),
        ("shellcheck", "ShellCheck", "Linux", 20, {"apt": ["shellcheck"]}),
    )
]
TOOL_BY_ID = {t["id"]: t for t in TOOLS}

APT_NAME = re.compile(r"^[a-z0-9][a-z0-9+.-]{0,80}$")
PIP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}(\[[A-Za-z0-9,._-]+\])?([=<>~!]=?[A-Za-z0-9.*+-]{1,40})?$")
NPM_NAME = re.compile(r"^(@[a-z0-9][a-z0-9._-]{0,60}/)?[a-z0-9][a-z0-9._-]{0,80}(@[A-Za-z0-9.^~*+-]{1,40})?$")
FILE_PATH = re.compile(r"^(?!/)(?!.*(^|/)\.\.(/|$))[A-Za-z0-9._@+ -]+(/[A-Za-z0-9._@+ -]+)*$")
MAX_FILES, MAX_FILES_BYTES = 100, 2_000_000


def registry() -> str:
    return (os.environ.get("STUDENTIDE_SANDBOX_REGISTRY") or "ghcr.io/codehamster69").rstrip("/")


def image_name(env_id: str, version: int) -> str:
    """One repository for every environment, tagged <env id>-<version>, so making
    that one package public once lets every student pull every environment."""
    return f"{registry()}/studentide-env:{env_id.lower()}-{version}"


# -- request bodies


class Recipe(BaseModel):
    base: Literal["c-cpp", "python", "java", "linux", "web-node", "databases"] = "linux"
    tools: list[str] = Field(default_factory=list, max_length=60)
    apt: list[str] = Field(default_factory=list, max_length=60)
    pip: list[str] = Field(default_factory=list, max_length=60)
    npm: list[str] = Field(default_factory=list, max_length=60)
    setup: str = Field(default="", max_length=20_000)
    dockerfile: str = Field(default="", max_length=50_000)  # raw: needs an admin to approve the build
    resources: dict = Field(default_factory=dict)

    @field_validator("tools")
    @classmethod
    def _tools(cls, v: list[str]) -> list[str]:
        bad = [t for t in v if t not in TOOL_BY_ID]
        if bad:
            raise ValueError(f"unknown tools: {', '.join(bad)}")
        return list(dict.fromkeys(v))

    @field_validator("apt", "pip", "npm")
    @classmethod
    def _names(cls, v: list[str], info) -> list[str]:
        pattern = {"apt": APT_NAME, "pip": PIP_NAME, "npm": NPM_NAME}[info.field_name]
        v = [s.strip() for s in v if s.strip()]
        bad = [s for s in v if not pattern.match(s)]
        if bad:
            raise ValueError(f"not a valid {info.field_name} package name: {', '.join(bad)}")
        return list(dict.fromkeys(v))

    @field_validator("resources")
    @classmethod
    def _resources(cls, v: dict) -> dict:
        return resources(v)


DEFAULT_RESOURCES = {"cpus": 2, "memory_mb": 2048, "disk_gb": 10, "pids": 512}
RESOURCE_LIMITS = {"cpus": (1, 8), "memory_mb": (512, 16384), "disk_gb": (2, 100), "pids": (128, 4096)}


def resources(v: dict | None) -> dict:
    out = dict(DEFAULT_RESOURCES)
    for k, val in (v or {}).items():
        if k not in RESOURCE_LIMITS:
            raise ValueError(f"unknown resource {k!r}")
        lo, hi = RESOURCE_LIMITS[k]
        if not isinstance(val, (int, float)) or not lo <= val <= hi:
            raise ValueError(f"{k} must be between {lo} and {hi}")
        out[k] = int(val)
    return out


class EnvironmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    recipe: Recipe = Field(default_factory=Recipe)
    shared: bool = False


class EnvironmentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    shared: bool | None = None


class VersionIn(BaseModel):
    recipe: Recipe


class BuildReport(BaseModel):
    status: Literal["building", "ready", "failed"]
    digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    log: str = Field(default="", max_length=20_000)


class SubjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    code: str = Field(default="", max_length=20)
    semester: str = Field(default="", max_length=40)
    color: str = ""
    environment_id: str | None = None   # reuse an environment (own or shared)
    recipe: Recipe | None = None        # or make a new one for this subject


class SubjectPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=20)
    semester: str | None = Field(default=None, max_length=40)
    color: str | None = None
    environment_id: str | None = None
    owner_email: str | None = None      # admins only


class PeopleIn(BaseModel):
    co_teachers: list[str] = Field(default_factory=list, max_length=50)
    tas: list[str] = Field(default_factory=list, max_length=50)


class RosterStudent(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    section: str = Field(default="", max_length=20)


class RosterIn(BaseModel):
    students: list[RosterStudent] | None = Field(default=None, max_length=3000)
    text: str | None = Field(default=None, max_length=200_000)  # pasted ids, addresses, ranges, "A: …" sections


class CopyIn(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    semester: str = Field(default="", max_length=40)


class LabIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=20_000)


class LabPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=20_000)
    status: Literal["draft", "published", "closed"] | None = None
    network: Network | None = None
    assessed: bool | None = None
    sections: list[str] | None = Field(default=None, max_length=20)
    environment_version: int | None = None
    opens_at: float | None = None
    due_at: float | None = None
    min_desktop_version: str | None = Field(default=None, max_length=20)


class SandboxFile(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=MAX_FILES_BYTES)
    executable: bool = False

    @field_validator("path")
    @classmethod
    def _path(cls, v: str) -> str:
        v = v.strip()
        if not FILE_PATH.match(v):
            raise ValueError("a file path is relative, uses / and has no '..'")
        return v


class SandboxTest(BaseModel):
    name: str = Field(default="", max_length=120)
    stdin: str = Field(default="", max_length=100_000)
    expected: str = Field(default="", max_length=100_000)
    hidden: bool = False
    compare: Compare = "text"


class Tests(BaseModel):
    kind: Literal["io", "command"] = "io"
    command: str = Field(default="", max_length=2000)
    timeout_s: int = Field(default=10, ge=1, le=300)
    cases: list[SandboxTest] = Field(default_factory=list, max_length=MAX_TESTS)


def _files(v: list[SandboxFile]) -> list[SandboxFile]:
    if len(v) > MAX_FILES:
        raise ValueError(f"at most {MAX_FILES} files")
    if sum(len(f.content) for f in v) > MAX_FILES_BYTES:
        raise ValueError("files are larger than 2 MB together")
    if len({f.path for f in v}) != len(v):
        raise ValueError("two files have the same path")
    return v


class AssignmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    statement: str = Field(default="", max_length=50_000)
    files: list[SandboxFile] = Field(default_factory=list)
    open: list[str] = Field(default_factory=list, max_length=20)
    run: str = Field(default="", max_length=2000)
    tests: Tests = Field(default_factory=Tests)
    solution_files: list[SandboxFile] = Field(default_factory=list)

    _f = field_validator("files", "solution_files")(classmethod(lambda cls, v: _files(v)))


class AssignmentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    statement: str | None = Field(default=None, max_length=50_000)
    files: list[SandboxFile] | None = None
    open: list[str] | None = Field(default=None, max_length=20)
    run: str | None = Field(default=None, max_length=2000)
    tests: Tests | None = None
    solution_files: list[SandboxFile] | None = None

    _f = field_validator("files", "solution_files")(classmethod(lambda cls, v: v if v is None else _files(v)))


class OrderIn(BaseModel):
    assignment_ids: list[str]


class ShareIn(BaseModel):
    summary: str = Field(default="", max_length=2000)
    topics: list[str] = Field(default_factory=list, max_length=20)
    difficulty: Literal["", "intro", "intermediate", "advanced"] = ""


class UseIn(BaseModel):
    subject_id: str


# -- recipes → Dockerfile


def recipe_packages(recipe: dict) -> dict[str, list[str]]:
    """Every apt, pip and npm package a recipe installs, in a stable order."""
    apt = [*COMMON_APT, *BASES[recipe["base"]]["apt"]]
    pip, npm = [], []
    for t in recipe.get("tools", []):
        tool = TOOL_BY_ID[t]
        apt += tool.get("apt", [])
        pip += tool.get("pip", [])
        npm += tool.get("npm", [])
    apt += recipe.get("apt", [])
    pip += recipe.get("pip", [])
    npm += recipe.get("npm", [])
    if pip:
        apt += ["python3", "python3-pip"]
    if npm:
        apt += ["nodejs", "npm"]
    return {k: list(dict.fromkeys(v)) for k, v in (("apt", apt), ("pip", pip), ("npm", npm))}


def recipe_size_mb(recipe: dict) -> int:
    """Rough image size for the live size meter: base + each ticked tool."""
    return BASE_MB + BASES[recipe["base"]]["mb"] + sum(
        TOOL_BY_ID[t]["mb"] for t in recipe.get("tools", []) if t not in recipe_base_tools(recipe["base"]))


def recipe_base_tools(base: str) -> set[str]:
    """Tools whose packages the base already has, so they don't count twice."""
    have = set(BASES[base]["apt"])
    return {t["id"] for t in TOOLS if t.get("apt") and not t.get("pip") and not t.get("npm") and set(t["apt"]) <= have}


def dockerfile(env_id: str, version: int, recipe: dict) -> str:
    """The image a recipe describes. Ubuntu 24.04, a `student` user (uid 1000,
    passwordless sudo), every package quoted, `sleep infinity` so the runtime
    can keep the instance up and exec into it."""
    if recipe.get("dockerfile"):
        return recipe["dockerfile"].rstrip() + "\n"
    p = recipe_packages(recipe)
    q = lambda xs: " ".join(shlex.quote(x) for x in xs)
    lines = [
        "# syntax=docker/dockerfile:1",
        f"# Generated by Student IDE from environment {env_id} version {version}. Do not edit; change the recipe.",
        "FROM ubuntu:24.04",
        "ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8",
        "RUN apt-get update \\",
        f"    && apt-get install -y --no-install-recommends {q(p['apt'])} \\",
        "    && rm -rf /var/lib/apt/lists/*",
        "RUN (userdel -r ubuntu 2>/dev/null || true) \\",
        "    && useradd -m -u 1000 -s /bin/bash student \\",
        "    && echo 'student ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/student \\",
        # sudo apt/pip must keep the registries proxy, or "registries only" breaks every install
        "    && echo 'Defaults env_keep += \"http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY\"' >> /etc/sudoers.d/student \\",
        "    && chmod 0440 /etc/sudoers.d/student \\",
        "    && mkdir -p /home/student/labs && chown -R student:student /home/student",
    ]
    if p["pip"]:
        lines.append(f"RUN pip install --no-cache-dir --break-system-packages {q(p['pip'])}")
    if p["npm"]:
        lines.append(f"RUN npm install -g {q(p['npm'])} && npm cache clean --force")
    if recipe.get("setup", "").strip():
        lines += ["RUN <<'STUDENTIDE_SETUP'", "set -eux", recipe["setup"].rstrip(), "STUDENTIDE_SETUP"]
    lines += [
        f'LABEL studentide.environment="{env_id}" studentide.version="{version}"',
        "USER student",
        "WORKDIR /home/student",
        'CMD ["sleep", "infinity"]',
    ]
    return "\n".join(lines) + "\n"


# -- rosters


ROLL = re.compile(r"^(.*?)(\d+)$")


def expand_roster(text: str, to_id: Callable[[str], str]) -> list[dict]:
    """Pasted roster text -> [{id, section}]. Ids or addresses separated by
    commas, spaces or lines; "UG24CS001 to UG24CS060" (or "-") expands; a line
    starting "A:" puts everything on it in section A."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        section = ""
        m = re.match(r"^\s*([A-Za-z0-9]{1,8})\s*:\s*(.*)$", line)
        if m and "@" not in m.group(1):
            section, line = m.group(1).upper(), m.group(2)
        line = re.sub(r"\s+(?:to|–|—)\s+|\s*-\s*(?=[A-Za-z]{0,6}\d)", " … ", line, flags=re.I)
        tokens = [t for t in re.split(r"[\s,;]+", line) if t]
        i = 0
        while i < len(tokens):
            if i + 2 < len(tokens) and tokens[i + 1] == "…":
                a, b = to_id(tokens[i]), to_id(tokens[i + 2])
                ma, mb = ROLL.match(a), ROLL.match(b)
                if not (ma and mb and (ma.group(1) == mb.group(1) or not mb.group(1))):
                    raise HTTPException(400, f"can't expand the range {tokens[i]} to {tokens[i + 2]}")
                lo, hi, width = int(ma.group(2)), int(mb.group(2)), len(ma.group(2))
                if hi < lo or hi - lo > 1000:
                    raise HTTPException(400, f"the range {tokens[i]} to {tokens[i + 2]} is backwards or over 1000 long")
                for n in range(lo, hi + 1):
                    out[f"{ma.group(1)}{n:0{width}d}"] = section
                i += 3
                continue
            if tokens[i] != "…":
                out[to_id(tokens[i])] = section
            i += 1
    return [{"id": k, "section": v} for k, v in out.items()]


# -- storage


def ensure_schema(db: Database) -> None:
    with db.connect() as conn:
        conn.executescript(SCHEMA)


def _now() -> float:
    return time.time()


def _new(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class Store:
    """Queries for the sbx_* tables."""

    def __init__(self, db: Database):
        self.db = db
        ensure_schema(db)

    def q(self, sql: str, args=()) -> list:
        with self.db.connect() as conn:
            return conn.execute(sql, args).fetchall()

    def one(self, sql: str, args=()):
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def x(self, sql: str, args=()) -> None:
        with self.db.connect() as conn:
            conn.execute(sql, args)

    def update(self, table: str, key: str, value, fields: dict) -> None:
        if not fields:
            return
        fields = dict(fields, updated_at=_now()) if table != "sbx_library" else fields
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.x(f"UPDATE {table} SET {cols} WHERE {key} = ?", (*fields.values(), value))

    # environments
    def create_environment(self, title: str, owner: str | None, recipe: dict, shared: bool = False) -> str:
        env_id, now = _new("env"), _now()
        self.x("INSERT INTO sbx_environments VALUES (?,?,?,?,?,?)", (env_id, title, owner, int(shared), now, now))
        self.add_version(env_id, recipe)
        return env_id

    def add_version(self, env_id: str, recipe: dict, approved_by: str | None = None) -> int:
        now = _now()
        v = (self.one("SELECT MAX(version) FROM sbx_env_versions WHERE environment_id = ?", (env_id,))[0] or 0) + 1
        status = "needs_approval" if recipe.get("dockerfile") and not approved_by else "queued"
        self.x("INSERT INTO sbx_env_versions VALUES (?,?,?,?,?,?,?,?,?)",
               (env_id, v, json.dumps(recipe), status, None, "", approved_by, now, now))
        return v

    def env_versions(self, env_id: str) -> list:
        return self.q("SELECT * FROM sbx_env_versions WHERE environment_id = ? ORDER BY version", (env_id,))

    def env_version(self, env_id: str, v: int):
        return self.one("SELECT * FROM sbx_env_versions WHERE environment_id = ? AND version = ?", (env_id, v))

    def newest_version(self, env_id: str, ready_only: bool = False):
        extra = "AND status = 'ready'" if ready_only else ""
        return self.one(f"SELECT * FROM sbx_env_versions WHERE environment_id = ? {extra} ORDER BY version DESC LIMIT 1",
                        (env_id,))

    # subjects
    def subject_ids(self, email: str) -> set[str]:
        return {r[0] for r in self.q("SELECT id FROM sbx_subjects WHERE owner_email = ? "
                                      "UNION SELECT subject_id FROM sbx_subject_people WHERE email = ?", (email, email))}

    def people(self, subject_id: str) -> dict[str, list[str]]:
        out = {"co_teachers": [], "tas": []}
        for r in self.q("SELECT email, role FROM sbx_subject_people WHERE subject_id = ? ORDER BY email", (subject_id,)):
            out["co_teachers" if r["role"] == "co_teacher" else "tas"].append(r["email"])
        return out

    def roster(self, subject_id: str) -> list[dict]:
        return [dict(r) for r in self.q("SELECT student_id AS id, section FROM sbx_subject_students "
                                        "WHERE subject_id = ? ORDER BY student_id", (subject_id,))]

    def labs(self, subject_id: str) -> list:
        return self.q("SELECT * FROM sbx_labs WHERE subject_id = ? ORDER BY created_at", (subject_id,))

    def assignments(self, lab_id: str) -> list:
        return self.q("SELECT * FROM sbx_assignments WHERE lab_id = ? ORDER BY position, created_at", (lab_id,))

    def bump(self, lab_id: str) -> None:
        self.x("UPDATE sbx_labs SET version = version + 1, updated_at = ? WHERE id = ?", (_now(), lab_id))

    def add_assignment(self, lab_id: str, a: dict) -> str:
        aid, now = _new("asg"), _now()
        pos = (self.one("SELECT MAX(position) FROM sbx_assignments WHERE lab_id = ?", (lab_id,))[0] or -1) + 1
        self.x("INSERT INTO sbx_assignments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
               (aid, lab_id, pos, a["title"], a.get("statement", ""), json.dumps(a.get("files", [])),
                json.dumps(a.get("open", [])), a.get("run", ""), json.dumps(a.get("tests", {})),
                json.dumps(a.get("solution_files", [])), now, now))
        return aid

    def create_lab(self, subject_id: str, title: str, description: str = "", **extra) -> str:
        lab_id, now = _new("slab"), _now()
        self.x("INSERT INTO sbx_labs (id, subject_id, title, description, created_at, updated_at) VALUES (?,?,?,?,?,?)",
               (lab_id, subject_id, title, description, now, now))
        if extra:
            self.update("sbx_labs", "id", lab_id, extra)
        return lab_id

    def copy_lab(self, lab, subject_id: str, **extra) -> str:
        """An independent draft copy of a lab (row) with its assignments."""
        new = self.create_lab(subject_id, lab["title"], lab["description"], network=lab["network"],
                              assessed=lab["assessed"], min_desktop_version=lab["min_desktop_version"], **extra)
        for a in self.assignments(lab["id"]):
            self.add_assignment(new, assignment_fields(a))
        return new


def assignment_fields(a) -> dict:
    """An assignment row -> the dict add_assignment takes."""
    return {"title": a["title"], "statement": a["statement"], "files": json.loads(a["files_json"]),
            "open": json.loads(a["open_json"]), "run": a["run"], "tests": json.loads(a["tests_json"]),
            "solution_files": json.loads(a["solution_json"])}


# -- what the API shows


def env_json(store: Store, env, me_email: str | None = None) -> dict:
    d = dict(env)
    d["shared"] = bool(d["shared"])
    d["versions"] = [version_json(env["id"], v) for v in store.env_versions(env["id"])]
    d["mine"] = me_email is None or env["owner_email"] == me_email
    return d


def version_json(env_id: str, v) -> dict:
    recipe = json.loads(v["recipe_json"])
    return {"version": v["version"], "status": v["status"], "digest": v["digest"], "log": v["log"],
            "recipe": recipe, "image": image_name(env_id, v["version"]),
            "size_mb": None if recipe.get("dockerfile") else recipe_size_mb(recipe),
            "approved_by": v["approved_by"], "updated_at": v["updated_at"]}


def tests_for(raw: str, student: bool) -> dict:
    t = Tests.model_validate(json.loads(raw) if raw else {}).model_dump()
    cases = t.pop("cases")
    if student:
        t["visible"] = [{k: c[k] for k in ("name", "stdin", "expected", "compare")} for c in cases if not c["hidden"]]
        t["n_hidden"] = sum(1 for c in cases if c["hidden"])
    else:
        t["cases"] = cases
    return t


def definition(store: Store, lab, student: bool = True) -> dict:
    """The lab in format studentide.sandbox-lab/1 (docs/sandbox-labs.md).
    `student`: without hidden tests or the reference solution."""
    subj = store.one("SELECT * FROM sbx_subjects WHERE id = ?", (lab["subject_id"],))
    env = None
    if subj["environment_id"]:
        e = store.one("SELECT * FROM sbx_environments WHERE id = ?", (subj["environment_id"],))
        v = (store.env_version(e["id"], lab["env_version"]) if lab["env_version"] else
             store.newest_version(e["id"], ready_only=True) or store.newest_version(e["id"]))
        recipe = json.loads(v["recipe_json"])
        if student:
            recipe = {k: val for k, val in recipe.items() if k != "dockerfile"} | (
                {"dockerfile": "(raw Dockerfile, built by the server)"} if recipe.get("dockerfile") else {})
        env = {"id": e["id"], "version": v["version"], "title": e["title"], "image": image_name(e["id"], v["version"]),
               "digest": v["digest"], "status": v["status"], "recipe": recipe,
               "resources": resources(recipe.get("resources"))}
    assignments = []
    for a in store.assignments(lab["id"]):
        item = {"id": a["id"], "position": a["position"], "title": a["title"], "statement": a["statement"],
                "workdir": f"/home/student/labs/{lab['id']}/{a['id']}", "files": json.loads(a["files_json"]),
                "open": json.loads(a["open_json"]), "run": a["run"], "tests": tests_for(a["tests_json"], student)}
        if not student:
            item["solution_files"] = json.loads(a["solution_json"])
        assignments.append(item)
    return {
        "format": FORMAT, "id": lab["id"], "version": lab["version"], "title": lab["title"],
        "description": lab["description"],
        "subject": {"id": subj["id"], "code": subj["code"], "title": subj["title"]},
        "environment": env,
        "instance": {"name": f"sid-{{student}}-{subj['id']}", "volume": f"sidv-{{student}}-{subj['id']}",
                     "user": "student", "home": "/home/student"},
        "network": lab["network"], "assessed": bool(lab["assessed"]), "status": lab["status"],
        "opens_at": lab["opens_at"], "due_at": lab["due_at"], "min_desktop_version": lab["min_desktop_version"],
        "assignments": assignments, "updated_at": lab["updated_at"],
    }


def lab_row_json(store: Store, lab) -> dict:
    d = dict(lab)
    d["assessed"] = bool(d["assessed"])
    d["sections"] = json.loads(d.pop("sections_json"))
    d["n_assignments"] = len(store.assignments(lab["id"]))
    lib = store.one("SELECT id, version, withdrawn_at FROM sbx_library WHERE lab_id = ?", (lab["id"],))
    d["shared"] = bool(lib and lib["withdrawn_at"] is None)
    if lab["based_on"]:
        src = store.one("SELECT version, withdrawn_at FROM sbx_library WHERE id = ?", (lab["based_on"],))
        d["update_available"] = bool(src and src["withdrawn_at"] is None and src["version"] > (lab["based_on_version"] or 0))
    return d


def lab_problems(d: dict) -> list[str]:
    """What would stop a lab from being published, in plain words."""
    out = []
    if not d["assignments"]:
        out.append("Add at least one assignment.")
    if d["environment"] is None:
        out.append("The subject has no environment yet.")
    for a in d["assignments"]:
        t = a["tests"]
        if t["kind"] == "command" and not t["command"].strip():
            out.append(f"{a['title']}: the test command is empty.")
        if t["kind"] == "io" and t["cases"] and not a["run"].strip():
            out.append(f"{a['title']}: input/output tests need a Run command to feed.")
    return out


# -- routes


def router(db: Database, require_teacher: Callable, auth) -> APIRouter:
    """Teacher routes under /api/sandbox (sign-in like /api/teach); the student
    routes under /api/sandbox/my and the build-service callback are on
    `.student_router`, which has no teacher dependency."""
    store = Store(db)
    r = APIRouter(prefix="/api/sandbox", dependencies=[Depends(require_teacher)])
    open_r = APIRouter(prefix="/api/sandbox")

    def me(request: Request):
        return auth.teacher(request)

    def subject_access(request: Request, subject_id: str, write: bool = True):
        subj = store.one("SELECT * FROM sbx_subjects WHERE id = ?", (subject_id,))
        if subj is None:
            raise HTTPException(404, "unknown subject")
        t = me(request)
        if t.admin:
            return subj, "admin"
        if subj["owner_email"] == t.email:
            return subj, "owner"
        role = store.one("SELECT role FROM sbx_subject_people WHERE subject_id = ? AND email = ?", (subject_id, t.email))
        if role is None:
            raise not_yours("this subject belongs to another teacher")
        if write and role["role"] == "ta":
            raise not_yours("TAs can view this subject but not change it")
        return subj, role["role"]

    def lab_access(request: Request, lab_id: str, write: bool = True):
        lab = store.one("SELECT * FROM sbx_labs WHERE id = ?", (lab_id,))
        if lab is None:
            raise HTTPException(404, "unknown lab")
        subject_access(request, lab["subject_id"], write)
        return lab

    def assignment_access(request: Request, aid: str):
        a = store.one("SELECT * FROM sbx_assignments WHERE id = ?", (aid,))
        if a is None:
            raise HTTPException(404, "unknown assignment")
        lab_access(request, a["lab_id"])
        return a

    def env_access(request: Request, env_id: str, write: bool = False):
        env = store.one("SELECT * FROM sbx_environments WHERE id = ?", (env_id,))
        if env is None:
            raise HTTPException(404, "unknown environment")
        t = me(request)
        if t.admin or env["owner_email"] == t.email:
            return env
        if write:
            raise not_yours("only its author can change this environment; make your own copy")
        users = {r[0] for r in store.q("SELECT id FROM sbx_subjects WHERE environment_id = ?", (env_id,))}
        if not env["shared"] and not users & store.subject_ids(t.email):
            raise not_yours("this environment is not shared")
        return env

    def subject_json(subj, role: str | None = None) -> dict:
        d = dict(subj)
        d["access"] = role
        d.update(store.people(subj["id"]))
        d["n_students"] = store.one("SELECT COUNT(*) FROM sbx_subject_students WHERE subject_id = ?", (subj["id"],))[0]
        labs = store.labs(subj["id"])
        d["n_labs"] = len(labs)
        d["n_published"] = sum(1 for l in labs if l["status"] == "published")
        env = store.one("SELECT * FROM sbx_environments WHERE id = ?", (subj["environment_id"],)) if subj["environment_id"] else None
        if env:
            v = store.newest_version(env["id"])
            d["environment"] = {"id": env["id"], "title": env["title"], "version": v["version"], "status": v["status"],
                                "base": json.loads(v["recipe_json"]).get("base")}
        else:
            d["environment"] = None
        return d

    def lab_detail(lab, request: Request) -> dict:
        d = lab_row_json(store, lab)
        d["definition"] = definition(store, lab, student=False)
        d["problems"] = lab_problems(d["definition"])
        d["access"] = subject_access(request, lab["subject_id"], write=False)[1]
        return d

    # catalogue of bases and tools
    @r.get("/bases")
    def bases() -> list[dict]:
        return [{"id": k, "label": b["label"], "includes": b["includes"], "mb": BASE_MB + b["mb"],
                 "tools": sorted(recipe_base_tools(k))} for k, b in BASES.items()]

    @r.get("/tools")
    def tools() -> list[dict]:
        return TOOLS

    # environments
    @r.get("/environments")
    def environments(request: Request) -> list[dict]:
        t = me(request)
        if t.admin:
            rows = store.q("SELECT * FROM sbx_environments ORDER BY updated_at DESC")
        else:
            rows = store.q("SELECT * FROM sbx_environments WHERE owner_email = ? OR shared = 1 ORDER BY updated_at DESC",
                           (t.email,))
        return [env_json(store, e, t.email) for e in rows]

    @r.post("/environments")
    def create_environment(body: EnvironmentIn, request: Request) -> dict:
        env_id = store.create_environment(body.title.strip(), me(request).email, body.recipe.model_dump(), body.shared)
        return env_json(store, store.one("SELECT * FROM sbx_environments WHERE id = ?", (env_id,)), me(request).email)

    @r.get("/environments/{env_id}")
    def get_environment(env_id: str, request: Request) -> dict:
        return env_json(store, env_access(request, env_id), me(request).email)

    @r.patch("/environments/{env_id}")
    def patch_environment(env_id: str, body: EnvironmentPatch, request: Request) -> dict:
        env_access(request, env_id, write=True)
        f = body.model_dump(exclude_none=True)
        if "shared" in f:
            f["shared"] = int(f["shared"])
        store.update("sbx_environments", "id", env_id, f)
        return get_environment(env_id, request)

    @r.post("/environments/{env_id}/versions")
    def new_version(env_id: str, body: VersionIn, request: Request) -> dict:
        env_access(request, env_id, write=True)
        store.add_version(env_id, body.recipe.model_dump())
        store.x("UPDATE sbx_environments SET updated_at = ? WHERE id = ?", (_now(), env_id))
        return get_environment(env_id, request)

    @r.get("/environments/{env_id}/versions/{v}/dockerfile")
    def get_dockerfile(env_id: str, v: int, request: Request) -> dict:
        env_access(request, env_id)
        ver = store.env_version(env_id, v)
        if ver is None:
            raise HTTPException(404, "unknown version")
        return {"image": image_name(env_id, v), "dockerfile": dockerfile(env_id, v, json.loads(ver["recipe_json"]))}

    @r.post("/environments/{env_id}/versions/{v}/approve")
    def approve(env_id: str, v: int, request: Request) -> dict:
        t = me(request)
        if not t.admin:
            raise HTTPException(403, "only an admin can approve a raw Dockerfile")
        ver = store.env_version(env_id, v)
        if ver is None or ver["status"] != "needs_approval":
            raise HTTPException(409, "this version is not waiting for approval")
        store.x("UPDATE sbx_env_versions SET status = 'queued', approved_by = ?, updated_at = ? "
                "WHERE environment_id = ? AND version = ?", (t.email or "admin", _now(), env_id, v))
        return get_environment(env_id, request)

    # subjects
    @r.get("/subjects")
    def subjects(request: Request) -> list[dict]:
        t = me(request)
        if t.admin:
            return [subject_json(s, "admin") for s in store.q("SELECT * FROM sbx_subjects ORDER BY updated_at DESC")]
        ids = store.subject_ids(t.email)
        out = []
        for s in store.q("SELECT * FROM sbx_subjects ORDER BY updated_at DESC"):
            if s["id"] in ids:
                out.append(subject_json(s, subject_access(request, s["id"], write=False)[1]))
        return out

    @r.post("/subjects")
    def create_subject(body: SubjectIn, request: Request) -> dict:
        t = me(request)
        env_id = body.environment_id
        if env_id:
            env_access(request, env_id)
        elif body.recipe is not None:
            label = BASES[body.recipe.base]["label"]
            env_id = store.create_environment(f"{body.code or body.title} ({label})".strip(), t.email,
                                              body.recipe.model_dump())
        sid, now = _new("subj"), _now()
        color = body.color if body.color in COLORS else COLORS[secrets.randbelow(len(COLORS))]
        store.x("INSERT INTO sbx_subjects VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sid, body.title.strip(), body.code.strip().upper(), body.semester.strip(), color, t.email, env_id,
                 None, now, now))
        return get_subject(sid, request)

    @r.get("/subjects/{subject_id}")
    def get_subject(subject_id: str, request: Request) -> dict:
        subj, role = subject_access(request, subject_id, write=False)
        d = subject_json(subj, role)
        d["labs"] = [lab_row_json(store, l) for l in store.labs(subject_id)]
        d["roster"] = store.roster(subject_id)
        return d

    @r.patch("/subjects/{subject_id}")
    def patch_subject(subject_id: str, body: SubjectPatch, request: Request) -> dict:
        subject_access(request, subject_id)
        f = body.model_dump(exclude_none=True)
        if "owner_email" in f:
            if not me(request).admin:
                raise HTTPException(403, "only an admin can change who owns a subject")
            f["owner_email"] = f["owner_email"].strip().lower() or None
        if "environment_id" in f:
            env_access(request, f["environment_id"])
        if "color" in f and f["color"] not in COLORS:
            raise HTTPException(400, f"colour is one of {', '.join(COLORS)}")
        if "code" in f:
            f["code"] = f["code"].strip().upper()
        store.update("sbx_subjects", "id", subject_id, f)
        return get_subject(subject_id, request)

    @r.delete("/subjects/{subject_id}")
    def delete_subject(subject_id: str, request: Request) -> dict:
        subj, role = subject_access(request, subject_id)
        if role not in ("owner", "admin"):
            raise not_yours("only the subject's owner can delete it")
        if any(l["status"] != "draft" for l in store.labs(subject_id)):
            raise HTTPException(409, "this subject has published labs; close them instead")
        store.x("DELETE FROM sbx_subjects WHERE id = ?", (subject_id,))
        return {"deleted": subject_id}

    @r.put("/subjects/{subject_id}/people")
    def put_people(subject_id: str, body: PeopleIn, request: Request) -> dict:
        subj, role = subject_access(request, subject_id)
        if role not in ("owner", "admin"):
            raise not_yours("only the subject's owner can change who it is shared with")
        clean = lambda xs: [e.strip().lower() for e in xs if e.strip() and e.strip().lower() != subj["owner_email"]]
        with db.connect() as conn:
            conn.execute("DELETE FROM sbx_subject_people WHERE subject_id = ?", (subject_id,))
            for role_name, emails in (("ta", clean(body.tas)), ("co_teacher", clean(body.co_teachers))):
                conn.executemany("INSERT OR REPLACE INTO sbx_subject_people VALUES (?,?,?)",
                                 [(subject_id, e, role_name) for e in emails])
        return get_subject(subject_id, request)

    @r.put("/subjects/{subject_id}/roster")
    def put_roster(subject_id: str, body: RosterIn, request: Request) -> dict:
        subject_access(request, subject_id)
        to_id = lambda raw: roster_id(raw, auth.cfg)
        if body.text is not None:
            students = expand_roster(body.text, to_id)
        else:
            students = [{"id": to_id(s.id), "section": s.section.strip().upper()} for s in body.students or []]
        bad = [s["id"] for s in students if not re.match(r"^[A-Za-z0-9_-]{1,32}$", s["id"])]
        if bad:
            raise HTTPException(400, f"not a roll number: {', '.join(bad[:5])}")
        if len(students) > 3000:
            raise HTTPException(400, "a subject holds at most 3000 students")
        with db.connect() as conn:
            conn.execute("DELETE FROM sbx_subject_students WHERE subject_id = ?", (subject_id,))
            conn.executemany("INSERT INTO sbx_subject_students VALUES (?,?,?)",
                             [(subject_id, s["id"], s["section"]) for s in students])
        return get_subject(subject_id, request)

    @r.post("/subjects/{subject_id}/copy")
    def copy_subject(subject_id: str, body: CopyIn, request: Request) -> dict:
        subj, _ = subject_access(request, subject_id, write=False)
        new, now = _new("subj"), _now()
        store.x("INSERT INTO sbx_subjects VALUES (?,?,?,?,?,?,?,?,?,?)",
                (new, (body.title or subj["title"]).strip(), subj["code"], body.semester.strip(), subj["color"],
                 me(request).email, subj["environment_id"], subject_id, now, now))
        for lab in store.labs(subject_id):
            store.copy_lab(lab, new)
        return get_subject(new, request)

    # labs
    @r.post("/subjects/{subject_id}/labs")
    def create_lab(subject_id: str, body: LabIn, request: Request) -> dict:
        subject_access(request, subject_id)
        lab_id = store.create_lab(subject_id, body.title.strip(), body.description)
        return lab_detail(store.one("SELECT * FROM sbx_labs WHERE id = ?", (lab_id,)), request)

    @r.get("/labs/{lab_id}")
    def get_lab(lab_id: str, request: Request) -> dict:
        return lab_detail(lab_access(request, lab_id, write=False), request)

    @r.get("/labs/{lab_id}/definition")
    def get_definition(lab_id: str, request: Request) -> dict:
        return definition(store, lab_access(request, lab_id, write=False), student=True)

    @r.patch("/labs/{lab_id}")
    def patch_lab(lab_id: str, body: LabPatch, request: Request) -> dict:
        lab = lab_access(request, lab_id)
        f = body.model_dump(exclude_unset=True)
        for k in ("title", "description", "status", "network", "assessed", "sections", "environment_version"):
            if k in f and f[k] is None:
                del f[k]
        network = f.get("network", lab["network"])
        assessed = f.get("assessed", bool(lab["assessed"]))
        if assessed and network == "open":
            raise HTTPException(400, "an assessed lab can use registries only or no network, never open")
        if "assessed" in f:
            f["assessed"] = int(f["assessed"])
        if "sections" in f:
            f["sections_json"] = json.dumps([s.strip().upper() for s in f.pop("sections") if s.strip()])
        if "environment_version" in f:
            subj = store.one("SELECT environment_id FROM sbx_subjects WHERE id = ?", (lab["subject_id"],))
            if not subj["environment_id"] or store.env_version(subj["environment_id"], f["environment_version"]) is None:
                raise HTTPException(400, "the subject's environment has no such version")
            f["env_version"] = f.pop("environment_version")
        if f.get("status") == "published" and lab["status"] != "published":
            d = definition(store, lab, student=False)
            problems = lab_problems(d)
            if problems:
                raise HTTPException(409, " ".join(problems))
            if lab["env_version"] is None and "env_version" not in f:  # running labs keep the version they started with
                f["env_version"] = d["environment"]["version"]
        store.update("sbx_labs", "id", lab_id, f)
        store.bump(lab_id)
        return get_lab(lab_id, request)

    @r.delete("/labs/{lab_id}")
    def delete_lab(lab_id: str, request: Request) -> dict:
        lab = lab_access(request, lab_id)
        if lab["status"] != "draft":
            raise HTTPException(409, "only a draft lab can be deleted; close it instead")
        store.x("DELETE FROM sbx_labs WHERE id = ?", (lab_id,))
        return {"deleted": lab_id}

    @r.post("/labs/{lab_id}/assignments")
    def add_assignment(lab_id: str, body: AssignmentIn, request: Request) -> dict:
        lab_access(request, lab_id)
        store.add_assignment(lab_id, body.model_dump())
        store.bump(lab_id)
        return get_lab(lab_id, request)

    @r.patch("/assignments/{aid}")
    def patch_assignment(aid: str, body: AssignmentPatch, request: Request) -> dict:
        a = assignment_access(request, aid)
        f = body.model_dump(exclude_none=True)
        cols = {}
        for k, col in (("files", "files_json"), ("open", "open_json"), ("tests", "tests_json"),
                       ("solution_files", "solution_json")):
            if k in f:
                cols[col] = json.dumps(f.pop(k))
        store.update("sbx_assignments", "id", aid, f | cols)
        store.bump(a["lab_id"])
        return get_lab(a["lab_id"], request)

    @r.delete("/assignments/{aid}")
    def delete_assignment(aid: str, request: Request) -> dict:
        a = assignment_access(request, aid)
        lab = store.one("SELECT status FROM sbx_labs WHERE id = ?", (a["lab_id"],))
        if lab["status"] != "draft":
            raise HTTPException(409, "students may have started this assignment; it can't be removed from a published lab")
        store.x("DELETE FROM sbx_assignments WHERE id = ?", (aid,))
        store.bump(a["lab_id"])
        return get_lab(a["lab_id"], request)

    @r.put("/labs/{lab_id}/order")
    def order(lab_id: str, body: OrderIn, request: Request) -> dict:
        lab_access(request, lab_id)
        have = {a["id"] for a in store.assignments(lab_id)}
        if set(body.assignment_ids) != have:
            raise HTTPException(400, "send every assignment of the lab exactly once")
        with db.connect() as conn:
            conn.executemany("UPDATE sbx_assignments SET position = ? WHERE id = ?",
                             [(i, aid) for i, aid in enumerate(body.assignment_ids)])
        store.bump(lab_id)
        return get_lab(lab_id, request)

    # library
    def library_json(e, full: bool = False) -> dict:
        d = {k: e[k] for k in ("id", "lab_id", "shared_by", "title", "summary", "subject_title", "difficulty", "base",
                               "version", "uses", "shared_at")}
        d["topics"] = json.loads(e["topics_json"])
        snap = json.loads(e["snapshot_json"])
        d["n_assignments"] = len(snap["assignments"])
        if full:
            d["lab"] = snap
        return d

    @r.post("/labs/{lab_id}/share")
    def share(lab_id: str, body: ShareIn, request: Request) -> dict:
        lab = lab_access(request, lab_id)
        snap = definition(store, lab, student=False)
        if not snap["assignments"]:
            raise HTTPException(409, "add an assignment before sharing")
        base = (snap["environment"] or {}).get("recipe", {}).get("base", "")
        subj = store.one("SELECT title FROM sbx_subjects WHERE id = ?", (lab["subject_id"],))
        topics = json.dumps([t.strip() for t in body.topics if t.strip()][:20])
        old = store.one("SELECT * FROM sbx_library WHERE lab_id = ?", (lab_id,))
        if old:
            store.x("""UPDATE sbx_library SET title = ?, summary = ?, subject_title = ?, topics_json = ?, difficulty = ?,
                       base = ?, snapshot_json = ?, version = version + 1, shared_at = ?, withdrawn_at = NULL,
                       shared_by = ? WHERE id = ?""",
                    (lab["title"], body.summary, subj["title"], topics, body.difficulty, base, json.dumps(snap), _now(),
                     me(request).email, old["id"]))
            entry_id = old["id"]
        else:
            entry_id = _new("lib")
            store.x("INSERT INTO sbx_library VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (entry_id, lab_id, me(request).email, lab["title"], body.summary, subj["title"], topics,
                     body.difficulty, base, json.dumps(snap), 1, 0, _now(), None))
        return library_json(store.one("SELECT * FROM sbx_library WHERE id = ?", (entry_id,)))

    @r.delete("/labs/{lab_id}/share")
    def unshare(lab_id: str, request: Request) -> dict:
        lab_access(request, lab_id)
        store.x("UPDATE sbx_library SET withdrawn_at = ? WHERE lab_id = ?", (_now(), lab_id))
        return {"withdrawn": lab_id}

    @r.get("/library")
    def library(q: str = "", subject: str = "", topic: str = "", difficulty: str = "", base: str = "") -> list[dict]:
        out = []
        for e in store.q("SELECT * FROM sbx_library WHERE withdrawn_at IS NULL ORDER BY uses DESC, shared_at DESC"):
            hay = " ".join([e["title"], e["summary"], e["subject_title"], e["topics_json"]]).lower()
            if q and not all(w in hay for w in q.lower().split()):
                continue
            if subject and subject.lower() not in e["subject_title"].lower():
                continue
            if topic and topic.lower() not in e["topics_json"].lower():
                continue
            if (difficulty and e["difficulty"] != difficulty) or (base and e["base"] != base):
                continue
            out.append(library_json(e))
        return out

    @r.get("/library/{entry_id}")
    def library_entry(entry_id: str) -> dict:
        e = store.one("SELECT * FROM sbx_library WHERE id = ? AND withdrawn_at IS NULL", (entry_id,))
        if e is None:
            raise HTTPException(404, "this lab is no longer in the library")
        return library_json(e, full=True)

    @r.post("/library/{entry_id}/use")
    def use(entry_id: str, body: UseIn, request: Request) -> dict:
        e = store.one("SELECT * FROM sbx_library WHERE id = ? AND withdrawn_at IS NULL", (entry_id,))
        if e is None:
            raise HTTPException(404, "this lab is no longer in the library")
        subject_access(request, body.subject_id)
        snap = json.loads(e["snapshot_json"])
        lab_id = store.create_lab(body.subject_id, snap["title"], snap["description"], network=snap["network"],
                                  assessed=int(snap["assessed"]), min_desktop_version=snap.get("min_desktop_version"),
                                  based_on=entry_id, based_on_version=e["version"])
        for a in snap["assignments"]:
            t = a["tests"]
            store.add_assignment(lab_id, {"title": a["title"], "statement": a["statement"], "files": a["files"],
                                          "open": a["open"], "run": a["run"], "solution_files": a.get("solution_files", []),
                                          "tests": {k: t[k] for k in ("kind", "command", "timeout_s", "cases")}})
        store.x("UPDATE sbx_library SET uses = uses + 1 WHERE id = ?", (entry_id,))
        return get_lab(lab_id, request)

    # build service (outside the VM): list what to build, report back. Token, not a teacher account.
    def build_token(request: Request) -> None:
        tok = os.environ.get("STUDENTIDE_BUILD_TOKEN")
        if not tok:
            raise HTTPException(403, "image builds are disabled: set STUDENTIDE_BUILD_TOKEN")
        if not secrets.compare_digest(request.headers.get("x-build-token", ""), tok):
            raise HTTPException(401, "bad build token")

    @open_r.get("/builds")
    def builds(request: Request, status: str = "queued") -> list[dict]:
        build_token(request)
        rows = store.q("SELECT * FROM sbx_env_versions WHERE status = ? ORDER BY created_at", (status,))
        if status == "queued":  # a builder that died mid-build: hand its job out again after 2 h
            rows += store.q("SELECT * FROM sbx_env_versions WHERE status = 'building' AND updated_at < ? "
                            "ORDER BY created_at", (_now() - 7200,))
        return [{"environment_id": v["environment_id"], "version": v["version"],
                 "image": image_name(v["environment_id"], v["version"]),
                 "dockerfile": dockerfile(v["environment_id"], v["version"], json.loads(v["recipe_json"]))} for v in rows]

    @open_r.post("/builds/{env_id}/{v}")
    def report(env_id: str, v: int, body: BuildReport, request: Request) -> dict:
        build_token(request)
        ver = store.env_version(env_id, v)
        if ver is None:
            raise HTTPException(404, "unknown version")
        if ver["status"] == "needs_approval":
            raise HTTPException(409, "an admin has not approved this Dockerfile")
        if body.status == "ready" and not body.digest:
            raise HTTPException(400, "a ready image needs its digest")
        store.x("UPDATE sbx_env_versions SET status = ?, digest = COALESCE(?, digest), log = ?, updated_at = ? "
                "WHERE environment_id = ? AND version = ?", (body.status, body.digest, body.log[-20_000:], _now(), env_id, v))
        return version_json(env_id, store.env_version(env_id, v))

    # students (desktop app; same sign-in cookie as the web app)
    def student_of(request: Request, student_id: str | None) -> str:
        if auth.cfg.google:
            user = auth.current(request)
            if user is None:
                raise HTTPException(401, "sign in first")
            return user["student_id"]
        if not student_id or not re.match(r"^[A-Za-z0-9_-]{1,32}$", student_id):
            raise HTTPException(400, "student_id is required in dev mode")
        return student_id

    def visible_labs(student_id: str) -> list:
        now = _now()
        rows = store.q("""SELECT l.*, s.section FROM sbx_labs l JOIN sbx_subject_students s ON s.subject_id = l.subject_id
                          WHERE s.student_id = ? AND l.status = 'published' AND (l.opens_at IS NULL OR l.opens_at <= ?)
                          ORDER BY l.created_at""", (student_id, now))
        return [l for l in rows if not json.loads(l["sections_json"]) or l["section"] in json.loads(l["sections_json"])]

    @open_r.get("/my/labs")
    def my_labs(request: Request, student_id: str | None = None) -> list[dict]:
        sid = student_of(request, student_id)
        by: dict[str, dict] = {}
        for lab in visible_labs(sid):
            subj = store.one("SELECT * FROM sbx_subjects WHERE id = ?", (lab["subject_id"],))
            g = by.setdefault(subj["id"], {"id": subj["id"], "title": subj["title"], "code": subj["code"],
                                           "semester": subj["semester"], "color": subj["color"], "labs": []})
            g["labs"].append({"id": lab["id"], "version": lab["version"], "title": lab["title"],
                              "description": lab["description"], "due_at": lab["due_at"], "assessed": bool(lab["assessed"]),
                              "network": lab["network"], "min_desktop_version": lab["min_desktop_version"],
                              "n_assignments": len(store.assignments(lab["id"]))})
        return list(by.values())

    @open_r.get("/my/labs/{lab_id}")
    def my_lab(lab_id: str, request: Request, student_id: str | None = None) -> dict:
        sid = student_of(request, student_id)
        lab = next((l for l in visible_labs(sid) if l["id"] == lab_id), None)
        if lab is None:
            raise HTTPException(404, "this lab is not open for you")
        return definition(store, store.one("SELECT * FROM sbx_labs WHERE id = ?", (lab_id,)), student=True)

    r.store = store  # previews.py reads lab definitions through it
    r.lab_access = lab_access
    r.student_router = open_r
    return r

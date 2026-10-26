"""SQLite storage. One file holds every student, session, event and run.

SQLite is plenty for a lab of ~80 students (WAL mode handles concurrent
writers fine at this rate) and the file is easy to hand to the analysis
code in later phases. Each request opens its own short-lived connection.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id            TEXT PRIMARY KEY,          -- roll number / pseudonymous id
    consented_at  REAL,                      -- unix seconds; NULL = no consent yet
    created_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,         -- uuid4 hex
    student_id     TEXT NOT NULL REFERENCES students(id),
    task_id        TEXT NOT NULL,
    started_at     REAL NOT NULL,            -- server unix seconds
    ended_at       REAL,
    end_reason     TEXT,
    schema_version INTEGER NOT NULL,
    client_meta    TEXT NOT NULL             -- JSON: user agent, screen, keyboard layout hint, ...
);
CREATE INDEX IF NOT EXISTS sessions_by_student ON sessions(student_id, started_at);

CREATE TABLE IF NOT EXISTS events (
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    seq          INTEGER NOT NULL,
    t            REAL NOT NULL,              -- ms since session start (client clock)
    type         TEXT NOT NULL,
    data         TEXT NOT NULL,              -- JSON payload, see schema.py
    received_at  REAL NOT NULL,              -- server unix seconds
    PRIMARY KEY (session_id, seq)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS runs (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    created_at   REAL NOT NULL,
    code         TEXT NOT NULL,
    stdin        TEXT NOT NULL,
    stdout       TEXT NOT NULL,
    stderr       TEXT NOT NULL,
    exit_code    INTEGER,
    duration_ms  REAL NOT NULL,
    error_type   TEXT
);
CREATE INDEX IF NOT EXISTS runs_by_session ON runs(session_id, created_at);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # students ---------------------------------------------------------------

    def get_or_create_student(self, student_id: str) -> sqlite3.Row:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO students(id, created_at) VALUES (?, ?)",
                (student_id, time.time()),
            )
            return conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()

    def record_consent(self, student_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE students SET consented_at = COALESCE(consented_at, ?) WHERE id = ?",
                (time.time(), student_id),
            )

    # sessions ---------------------------------------------------------------

    def create_session(self, session_id: str, student_id: str, task_id: str, schema_version: int, client_meta: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO sessions(id, student_id, task_id, started_at, schema_version, client_meta) VALUES (?,?,?,?,?,?)",
                (session_id, student_id, task_id, time.time(), schema_version, json.dumps(client_meta)),
            )

    def get_session(self, session_id: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

    def end_session(self, session_id: str, reason: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = COALESCE(ended_at, ?), end_reason = COALESCE(end_reason, ?) WHERE id = ?",
                (time.time(), reason, session_id),
            )

    def list_sessions(self, student_id: str | None = None) -> list[sqlite3.Row]:
        sql = """SELECT s.*, (SELECT COUNT(*) FROM events e WHERE e.session_id = s.id) AS n_events
                 FROM sessions s"""
        args: tuple = ()
        if student_id is not None:
            sql += " WHERE s.student_id = ?"
            args = (student_id,)
        with self.connect() as conn:
            return conn.execute(sql + " ORDER BY s.started_at", args).fetchall()

    # events -----------------------------------------------------------------

    def insert_events(self, session_id: str, events: list[dict]) -> int:
        """Insert a batch; duplicates (same seq) are ignored so client retries are safe.
        Returns the number of new rows."""
        now = time.time()
        rows = [(session_id, e["seq"], e["t"], e["type"], json.dumps(e["data"]), now) for e in events]
        with self.connect() as conn:
            before = conn.total_changes
            conn.executemany(
                "INSERT OR IGNORE INTO events(session_id, seq, t, type, data, received_at) VALUES (?,?,?,?,?,?)",
                rows,
            )
            return conn.total_changes - before

    def iter_events(self, session_id: str, types: tuple[str, ...] | None = None) -> Iterator[dict]:
        sql = "SELECT seq, t, type, data FROM events WHERE session_id = ?"
        args: list = [session_id]
        if types:
            sql += f" AND type IN ({','.join('?' * len(types))})"
            args.extend(types)
        with self.connect() as conn:
            for row in conn.execute(sql + " ORDER BY seq", args):
                yield {"seq": row["seq"], "t": row["t"], "type": row["type"], "data": json.loads(row["data"])}

    def max_seq(self, session_id: str) -> int | None:
        with self.connect() as conn:
            return conn.execute("SELECT MAX(seq) FROM events WHERE session_id = ?", (session_id,)).fetchone()[0]

    # runs -------------------------------------------------------------------

    def insert_run(self, run: dict) -> None:
        cols = ("id", "session_id", "created_at", "code", "stdin", "stdout", "stderr", "exit_code", "duration_ms", "error_type")
        with self.connect() as conn:
            conn.execute(
                f"INSERT INTO runs({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                tuple(run[c] for c in cols),
            )

    def list_runs(self, session_id: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM runs WHERE session_id = ? ORDER BY created_at", (session_id,)).fetchall()

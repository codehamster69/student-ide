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
    client_meta    TEXT NOT NULL,            -- JSON: user agent, screen, keyboard layout hint, ...
    lab_id         TEXT,                     -- teacher-made lab this session belongs to (NULL = practice task)
    question_id    TEXT,                     -- question within that lab; task_id holds the same id
    question_json  TEXT                      -- JSON copy of the question as the student saw it
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

-- Teacher authoring: a lab is one sitting (a lab class, an assignment, a staged
-- study session) holding ordered questions, assigned to a roster of students.
CREATE TABLE IF NOT EXISTS labs (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'closed')),
    everyone      INTEGER NOT NULL DEFAULT 0,  -- 1 = every consented student, roster ignored
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id            TEXT PRIMARY KEY,
    lab_id        TEXT NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    title         TEXT NOT NULL,
    prompt        TEXT NOT NULL DEFAULT '',
    starter_code  TEXT NOT NULL DEFAULT '',
    sample_input  TEXT NOT NULL DEFAULT '',
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS questions_by_lab ON questions(lab_id, position);

-- No foreign key to students: a teacher can assign roll numbers before those
-- students have ever signed in.
CREATE TABLE IF NOT EXISTS lab_students (
    lab_id        TEXT NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    student_id    TEXT NOT NULL,
    PRIMARY KEY (lab_id, student_id)
) WITHOUT ROWID;
"""

# Columns added after phase 1. Older database files get them on open.
MIGRATIONS = {
    "sessions": (("lab_id", "TEXT"), ("question_id", "TEXT"), ("question_json", "TEXT")),
}


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            for table, cols in MIGRATIONS.items():
                have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                for name, kind in cols:
                    if name not in have:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
            conn.execute("CREATE INDEX IF NOT EXISTS sessions_by_lab ON sessions(lab_id, question_id)")

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

    def create_session(self, session_id: str, student_id: str, task_id: str, schema_version: int, client_meta: dict,
                       question: dict | None = None) -> None:
        """`question`: the lab question row (as a dict) when the session answers one."""
        q = question or {}
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO sessions(id, student_id, task_id, started_at, schema_version, client_meta,
                                        lab_id, question_id, question_json) VALUES (?,?,?,?,?,?,?,?,?)""",
                (session_id, student_id, task_id, time.time(), schema_version, json.dumps(client_meta),
                 q.get("lab_id"), q.get("id"), json.dumps(q) if q else None),
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

    def list_sessions(self, student_id: str | None = None, lab_id: str | None = None) -> list[sqlite3.Row]:
        sql = """SELECT s.*, (SELECT COUNT(*) FROM events e WHERE e.session_id = s.id) AS n_events
                 FROM sessions s"""
        where, args = [], []
        if student_id is not None:
            where.append("s.student_id = ?")
            args.append(student_id)
        if lab_id is not None:
            where.append("s.lab_id = ?")
            args.append(lab_id)
        if where:
            sql += " WHERE " + " AND ".join(where)
        with self.connect() as conn:
            return conn.execute(sql + " ORDER BY s.started_at", args).fetchall()

    def list_students(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM students ORDER BY id").fetchall()

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

    # labs and questions (teacher authoring) -----------------------------------

    def create_lab(self, lab_id: str, title: str, description: str) -> None:
        now = time.time()
        with self.connect() as conn:
            conn.execute("INSERT INTO labs(id, title, description, created_at, updated_at) VALUES (?,?,?,?,?)",
                         (lab_id, title, description, now, now))

    def get_lab(self, lab_id: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone()

    def list_labs(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """SELECT l.*,
                          (SELECT COUNT(*) FROM questions q WHERE q.lab_id = l.id) AS n_questions,
                          (SELECT COUNT(*) FROM lab_students r WHERE r.lab_id = l.id) AS n_roster,
                          (SELECT COUNT(*) FROM sessions s WHERE s.lab_id = l.id) AS n_sessions,
                          (SELECT COUNT(DISTINCT s.student_id) FROM sessions s WHERE s.lab_id = l.id) AS n_started
                   FROM labs l ORDER BY l.created_at DESC""").fetchall()

    def update_lab(self, lab_id: str, fields: dict) -> None:
        allowed = {k: v for k, v in fields.items() if k in ("title", "description", "status", "everyone")}
        if not allowed:
            return
        sets = ", ".join(f"{k} = ?" for k in allowed)
        with self.connect() as conn:
            conn.execute(f"UPDATE labs SET {sets}, updated_at = ? WHERE id = ?", (*allowed.values(), time.time(), lab_id))

    def delete_lab(self, lab_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM labs WHERE id = ?", (lab_id,))

    def lab_questions(self, lab_id: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM questions WHERE lab_id = ? ORDER BY position, created_at", (lab_id,)).fetchall()

    def get_question(self, question_id: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()

    def add_question(self, question_id: str, lab_id: str, q: dict) -> None:
        now = time.time()
        with self.connect() as conn:
            pos = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM questions WHERE lab_id = ?", (lab_id,)).fetchone()[0]
            conn.execute(
                """INSERT INTO questions(id, lab_id, position, title, prompt, starter_code, sample_input, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (question_id, lab_id, pos, q["title"], q["prompt"], q["starter_code"], q["sample_input"], now, now),
            )
            conn.execute("UPDATE labs SET updated_at = ? WHERE id = ?", (now, lab_id))

    def update_question(self, question_id: str, fields: dict) -> None:
        allowed = {k: v for k, v in fields.items() if k in ("title", "prompt", "starter_code", "sample_input")}
        if not allowed:
            return
        sets = ", ".join(f"{k} = ?" for k in allowed)
        with self.connect() as conn:
            conn.execute(f"UPDATE questions SET {sets}, updated_at = ? WHERE id = ?", (*allowed.values(), time.time(), question_id))

    def reorder_questions(self, lab_id: str, order: list[str]) -> None:
        with self.connect() as conn:
            conn.executemany("UPDATE questions SET position = ? WHERE id = ? AND lab_id = ?",
                             [(i, qid, lab_id) for i, qid in enumerate(order)])

    def delete_question(self, question_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))

    def count_sessions(self, *, lab_id: str | None = None, question_id: str | None = None) -> int:
        col, val = ("question_id", question_id) if question_id else ("lab_id", lab_id)
        with self.connect() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM sessions WHERE {col} = ?", (val,)).fetchone()[0]

    def lab_roster(self, lab_id: str) -> list[str]:
        with self.connect() as conn:
            return [r[0] for r in conn.execute("SELECT student_id FROM lab_students WHERE lab_id = ? ORDER BY student_id", (lab_id,))]

    def set_roster(self, lab_id: str, student_ids: list[str]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM lab_students WHERE lab_id = ?", (lab_id,))
            conn.executemany("INSERT OR IGNORE INTO lab_students(lab_id, student_id) VALUES (?, ?)",
                             [(lab_id, s) for s in student_ids])

    def labs_for_student(self, student_id: str) -> list[sqlite3.Row]:
        """Open labs this student may work on."""
        with self.connect() as conn:
            return conn.execute(
                """SELECT * FROM labs l WHERE l.status = 'open' AND
                       (l.everyone = 1 OR EXISTS (SELECT 1 FROM lab_students r WHERE r.lab_id = l.id AND r.student_id = ?))
                   ORDER BY l.created_at DESC""", (student_id,)).fetchall()

    def attempts(self, student_id: str, lab_id: str) -> dict[str, dict]:
        """Per question: how many sessions this student started and whether one was submitted."""
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT question_id, COUNT(*) AS n, MAX(end_reason = 'submit') AS submitted
                   FROM sessions WHERE student_id = ? AND lab_id = ? GROUP BY question_id""", (student_id, lab_id)).fetchall()
        return {r["question_id"]: {"sessions": r["n"], "submitted": bool(r["submitted"])} for r in rows}

    def lab_progress(self, lab_id: str) -> list[sqlite3.Row]:
        """One row per (student, question) that has at least one session."""
        with self.connect() as conn:
            return conn.execute(
                """SELECT student_id, question_id, COUNT(*) AS n, MAX(end_reason = 'submit') AS submitted,
                          MAX(started_at) AS last_at
                   FROM sessions WHERE lab_id = ? GROUP BY student_id, question_id""", (lab_id,)).fetchall()

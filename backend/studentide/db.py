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
    question_json  TEXT,                     -- JSON copy of the question as the student saw it
    keys_purged_at REAL,                     -- raw key events deleted at this time, see retention.py
    sitting_id     TEXT,                     -- one opening of a lab: its questions' sessions share it
    context        TEXT                      -- 'learn' = learning lab practice (see learn.py); 'preview' = a teacher's
                                             -- "View as student" (never study data); NULL = everything else
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
    subject       TEXT NOT NULL DEFAULT '',    -- e.g. "Data Structures"; free text
    language      TEXT NOT NULL DEFAULT 'python',  -- runner.LANGUAGES key the editor and runner use, or 'any'
                                                 -- (competitions only: each student picks per question, see grading.ANY)
    kind          TEXT NOT NULL DEFAULT 'lab', -- 'lab' or 'competition' (see compete.py)
    owner_email   TEXT,                        -- teacher who made it; NULL = admins only (labs from before ownership)
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
    tests_json    TEXT NOT NULL DEFAULT '[]',  -- optional: [{name, stdin, expected, hidden, compare}], see grading.py
    harness       TEXT NOT NULL DEFAULT '',    -- optional code appended after the student's when tests run
    checker       TEXT NOT NULL DEFAULT '',    -- optional Python checker for tests with compare "checker"
    variants_json TEXT NOT NULL DEFAULT '{}',  -- any-language competitions: {language: {starter_code, harness}}
    source_json   TEXT,                        -- where an imported question came from (provider, url, license)
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

-- Roll Call class groups attached to a lab, with a copy of their student ids.
CREATE TABLE IF NOT EXISTS lab_classes (
    lab_id        TEXT NOT NULL,             -- a web lab or a Sandbox Lab (no foreign key: delete_lab clears it)
    class_id      TEXT NOT NULL,             -- Roll Call class uuid
    label         TEXT NOT NULL,             -- "CSE · A · G1"
    students_json TEXT NOT NULL,             -- registration numbers on its roster, upper-case
    attached_by   TEXT NOT NULL,             -- whose Roll Call holds the class (sends go through their key)
    attached_at   REAL NOT NULL,
    PRIMARY KEY (lab_id, class_id)
) WITHOUT ROWID;

-- A sitting: one opening of a lab for the class groups performing in it
-- (attendance.py). class_ids '[]' = every attached group / the whole roster.
-- While a sitting with chosen groups is open, students of the lab's other
-- groups can't work in it; closing it sends attendance for its groups only.
CREATE TABLE IF NOT EXISTS lab_runs (
    id            TEXT PRIMARY KEY,
    lab_id        TEXT NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    class_ids     TEXT NOT NULL DEFAULT '[]',
    opened_at     REAL NOT NULL,
    opened_by     TEXT NOT NULL DEFAULT '',
    closed_at     REAL
);
CREATE INDEX IF NOT EXISTS lab_runs_lab ON lab_runs(lab_id, opened_at);

-- Co-teachers a lab's owner shares it with: same view and edit rights as the
-- owner, except changing who it is shared with. Addresses, so a colleague can
-- be added before their first sign-in.
CREATE TABLE IF NOT EXISTS lab_teachers (
    lab_id        TEXT NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    email         TEXT NOT NULL,
    PRIMARY KEY (lab_id, email)
) WITHOUT ROWID;

-- A student pressing "Check": their code against the question's tests. Kept
-- server side (not as a client event) so the event schema stays at v1.
CREATE TABLE IF NOT EXISTS checks (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    created_at    REAL NOT NULL,
    code          TEXT NOT NULL,
    passed        INTEGER NOT NULL,
    total         INTEGER NOT NULL,
    results_json  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS checks_by_session ON checks(session_id, created_at);
"""

# Columns added after phase 1. Older database files get them on open.
MIGRATIONS = {
    "students": (("consent_version", "INTEGER"),),
    "sessions": (("lab_id", "TEXT"), ("question_id", "TEXT"), ("question_json", "TEXT"), ("keys_purged_at", "REAL"),
                 ("sitting_id", "TEXT"), ("context", "TEXT")),
    "labs": (("subject", "TEXT NOT NULL DEFAULT ''"), ("language", "TEXT NOT NULL DEFAULT 'python'"),
             ("kind", "TEXT NOT NULL DEFAULT 'lab'"), ("owner_email", "TEXT")),
    "questions": (("tests_json", "TEXT NOT NULL DEFAULT '[]'"), ("harness", "TEXT NOT NULL DEFAULT ''"),
                  ("source_json", "TEXT"), ("checker", "TEXT NOT NULL DEFAULT ''"),
                  ("variants_json", "TEXT NOT NULL DEFAULT '{}'")),
}
# Bumped whenever the consent screen promises something new, so every student
# reads and agrees again. 2: teachers can watch a lab live (live.py).
CONSENT_VERSION = 2
# 3: Sandbox Labs (desktop app): terminal keys and commands, files changed outside the editor,
# workspace copies, packages and hosts, the terminal in the live view. Asked only before a
# student's first Sandbox Lab, so web-only students are not asked again; agreeing to 3 covers 2.
SANDBOX_CONSENT_VERSION = 3


def has_consent(row) -> bool:
    """Agreed to the current consent text (a NULL version is the original text, 1)."""
    return row["consented_at"] is not None and (row["consent_version"] or 1) >= CONSENT_VERSION


def has_sandbox_consent(row) -> bool:
    """Agreed to the Sandbox Labs text too: needed before recording any Sandbox Lab session."""
    return row["consented_at"] is not None and (row["consent_version"] or 1) >= SANDBOX_CONSENT_VERSION


QUESTION_FIELDS = ("title", "prompt", "starter_code", "sample_input", "tests_json", "harness", "source_json", "checker",
                   "variants_json")


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

    def record_consent(self, student_id: str, version: int = CONSENT_VERSION) -> None:
        with self.connect() as conn:
            # Agreeing to a newer text restarts the clock: consented_at is when they agreed to what applies now.
            # A version never goes down (a v3 student who signs the web text again stays v3).
            conn.execute(
                """UPDATE students SET consented_at = CASE WHEN COALESCE(consent_version, 1) >= ? AND consented_at IS NOT NULL
                                                           THEN consented_at ELSE ? END,
                                       consent_version = MAX(COALESCE(consent_version, 1), ?) WHERE id = ?""",
                (version, time.time(), version, student_id),
            )

    # sessions ---------------------------------------------------------------

    def create_session(self, session_id: str, student_id: str, task_id: str, schema_version: int, client_meta: dict,
                       question: dict | None = None, sitting_id: str | None = None, context: str | None = None) -> None:
        """`question`: the lab question row (as a dict) when the session answers one.
        `sitting_id`: shared by the sessions of one opening of a lab (one per question visited).
        `context`: "learn" for a learning-lab lesson, kept apart from everything the detector reads."""
        q = question or {}
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO sessions(id, student_id, task_id, started_at, schema_version, client_meta,
                                        lab_id, question_id, question_json, sitting_id, context) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (session_id, student_id, task_id, time.time(), schema_version, json.dumps(client_meta),
                 q.get("lab_id"), q.get("id"), json.dumps(q) if q else None, sitting_id, context),
            )

    def previous_sessions(self, student_id: str, question_id: str) -> list[sqlite3.Row]:
        """This student's earlier sessions on a question, newest first."""
        with self.connect() as conn:
            return conn.execute("""SELECT * FROM sessions WHERE student_id = ? AND question_id = ?
                                   ORDER BY started_at DESC""", (student_id, question_id)).fetchall()

    def get_session(self, session_id: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

    def end_session(self, session_id: str, reason: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = COALESCE(ended_at, ?), end_reason = COALESCE(end_reason, ?) WHERE id = ?",
                (time.time(), reason, session_id),
            )

    def list_sessions(self, student_id: str | None = None, lab_id: str | None = None,
                      include_learn: bool = False) -> list[sqlite3.Row]:
        """Learning-lab sessions are left out unless `include_learn`: the
        detector, baselines, review, live view and harness never see them.
        Teachers' "View as student" sessions are always left out (not study data)."""
        sql = """SELECT s.*, (SELECT COUNT(*) FROM events e WHERE e.session_id = s.id) AS n_events
                 FROM sessions s"""
        where, args = (["(s.context IS NULL OR s.context = 'learn')"] if include_learn else ["s.context IS NULL"]), []
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

    def insert_check(self, check_id: str, session_id: str, code: str, grade: dict) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO checks(id, session_id, created_at, code, passed, total, results_json) VALUES (?,?,?,?,?,?,?)",
                         (check_id, session_id, time.time(), code, grade["passed"], grade["total"], json.dumps(grade["results"])))

    def list_checks(self, session_id: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM checks WHERE session_id = ? ORDER BY created_at", (session_id,)).fetchall()

    # labs and questions (teacher authoring) -----------------------------------

    def create_lab(self, lab_id: str, title: str, description: str, owner_email: str | None = None) -> None:
        now = time.time()
        with self.connect() as conn:
            conn.execute("INSERT INTO labs(id, title, description, owner_email, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                         (lab_id, title, description, owner_email, now, now))

    def get_lab(self, lab_id: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone()

    def list_labs(self, ids: set[str] | None = None) -> list[sqlite3.Row]:
        """Every lab, or only those in `ids` (a teacher's own and shared labs)."""
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT l.*,
                          (SELECT COUNT(*) FROM questions q WHERE q.lab_id = l.id) AS n_questions,
                          (SELECT COUNT(*) FROM lab_students r WHERE r.lab_id = l.id) AS n_roster,
                          (SELECT COUNT(*) FROM sessions s WHERE s.lab_id = l.id AND s.context IS NOT 'preview') AS n_sessions,
                          (SELECT COUNT(DISTINCT s.student_id) FROM sessions s
                            WHERE s.lab_id = l.id AND s.context IS NOT 'preview') AS n_started
                   FROM labs l ORDER BY l.created_at DESC""").fetchall()
        return rows if ids is None else [r for r in rows if r["id"] in ids]

    def update_lab(self, lab_id: str, fields: dict) -> None:
        allowed = {k: v for k, v in fields.items()
                   if k in ("title", "description", "status", "everyone", "subject", "language")}
        if not allowed:
            return
        sets = ", ".join(f"{k} = ?" for k in allowed)
        with self.connect() as conn:
            conn.execute(f"UPDATE labs SET {sets}, updated_at = ? WHERE id = ?", (*allowed.values(), time.time(), lab_id))

    def lab_teachers(self, lab_id: str | None = None) -> dict[str, list[str]]:
        """Co-teacher addresses per lab (of one lab, or of all)."""
        with self.connect() as conn:
            rows = conn.execute("SELECT lab_id, email FROM lab_teachers" + (" WHERE lab_id = ?" if lab_id else "") +
                                " ORDER BY email", (lab_id,) if lab_id else ()).fetchall()
        out: dict[str, list[str]] = {}
        for r in rows:
            out.setdefault(r["lab_id"], []).append(r["email"])
        return out

    def set_lab_teachers(self, lab_id: str, emails: list[str], owner_email: str | None) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE labs SET owner_email = ?, updated_at = ? WHERE id = ?", (owner_email, time.time(), lab_id))
            conn.execute("DELETE FROM lab_teachers WHERE lab_id = ?", (lab_id,))
            conn.executemany("INSERT OR IGNORE INTO lab_teachers(lab_id, email) VALUES (?, ?)", [(lab_id, e) for e in emails])

    def teacher_lab_ids(self, email: str) -> set[str]:
        """Labs a teacher owns or was added to."""
        with self.connect() as conn:
            return {r[0] for r in conn.execute(
                "SELECT id FROM labs WHERE owner_email = ? UNION SELECT lab_id FROM lab_teachers WHERE email = ?", (email, email))}

    def sandbox_lab_teacher(self, lab_id: str, email: str | None) -> bool:
        """A Sandbox Lab (sandbox.py) whose subject this teacher owns or was added to (teacher or TA)."""
        if not email:
            return False
        with self.connect() as conn:
            try:
                return conn.execute("""SELECT 1 FROM sbx_labs l JOIN sbx_subjects s ON s.id = l.subject_id WHERE l.id = ?
                                       AND (s.owner_email = ? OR EXISTS (SELECT 1 FROM sbx_subject_people p
                                            WHERE p.subject_id = s.id AND p.email = ?))""", (lab_id, email, email)).fetchone() is not None
            except sqlite3.OperationalError:  # sandbox tables not created
                return False

    def delete_lab(self, lab_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM labs WHERE id = ?", (lab_id,))
            # attendance tables also hold Sandbox Lab ids, so they have no foreign key to cascade
            for table in ("lab_classes", "lab_attendance", "attendance_sent"):
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone():
                    conn.execute(f"DELETE FROM {table} WHERE lab_id = ?", (lab_id,))

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
            cols = [c for c in QUESTION_FIELDS if c in q]
            conn.execute(
                f"""INSERT INTO questions(id, lab_id, position, {', '.join(cols)}, created_at, updated_at)
                    VALUES (?,?,?,{','.join('?' * len(cols))},?,?)""",
                (question_id, lab_id, pos, *(q[c] for c in cols), now, now),
            )
            conn.execute("UPDATE labs SET updated_at = ? WHERE id = ?", (now, lab_id))

    def update_question(self, question_id: str, fields: dict) -> None:
        allowed = {k: v for k, v in fields.items() if k in QUESTION_FIELDS}
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
            return conn.execute(f"SELECT COUNT(*) FROM sessions WHERE {col} = ? AND context IS NOT 'preview'",
                                (val,)).fetchone()[0]

    def delete_preview_sessions(self, *, lab_id: str | None = None, question_id: str | None = None) -> int:
        """Teachers' "View as student" sessions on a lab or question about to be
        deleted (they never block the delete), with everything recorded in them."""
        col, val = ("question_id", question_id) if question_id else ("lab_id", lab_id)
        with self.connect() as conn:
            ids = [r[0] for r in conn.execute(f"SELECT id FROM sessions WHERE {col} = ? AND context = 'preview'", (val,))]
            if not ids:
                return 0
            have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            marks = ",".join("?" * len(ids))
            for table in ("events", "runs", "checks", "session_windows", "submissions"):
                if table in have:
                    conn.execute(f"DELETE FROM {table} WHERE session_id IN ({marks})", ids)
            return conn.execute(f"DELETE FROM sessions WHERE id IN ({marks})", ids).rowcount

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
                       (l.everyone = 1 OR EXISTS (SELECT 1 FROM lab_students r WHERE r.lab_id = l.id AND r.student_id = :s))
                       -- not while the lab is open for another of the lab's class groups (lab_runs)
                       AND NOT (
                         EXISTS (SELECT 1 FROM lab_runs u WHERE u.lab_id = l.id AND u.closed_at IS NULL AND u.class_ids <> '[]')
                         AND EXISTS (SELECT 1 FROM lab_classes c WHERE c.lab_id = l.id AND instr(c.students_json, '"' || :s || '"') > 0)
                         AND NOT EXISTS (SELECT 1 FROM lab_runs u JOIN lab_classes c ON c.lab_id = u.lab_id
                                         WHERE u.lab_id = l.id AND u.closed_at IS NULL
                                           AND instr(u.class_ids, '"' || c.class_id || '"') > 0
                                           AND instr(c.students_json, '"' || :s || '"') > 0))
                   ORDER BY l.created_at DESC""", {"s": student_id}).fetchall()

    def preview_labs(self, ids: set[str] | None) -> list[sqlite3.Row]:
        """What "View as student" lists: open and draft labs among `ids` (None = all),
        so a teacher can try a lab before opening it."""
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM labs WHERE status IN ('open', 'draft') ORDER BY created_at DESC").fetchall()
        return rows if ids is None else [r for r in rows if r["id"] in ids]

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
                   FROM sessions WHERE lab_id = ? AND context IS NOT 'preview'
                   GROUP BY student_id, question_id""", (lab_id,)).fetchall()

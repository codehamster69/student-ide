"""Deleting raw keystrokes, as the consent screen promises.

The consent screen says "Raw keystroke data is deleted once summary
statistics have been computed". This module keeps that promise:

1. For each session whose raw keys are due, compute the detector's window
   features at every window length the frozen config uses and store them in
   `session_windows`. A window holds aggregates over 30-90 s (medians, spreads,
   rates, per-key-pair mean log time and count), never single key presses.
2. Delete that session's `key` events and stamp `sessions.keys_purged_at`.

The review timeline and baselines then read the stored windows (see
`Reviewer.windows`), so a purged session can still be opened, scored and used
as a baseline. What it loses is the rhythm strip on the replay, and any
re-analysis at a window length that was not stored.

When raw keys are due:
* a lab session in a student's baseline (the first BASELINE_DAYS after their
  first lab session) once that baseline period is over, and
* any session (lab or competition) once it is older than
  $STUDENTIDE_RAW_KEY_DAYS (default 28) days.
A session still open (no end, started under a day ago) is never touched.

Edit events stay: they are the student's code and drive the code replay. They
carry a time per change, so coarsening their timestamps is a follow-up if the
ethics committee reads "keystroke data" to include them.

Runs in the server every 6 hours when enabled: on by default in Google mode
(a real deployment), off in dev mode; $STUDENTIDE_PURGE=on|off overrides.
By hand: python -m studentide.retention [--dry-run]

A student who withdraws, or asks for their data to be erased (DPDP Act
2023, s. 12), is removed completely with
    python -m studentide.retention --erase-student PG25CS07
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time

from .db import Database
from .detector.features import streams, window_features

BASELINE_DAYS = 28.0  # same as review.BASELINE_DAYS (not imported: review imports this module)
OPEN_GRACE_S = 86400.0
INTERVAL_S = 6 * 3600.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS session_windows (
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    window_s      REAL NOT NULL,
    windows_json  TEXT NOT NULL,      -- list of window feature dicts (NaN kept as NaN)
    created_at    REAL NOT NULL,
    PRIMARY KEY (session_id, window_s)
) WITHOUT ROWID;
"""


def ensure_schema(db: Database) -> None:
    with db.connect() as conn:
        conn.executescript(SCHEMA)


def raw_key_days() -> float:
    return float(os.environ.get("STUDENTIDE_RAW_KEY_DAYS") or 28)


def stored_windows(db: Database, session_id: str, window_s: float) -> list[dict] | None:
    """Only called for purged sessions, so the table exists."""
    with db.connect() as conn:
        row = conn.execute("SELECT windows_json FROM session_windows WHERE session_id = ? AND window_s = ?",
                           (session_id, float(window_s))).fetchone()
    return json.loads(row[0]) if row else None


def due(db: Database, now: float | None = None, days: float | None = None) -> list[dict]:
    """Sessions whose raw keys should be deleted now, with the reason."""
    now = time.time() if now is None else now
    days = raw_key_days() if days is None else days
    with db.connect() as conn:
        comp = {r[0] for r in conn.execute("SELECT id FROM labs WHERE kind = 'competition'")}
        rows = [dict(r) for r in conn.execute(
            """SELECT s.id, s.student_id, s.lab_id, s.started_at, s.ended_at, s.keys_purged_at,
                      EXISTS (SELECT 1 FROM events e WHERE e.session_id = s.id) AS has_events
               FROM sessions s ORDER BY s.started_at""")]
    first_lab: dict[str, float] = {}
    for r in rows:
        if r["has_events"] and r["lab_id"] not in comp:
            first_lab.setdefault(r["student_id"], r["started_at"])
    out = []
    for r in rows:
        if r["keys_purged_at"] is not None or not r["has_events"]:
            continue
        if r["ended_at"] is None and r["started_at"] > now - OPEN_GRACE_S:
            continue
        t0 = first_lab.get(r["student_id"])
        in_baseline = r["lab_id"] not in comp and t0 is not None and r["started_at"] < t0 + BASELINE_DAYS * 86400
        if in_baseline and now >= t0 + BASELINE_DAYS * 86400:
            out.append(r | {"reason": "baseline built"})
        elif r["started_at"] < now - days * 86400:
            out.append(r | {"reason": f"older than {days:g} days"})
    return out


def _plain(o):
    """numpy scalars in a window dict -> plain numbers."""
    return o.item() if hasattr(o, "item") else str(o)


def purge_session(db: Database, session_id: str, window_lengths: list[float]) -> int:
    """Store the session's windows, then delete its key events. Returns how many were deleted."""
    ensure_schema(db)
    events = list(db.iter_events(session_id))
    s = streams(events)
    now = time.time()
    stored = {float(W): json.dumps(window_features(s, W), default=_plain) for W in sorted(set(window_lengths))}
    with db.connect() as conn:  # one transaction: never keys gone without windows stored
        conn.executemany(
            "INSERT OR REPLACE INTO session_windows(session_id, window_s, windows_json, created_at) VALUES (?,?,?,?)",
            [(session_id, W, js, now) for W, js in stored.items()])
        n = conn.execute("DELETE FROM events WHERE session_id = ? AND type = 'key'", (session_id,)).rowcount
        conn.execute("UPDATE sessions SET keys_purged_at = ? WHERE id = ?", (now, session_id))
    return n


def purge(db: Database, window_lengths: list[float], now: float | None = None, days: float | None = None,
          dry_run: bool = False) -> list[dict]:
    out = []
    for r in due(db, now, days):
        n = 0 if dry_run else purge_session(db, r["id"], window_lengths)
        out.append({"session_id": r["id"], "student_id": r["student_id"], "reason": r["reason"], "deleted_keys": n})
    return out


def erase_student(db: Database, student_id: str) -> dict[str, int]:
    """Delete everything recorded about one student: sessions with their
    events, runs, checks, stored windows and competition entries, roster
    places, the consent record and the account. Returns rows deleted per table.
    Backups still hold the data until they age out (BACKUP_KEEP_DAYS)."""
    ensure_schema(db)
    n: dict[str, int] = {}
    with db.connect() as conn:
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        ids = [r[0] for r in conn.execute("SELECT id FROM sessions WHERE student_id = ?", (student_id,))]
        marks = ",".join("?" * len(ids))
        for table in ("events", "runs", "checks", "session_windows", "submissions"):
            if table in have and ids:
                n[table] = conn.execute(f"DELETE FROM {table} WHERE session_id IN ({marks})", ids).rowcount
        n["sessions"] = conn.execute("DELETE FROM sessions WHERE student_id = ?", (student_id,)).rowcount
        for table in ("competition_players", "lab_students"):
            if table in have:
                n[table] = conn.execute(f"DELETE FROM {table} WHERE student_id = ?", (student_id,)).rowcount
        if "users" in have:
            emails = [r[0] for r in conn.execute("SELECT email FROM users WHERE student_id = ?", (student_id,))]
            for e in emails:
                conn.execute("DELETE FROM auth_sessions WHERE email = ?", (e,))
            n["users"] = conn.execute("DELETE FROM users WHERE student_id = ?", (student_id,)).rowcount
        n["students"] = conn.execute("DELETE FROM students WHERE id = ?", (student_id,)).rowcount
    return n


def enabled() -> bool:
    flag = (os.environ.get("STUDENTIDE_PURGE") or "").lower()
    if flag in ("on", "1", "true"):
        return True
    if flag in ("off", "0", "false"):
        return False
    return bool(os.environ.get("STUDENTIDE_GOOGLE_CLIENT_ID"))


def start_background(db: Database, settings) -> threading.Thread | None:
    """Purge every INTERVAL_S in a daemon thread, if enabled."""
    if not enabled():
        return None
    lengths = list(settings.window_s.values())

    def loop() -> None:
        while True:
            try:
                done = purge(db, lengths)
                if done:
                    print(f"retention: deleted raw keys of {len(done)} session(s)", flush=True)
            except Exception as e:  # never take the server down; try again next round
                print(f"retention: purge failed: {e!r}", flush=True)
            time.sleep(INTERVAL_S)

    t = threading.Thread(target=loop, name="retention", daemon=True)
    t.start()
    return t


def main() -> None:
    from .review import load_settings

    ap = argparse.ArgumentParser(description="Delete raw keystrokes that are due (see module docstring).")
    ap.add_argument("--db", default=os.environ.get("STUDENTIDE_DB", "data/studentide.sqlite3"))
    ap.add_argument("--dry-run", action="store_true", help="list what is due, delete nothing")
    ap.add_argument("--erase-student", metavar="ID", help="delete everything about this student instead")
    a = ap.parse_args()
    db = Database(a.db)
    if a.erase_student:
        n = erase_student(db, a.erase_student)
        print(", ".join(f"{t}: {k}" for t, k in n.items() if k) or f"nothing stored for {a.erase_student}")
        return
    done = purge(db, list(load_settings().window_s.values()), dry_run=a.dry_run)
    for d in done:
        print(f"{d['session_id']}  {d['student_id']:<12} {d['reason']:<22} {d['deleted_keys']} keys")
    print(f"{len(done)} session(s) {'due' if a.dry_run else 'purged'}")


if __name__ == "__main__":
    main()

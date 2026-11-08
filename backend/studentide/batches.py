"""Signed, hash-chained event batches from the desktop app (plan 4.3 and 4.4).

A student controls their own machine, so the app cannot be tamper-proof; the
aim is that dropping, reordering or editing events is visible. Each install
makes an Ed25519 key pair (the private key stays in the OS keychain through
Electron safeStorage) and registers the public key here once per student:

    POST /api/devices?student_id=   {public_key, app_version, platform}  -> {device_id}

From then on the app's journal (desktop/app/src/main/modules/journal.ts)
uploads to the usual POST /api/sessions/{id}/events, wrapped:

    {"schema_version": 3, "signed": {"device_id": "...", "payload": "<JSON text>", "sig": "<base64>"}}

`payload` is the exact JSON text that was signed:
{session_id, batch_seq, prev_hash, wall_ms, mono_ms, offline_ms, events}. Its
hash is sha256(payload bytes), and the next batch's prev_hash must equal it
(batch 0 has prev_hash ""). Signing the text itself means neither side has
to canonicalise JSON.

The server never throws events away over a bad signature or a broken chain:
study data is kept, and the batch row records what was wrong (`problem`), so
the review shows a "chain break" lane instead. A retry of the same batch
(same batch_seq and hash) is idempotent. Each row also keeps the client's
wall and monotonic clocks next to the receive time, so skew and catch-up
delays after an offline spell are visible.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import time

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .db import Database

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id          TEXT PRIMARY KEY,
    student_id  TEXT NOT NULL,
    public_key  TEXT NOT NULL,            -- base64 raw Ed25519 key (32 bytes)
    app_version TEXT NOT NULL DEFAULT '',
    platform    TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    UNIQUE (student_id, public_key)
);
CREATE TABLE IF NOT EXISTS event_batches (
    session_id  TEXT NOT NULL,
    batch_seq   INTEGER NOT NULL,
    device_id   TEXT NOT NULL,
    hash        TEXT NOT NULL,
    prev_hash   TEXT NOT NULL,
    n_events    INTEGER NOT NULL,
    min_seq     INTEGER,
    max_seq     INTEGER,
    wall_ms     REAL,
    mono_ms     REAL,
    offline_ms  REAL NOT NULL DEFAULT 0,  -- how long the app had been offline when this batch was made
    received_at REAL NOT NULL,
    problem     TEXT,                     -- NULL = signed and chained; else bad_signature | chain_break | rewritten | other_device
    PRIMARY KEY (session_id, batch_seq)
);
"""

B64 = re.compile(r"^[A-Za-z0-9+/]{42,44}={0,2}$")
MAX_PAYLOAD = 8 * 1024 * 1024


class DeviceIn(BaseModel):
    public_key: str = Field(max_length=64)
    app_version: str = Field(default="", max_length=32)
    platform: str = Field(default="", max_length=32)


def init(db: Database) -> None:
    with db.connect() as conn:
        conn.executescript(SCHEMA)


def register_device(db: Database, student_id: str, body: DeviceIn) -> dict:
    if not B64.match(body.public_key) or len(base64.b64decode(body.public_key)) != 32:
        raise HTTPException(400, "public_key must be a base64 raw Ed25519 key")
    with db.connect() as conn:
        row = conn.execute("SELECT id FROM devices WHERE student_id = ? AND public_key = ?", (student_id, body.public_key)).fetchone()
        if row:
            conn.execute("UPDATE devices SET app_version = ?, platform = ? WHERE id = ?", (body.app_version, body.platform, row["id"]))
            return {"device_id": row["id"]}
        did = secrets.token_hex(8)
        conn.execute("INSERT INTO devices(id, student_id, public_key, app_version, platform, created_at) VALUES (?,?,?,?,?,?)",
                     (did, student_id, body.public_key, body.app_version, body.platform, time.time()))
    return {"device_id": did}


def _verify(public_key_b64: str, payload: bytes, sig_b64: str) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(base64.b64decode(sig_b64), payload)
        return True
    except (InvalidSignature, ValueError):
        return False


def unwrap(db: Database, session_row, signed: dict) -> tuple[list, dict]:
    """The events inside a signed batch, plus the batch row to record once they are stored.
    Raises 400 only when the envelope cannot be read at all."""
    try:
        device_id = str(signed["device_id"])
        payload_text = signed["payload"]
        sig = str(signed.get("sig", ""))
        if not isinstance(payload_text, str) or len(payload_text) > MAX_PAYLOAD:
            raise ValueError
        payload_bytes = payload_text.encode("utf-8")
        p = json.loads(payload_text)
        batch_seq = int(p["batch_seq"])
        prev_hash = str(p.get("prev_hash", ""))
        events = p["events"]
        if batch_seq < 0 or not isinstance(events, list):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "unreadable signed batch")
    digest = hashlib.sha256(payload_bytes).hexdigest()
    problem = None
    with db.connect() as conn:
        dev = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        if dev is None:
            raise HTTPException(409, "unknown device: register it again")
        if dev["student_id"] != session_row["student_id"]:
            problem = "other_device"
        elif p.get("session_id") != session_row["id"] or not _verify(dev["public_key"], payload_bytes, sig):
            problem = "bad_signature"
        have = conn.execute("SELECT hash FROM event_batches WHERE session_id = ? AND batch_seq = ?",
                            (session_row["id"], batch_seq)).fetchone()
        if have is not None and have["hash"] != digest and problem is None:
            problem = "rewritten"  # the same batch number came back with other contents
        if problem is None:
            prev = conn.execute("SELECT hash FROM event_batches WHERE session_id = ? AND batch_seq = ?",
                                (session_row["id"], batch_seq - 1)).fetchone()
            expected = "" if batch_seq == 0 else (prev["hash"] if prev else None)
            if expected != prev_hash:
                problem = "chain_break"
    seqs = [e.get("seq") for e in events if isinstance(e, dict) and isinstance(e.get("seq"), int)]
    row = {
        "session_id": session_row["id"], "batch_seq": batch_seq, "device_id": device_id, "hash": digest,
        "prev_hash": prev_hash, "n_events": len(events), "min_seq": min(seqs) if seqs else None,
        "max_seq": max(seqs) if seqs else None, "wall_ms": _num(p.get("wall_ms")), "mono_ms": _num(p.get("mono_ms")),
        "offline_ms": _num(p.get("offline_ms")) or 0.0, "problem": problem, "duplicate": have is not None and have["hash"] == digest,
    }
    return events, row


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def record(db: Database, row: dict) -> None:
    if row.get("duplicate"):
        return
    cols = ("session_id", "batch_seq", "device_id", "hash", "prev_hash", "n_events", "min_seq", "max_seq",
            "wall_ms", "mono_ms", "offline_ms", "problem")
    with db.connect() as conn:
        # a rewritten batch keeps the first row (what arrived first) and adds a marker row past the end
        if row["problem"] == "rewritten":
            last = conn.execute("SELECT COALESCE(MAX(batch_seq), -1) FROM event_batches WHERE session_id = ?",
                                (row["session_id"],)).fetchone()[0]
            row = row | {"batch_seq": max(last + 1, 1_000_000 + row["batch_seq"])}
        conn.execute(f"INSERT OR IGNORE INTO event_batches({', '.join(cols)}, received_at) VALUES ({', '.join('?' * len(cols))}, ?)",
                     (*(row[c] for c in cols), time.time()))


def integrity(db: Database, session_id: str) -> dict:
    """What the review shows about a session's transport: signed or not, breaks, offline spells."""
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM event_batches WHERE session_id = ? ORDER BY batch_seq", (session_id,)).fetchall()
    breaks = [{"batch_seq": r["batch_seq"] % 1_000_000, "problem": r["problem"], "min_seq": r["min_seq"], "max_seq": r["max_seq"],
               "received_at": r["received_at"]} for r in rows if r["problem"]]
    offline = [{"min_seq": r["min_seq"], "offline_ms": r["offline_ms"], "received_at": r["received_at"],
                "lag_ms": (r["received_at"] * 1000 - r["wall_ms"]) if r["wall_ms"] else None}
               for r in rows if r["offline_ms"] and r["offline_ms"] > 0]
    return {"signed": bool(rows), "batches": len(rows), "breaks": breaks, "offline": offline}

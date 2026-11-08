"""Signed, hash-chained batches from the desktop journal: good chains are clean, every kind of
tampering is recorded (never dropped), retries are idempotent, and v3 events are accepted."""

import base64
import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from studentide import batches
from studentide.app import create_app


@pytest.fixture
def rig(tmp_path):
    app = create_app(tmp_path / "b.sqlite3", admin_token="t", serve_frontend=False)
    c = TestClient(app)
    c.post("/api/consent", json={"student_id": "S1"})
    sid = c.post("/api/sessions", json={"student_id": "S1", "task_id": "free"}).json()["session_id"]
    key = Ed25519PrivateKey.generate()
    pub = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    dev = c.post("/api/devices", params={"student_id": "S1"}, json={"public_key": pub, "app_version": "0.3.0", "platform": "linux"}).json()
    return c, app, sid, key, dev["device_id"]


def ev(seq, typ="focus", data=None):
    return {"seq": seq, "t": seq * 10.0, "type": typ, "data": data or {"target": "window", "state": "in"}}


def wrap(key, device_id, session_id, batch_seq, prev_hash, events, offline_ms=0, sig_key=None):
    payload = json.dumps({"session_id": session_id, "batch_seq": batch_seq, "prev_hash": prev_hash, "wall_ms": 1.7e12,
                          "mono_ms": 1000.0, "offline_ms": offline_ms, "events": events})
    sig = base64.b64encode((sig_key or key).sign(payload.encode())).decode()
    return {"schema_version": 3, "signed": {"device_id": device_id, "payload": payload, "sig": sig}}, hashlib.sha256(payload.encode()).hexdigest()




def test_a_good_chain_is_clean_and_retries_are_idempotent(rig):
    c, app, sid, key, did = rig
    body0, h0 = wrap(key, did, sid, 0, "", [ev(0), ev(1)])
    assert c.post(f"/api/sessions/{sid}/events", json=body0).json()["inserted"] == 2
    assert c.post(f"/api/sessions/{sid}/events", json=body0).json()["inserted"] == 0  # retry
    body1, _ = wrap(key, did, sid, 1, h0, [ev(2)], offline_ms=90_000)
    assert c.post(f"/api/sessions/{sid}/events", json=body1).status_code == 200
    db = app.state.db
    info = batches.integrity(db, sid)
    assert info["signed"] and info["batches"] == 2 and info["breaks"] == []
    assert info["offline"][0]["offline_ms"] == 90_000


@pytest.mark.parametrize("case", ["bad_signature", "chain_break", "rewritten", "wrong_session"])
def test_tampering_is_recorded_not_dropped(rig, case):
    c, app, sid, key, did = rig
    body0, h0 = wrap(key, did, sid, 0, "", [ev(0)])
    c.post(f"/api/sessions/{sid}/events", json=body0)
    if case == "bad_signature":
        body, _ = wrap(key, did, sid, 1, h0, [ev(1)], sig_key=Ed25519PrivateKey.generate())
    elif case == "chain_break":  # batch 1 skipped (dropped events), batch 2 points at it
        body, _ = wrap(key, did, sid, 2, "f" * 64, [ev(5)])
    elif case == "rewritten":
        body, _ = wrap(key, did, sid, 0, "", [ev(0, data={"target": "window", "state": "out"})])
    else:
        body, _ = wrap(key, did, "another-session", 1, h0, [ev(1)])
    r = c.post(f"/api/sessions/{sid}/events", json=body)
    assert r.status_code == 200
    problems = [b["problem"] for b in batches.integrity(app.state.db, sid)["breaks"]]
    assert problems == ["bad_signature" if case == "wrong_session" else case]


def test_unknown_device_and_bad_keys(rig):
    c, app, sid, key, did = rig
    body, _ = wrap(key, "nope", sid, 0, "", [ev(0)])
    assert c.post(f"/api/sessions/{sid}/events", json=body).status_code == 409
    assert c.post("/api/devices", params={"student_id": "S1"}, json={"public_key": "abc"}).status_code == 400
    # same key again gives the same device
    pub = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    assert c.post("/api/devices", params={"student_id": "S1"}, json={"public_key": pub}).json()["device_id"] == did


def test_v3_events_are_accepted(rig):
    c, app, sid, key, did = rig
    fs = {"path": "/home/student/labs/l/a/main.c", "size": 20, "sha256": "a" * 64, "origin": "terminal-editor",
          "command": "vim main.c", "added": "int x;", "added_lines": 1, "removed_lines": 0, "diff": "+int x;"}
    events = [ev(0, "fs_change", fs), ev(1, "port_open", {"port": 5000, "process": "flask", "open": True})]
    r = c.post(f"/api/sessions/{sid}/events", json={"schema_version": 3, "events": events}).json()
    assert r["inserted"] == 2 and r["rejected"] == []

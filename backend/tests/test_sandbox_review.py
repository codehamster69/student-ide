"""Review lanes for a Sandbox Lab session: multi-file replay, terminal commands with output, vim saves
with and without typing, changes outside the app, ports, offline gaps and chain breaks from signed batches."""

import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from studentide.app import create_app

from test_attendance import ADMIN, TOKEN
from test_live import ev
from test_sandbox_attendance import sandbox_lab, sandbox_session


def test_lanes_and_multi_file_replay(tmp_path):
    app = create_app(tmp_path / "r.sqlite3", admin_token=TOKEN, serve_frontend=False)
    c = TestClient(app)
    lab = sandbox_lab(c)
    sid = sandbox_session(app, "S1", lab)
    W = f"/home/student/labs/{lab['id']}/{lab['definition']['assignments'][0]['id']}"
    key = Ed25519PrivateKey.generate()
    pub = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    did = c.post("/api/devices", params={"student_id": "S1"}, json={"public_key": pub}).json()["device_id"]

    def send(batch_seq, prev, events, offline_ms=0):
        payload = json.dumps({"session_id": sid, "batch_seq": batch_seq, "prev_hash": prev, "wall_ms": 1, "mono_ms": 1,
                              "offline_ms": offline_ms, "events": events})
        sig = base64.b64encode(key.sign(payload.encode())).decode()
        assert c.post(f"/api/sessions/{sid}/events", json={"schema_version": 3, "signed": {"device_id": did, "payload": payload, "sig": sig}}).status_code == 200
        import hashlib
        return hashlib.sha256(payload.encode()).hexdigest()

    vim_line = "int square(int x) { return x * x; }"
    h0 = send(0, "", [
        ev(0, "snapshot", {"reason": "start", "text": "", "path": f"{W}/main.c"}, t=0),
        ev(1, "edit", {"origin": "input.type", "changes": [[0, 0, "x"]], "len_before": 0, "len_after": 1, "path": f"{W}/main.c"}, t=500),
        ev(2, "snapshot", {"reason": "start", "text": "", "path": f"{W}/util.h"}, t=600),
        ev(3, "edit", {"origin": "input.type", "changes": [[0, 0, "y"]], "len_before": 0, "len_after": 1, "path": f"{W}/util.h"}, t=700),
        ev(4, "term_cmd", {"term_id": "t1", "phase": "start", "command": "gcc main.c", "cwd": W}, t=1000),
        ev(5, "term_output", {"term_id": "t1", "bytes": 20, "tail": "main.c:1: error"}, t=1500),
        ev(6, "term_cmd", {"term_id": "t1", "phase": "end", "command": "gcc main.c", "cwd": W, "exit_code": 1, "duration_ms": 600}, t=1600),
        ev(7, "fs_change", {"path": f"{W}/main.c", "size": 40, "sha256": "a" * 64, "origin": "terminal-editor",
                            "command": "vim main.c", "added": vim_line, "added_lines": 1}, t=5000),
        ev(8, "fs_change", {"path": f"{W}/sol.c", "size": 99, "sha256": "b" * 64, "origin": "outside", "command": None,
                            "added": "a" * 90, "added_lines": 1}, t=6000),
        ev(9, "port_open", {"port": 8000, "process": "python3", "open": True}, t=7000),
    ])
    send(1, h0, [ev(10, "focus", {"target": "window", "state": "in"}, t=400_000)], offline_ms=120_000)
    send(5, "f" * 64, [ev(11, "focus", {"target": "window", "state": "out"}, t=410_000)])  # batches 2-4 never arrived

    rep = c.get(f"/api/review/sessions/{sid}/replay", headers=ADMIN).json()
    assert [f["path"] for f in rep["files"]] == [f"{W}/main.c", f"{W}/util.h"]
    assert rep["edits"] == rep["files"][0]["edits"] and len(rep["edits"]) == 1

    lanes = c.get(f"/api/review/sessions/{sid}/sandbox", headers=ADMIN).json()
    [cmd] = lanes["commands"]
    assert cmd["command"] == "gcc main.c" and cmd["exit_code"] == 1 and cmd["tail"] == "main.c:1: error" and cmd["t"] == 1.0
    assert [(s["origin"], s["explained"]) for s in lanes["saves"]] == [("terminal-editor", False), ("outside", False)]
    assert lanes["ports"] == [{"t": 7.0, "port": 8000, "process": "python3", "open": True}]
    assert lanes["signed"] is True
    assert lanes["offline"] == [{"t": 280.0, "end": 400.0, "seconds": 120, "lag_s": lanes["offline"][0]["lag_s"]}]
    assert [b["problem"] for b in lanes["breaks"]] == ["chain_break"] and lanes["breaks"][0]["t"] == 410.0

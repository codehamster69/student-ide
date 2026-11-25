"""Paste guard (schema v4): blocked outside pastes are logged, in-IDE pastes count as normal editing."""

from fastapi.testclient import TestClient

from studentide import similarity
from studentide.app import create_app
from studentide.review import _evidence_events
from studentide.schema import SCHEMA_VERSION, is_internal_paste, is_outside_paste


def clip(seq, t, action="paste", **extra):
    return {"seq": seq, "t": t, "type": "clipboard",
            "data": {"action": action, "length": 5, "lines": 1, "text": "hello", **extra}}


def edit(seq, t, text, origin):
    return {"seq": seq, "t": t, "type": "edit",
            "data": {"origin": origin, "changes": [[0, 0, text]], "len_before": 0, "len_after": len(text)}}


def test_origins():
    assert SCHEMA_VERSION == 4
    assert is_outside_paste("input.paste") and is_outside_paste("input.drop")
    assert not is_outside_paste("input.paste.internal") and not is_outside_paste("input.drop.internal")
    assert not is_outside_paste("input.type")
    assert is_internal_paste("input.paste.internal") and not is_internal_paste("input.paste")


def test_v4_events_are_accepted(tmp_path):
    c = TestClient(create_app(tmp_path / "t.sqlite3", admin_token="t", serve_frontend=False))
    c.post("/api/consent", json={"student_id": "PG25CS07"})
    sid = c.post("/api/sessions", json={"student_id": "PG25CS07", "task_id": "free"}).json()["session_id"]
    events = [clip(0, 1, source="external", blocked=True), clip(1, 2, source="editor"), edit(2, 3, "hello", "input.paste.internal"),
              clip(3, 4, "drop", source="external", blocked=True), clip(4, 5, source="external", blocked=True, surface="terminal")]
    r = c.post(f"/api/sessions/{sid}/events", json={"schema_version": 4, "events": events}).json()
    assert r["rejected"] == [] and r["inserted"] == 5
    bad = c.post(f"/api/sessions/{sid}/events", json={"schema_version": 4, "events": [clip(5, 6, source="llm")]}).json()
    assert len(bad["rejected"]) == 1
    # old clients still send v1 clipboard events without the new fields
    old = c.post(f"/api/sessions/{sid}/events", json={"schema_version": 1, "events": [clip(6, 7)]}).json()
    assert old["rejected"] == []


def test_review_lists_only_outside_pastes_and_marks_blocked():
    events = [clip(0, 1000, source="editor"), clip(1, 2000, source="document"), clip(2, 3000, source="external", blocked=True),
              clip(3, 4000), clip(4, 5000, "drop", source="page")]
    pastes = _evidence_events(events)["pastes"]
    assert [(p["t"], p["blocked"]) for p in pastes] == [(3.0, True), (4.0, False)]


def test_internal_pastes_are_neither_typed_nor_pasted():
    ev = [edit(0, 1, "ab", "input.type"), edit(1, 2, "hello", "input.paste.internal"), edit(2, 3, "world", "input.paste")]
    assert similarity.paste_stats(ev) == {"typed_chars": 2, "pasted_chars": 5, "n_pastes": 1}

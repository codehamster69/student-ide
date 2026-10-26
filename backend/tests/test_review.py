"""Review timeline API (phase 3) on seeded synthetic students."""

import pytest
from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.db import Database
from studentide.replay import apply_edit
from studentide.review import episodes, parse_h
from studentide.seed import seed

TOKEN = "test-token"
ADMIN = {"X-Admin-Token": TOKEN}


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    path = tmp_path_factory.mktemp("review") / "demo.sqlite3"
    seed(Database(path), n_students=4, minutes=20, log=lambda *_: None)
    return path


@pytest.fixture(scope="module")
def client(seeded):
    return TestClient(create_app(seeded, admin_token=TOKEN, serve_frontend=False))


def test_review_needs_the_admin_token(seeded):
    closed = TestClient(create_app(seeded, admin_token="", serve_frontend=False))
    assert closed.get("/api/review/students", headers=ADMIN).status_code == 403
    open_ = TestClient(create_app(seeded, admin_token=TOKEN, serve_frontend=False))
    assert open_.get("/api/review/students").status_code == 401
    assert open_.get("/api/review/students", headers={"X-Admin-Token": "nope"}).status_code == 401


def test_students_and_session_summaries(client):
    students = client.get("/api/review/students", headers=ADMIN).json()
    assert [s["student_id"] for s in students] == ["DEMO01", "DEMO02", "DEMO03", "DEMO04"]
    assert all(s["n_sessions"] == 6 and s["n_baseline"] == 4 and s["baseline_ready"] for s in students)
    rows = client.get("/api/review/sessions", headers=ADMIN, params={"student_id": "DEMO01"}).json()
    assert [r["phase"] for r in rows] == ["baseline"] * 4 + ["assessed"] * 2
    assert all(r["baseline"] == "ready" and set(r["spark"]) == {"identity", "process"} for r in rows)
    assert all(r["synthetic"]["student"] == "DEMO01" for r in rows)


def test_takeover_session_has_an_identity_episode_with_evidence(client):
    # DEMO01 and DEMO04 each have a takeover by a speed-matched partner; use the first one caught
    rows = client.get("/api/review/sessions", headers=ADMIN).json()
    takeover = next(r for r in rows if r["synthetic"]["condition"] == "takeover"
                    and any(e["channel"] == "identity" for e in r["episodes"]))
    r = client.get(f"/api/review/sessions/{takeover['id']}", headers=ADMIN).json()
    assert set(r["channels"]) == {"identity", "process"}
    n = len(r["windows"])
    assert all(len(c["score"]) == n and len(c["cusum"]) == n for c in r["channels"].values())
    ep = [e for e in r["episodes"] if e["channel"] == "identity"]
    assert ep[0]["switch_est"] <= ep[0]["first_alarm"] <= ep[0]["last_alarm"]
    assert ep[0]["evidence"] and {"feature", "label", "z", "baseline", "observed", "unit"} <= set(ep[0]["evidence"][0])
    # the detector's guess should land near the simulated switch
    assert abs(ep[0]["switch_est"] - r["session"]["synthetic"]["switch_s"]) < 180
    assert r["events"]["runs"] and all(f["until"] >= f["t"] for f in r["events"]["focus"])


def test_replay_rebuilds_the_final_code(client, seeded):
    sid = client.get("/api/review/sessions", headers=ADMIN).json()[-1]["id"]
    rep = client.get(f"/api/review/sessions/{sid}/replay", headers=ADMIN).json()
    doc = rep["initial"]
    for _, changes, _ in rep["edits"]:
        delta = sum(len(t) - (b - a) for a, b, t in changes)
        doc = apply_edit(doc, {"changes": changes, "len_before": len(doc), "len_after": len(doc) + delta})
    end = [e for e in Database(seeded).iter_events(sid, ("snapshot",)) if e["data"]["reason"] == "end"][-1]
    assert doc == end["data"]["text"]
    assert rep["keys"] == sorted(rep["keys"]) and len(rep["keys"]) > 100


def test_student_without_baseline_is_not_scored(client):
    c = client
    c.post("/api/consent", json={"student_id": "NEW01"})
    sid = c.post("/api/sessions", json={"student_id": "NEW01", "task_id": "free"}).json()["session_id"]
    r = c.get(f"/api/review/sessions/{sid}", headers=ADMIN).json()
    assert r["baseline"]["status"] == "insufficient" and r["channels"] == {} and r["episodes"] == []
    assert r["session"]["synthetic"] is None


def test_chained_alarms_merge_into_one_episode():
    alarms = [(300.0, 210.0, "identity"), (360.0, 300.0, "identity"), (420.0, 360.0, "identity"),
              (400.0, 120.0, "process"), (900.0, 700.0, "identity")]
    eps = episodes(alarms, 30.0)
    assert [(e["channel"], e["switch_est"], e["last_alarm"], e["n_alarms"]) for e in eps] == [
        ("process", 120.0, 400.0, 1), ("identity", 210.0, 420.0, 3), ("identity", 700.0, 900.0, 1)]


def test_parse_h():
    assert parse_h("identity=4,process=12.5,bogus=1") == {"identity": 4.0, "process": 12.5}
    assert parse_h(None) == {"identity": 5.25, "process": 16.5}

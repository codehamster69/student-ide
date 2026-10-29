"""Review timeline API (phase 3) on seeded synthetic students."""

import json

import pytest
from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.db import Database
from studentide.replay import apply_edit
from studentide.review import episodes, key_name, load_settings, parse_h
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
    c = TestClient(create_app(seeded, admin_token=TOKEN, serve_frontend=False))
    c.app.state.reviewer.fresh_s = 0  # these tests edit the database directly and expect to see it at once
    return c


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
    assert all(r["baseline"] == "ready" and set(r["spark"]) == set(load_settings().channels) for r in rows)
    assert all(r["synthetic"]["student"] == "DEMO01" for r in rows)


TYPING = ("identity", "pairs")  # the channels that ask whether the hands changed


def test_takeover_session_has_a_typing_episode_with_evidence(client):
    # DEMO01 and DEMO04 each have a takeover by a speed-matched partner; use the first one caught
    rows = client.get("/api/review/sessions", headers=ADMIN).json()
    takeover = next(r for r in rows if r["synthetic"]["condition"] == "takeover"
                    and any(e["channel"] in TYPING for e in r["episodes"]))
    r = client.get(f"/api/review/sessions/{takeover['id']}", headers=ADMIN).json()
    st = load_settings()
    assert set(r["channels"]) == set(st.channels)
    # every channel runs at its frozen window length
    for ch, c in r["channels"].items():
        assert c["window_s"] == st.window_s[ch] and c["h"] == st.h[ch]
        assert len(c["score"]) == len(c["cusum"]) == len(c["start"]) == len(c["end"])
        assert len(c["score"]) == int(r["session"]["duration_s"] // st.window_s[ch])
    assert len(r["windows"]) == len(r["channels"]["identity"]["score"])
    ep = [e for e in r["episodes"] if e["channel"] in TYPING]
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
    base = {"identity": 19.25, "process": 7.25}
    assert parse_h("identity=4,process=12.5,bogus=1", base) == {"identity": 4.0, "process": 12.5}
    assert parse_h(None, base) == base


def test_settings_follow_the_frozen_config(tmp_path):
    cfg = tmp_path / "frozen.json"
    cfg.write_text(json.dumps({"methods": {"thesis": {"kind": "thesis", "process_w": 90, "prior_n": 2.0,
                                                      "pairs": {"channel": "pairs", "k": 0.5, "n": 40}}},
                               "operating_point": {"h": {"identity": 20, "process": 8, "pairs": 11},
                                                   "pair_vocab": ["KeyT>KeyH"]}}))
    st = load_settings(cfg, h_override="")
    assert st.window_s == {"identity": 30.0, "process": 90.0, "pairs": 30.0}
    assert st.k == {"identity": 1.0, "process": 0.5, "pairs": 0.5}
    assert st.h == {"identity": 20.0, "process": 8.0, "pairs": 11.0} and st.prior_n == 2.0
    assert st.pair_channel == "pairs" and st.pair_vocab == ["KeyT>KeyH"]
    assert load_settings(cfg, h_override="pairs=3").h["pairs"] == 3.0
    # no config file: the built-in copy of the frozen settings
    fb = load_settings(tmp_path / "missing.json", h_override="")
    assert fb.source == "built-in" and fb.window_s["process"] == 90.0


def test_key_names():
    assert [key_name(c) for c in ("KeyT", "Digit3", "Space", "Period", "F5")] == ["t", "3", "space", ".", "F5"]


def test_competition_sessions_have_their_own_baseline():
    from studentide.review import Reviewer

    day = 86400
    lab = [{"id": f"l{i}", "lab_id": None, "context": "lab", "started_at": i * day, "n_events": 9} for i in range(3)]
    comp = [{"id": f"c{i}", "lab_id": f"comp{i // 2}", "context": "competition", "started_at": (i + 1) * day + 5,
             "n_events": 9} for i in range(5)]
    r = Reviewer.__new__(Reviewer)
    # a lab baseline never takes in competition sittings, even inside the first four weeks
    assert r.baseline_ids(lab + comp) == ["l0", "l1", "l2"]
    # a competition is compared only with the same student's other competitions
    assert r.baseline_ids(lab + comp, "competition", "comp0") == ["c2", "c3", "c4"]
    assert r.baseline_ids(lab + comp, "competition", "comp2") == ["c0", "c1", "c2", "c3"]


def test_review_tags_competition_sessions(client, seeded):
    db = Database(seeded)
    sid = next(s["id"] for s in db.list_sessions("DEMO01") if s["lab_id"])
    with db.connect() as conn:
        conn.execute("INSERT INTO labs(id, title, created_at, updated_at, kind) VALUES ('lab_cmp', 'Sprint', 0, 0, 'competition')")
        conn.execute("UPDATE sessions SET lab_id = 'lab_cmp' WHERE id = ?", (sid,))
    try:
        r = client.get(f"/api/review/sessions/{sid}", headers=ADMIN).json()
        assert r["session"]["context"] == "competition" and r["baseline"]["context"] == "competition"
        assert r["baseline"]["status"] == "insufficient"  # no other competition yet: nothing to compare with
        assert all(i != sid for i in r["baseline"]["session_ids"])
    finally:
        with db.connect() as conn:
            conn.execute("UPDATE sessions SET lab_id = 'lab_demo1' WHERE id = ?", (sid,))
            conn.execute("DELETE FROM labs WHERE id = 'lab_cmp'")


def test_review_list_reads_the_sessions_once(seeded):
    """Each summary used to re-query every session (with event counts): with a
    class online the list took tens of seconds and froze the server."""
    c = TestClient(create_app(seeded, admin_token=TOKEN, serve_frontend=False))
    rv = c.app.state.reviewer
    calls = []
    load = rv._load_sessions
    rv._load_sessions = lambda: calls.append(1) or load()
    rows = c.get("/api/review/sessions", headers=ADMIN).json()
    assert len(rows) > 4 and len(calls) <= 2  # the warm-up thread may load once too

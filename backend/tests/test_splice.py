"""Classroom corpus (no labels), the shared pilot split, and spliced takeovers."""

import numpy as np
import pytest

from studentide.db import Database
from studentide.detector.features import streams
from studentide.detector.synth import generate_session, population
from studentide.harness.corpus import classroom_corpus
from studentide.harness.engine import outcomes, score_run
from studentide.harness.methods import thesis_detector
from studentide.harness.splice import SNAP_S, add_splices, splice_session, splice_streams, splice_windows
from studentide.harness.split import PILOT_TEST_FROM, assign, pilot_split


def _st(seed, ty=0):
    pop = population(2, 0)
    ev, _ = generate_session(pop[ty], "honest", duration_s=300, seed=seed)
    return streams(ev)


def test_splice_streams_keeps_a_before_and_shifted_b_after():
    a, b = _st(1, 0), _st(2, 1)
    s = splice_streams(a, b, 120.0, 60.0)
    na = int((a.k_t < 120_000).sum())
    nb = int((b.k_t >= 60_000).sum())
    assert len(s.k_t) == len(s.k_code) == len(s.k_hold) == na + nb
    assert np.all(np.diff(s.k_t) >= 0)
    assert np.array_equal(s.k_t[:na], a.k_t[:na])
    assert s.k_t[na] == pytest.approx(b.k_t[b.k_t >= 60_000][0] + 60_000)
    assert s.k_code[na:] == [c for c, t in zip(b.k_code, b.k_t) if t >= 60_000]
    assert len(s.e_t) == len(s.e_paste) and s.duration_ms == pytest.approx(b.duration_ms + 60_000)


def test_splice_windows_join_on_a_boundary():
    wa = [{"start": t, "end": t + 30, "x": "a"} for t in range(0, 300, 30)]
    wb = [{"start": t, "end": t + 30, "x": "b"} for t in range(0, 300, 30)]
    w = splice_windows(wa, wb, 90.0)
    assert [x["x"] for x in w] == ["a"] * 3 + ["b"] * 7
    assert [x["start"] for x in w] == list(range(0, 300, 30))


def test_pilot_split_holds_out_later_weeks_and_test_hash_students():
    ids = [f"S{i}" for i in range(50)]
    side = assign(ids)
    for s in ids:
        assert pilot_split(s, PILOT_TEST_FROM - 1) == side[s]
        assert pilot_split(s, PILOT_TEST_FROM) == "test"


@pytest.fixture(scope="module")
def classroom(tmp_path_factory):
    """Four students, two 6-minute sessions each on one question, before the test cut."""
    path = tmp_path_factory.mktemp("cls") / "pilot.sqlite3"
    db = Database(str(path))
    pop = population(4, 1)
    for i, ty in enumerate(pop):
        db.get_or_create_student(ty.id)
        for j in range(2):
            ev, _ = generate_session(ty, "honest", duration_s=360, seed=i * 10 + j)
            sid = f"{ty.id}-{j}"
            db.create_session(sid, ty.id, "q1", 1, {"user_agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120"})
            db.insert_events(sid, ev)
            with db.connect() as con:
                con.execute("UPDATE sessions SET started_at = ?, question_id = 'q1' WHERE id = ?",
                            (1_700_000_000 + j * 86400 + i, sid))
    return path


def test_classroom_corpus_baseline_is_earliest_minutes(classroom):
    c = classroom_corpus(classroom, baseline_min=2, test_frac=0.0)
    assert len(c.students) == 4
    for st in c.students:
        roles = [s.role for s in sorted(c.sessions, key=lambda s: s.order) if s.student == st]
        assert roles == ["baseline", "test"]  # the first session has well over 2 active minutes
        assert c.students[st]["device"] == "lab-PC-like"  # one fingerprint shared by 4 students
    assert all(s.condition == "honest" and s.switch_s is None for s in c.sessions)


def test_add_splices_pairs_same_question_other_students(classroom):
    c = classroom_corpus(classroom, baseline_min=2, test_frac=0.0)
    made = add_splices(c, seed=1, test_frac=0.0)
    assert len(made) == 4  # one per honest test session
    by_id = {s.id: s for s in c.sessions}
    for s in made:
        a_id, rest = s.id.split("~")
        b = by_id[rest.split("@")[0]]
        assert b.student != s.student and s.partner == b.student
        assert s.variant == "takeover" and s.switch_s % SNAP_S == 0 and 180 <= s.switch_s
        a = by_id[a_id]
        assert np.array_equal(s.st.k_t[s.st.k_t < s.switch_s * 1000], a.st.k_t[a.st.k_t < s.switch_s * 1000])
    assert add_splices(classroom_corpus(classroom, baseline_min=2, test_frac=0.0), seed=1, test_frac=0.0)[0].id == made[0].id


def test_purged_sessions_splice_by_stored_windows(classroom):
    c = classroom_corpus(classroom, baseline_min=2, test_frac=0.0)
    a, b = [s for s in c.sessions if s.role == "test"][:2]
    b.win = {30.0: c.windows(b, 30.0), 90.0: c.windows(b, 90.0)}
    b.meta["purged"] = True
    s = splice_session(c, a, b, 180.0, "takeover")
    assert s.meta["windows_only"] and sorted(s.win) == [30.0, 90.0]
    w = c.windows(s, 30.0)
    assert w[:6] == c.windows(a, 30.0)[:6] and w[6]["start"] == 180.0


def test_detector_scores_spliced_classroom_sessions(classroom):
    c = classroom_corpus(classroom, baseline_min=2, test_frac=0.0)
    add_splices(c, seed=1, test_frac=0.0)
    run = score_run(thesis_detector(), c, list(c.students), list(c.students))
    recs = outcomes([run], c, source="self")
    assert {r["condition"] for r in recs} == {"honest", "takeover"}


def test_harness_dev_then_test_on_classroom_data(tmp_path):
    from studentide.harness.run import main as harness_main
    db = Database(str(tmp_path / "pilot.sqlite3"))
    for i, ty in enumerate(population(10, 4)):
        db.get_or_create_student(ty.id)
        for j in range(3):
            ev, _ = generate_session(ty, "honest", duration_s=480, seed=i * 10 + j)
            sid = f"{ty.id}-{j}"
            db.create_session(sid, ty.id, "q1", 1, {})
            db.insert_events(sid, ev)
            with db.connect() as con:
                con.execute("UPDATE sessions SET started_at = ?, question_id = 'q1' WHERE id = ?",
                            (1_700_000_000 + j * 86400 + i, sid))
    args = ["--db", str(tmp_path / "pilot.sqlite3"), "--classroom", "--baseline-min", "6", "--test-frac", "0.4",
            "--out", str(tmp_path / "out"), "--workers", "1", "--typenet-steps", "20"]
    harness_main(["dev", *args])
    harness_main(["test", *args])
    assert (tmp_path / "out/test-ledger.jsonl").read_text().count("\n") == 1


def test_compare_scores_configs_at_their_own_operating_point(classroom, tmp_path):
    import json
    from pathlib import Path
    from studentide.harness.run import main as harness_main
    frozen = Path(__file__).resolve().parents[2] / "thesis/evaluation/frozen-config.json"
    loose = json.loads(frozen.read_text())
    loose["operating_point"]["k"] = {ch: 2.0 for ch in loose["operating_point"]["k"]}
    (tmp_path / "k2.json").write_text(json.dumps(loose))
    harness_main(["compare", "--db", str(classroom), "--classroom", "--baseline-min", "2", "--test-frac", "0",
                  "--configs", str(frozen), str(tmp_path / "k2.json"), "--compare-out", str(tmp_path / "c.json")])
    out = json.loads((tmp_path / "c.json").read_text())
    a, b = out["configs"].values()
    assert out["dev_students"] == 4 and a["honest_sessions"] == 4
    assert b["fa_per_h"] <= a["fa_per_h"]  # a larger k can only remove alarms at the same h
    assert "takeover" in a and a["takeover"]["n"] == 4

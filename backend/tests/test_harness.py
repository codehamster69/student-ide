import numpy as np
import pytest

from studentide.db import Database
from studentide.detector.detector import cusum
from studentide.harness import rq2
from studentide.harness.alarms import H_GRID, calibrate, grid
from studentide.harness.corpus import db_corpus, synthetic_corpus, write_manifest_template
from studentide.harness.engine import outcomes, precision, score_run, summarise
from studentide.harness.lstm import LSTMEmbedder, triplet_loss
from studentide.harness.methods import ScaledManhattan, Series, TypeNetStyle, nosi_style, thesis_detector
from studentide.harness.run import main as harness_main
from studentide.harness.split import Ledger, assign, folds, split


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    return synthetic_corpus(10, seed=3, n_base=3, minutes=6, cache=tmp_path_factory.mktemp("cache"), workers=2,
                            log=lambda *a: None)


def test_split_is_by_student_deterministic_and_stable():
    ids = [f"S{i:03d}" for i in range(200)]
    a = assign(ids)
    assert a == assign(list(reversed(ids)))  # order does not matter
    assert assign(ids + ["NEW1", "NEW2"])["S005"] == a["S005"]  # adding students moves nobody
    dev, test = split(ids)
    assert not set(dev) & set(test) and len(dev) + len(test) == 200
    assert 0.2 < len(test) / 200 < 0.4
    f = folds(dev, 5)
    assert sorted(s for fo in f for s in fo) == sorted(dev)


def test_cusum_grid_matches_the_detector_cusum():
    r = np.random.default_rng(0)
    x = r.normal(0, 1.5, 120)
    x[40:] += 2
    x[r.choice(120, 10)] = np.nan
    s = Series(np.arange(120) * 30.0, np.arange(1, 121) * 30.0, x)
    g = grid(s, 0.5, 1200.0)
    for hi in (5, 20, 40):
        h = H_GRID[hi]
        _, al, st = cusum(list(x), 0.5, h)
        assert g.n_alarms[hi] == len(al)
        after = [(a, b) for a, b in zip(al, st) if s.end[a] > 1200]
        assert g.n_before[hi] == len(al) - len(after)
        if after:
            assert g.first_after[hi] == s.end[after[0][0]] and g.est_switch[hi] == s.start[after[0][1]]


def test_calibrate_picks_smallest_h_meeting_target():
    s = Series(np.arange(60) * 30.0, np.arange(1, 61) * 30.0, np.random.default_rng(1).normal(0, 1, 60))
    gs = [grid(s, 0.5, None)]
    i = calibrate(gs, 0.5, 2.0)
    assert gs[0].n_alarms[i] / 0.5 <= 2.0
    assert i == 0 or gs[0].n_alarms[i - 1] / 0.5 > 2.0


def test_precision_formula():
    assert precision(0.8, 0.1, 0.01) == pytest.approx(0.008 / (0.008 + 0.099))
    assert precision(1.0, 0.0, 0.002) == 1.0


def test_lstm_gradients_match_finite_differences():
    r = np.random.default_rng(0)
    m = LSTMEmbedder(5, hidden=6, emb=4, seed=1)
    X = r.normal(size=(9, 7, 5))

    def loss():
        e = m.forward(X)
        return triplet_loss(e[:3], e[3:6], e[6:], 1.5)[0]

    e, hT, cache = m.forward(X, keep=True)
    _, ga, gp, gn = triplet_loss(e[:3], e[3:6], e[6:], 1.5)
    g = m.backward(np.concatenate([ga, gp, gn]), hT, cache)
    for k, P in m.p.items():
        idx = tuple(r.integers(0, n) for n in P.shape)
        old = P[idx]
        P[idx] = old + 1e-5
        a = loss()
        P[idx] = old - 1e-5
        b = loss()
        P[idx] = old
        assert (a - b) / 2e-5 == pytest.approx(g[k][idx], rel=1e-4, abs=1e-8)


PAIRS = {"channel": "pairs", "k": 0.5, "n": 20}


@pytest.mark.parametrize("make", [thesis_detector, lambda: thesis_detector(pairs=PAIRS),
                                  lambda: thesis_detector(pairs={"channel": "identity", "block": 1.0, "n": 20}),
                                  nosi_style, ScaledManhattan, lambda: TypeNetStyle(steps=30)])
def test_every_method_scores_every_test_session(corpus, make):
    dev, test = split(corpus.students, 0.3)
    m = make()
    run = score_run(m, corpus, dev, test, n_base=3)
    assert {s.id for s in run.eval_sessions} == {s.id for s in corpus.tests(test)}
    for s in run.eval_sessions:
        for ch, x in run.series[s.id].items():
            assert len(x.start) == len(x.end) == len(x.x)
    assert run.holdout and all(s.student in dev and s.condition == "honest" for s, _ in run.holdout)
    recs = outcomes([run], corpus, "pooled", 1.0)
    summ = summarise(recs)
    assert summ["honest"]["n"] == 2 * len(test)
    assert 0 <= summ["tpr"] <= 1


def test_population_parts_never_see_test_students(corpus, monkeypatch):
    dev, test = split(corpus.students, 0.3)
    seen = []
    m = thesis_detector(prior_n=2.0, pairs=PAIRS)
    orig = corpus.baseline

    def spy(st, n=None):
        seen.append(st)
        return orig(st, n)

    monkeypatch.setattr(corpus, "baseline", spy)
    m.fit_population(corpus, dev, 3)
    assert seen and set(seen) <= set(dev)
    # the key-pair vocabulary comes from dev baselines too and becomes the pair channel's features
    assert m.vocab and m.channels["pairs"].features == ["pk:" + p for p in m.vocab]


def test_rq2_lopo_runs(corpus):
    res = rq2.run(corpus, list(corpus.students), windows=[60], log=lambda *a: None)
    w = res["windows"][0]
    assert 0 <= w["nosi"] <= 1 and 0 <= w["process"] <= 1
    assert res["comments"]["n_chunks"]["code"] > 0


def test_db_corpus_reads_recorded_sessions_with_a_manifest(tmp_path):
    from studentide.detector.synth import generate_session, population
    db = Database(str(tmp_path / "study.sqlite3"))
    pop = population(2, 0)
    rows = []
    for i, ty in enumerate(pop):
        db.get_or_create_student(ty.id)
        for j, cond in enumerate(["honest", "honest", "takeover"]):
            ev, truth = generate_session(ty, cond, other=pop[1 - i], duration_s=180, switch_s=60, seed=i * 10 + j)
            sid = f"{ty.id}-{j}"
            db.create_session(sid, ty.id, "t1", 1, {})
            db.insert_events(sid, ev)
            day = 1_700_000_000 + (j if cond == "honest" else 40) * 86400  # the takeover is staged after the baseline weeks
            with db.connect() as con:
                con.execute("UPDATE sessions SET started_at = ? WHERE id = ?", (day, sid))
            rows.append((sid, cond, truth.switch_t / 1000 if truth.switch_t else ""))
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "sessions.csv").write_text("session_id,role,condition,variant,switch_s,partner\n" +
                                         "".join(f"{a},,{c},,{d},\n" for a, c, d in rows))
    (labels / "students.csv").write_text("student,layout\n" + "".join(f"{t.id},qwerty\n" for t in pop))
    c = db_corpus(tmp_path / "study.sqlite3", labels)
    assert len(c.sessions) == 6
    assert sum(s.role == "baseline" for s in c.sessions) == 4  # honest, within 28 days -> baseline
    tk = [s for s in c.sessions if s.condition == "takeover"]
    assert len(tk) == 2 and all(s.role == "test" and s.switch_s > 0 for s in tk)
    assert c.students[pop[0].id]["layout"] == "qwerty"
    write_manifest_template(c, tmp_path / "copy")
    assert (tmp_path / "copy/sessions.csv").read_text().count("\n") == 7


def test_test_mode_needs_a_frozen_config_and_logs_every_run(tmp_path):
    with pytest.raises(SystemExit, match="frozen"):
        harness_main(["test", "--typists", "10", "--minutes", "6", "--out", str(tmp_path), "--cache", str(tmp_path / "c")])
    led = Ledger(tmp_path / "test-ledger.jsonl")
    led.record({"corpus": "abc", "config": "x1", "reason": "first"})
    assert led.previous("abc", "x1") and not led.previous("abc", "x2")
    assert len(led.entries()) == 1

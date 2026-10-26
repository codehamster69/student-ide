import math

import numpy as np
import pytest

from studentide.detector.detector import (Baseline, channel_features, cusum, detect, detect_channels, feature_weights,
                                         fit_channels, pair_block_weights)
from studentide.detector.features import (FEATURES, PAIR_PREFIX, _in_comment, add_pair_features, feature_group, lscale,
                                          pair_vocabulary, streams, window_features)
from studentide.detector.synth import CONDITIONS, generate_session, key_for, nearest_speed, population
from studentide.replay import final_text
from studentide.schema import Event

POP = population(4, seed=1)


@pytest.mark.parametrize("cond", CONDITIONS)
def test_synthetic_sessions_match_the_editor_schema_and_replay(cond):
    ev, truth = generate_session(POP[0], cond, other=POP[1], duration_s=300, switch_s=120, seed=5)
    for e in ev:
        Event.model_validate(e)  # same validation the ingest API applies
    assert [e["seq"] for e in ev] == list(range(len(ev)))
    final = final_text(ev)  # raises if replay disagrees with any snapshot
    assert final == ev[-2]["data"]["text"]
    if cond == "honest":
        assert truth.switch_t is None
    elif cond == "proxy":
        assert truth.switch_t == 0 and truth.author_after == POP[1].id
    else:
        assert 120_000 <= truth.switch_t < 300_000


def test_generator_is_deterministic():
    a, _ = generate_session(POP[0], "takeover", other=POP[1], duration_s=120, seed=9)
    b, _ = generate_session(POP[0], "takeover", other=POP[1], duration_s=120, seed=9)
    assert a == b


def test_paste_condition_logs_clipboard_and_paste_edits():
    ev, truth = generate_session(POP[2], "paste", duration_s=600, switch_s=60, seed=3)
    pastes = [e for e in ev if e["type"] == "edit" and e["data"]["origin"] == "input.paste"]
    assert pastes and all(e["t"] >= truth.switch_t - 20_000 for e in pastes)
    assert any(e["type"] == "clipboard" for e in ev)


def test_key_mapping():
    assert key_for("a") == ("KeyA", False, "letter")
    assert key_for("A") == ("KeyA", True, "letter")
    assert key_for("(") == ("Digit9", True, "punct")
    assert key_for("#") == ("Digit3", True, "punct")
    assert key_for(" ")[0] == "Space"


def test_comment_detection_ignores_hash_in_strings():
    assert _in_comment("x = 1  # note", 13)
    assert not _in_comment("x = 1  # note", 5)
    assert not _in_comment('s = "#not a comment', 19)
    assert _in_comment("a\n    # hi", 10)


def test_lscale_matches_definition():
    x = np.array([1.0, 2.0, 4.0, 7.0])
    pairs = [abs(a - b) for i, a in enumerate(x) for b in x[i + 1:]]
    assert lscale(x) == pytest.approx(0.5 * np.mean(pairs))


def test_window_features_and_comment_separation():
    ev, _ = generate_session(POP[0], "honest", duration_s=600, seed=2)
    s = streams(ev)
    assert len(s.k_t) > 300 and s.k_comment.any() and not s.k_comment.all()
    w = window_features(s, 30)
    assert len(w) == int(s.duration_ms // 30_000)
    active = [x for x in w if x["active"]]
    assert active
    for x in active:
        assert set(FEATURES) <= set(x)
        assert 3 < x["dg_median"] < 8  # log ms
    mixed = window_features(s, 30, comments="mixed")
    assert sum(x["n_keys"] for x in mixed) > sum(x["n_keys"] for x in w)


def test_key_pair_features():
    ev, _ = generate_session(POP[0], "honest", duration_s=600, seed=2)
    w = window_features(streams(ev), 30)
    vocab = pair_vocabulary([w], 10)
    assert len(vocab) == 10 and all(">" in p for p in vocab)
    counts = [sum(x["_pairs"].get(p, (0, 0))[1] for x in w) for p in vocab]
    assert counts == sorted(counts, reverse=True)
    raw = add_pair_features(w, vocab, normalise=False)
    rel = add_pair_features(w, vocab)
    x, r = next((a, b) for a, b in zip(raw, rel) if a["active"] and vocab[0] in a["_pairs"])
    f = PAIR_PREFIX + vocab[0]
    s_, n = x["_pairs"][vocab[0]]
    assert x[f] == pytest.approx(s_ / n) and r[f] == pytest.approx(s_ / n - x["_pace"])
    assert feature_group(f) == "pairs" and f in channel_features("identity", list(FEATURES) + [f])
    # needing two typings per window can only blank features out
    two = add_pair_features(w, vocab, min_count=2)
    assert sum(math.isnan(a[f]) for a in two) >= sum(math.isnan(a[f]) for a in rel)


def test_pair_block_weights():
    feats = ["dg_median", "hold_median", "pk:KeyA>KeyB", "pk:KeyC>KeyD"]
    w = pair_block_weights(feats, {"dg_median": 0.6, "hold_median": 0.4, "pk:KeyA>KeyB": 0.3, "pk:KeyC>KeyD": 0.1}, 2.0)
    assert w["dg_median"] == 0.6 and w["pk:KeyA>KeyB"] + w["pk:KeyC>KeyD"] == pytest.approx(2.0)
    assert w["pk:KeyA>KeyB"] == pytest.approx(3 * w["pk:KeyC>KeyD"])
    eq = pair_block_weights(feats, None, 1.0)
    assert eq["dg_median"] == 1.0 and eq["pk:KeyA>KeyB"] == pytest.approx(1.0)


def test_cusum_alarm_and_switch_estimate():
    x = [0.0] * 20 + [2.0] * 10
    trace, alarms, starts = cusum(x, k=0.5, h=4.0)
    assert alarms[0] == 22  # 1.5 per step after index 19: 1.5, 3.0, 4.5
    assert starts[0] == 20
    assert alarms[1:] == [25, 28]  # S restarts from zero after each alarm
    assert cusum([math.nan, 3.0, math.nan], 0.5, 10)[0] == [0.0, 2.5, 2.5]


def _windows(typist, cond, seed, other=None, minutes=20):
    ev, truth = generate_session(typist, cond, other=other, duration_s=minutes * 60, seed=seed)
    return window_features(streams(ev), 30), truth


def test_baseline_keeps_only_summary_stats_and_round_trips():
    base = [_windows(POP[0], "honest", s)[0] for s in range(3)]
    b = Baseline.fit(POP[0].id, base)
    assert set(b.centre) <= set(FEATURES) and b.sd0 > 0
    assert Baseline.from_json(b.to_json()) == b
    assert "k_t" not in b.to_json()


def test_takeover_by_a_different_typist_raises_the_score():
    pop = population(8, seed=4)
    me = pop[0]
    other = max(pop[1:], key=lambda t: abs(t.mu - me.mu))  # clearly different typist
    base = [_windows(me, "honest", s)[0] for s in range(4)]
    weights = feature_weights({t.id: [_windows(t, "honest", 100 + i)[0]] for i, t in enumerate(pop)})
    chans = fit_channels(me.id, base, weights)
    w, truth = _windows(me, "takeover", 77, other=other, minutes=30)
    sw = truth.switch_t / 1000
    d = chans["identity"].distances(w)
    pre = np.nanmean([v for v, x in zip(d, w) if x["end"] <= sw])
    post = np.nanmean([v for v, x in zip(d, w) if x["start"] >= sw])
    assert post > pre + 1
    dets, alarms = detect_channels(chans, w, {"identity": 8.0, "process": 8.0})
    assert any(a > sw for a, _, ch in alarms if ch == "identity")
    assert isinstance(detect(chans["identity"], w).cusum, list)


def test_nearest_speed_partner():
    p = nearest_speed(POP, POP[0])
    assert p.id != POP[0].id

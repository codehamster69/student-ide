"""Pilot statistics: aggregates only, pseudonymous, and the summary tables run."""

import json

from studentide import pilot
from studentide.db import Database
from studentide.seed import seed


def test_report_is_aggregate_and_pseudonymous(tmp_path):
    path = tmp_path / "demo.sqlite3"
    db = Database(path)
    seed(db, n_students=3, minutes=4, log=lambda *_: None)
    rep = pilot.report(str(path), detector=True, log=lambda *_: None)
    rows = rep["rows"]
    assert len(rows) == 3 * 6
    text = json.dumps(rep)
    assert "DEMO0" not in text  # no roll numbers
    with db.connect() as conn:
        sids = [r[0] for r in conn.execute("SELECT id FROM sessions")]
    assert not any(s in text for s in sids)  # no session ids
    for r in rows:
        assert r["n_events"] > 0 and r["key_downs"] > 0 and r["missing_events"] == 0
        assert r["baseline"] in ("ready", "insufficient")
        assert set(r["features"]) == set(pilot.WINDOW_FEATURES)
    # the synthetic "paste" condition pastes a big block
    assert any("big paste" in r["copying_signs"] for r in rows)
    out = pilot.summary(rep)
    assert "data quality" in out and "detector" in out and "copying signs" in out


def test_pseudonyms_differ_between_runs(tmp_path):
    path = tmp_path / "demo.sqlite3"
    seed(Database(path), n_students=2, minutes=2, log=lambda *_: None)
    a = {r["student"] for r in pilot.session_rows(str(path)).values()}
    b = {r["student"] for r in pilot.session_rows(str(path)).values()}
    assert len(a) == 2 and not a & b


def test_devices_and_signs():
    assert pilot.ua_info("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/156.0.0.0 Safari/537.36")[:2] == ("Windows", "Chrome")
    assert pilot.ua_info("Mozilla/5.0 (Linux; Android 14) Chrome/156.0 Mobile")[0] == "Android"
    r = {"big_pastes": 0, "away_pastes": 1, "typed_no_key": 30, "typed_no_key_chars": 400, "typed_edits": 50}
    assert pilot.copying_signs(r) == ["paste soon after leaving the window", "typed text with no key presses"]

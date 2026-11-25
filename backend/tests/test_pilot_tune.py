"""Pilot re-tune: pastes from inside the IDE, the dev-only split, and the tune tool's output."""

import json

from studentide import pilot_tune
from studentide.db import Database
from studentide.detector.features import fix_paste_frac, internal_paste, squash, streams
from studentide.harness.split import assign
from studentide.seed import seed


def _ev(t, typ, **d):
    return {"t": t, "type": typ, "data": d}


def _edit(t, frm, text, origin, len_before):
    return _ev(t, "edit", origin=origin, changes=[[frm, frm, text]], len_before=len_before, len_after=len_before + len(text))


def test_internal_paste_rules():
    assert internal_paste("input.paste.internal", "anything new", "", [])
    assert internal_paste("input.paste", "for i in range(3):\n    print(i)", "x = 1\nfor i in range(3):\n  print(i)\n", [])
    assert internal_paste("input.paste", "total += x", "", [squash("total  +=  x;")])
    assert internal_paste("input.paste", "Given n numbers", "", [], (squash("Given n numbers, print the sum"),))
    assert not internal_paste("input.paste", "def solve(): return 42", "x = 1", [squash("x = 1")])


def test_own_pastes_do_not_count_as_pasting():
    doc = "a = 1\nb = 2\n"
    code = "print(a + b)\n"
    evs = [_ev(0, "snapshot", text=doc, reason="start"),
           _ev(100, "clipboard", action="copy", length=len(code), lines=1, text=code),
           _edit(200, len(doc), code, "input.paste", len(doc)),
           _edit(300, len(doc) + len(code), "def other():\n    return 99\n", "input.paste", len(doc) + len(code))]
    s = streams(evs)
    assert list(s.e_paste) == [False, True] and s.meta["internal_pastes"] == 1
    assert list(streams(evs, own_pastes=False).e_paste) == [True, True]
    # a purged session's stored window gets paste_frac redone from its edits
    w = fix_paste_frac([{"start": 0.0, "end": 1.0, "active": True, "paste_frac": 1.0}], evs)[0]
    assert 0 < w["paste_frac"] < 1 and w["paste_frac"] == 27 / (27 + len(code))


def test_split_keeps_test_students_and_late_weeks_out():
    early = pilot_tune.TEST_FROM - 86400
    ids = [f"S{i:03d}" for i in range(50)]
    a = assign(ids)
    for sid in ids:
        assert pilot_tune.pilot_split(sid, early) == a[sid]
        assert pilot_tune.pilot_split(sid, pilot_tune.TEST_FROM) == "test"


def test_tune_tool_writes_only_scores_and_pseudonyms(tmp_path):
    path = tmp_path / "demo.sqlite3"
    db = Database(path)
    seed(db, n_students=3, minutes=4, log=lambda *_: None)
    rep = pilot_tune.run(str(path), ["frozen", "device"], log=lambda *_: None, test_from=4e9)
    text = json.dumps(rep)
    assert "DEMO0" not in text
    with db.connect() as conn:
        sids = [r[0] for r in conn.execute("SELECT id FROM sessions")]
        students = [r[0] for r in conn.execute("SELECT id FROM students")]
    assert not any(s in text for s in sids)
    dev = [s for s in students if assign([s])[s] == "dev"]
    assert len({r["student"] for r in rep["rows"]}) == len(dev)
    assert rep["rows"] and all(set(r["v"]) == {"frozen", "device"} for r in rep["rows"])
    s = pilot_tune.summary(rep)
    assert set(s["variants"]) == {"frozen", "device"}
    assert "frozen" in pilot_tune.print_summary(s)
    # with test_from in the past nothing is dev
    assert pilot_tune.run(str(path), ["frozen"], log=lambda *_: None, test_from=0)["rows"] == []

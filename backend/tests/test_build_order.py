"""Build-order features on hand-made mock sessions and edge cases."""

import math
from dataclasses import replace

import numpy as np

from studentide.detector.features import open_blocks, streams, window_features
from studentide.detector.synth import generate_session, key_for, population
from studentide.replay import final_text


class Mock:
    """Builds a schema-v1 event list by typing and pasting at given positions."""

    def __init__(self, text: str = ""):
        self.doc = text
        self.t = 0.0
        self.ev = []
        self._push("session_start", {"wall_clock_ms": 0.0, "reason": None})
        self._push("snapshot", {"reason": "start", "text": text})

    def _push(self, typ, data):
        self.ev.append({"seq": len(self.ev), "t": round(self.t, 3), "type": typ, "data": data})

    def edit(self, changes, origin="input.type"):
        before = len(self.doc)
        for frm, to, text in reversed(changes):
            self.doc = self.doc[:frm] + text + self.doc[to:]
        self._push("edit", {"origin": origin, "changes": [list(c) for c in changes],
                            "len_before": before, "len_after": len(self.doc)})

    def type(self, text: str, at: int | None = None, gap_ms: float = 150):
        pos = len(self.doc) if at is None else at
        for ch in text:
            self.t += gap_ms
            code, shift, cls = key_for(ch)
            self._push("key", {"action": "down", "code": code, "cls": cls, "shift": shift})
            self.edit([(pos, pos, ch)])
            self.t += 60
            self._push("key", {"action": "up", "code": code, "cls": cls, "shift": shift})
            pos += 1
        return pos

    def paste(self, text: str, at: int | None = None):
        pos = len(self.doc) if at is None else at
        self.t += 500
        self.edit([(pos, pos, text)], origin="input.paste")

    def delete(self, frm: int, to: int):
        self.t += 200
        self.edit([(frm, to, "")], origin="delete.selection")

    def end(self):
        self.t += 1000
        self._push("snapshot", {"reason": "end", "text": self.doc})
        self._push("session_end", {"wall_clock_ms": self.t, "reason": "submit"})
        assert final_text(self.ev) == self.doc  # the mock is a valid replayable log
        return self.ev


PROGRAM = [
    "def area(w, h):",
    "    # width times height",
    "    a = w * h",
    "    return a",
    "",
    "for n in range(3):",
    "    print(area(n, 2))",
]


def linear():
    m = Mock()
    for ln in PROGRAM:
        m.type(ln + "\n")
    return m


def skeleton():
    """Block headers first, then go back and fill the bodies in."""
    m = Mock()
    m.type("def area(w, h):\n\nfor n in range(3):\n")
    m.type("    # width times height\n    a = w * h\n    return a\n", at=len("def area(w, h):\n"))
    m.type("    print(area(n, 2))\n")
    return m


def test_linear_writer_never_fills_in():
    s = streams(linear().end())
    assert len(s.l_t) == 5  # 7 lines minus the comment and the blank line
    assert not s.l_fill.any()
    assert s.b_open.max() <= 1  # only the header just typed is open


def test_skeleton_writer_fills_in_and_leaves_blocks_open():
    m = skeleton()
    assert m.doc == "\n".join(PROGRAM) + "\n"
    s = streams(m.end())
    assert len(s.l_t) == 5
    assert s.l_fill.sum() == 2  # `a = ...` and `return a`, typed above `for` (the comment does not count)
    assert s.b_open.max() == 2  # `def` and `for` both without a body at one point


def test_window_features_separate_linear_from_skeleton():
    fl = window_features(streams(linear().end()), 10)[-1]
    fs = window_features(streams(skeleton().end()), 10)[-1]
    assert fl["fill_in_frac"] == 0.0 and fs["fill_in_frac"] > 0.3
    assert fs["open_blocks"] > fl["open_blocks"]


def test_enter_in_the_middle_of_a_line_counts_as_filling_in():
    m = Mock("x = 1; y = 2\n")
    m.type("\n", at=len("x = 1;"))
    s = streams(m.end())
    assert list(s.l_fill) == [True]


def test_multiline_paste_counts_each_code_line():
    m = Mock("def f():\n    return 0\n")
    m.paste("    a = 1\n\n    # note\n    b = 2\n", at=len("def f():\n"))
    s = streams(m.end())
    assert len(s.l_t) == 2 and s.l_fill.all()  # blank and comment lines are skipped


def test_paste_at_end_is_appending():
    m = Mock("x = 1\n")
    m.paste("y = 2\nz = 3\n")
    s = streams(m.end())
    assert len(s.l_t) == 2 and not s.l_fill.any()


def test_trailing_blank_lines_and_comments_do_not_count_as_code_below():
    m = Mock("\n\n# todo\n")
    m.type("x = 1\n", at=0)
    s = streams(m.end())
    assert list(s.l_fill) == [False]


def test_deleting_lines_records_nothing():
    m = Mock("a = 1\nb = 2\nc = 3\n")
    m.delete(0, 6)
    s = streams(m.end())
    assert len(s.l_t) == 0 and len(s.b_t) == 0


def test_two_changes_in_one_edit():
    m = Mock("a\nb\n")
    m.edit([(0, 0, "x = 0\n"), (2, 2, "y = 0\n")])  # e.g. multi-cursor; pre-edit coordinates
    assert m.doc == "x = 0\na\ny = 0\nb\n"
    s = streams(m.end())
    assert len(s.l_t) == 2 and s.l_fill.all()


def test_reset_to_starter_is_not_writing():
    """The Reset button replaces the code with the starter in one edit: no
    inserted characters, lines or blocks, and later typing is read on the starter."""
    starter = "def f():\n    pass\n"
    before = streams(linear().end())
    m = linear()
    m.t += 2000
    m.edit([(0, len(m.doc), starter)], origin="reset")
    m.type("x = 1\n")
    s = streams(m.end())
    assert len(s.l_t) == len(before.l_t) + 1 and len(s.e_t) == len(before.e_t) + 6
    assert s.e_inserted.max() == 1  # the starter text is not counted as inserted
    assert final_text(m.ev) == starter + "x = 1\n"


def test_open_blocks_edge_cases():
    assert open_blocks("") == 0
    assert open_blocks("if a:  # done?\n") == 1  # trailing comment ignored
    assert open_blocks('s = "x:"\n') == 0  # colon inside a string ends with a quote
    assert open_blocks("d = {1: 2}\n") == 0
    assert open_blocks("if a:\n    # body later\nb = 1\n") == 1  # a comment is not a body
    assert open_blocks("if a:\n\tpass\n") == 0  # tab indentation
    assert open_blocks("class A:\n    def f(self):\n        return 1\n") == 0
    assert open_blocks("class A:\n    def f(self):\n") == 1  # class has a body, f does not


def test_too_few_lines_gives_nan_not_zero():
    m = Mock()
    m.type("x = 1\n")
    w = window_features(streams(m.end()), 1)
    assert all(math.isnan(x["fill_in_frac"]) for x in w)


def test_empty_session():
    m = Mock()
    m.t = 65_000
    w = window_features(streams(m.end()), 30)
    assert len(w) == 2 and not any(x["active"] for x in w)
    assert all(math.isnan(x["fill_in_frac"]) and math.isnan(x["open_blocks"]) for x in w)


def test_simulated_skeleton_typists_fill_in_more():
    base = population(1, seed=11)[0]
    sk, li = replace(base, skeleton_p=1.0), replace(base, skeleton_p=0.0)
    f = lambda ty: streams(generate_session(ty, "honest", duration_s=900, seed=2)[0]).l_fill.mean()  # noqa: E731
    assert f(li) == 0.0
    assert f(sk) > 0.2


def test_new_feature_is_steadier_than_edit_position():
    """The reason for the change: per-window noise of the old edit-position
    feature vs the line-level trailing-span feature, within honest sessions."""
    pop = population(6, seed=21)
    cv_old, cv_new = [], []
    for i, ty in enumerate(pop):
        w = [x for x in window_features(streams(generate_session(ty, "honest", duration_s=1200, seed=i)[0]), 30)
             if x["active"]]
        for key, out in (("nonappend_frac", cv_old), ("fill_in_frac", cv_new)):
            v = np.array([x[key] for x in w if not math.isnan(x[key])])
            out.append(v.std())
    assert np.mean(cv_new) < np.mean(cv_old)

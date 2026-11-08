"""Habit features per time window.

Step 1, `streams()`: one pass over a session's events (replaying the
document as it goes) turns them into flat arrays: key presses with hold
time, hand and whether the caret was inside a comment; edits with position
and origin; pastes; runs; focus losses.

Step 2, `window_features()`: cuts the session into windows of W seconds and
computes the habit features below for each. Keystrokes typed inside a
`# comment` are kept apart from code keystrokes, because comment text is
typed like retyping (fluent, few pauses) and would blur the code rhythm
(Lueder et al., Nosi). They get their own two features, which the detector
ignores unless `comments="mixed"` folds them back in (the ablation).

Latency features are on a log scale (log ms) so that differences mean the
same at every typing speed. A window with too few code keystrokes is
`active=False` and the detector skips it.

Step 3 (optional), `add_pair_features()`: per-key-pair timing. Every window
also keeps, for each key pair typed in flow (`KeyT>KeyH`), the sum and count
of its log latencies. Given a vocabulary of common pairs (fitted on the
population's baseline sessions, `pair_vocabulary()`), each pair becomes a
feature `pk:KeyT>KeyH`: its mean log latency in the window, minus the
window's mean log latency over all pairs when `normalise` is on. The
normalised form describes the *shape* of a person's rhythm (which pairs they
are quick or slow on, relative to their own pace that minute), so it does not
repeat what `dg_median` already says about overall speed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..replay import apply_edit
from .synth import hand

PAUSE_MS = 2000.0  # an inter-key gap at least this long is a pause, not rhythm
MIN_KEYS = 20  # code keystrokes needed for a window to count
MIN_PAIRS = 5  # digraphs needed for a latency statistic
RUN_SPAN_S = 300.0  # run frequency is measured over the trailing five minutes
BUILD_SPAN_S = 300.0  # so is build order: one window holds too few new lines
MIN_LINES = 3  # completed code lines needed for fill_in_frac

# feature -> group. Groups are what the ablation removes.
FEATURES: dict[str, str] = {
    "dg_median": "rhythm",  # median digraph latency
    "dg_lscale": "rhythm",  # L-scale of log inter-key time (Nosi's spread measure)
    "hold_median": "rhythm",  # median key hold time
    "dg_alt_hand": "digraph",  # median latency, hands alternate
    "dg_same_hand": "digraph",  # median latency, same hand
    "dg_to_space": "digraph",  # into the space bar
    "dg_from_space": "digraph",  # out of the space bar
    "dg_shifted": "digraph",  # into a shifted character
    "pause_per_100": "pauses",  # pauses per 100 code keys
    "pause_median": "pauses",  # median pause length (log ms)
    "del_per_100": "revision",  # backspace/delete per 100 code keys
    "del_burst": "revision",  # mean length of a run of deletions
    "fill_in_frac": "build_order",  # new code lines written above existing code, trailing 5 min
    "open_blocks": "build_order",  # block headers (`...:`) still without a body, trailing 5 min
    "run_rate": "runs",  # runs per minute, trailing five minutes
    "focus_out_rate": "focus",  # looks away from the editor per minute
    "paste_frac": "paste",  # share of inserted characters that were pasted
}
PAIR_PREFIX = "pk:"  # per-key-pair features, named pk:<code>><code>, group "pairs"
COMMENT_FEATURES = ("c_dg_median", "c_key_frac")
# first-version build-order features, still computed for the ablation
# comparison but no longer scored: per-edit position is too noisy per window
LEGACY_FEATURES = ("nonappend_frac", "jump_rate")
GROUPS = tuple(dict.fromkeys(FEATURES.values()))


def feature_group(f: str) -> str:
    """The group of any feature, including the per-pair `pk:` ones."""
    return "pairs" if f.startswith(PAIR_PREFIX) else FEATURES[f]


@dataclass
class Streams:
    duration_ms: float
    # key presses (non-modifier, non-navigation)
    k_t: np.ndarray
    k_code: list[str]
    k_cls: list[str]
    k_shift: np.ndarray
    k_hold: np.ndarray  # ms, NaN if no matching release
    k_comment: np.ndarray
    k_hand: list[str | None]
    # edits
    e_t: np.ndarray
    e_append: np.ndarray  # insertion/deletion at the end of the document
    e_line: np.ndarray
    e_inserted: np.ndarray  # characters inserted
    e_paste: np.ndarray
    run_t: np.ndarray
    focus_out_t: np.ndarray
    # times the student came back to this question from another one in the same
    # lab sitting; a key gap across one is time spent elsewhere, not a pause
    switch_t: np.ndarray = field(default_factory=lambda: np.zeros(0))
    # build order, at line level
    l_t: np.ndarray = field(default_factory=lambda: np.zeros(0))  # a code line was completed
    l_fill: np.ndarray = field(default_factory=lambda: np.zeros(0, bool))  # ... above existing code
    b_t: np.ndarray = field(default_factory=lambda: np.zeros(0))  # open-block count sampled here
    b_open: np.ndarray = field(default_factory=lambda: np.zeros(0))
    meta: dict = field(default_factory=dict)


def _in_comment(doc: str, pos: int) -> bool:
    """Is the caret at `pos` after a '#' that starts a comment on its line?"""
    start = doc.rfind("\n", 0, pos) + 1
    seg = doc[start:pos]
    if "#" not in seg:
        return False
    quote = None
    for ch in seg:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#":
            return True
    return False


def _code_part(line: str) -> str:
    """The line without its trailing comment, stripped; '' for blank/comment lines."""
    if "#" in line:
        quote = None
        for i, ch in enumerate(line):
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "'\"":
                quote = ch
            elif ch == "#":
                line = line[:i]
                break
    return line.strip()


def open_blocks(doc: str) -> int:
    """Block headers (a code line ending in ':') whose next code line is not
    indented deeper, i.e. a def/if/for/class written before its body."""
    code = []
    for ln in doc.split("\n"):
        c = _code_part(ln)
        if c:
            code.append((len(ln) - len(ln.lstrip(" \t")), c))
    n = 0
    for i, (ind, c) in enumerate(code):
        if c.endswith(":") and (i + 1 == len(code) or code[i + 1][0] <= ind):
            n += 1
    return n


def _new_lines(before: str, after: str, frm: int, text: str) -> tuple[int, bool]:
    """For an insertion of `text` at `frm`: how many non-blank, non-comment
    lines it completes, and whether code already follows the insertion
    (the new lines go above existing code, i.e. filling in, not appending)."""
    if "\n" not in text:
        return 0, False
    head = after[after.rfind("\n", 0, frm) + 1: frm + len(text)]
    completed = head.split("\n")[:-1]  # the part after the last newline is not finished yet
    n = sum(1 for ln in completed if _code_part(ln))
    rest = after[frm + len(text):]
    follows = any(_code_part(ln) for ln in rest.split("\n"))
    return n, follows


def streams(events: list[dict]) -> Streams:
    doc: str | None = None
    caret = 0
    # schema v2: a desktop workspace has several files; each edit/snapshot names its path
    # (None = the single document of a web session). `doc` is always the current file's text.
    docs: dict[str | None, str | None] = {}
    cur: str | None = None
    k_t, k_code, k_cls, k_shift, k_hold, k_comment, k_hand = [], [], [], [], [], [], []
    open_down: dict[str, int] = {}
    e_t, e_app, e_line, e_ins, e_paste = [], [], [], [], []
    run_t, focus_t, switch_t = [], [], []
    l_t, l_fill, b_t, b_open = [], [], [], []
    end = 0.0
    for ev in events:
        typ, d, t = ev["type"], ev["data"], ev["t"]
        end = max(end, t)
        if typ in ("snapshot", "edit") and d.get("path") != cur:
            docs[cur] = doc
            cur = d.get("path")
            doc = docs.get(cur)
        if typ == "snapshot":
            if doc is None:
                doc = d["text"]
        elif typ == "key":
            # terminal keys (shell prompt, vim/nano in the desktop terminal) are recorded but kept
            # out of the identity channel until tested on the dev split (plan 4.2)
            if d.get("surface", "editor") != "editor":
                continue
            if d["cls"] in ("modifier", "nav") or d.get("ctrl") or d.get("meta"):
                continue
            if d["action"] == "down":
                if d.get("repeat"):
                    continue
                open_down[d["code"]] = len(k_t)
                k_t.append(t)
                k_code.append(d["code"])
                k_cls.append(d["cls"])
                k_shift.append(bool(d.get("shift")))
                k_hold.append(math.nan)
                k_comment.append(_in_comment(doc or "", caret))
                k_hand.append(hand(d["code"]))
            else:
                i = open_down.pop(d["code"], None)
                if i is not None:
                    k_hold[i] = t - k_t[i]
        elif typ == "edit":
            doc = doc or ""
            ch = d["changes"]
            # Reset button (back to the starter code) or "reload" (a desktop file changed on disk by the
            # terminal, vim or a tool): the text changes but nothing was typed in the editor
            if d["origin"] in ("reset", "reload"):
                doc = apply_edit(doc, d)
                caret = 0
                continue
            if ch:
                frm = ch[0][0]
                ins = sum(len(c[2]) for c in ch)
                e_t.append(t)
                e_app.append(ch[-1][1] >= d["len_before"] - 1)
                e_line.append(doc.count("\n", 0, frm))
                e_ins.append(ins)
                e_paste.append(d["origin"].startswith("input.paste") or d["origin"].startswith("input.drop"))
                last = ch[-1]
                caret = last[0] + len(last[2]) + sum(len(c[2]) - (c[1] - c[0]) for c in ch[:-1])
            before = doc
            doc = apply_edit(doc, d)
            completed = False
            shift = 0
            for frm, to, text in ch:
                n, follows = _new_lines(before, doc, frm + shift, text)
                shift += len(text) - (to - frm)
                if n:
                    l_t.extend([t] * n)
                    l_fill.extend([follows] * n)
                    completed = True
            if completed:
                b_t.append(t)
                b_open.append(open_blocks(doc))
        elif typ == "cursor":
            caret = d["head"]
            if doc is not None:
                e_t.append(t)
                e_app.append(caret >= len(doc) - 1)
                e_line.append(d["line"] - 1)
                e_ins.append(0)
                e_paste.append(False)
        elif typ == "run":
            run_t.append(t)
        elif typ == "focus":
            if d["state"] == "out" and d["target"] in ("window", "page"):
                focus_t.append(t)
            elif d["state"] == "in" and d["target"] == "question":
                switch_t.append(t)
    a = np.asarray
    return Streams(
        duration_ms=end,
        k_t=a(k_t, float), k_code=k_code, k_cls=k_cls, k_shift=a(k_shift, bool),
        k_hold=a(k_hold, float), k_comment=a(k_comment, bool), k_hand=k_hand,
        e_t=a(e_t, float), e_append=a(e_app, bool), e_line=a(e_line, float),
        e_inserted=a(e_ins, float), e_paste=a(e_paste, bool),
        run_t=a(run_t, float), focus_out_t=a(focus_t, float), switch_t=a(switch_t, float),
        l_t=a(l_t, float), l_fill=a(l_fill, bool), b_t=a(b_t, float), b_open=a(b_open, float),
    )


def lscale(x: np.ndarray) -> float:
    """Second sample L-moment (half the mean absolute pairwise difference)."""
    n = len(x)
    if n < 2:
        return math.nan
    xs = np.sort(x)
    i = np.arange(n)
    b0 = xs.mean()
    b1 = (i * xs).sum() / (n * (n - 1))
    return 2 * b1 - b0


def _logmed(x: np.ndarray, min_n: int = MIN_PAIRS) -> float:
    return float(np.log(np.median(x))) if len(x) >= min_n else math.nan


def _across_switch(s: Streams, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """For key pairs (a[i], b[i]): did the student come back from another question in between?"""
    if not len(s.switch_t):
        return np.zeros(len(a), bool)
    return np.searchsorted(s.switch_t, b, side="right") > np.searchsorted(s.switch_t, a, side="right")


def _window(s: Streams, lo: float, hi: float, comments: str) -> dict:
    W_min = (hi - lo) / 60000
    ki = np.flatnonzero((s.k_t >= lo) & (s.k_t < hi))
    comment = s.k_comment[ki]
    code_i = ki if comments == "mixed" else ki[~comment]
    com_i = ki[comment]
    cls = s.k_cls
    is_del = np.array([cls[i] in ("backspace", "delete") for i in code_i], bool)
    n_code = int((~is_del).sum())
    f: dict = {"start": lo / 1000, "end": hi / 1000, "n_keys": n_code, "active": n_code >= MIN_KEYS}

    # digraphs: consecutive code keys, neither a deletion, gap below the pause threshold
    typing = code_i[~is_del]
    lat_all = np.diff(s.k_t[code_i]) if len(code_i) > 1 else np.zeros(0)
    if len(lat_all):
        lat_all = lat_all[~_across_switch(s, s.k_t[code_i[:-1]], s.k_t[code_i[1:]])]
    pairs_a, pairs_b = typing[:-1], typing[1:]
    # keep only pairs that were adjacent in the full key stream (no deletion between)
    pos = {k: j for j, k in enumerate(ki)}
    adj = np.array([pos[b] - pos[a] == 1 for a, b in zip(pairs_a, pairs_b)], bool) if len(typing) > 1 else np.zeros(0, bool)
    pa, pb = pairs_a[adj], pairs_b[adj]
    lat = s.k_t[pb] - s.k_t[pa]
    flow = (lat < PAUSE_MS) & ~_across_switch(s, s.k_t[pa], s.k_t[pb])
    pa, pb, lat = pa[flow], pb[flow], lat[flow]
    f["dg_median"] = _logmed(lat)
    f["dg_lscale"] = lscale(np.log(lat)) if len(lat) >= MIN_PAIRS else math.nan
    holds = s.k_hold[typing]
    holds = holds[~np.isnan(holds)]
    f["hold_median"] = _logmed(holds)
    hands_a = [s.k_hand[i] for i in pa]
    hands_b = [s.k_hand[i] for i in pb]
    alt = np.array([x is not None and y is not None and x != y for x, y in zip(hands_a, hands_b)], bool)
    same = np.array([x is not None and x == y for x, y in zip(hands_a, hands_b)], bool)
    to_sp = np.array([s.k_code[i] == "Space" for i in pb], bool)
    from_sp = np.array([s.k_code[i] == "Space" for i in pa], bool)
    shifted = s.k_shift[pb] if len(pb) else np.zeros(0, bool)
    f["dg_alt_hand"] = _logmed(lat[alt]) if len(lat) else math.nan
    f["dg_same_hand"] = _logmed(lat[same]) if len(lat) else math.nan
    f["dg_to_space"] = _logmed(lat[to_sp]) if len(lat) else math.nan
    f["dg_from_space"] = _logmed(lat[from_sp]) if len(lat) else math.nan
    f["dg_shifted"] = _logmed(lat[shifted], 3) if len(lat) else math.nan
    # per-pair sums for add_pair_features(); private (underscore) keys
    pairs: dict[str, list[float]] = {}
    loglat = np.log(np.maximum(lat, 1.0))
    for a_, b_, v in zip(pa, pb, loglat):
        acc = pairs.setdefault(f"{s.k_code[a_]}>{s.k_code[b_]}", [0.0, 0])
        acc[0] += float(v)
        acc[1] += 1
    f["_pairs"] = pairs
    f["_pace"] = float(loglat.mean()) if len(loglat) >= MIN_PAIRS else math.nan

    # pauses: gaps between any two consecutive code keys
    gaps = lat_all[lat_all >= PAUSE_MS]
    f["pause_per_100"] = 100 * len(gaps) / n_code if n_code else math.nan
    f["pause_median"] = float(np.log(np.median(gaps))) if len(gaps) else math.log(PAUSE_MS)

    # revisions
    n_del = int(is_del.sum())
    f["del_per_100"] = 100 * n_del / n_code if n_code else math.nan
    if n_del:
        runs = np.diff(np.flatnonzero(np.diff(np.r_[0, is_del.astype(int), 0]) != 0))[::2]
        f["del_burst"] = float(runs.mean())
    else:
        f["del_burst"] = 0.0

    # build order
    ei = np.flatnonzero((s.e_t >= lo) & (s.e_t < hi))
    f["nonappend_frac"] = float(1 - s.e_append[ei].mean()) if len(ei) else math.nan
    lines = s.e_line[ei]
    f["jump_rate"] = float((np.abs(np.diff(lines)) > 2).sum() / W_min) if len(ei) > 1 else 0.0
    ins = s.e_inserted[ei]
    f["paste_frac"] = float(ins[s.e_paste[ei]].sum() / ins.sum()) if ins.sum() else 0.0

    blo = max(0.0, hi - max(BUILD_SPAN_S * 1000, hi - lo))
    li = (s.l_t >= blo) & (s.l_t < hi)
    f["fill_in_frac"] = float(s.l_fill[li].mean()) if li.sum() >= MIN_LINES else math.nan
    bi = (s.b_t >= blo) & (s.b_t < hi)
    f["open_blocks"] = float(s.b_open[bi].mean()) if bi.any() else math.nan

    span = max(RUN_SPAN_S * 1000, hi - lo)
    rlo = max(0.0, hi - span)
    f["run_rate"] = float(((s.run_t >= rlo) & (s.run_t < hi)).sum() / ((hi - rlo) / 60000))
    f["focus_out_rate"] = float(((s.focus_out_t >= lo) & (s.focus_out_t < hi)).sum() / W_min)

    # comments, kept apart
    if len(com_i) > 1:
        cl = np.diff(s.k_t[com_i])
        cl = cl[cl < PAUSE_MS]
        f["c_dg_median"] = _logmed(cl)
    else:
        f["c_dg_median"] = math.nan
    f["c_key_frac"] = len(com_i) / len(ki) if len(ki) else 0.0
    return f


def window_features(s: Streams, window_s: float = 30.0, hop_s: float | None = None,
                    comments: str = "separate") -> list[dict]:
    """Features for consecutive windows. `comments`: "separate" (default) or "mixed"."""
    W = window_s * 1000
    hop = (hop_s or window_s) * 1000
    out = []
    lo = 0.0
    while lo + W <= s.duration_ms + 1e-6:
        out.append(_window(s, lo, lo + W, comments))
        lo += hop
    return out


def pair_vocabulary(sessions, n: int = 40) -> list[str]:
    """The `n` key pairs typed most often in flow over the given window lists
    (one list per session), most frequent first; ties by name, so the result
    does not depend on input order."""
    count: dict[str, int] = {}
    for windows in sessions:
        for w in windows:
            for p, (_, c) in w.get("_pairs", {}).items():
                count[p] = count.get(p, 0) + c
    return sorted(count, key=lambda p: (-count[p], p))[:n]


def add_pair_features(windows: list[dict], vocab: list[str], normalise: bool = True,
                      min_count: int = 1) -> list[dict]:
    """Copies of `windows` with one `pk:` feature per vocabulary pair (NaN when
    the pair was typed fewer than `min_count` times in the window)."""
    out = []
    for w in windows:
        x = dict(w)
        pace = w["_pace"] if normalise else 0.0
        for p in vocab:
            acc = w["_pairs"].get(p)
            x[PAIR_PREFIX + p] = acc[0] / acc[1] - pace if acc and acc[1] >= min_count else math.nan
        out.append(x)
    return out

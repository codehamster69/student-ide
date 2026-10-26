"""Synthetic session generator.

Produces event logs in the editor's own format (schema v1: `key`, `edit`,
`clipboard`, `cursor`, `run`, `snapshot`, `focus`, `session_start`/`end`)
for simulated typists, so the feature extractor and detector can be built
and tuned before Phase 2 lab data exists. The same code path that will read
real sessions reads these.

Each simulated typist has a stable "habit profile": base digraph latency,
rhythm spread, personal digraph idiosyncrasies, hand-alternation speed-up,
hold time, hesitation and think-pause habits, typo rate, revision habit,
skeleton-first vs linear code order, run frequency and how often they look
away. Day-to-day drift is added per session so a student's own sessions are
not identical.

Conditions (study design, Phase 2):

    honest      A  - one student composes the whole session
    proxy       B  - another person composes the whole session
    takeover    C  - student composes, a second person takes over at a random
                     minute (short seat-swap gap) and continues the same code
    copying     D  - student composes, then switches to transcribing code
                     from another source (fluent typing, glances away)
    paste       E  - student composes, then pastes chunks copied from elsewhere

`switch_t` in the returned truth is the time (ms) of the first keystroke
made under the new condition, or None for honest sessions and 0 for proxy.

Known simplifications: indentation is typed with Tab (the real editor
auto-indents and auto-closes brackets); there is no mouse selection editing.
"""

from __future__ import annotations

import hashlib
import math
import random
import zlib
from dataclasses import dataclass, field, replace
from typing import Iterable

from .corpus import PROGRAMS

CONDITIONS = ("honest", "proxy", "takeover", "copying", "paste")

# ---------------------------------------------------------------- keyboard

_SHIFTED = {
    "!": "Digit1", "@": "Digit2", "#": "Digit3", "$": "Digit4", "%": "Digit5", "^": "Digit6",
    "&": "Digit7", "*": "Digit8", "(": "Digit9", ")": "Digit0", "_": "Minus", "+": "Equal",
    "{": "BracketLeft", "}": "BracketRight", "|": "Backslash", ":": "Semicolon", '"': "Quote",
    "<": "Comma", ">": "Period", "?": "Slash", "~": "Backquote",
}
_PLAIN = {
    "-": "Minus", "=": "Equal", "[": "BracketLeft", "]": "BracketRight", "\\": "Backslash",
    ";": "Semicolon", "'": "Quote", ",": "Comma", ".": "Period", "/": "Slash", "`": "Backquote",
    " ": "Space", "\n": "Enter", "\t": "Tab",
}
_LEFT = set("QWERTASDFGZXCVB12345") | {"Backquote", "Tab"}


def key_for(ch: str) -> tuple[str, bool, str]:
    """(KeyboardEvent.code, needs shift, key class as the frontend computes it)."""
    if ch.isalpha():
        return "Key" + ch.upper(), ch.isupper(), "letter"
    if ch.isdigit():
        return "Digit" + ch, False, "digit"
    if ch in _SHIFTED:
        return _SHIFTED[ch], True, "punct"
    if ch == " ":
        return "Space", False, "space"
    if ch == "\n":
        return "Enter", False, "enter"
    if ch == "\t":
        return "Tab", False, "tab"
    return _PLAIN.get(ch, "Unidentified"), False, "punct"


def hand(code: str) -> str | None:
    """'L' / 'R' for the hand that normally types `code`, None for the space bar."""
    if code == "Space":
        return None
    k = code[3:] if code.startswith("Key") else code[5:] if code.startswith("Digit") else code
    return "L" if k in _LEFT else "R"


# ---------------------------------------------------------------- typists


@dataclass(frozen=True)
class Typist:
    id: str
    mu: float  # log ms, median digraph latency in flow
    sigma: float  # log-sd of digraph latency
    alt_hand: float  # log offset when hands alternate (negative = faster)
    to_space: float
    from_space: float
    shifted: float  # extra log latency into a shifted character
    digit: float
    pair_sd: float  # spread of personal digraph idiosyncrasies
    pair_seed: int
    hold_mu: float  # log ms
    hold_sd: float
    word_pause_p: float  # hesitation probability at a word boundary
    line_think_p: float  # think-pause probability before a code line
    think_mu: float  # log seconds
    think_sd: float
    typo_rate: float
    revise_p: float  # per line: delete the last word and retype it
    skeleton_p: float  # per program: write top-level lines first, bodies after
    run_every_s: float
    glance_p: float  # per line: look away (window blur) while composing
    comment_offset: float  # comments are typed more fluently

    @property
    def speed(self) -> float:
        return self.mu


def sample_typist(rng: random.Random, tid: str) -> Typist:
    return Typist(
        id=tid,
        mu=rng.gauss(math.log(210), 0.25),
        sigma=rng.uniform(0.28, 0.5),
        alt_hand=rng.gauss(-0.15, 0.08),
        to_space=rng.gauss(-0.05, 0.1),
        from_space=rng.gauss(0.1, 0.1),
        shifted=rng.gauss(0.25, 0.1),
        digit=rng.gauss(0.2, 0.12),
        pair_sd=rng.uniform(0.08, 0.2),
        pair_seed=rng.randrange(2**31),
        hold_mu=rng.gauss(math.log(95), 0.18),
        hold_sd=rng.uniform(0.15, 0.3),
        word_pause_p=rng.uniform(0.02, 0.1),
        line_think_p=rng.uniform(0.15, 0.55),
        think_mu=rng.gauss(math.log(4.0), 0.35),
        think_sd=rng.uniform(0.5, 0.9),
        typo_rate=rng.uniform(0.008, 0.05),
        revise_p=rng.uniform(0.02, 0.12),
        skeleton_p=rng.betavariate(1.2, 1.2),
        run_every_s=rng.uniform(60, 360),
        glance_p=rng.uniform(0.0, 0.08),
        comment_offset=rng.gauss(-0.1, 0.05),
    )


def day_variant(t: Typist, rng: random.Random) -> Typist:
    """The same student on a different day: small drift in every habit."""
    j = lambda s: math.exp(rng.gauss(0, s))  # noqa: E731
    return replace(
        t,
        mu=t.mu + rng.gauss(0, 0.06),
        sigma=t.sigma * j(0.06),
        hold_mu=t.hold_mu + rng.gauss(0, 0.04),
        word_pause_p=min(0.5, t.word_pause_p * j(0.2)),
        line_think_p=min(0.9, t.line_think_p * j(0.15)),
        think_mu=t.think_mu + rng.gauss(0, 0.15),
        typo_rate=t.typo_rate * j(0.2),
        revise_p=min(0.5, t.revise_p * j(0.2)),
        run_every_s=t.run_every_s * j(0.2),
        glance_p=min(0.5, t.glance_p * j(0.3)),
    )


def population(n: int, seed: int = 0) -> list[Typist]:
    rng = random.Random(seed)
    return [sample_typist(rng, f"S{i:03d}") for i in range(n)]


# ---------------------------------------------------------------- sessions


@dataclass
class Segment:
    start_s: float  # session time at which this segment takes over
    typist: Typist
    mode: str  # compose | transcribe | paste


@dataclass
class Truth:
    condition: str
    student: str
    author_after: str | None = None  # who typed after the switch
    switch_t: float | None = None  # ms; first keystroke under the new condition
    duration_ms: float = 0.0


def _pair_offset(seed: int, a: str, b: str, sd: float, cache: dict) -> float:
    key = (a, b)
    v = cache.get(key)
    if v is None:
        u = zlib.crc32(f"{seed}:{a}:{b}".encode()) / 2**32
        u = min(max(u, 1e-6), 1 - 1e-6)
        # inverse-normal via a cheap logistic approximation is enough here
        v = sd * math.log(u / (1 - u)) / 1.702
        cache[key] = v
    return v


_POP_SEED = 12345
_POP_PAIR_SD = 0.12


class _Session:
    """Builds one event stream. Times are ms since session start."""

    def __init__(self, rng: random.Random, segments: list[Segment], duration_s: float):
        self.rng = rng
        self.segments = sorted(segments, key=lambda s: s.start_s)
        self.duration = duration_s * 1000
        self.events: list[tuple[float, int, str, dict]] = []
        self.n = 0
        self.t = 0.0
        self.doc = ""
        self.cursor = 0
        self.prev_code: str | None = None
        self.last_edit_t = 0.0
        self.next_snap = 30_000.0
        self.snap_doc = ""
        self.last_run = 0.0
        self.next_run_gap = 0.0
        self.seg_i = 0
        self.switch_t: float | None = None
        self._pairs: dict[str, dict] = {}
        self._pop_pairs: dict = {}
        self.seg = self.segments[0]
        self.chars_since_glance = 0
        self.glance_every = rng.randint(12, 40)
        self._new_run_gap()

    # -- low level

    def emit(self, t: float, typ: str, data: dict) -> None:
        self._push(t, typ, data)

    def _before_edit(self, t: float) -> None:
        """Periodic snapshot (every 30 s if changed), taken before the doc changes."""
        if t > self.next_snap:
            if self.doc != self.snap_doc:
                self._push(self.next_snap, "snapshot", {"reason": "periodic", "text": self.doc})
                self.snap_doc = self.doc
            while self.next_snap < t:
                self.next_snap += 30_000
        self.last_edit_t = t

    def _push(self, t: float, typ: str, data: dict) -> None:
        self.events.append((round(t, 3), self.n, typ, data))
        self.n += 1

    def _edit(self, t: float, frm: int, to: int, text: str, origin: str) -> None:
        self._before_edit(t + 0.4)
        before = len(self.doc)
        self.doc = self.doc[:frm] + text + self.doc[to:]
        self.cursor = frm + len(text)
        self.emit(t + 0.4, "edit", {"origin": origin, "changes": [[frm, to, text]],
                                    "len_before": before, "len_after": len(self.doc)})

    def _key(self, t: float, code: str, cls: str, shift: bool = False, ctrl: bool = False,
             hold: float | None = None) -> float:
        hold = hold if hold is not None else self._hold()
        mods = {"shift": shift, "ctrl": ctrl, "alt": False, "meta": False, "repeat": False}
        self.emit(t, "key", {"action": "down", "code": code, "cls": cls, **mods})
        self.emit(t + hold, "key", {"action": "up", "code": code, "cls": cls, **mods})
        return t + hold

    @property
    def typist(self) -> Typist:
        return self.seg.typist

    @property
    def mode(self) -> str:
        return self.seg.mode

    def _hold(self) -> float:
        ty = self.typist
        return min(400.0, math.exp(self.rng.gauss(ty.hold_mu, ty.hold_sd)))

    def _latency(self, code: str, cls: str, shifted: bool, comment: bool) -> float:
        ty = self.typist
        mu = ty.mu
        prev = self.prev_code
        if prev is not None:
            h1, h2 = hand(prev), hand(code)
            if h1 and h2 and h1 != h2:
                mu += ty.alt_hand
            if code == "Space":
                mu += ty.to_space
            if prev == "Space":
                mu += ty.from_space
            pairs = self._pairs.setdefault(ty.id, {})
            mu += _pair_offset(ty.pair_seed, prev, code, ty.pair_sd, pairs)
            mu += _pair_offset(_POP_SEED, prev, code, _POP_PAIR_SD, self._pop_pairs)
        if shifted:
            mu += ty.shifted
        if cls == "digit":
            mu += ty.digit
        sigma = ty.sigma
        if comment:
            mu += ty.comment_offset
        if self.mode == "transcribe":
            mu -= 0.08
            sigma *= 0.7
        return min(1800.0, max(25.0, math.exp(self.rng.gauss(mu, sigma))))

    def type_char(self, ch: str, comment: bool, origin: str = "input.type") -> None:
        code, shifted, cls = key_for(ch)
        lat = self._latency(code, cls, shifted, comment)
        t = self.t + lat
        if shifted:
            lead = min(self.rng.uniform(30, 80), 0.5 * lat)
            sh = "ShiftRight" if hand(code) == "L" else "ShiftLeft"
            self.emit(t - lead, "key", {"action": "down", "code": sh, "cls": "modifier", "shift": True,
                                        "ctrl": False, "alt": False, "meta": False, "repeat": False})
        up = self._key(t, code, cls, shift=shifted)
        if shifted:
            self.emit(up + self.rng.uniform(5, 40), "key", {"action": "up", "code": sh, "cls": "modifier",
                                                             "shift": False, "ctrl": False, "alt": False,
                                                             "meta": False, "repeat": False})
        text = "    " if ch == "\t" else ch
        self._edit(t, self.cursor, self.cursor, text, "input.indent" if ch == "\t" else origin)
        self.t = t
        self.prev_code = code

    def backspace(self, n: int = 1) -> None:
        ty = self.typist
        for _ in range(n):
            if self.cursor == 0:
                return
            lat = max(40.0, math.exp(self.rng.gauss(ty.mu - 0.15, ty.sigma * 0.8)))
            t = self.t + lat
            self._key(t, "Backspace", "backspace")
            k = 4 if self.doc[max(0, self.cursor - 4):self.cursor] == "    " else 1
            self._edit(t, self.cursor - k, self.cursor, "", "delete.backward")
            self.t = t
            self.prev_code = "Backspace"

    def pause(self, seconds: float) -> None:
        self.t += seconds * 1000
        self.prev_code = None

    def glance(self, lo: float, hi: float) -> None:
        """Look away from the editor (other window) and come back."""
        self.t += self.rng.uniform(50, 200)
        self.emit(self.t, "focus", {"target": "window", "state": "out"})
        self.t += self.rng.uniform(lo, hi) * 1000
        self.emit(self.t, "focus", {"target": "window", "state": "in"})
        self.prev_code = None

    def move_cursor(self, pos: int) -> None:
        if pos == self.cursor:
            return
        self.t += self.rng.uniform(600, 2000)
        self.cursor = pos
        self.emit(self.t, "cursor", {"anchor": pos, "head": pos, "line": self.doc.count("\n", 0, pos) + 1})
        self.prev_code = None

    def _new_run_gap(self) -> None:
        self.next_run_gap = self.rng.expovariate(1 / (self.typist.run_every_s * 1000))

    def run(self, complete: bool) -> None:
        self.t += self.rng.uniform(400, 1500)
        self.emit(self.t, "snapshot", {"reason": "run", "text": self.doc})
        self.snap_doc = self.doc
        err = None
        if not complete and self.rng.random() < 0.4:
            err = "SyntaxError"
        elif self.rng.random() < 0.12:
            err = self.rng.choice(["NameError", "TypeError", "IndexError", "ValueError"])
        self.t += 5
        self.emit(self.t, "run", {"run_id": f"r{self.n}", "code_sha256": hashlib.sha256(self.doc.encode()).hexdigest(),
                                  "exit_code": 1 if err else 0, "duration_ms": self.rng.uniform(40, 400),
                                  "error_type": err})
        self.last_run = self.t
        self._new_run_gap()
        self.pause(self.rng.uniform(2, 10))

    # -- segments

    def _maybe_switch(self) -> None:
        nxt = self.seg_i + 1
        if nxt < len(self.segments) and self.t >= self.segments[nxt].start_s * 1000:
            old = self.seg
            self.seg_i = nxt
            self.seg = self.segments[nxt]
            if self.seg.typist.id != old.typist.id:
                self.pause(self.rng.uniform(5, 40))  # seat swap
            self.switch_t = self.t + 1
            self._new_run_gap()

    # -- writing code

    def write_line(self, line: str) -> None:
        ty, rng = self.typist, self.rng
        stripped = line.lstrip(" ")
        comment = stripped.startswith("#")
        mode = self.mode
        if stripped:
            think = ty.line_think_p * (0.15 if mode == "transcribe" else 1.0)
            if rng.random() < think:
                self.pause(min(90.0, math.exp(rng.gauss(ty.think_mu, ty.think_sd))))
            if mode == "compose" and rng.random() < ty.glance_p:
                self.glance(2, 8)
        for _ in range((len(line) - len(stripped)) // 4):
            self.type_char("\t", False)
        i = 0
        in_comment = False
        while i < len(stripped):
            ch = stripped[i]
            if ch == "#":
                in_comment = True
            boundary = i > 0 and stripped[i - 1] in " ,.:()[]"
            if boundary:
                if mode == "transcribe" and self.chars_since_glance >= self.glance_every:
                    self.glance(1.0, 3.5)  # look back at the source
                    self.chars_since_glance = 0
                    self.glance_every = rng.randint(12, 40)
                else:
                    p = ty.word_pause_p * (0.3 if (in_comment or mode == "transcribe") else 1.0)
                    if rng.random() < p:
                        self.pause(rng.uniform(0.4, 2.5))
            typo = ty.typo_rate * (0.6 if mode == "transcribe" else 1.0)
            if ch.isalpha() and rng.random() < typo:
                extra = min(rng.choice([0, 0, 1, 2]), len(stripped) - i - 1)
                self.type_char(rng.choice("asdfghjklqwertyuiopzxcvbnm"), in_comment)
                for j in range(extra):
                    self.type_char(stripped[i + 1 + j], in_comment)
                self.pause(rng.uniform(0.25, 0.9))
                self.backspace(extra + 1)
            self.type_char(ch, in_comment)
            self.chars_since_glance += 1
            i += 1
        if stripped and mode == "compose" and rng.random() < ty.revise_p:
            word = stripped.rstrip().split(" ")[-1][:8]
            if word:
                self.pause(rng.uniform(1, 3))
                self.backspace(len(word))
                self.pause(rng.uniform(0.5, 2))
                for ch in word:
                    self.type_char(ch, in_comment)
        self.type_char("\n", in_comment)

    def paste_lines(self, text: str) -> None:
        rng = self.rng
        self.glance(3, 12)  # copy it from elsewhere
        self.t += rng.uniform(200, 600)
        mods = {"shift": False, "ctrl": True, "alt": False, "meta": False, "repeat": False}
        self.emit(self.t, "key", {"action": "down", "code": "ControlLeft", "cls": "modifier", **mods})
        t = self.t + rng.uniform(60, 180)
        self.emit(t, "key", {"action": "down", "code": "KeyV", "cls": "letter", **mods})
        self.emit(t + 0.2, "clipboard", {"action": "paste", "length": len(text), "lines": text.count("\n") + 1,
                                         "text": text, "truncated": False})
        self._before_edit(t + 0.4)
        before = len(self.doc)
        self.doc = self.doc[:self.cursor] + text + self.doc[self.cursor:]
        frm = self.cursor
        self.cursor += len(text)
        self.emit(t + 0.4, "edit", {"origin": "input.paste", "changes": [[frm, frm, text]],
                                    "len_before": before, "len_after": len(self.doc)})
        self.emit(t + 90, "key", {"action": "up", "code": "KeyV", "cls": "letter", **mods})
        self.emit(t + 130, "key", {"action": "up", "code": "ControlLeft", "cls": "modifier", **mods})
        self.t = t + 150
        self.prev_code = None
        self.pause(rng.uniform(1, 4))

    def write_program(self, program: str) -> bool:
        """Write one program; False if the session ran out of time first."""
        lines = program.splitlines()
        base = len(self.doc)
        skeleton = self.mode == "compose" and self.rng.random() < self.typist.skeleton_p
        if skeleton:
            first = [i for i, ln in enumerate(lines)
                     if ln.strip() and (not ln.startswith(" ") or ln.strip().startswith("return"))]
            order = first + [i for i in range(len(lines)) if i not in set(first)]
        else:
            order = list(range(len(lines)))
        present: list[int] = []
        k = 0
        while k < len(order):
            if self.t >= self.duration:
                return False
            self._maybe_switch()
            i = order[k]
            if self.mode == "paste" and self.rng.random() < 0.6:
                # paste the next run of consecutive missing lines, then carry on typing
                run = [i]
                while k + len(run) < len(order) and order[k + len(run)] == run[-1] + 1 and len(run) < self.rng.randint(3, 10):
                    run.append(order[k + len(run)])
                pos = base + sum(len(lines[j]) + 1 for j in present if j < i)
                self.move_cursor(pos)
                self.paste_lines("".join(lines[j] + "\n" for j in run))
                present = sorted(present + run)
                k += len(run)
                continue
            pos = base + sum(len(lines[j]) + 1 for j in present if j < i)
            self.move_cursor(pos)
            self.write_line(lines[i])
            present = sorted(present + [i])
            k += 1
            if self.t - self.last_run > self.next_run_gap:
                self.run(complete=False)
        if self.rng.random() < 0.9:
            self.run(complete=True)
        return True

    def build(self, programs: Iterable[str]) -> list[dict]:
        wall = 1.7e12 + self.rng.uniform(0, 1e10)
        self._push(0.0, "session_start", {"wall_clock_ms": wall, "reason": None})
        self._push(0.5, "snapshot", {"reason": "start", "text": ""})
        self.t = self.rng.uniform(1500, 6000)  # read the task
        for p in programs:
            if not self.write_program(p):
                break
        self.t = max(self.t, self.last_edit_t) + 500
        self._push(self.t, "snapshot", {"reason": "end", "text": self.doc})
        self._push(self.t + 1, "session_end", {"wall_clock_ms": wall + self.t, "reason": "submit"})
        self.events.sort(key=lambda e: (e[0], e[1]))
        return [{"seq": i, "t": t, "type": typ, "data": data} for i, (t, _, typ, data) in enumerate(self.events)]


def _program_stream(rng: random.Random) -> Iterable[str]:
    while True:
        order = list(PROGRAMS)
        rng.shuffle(order)
        yield from order


def generate_session(student: Typist, condition: str = "honest", *, other: Typist | None = None,
                     duration_s: float = 1800, switch_s: float | None = None,
                     seed: int = 0) -> tuple[list[dict], Truth]:
    """One synthetic session. `other` is the second person for proxy/takeover.

    `switch_s` defaults to a uniformly random minute in the middle 60% of the
    session. Every session gets day-to-day drift on each person's habits.
    """
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}")
    rng = random.Random(seed)
    me = day_variant(student, rng)
    if condition in ("proxy", "takeover"):
        if other is None:
            raise ValueError(f"{condition} needs `other`")
        them = day_variant(other, rng)
    if switch_s is None:
        switch_s = 60 * rng.randint(math.ceil(duration_s * 0.2 / 60), int(duration_s * 0.8 / 60))
    segs = {
        "honest": [Segment(0, me, "compose")],
        "proxy": [Segment(0, them, "compose")] if condition == "proxy" else None,
        "takeover": [Segment(0, me, "compose"), Segment(switch_s, them, "compose")] if condition == "takeover" else None,
        "copying": [Segment(0, me, "compose"), Segment(switch_s, me, "transcribe")],
        "paste": [Segment(0, me, "compose"), Segment(switch_s, me, "paste")],
    }[condition]
    s = _Session(rng, segs, duration_s)
    events = s.build(_program_stream(rng))
    truth = Truth(condition=condition, student=student.id, duration_ms=events[-1]["t"])
    if condition == "proxy":
        truth.author_after, truth.switch_t = other.id, 0.0
    elif condition != "honest" and s.switch_t is not None:
        truth.author_after = other.id if condition == "takeover" else student.id
        truth.switch_t = s.switch_t
    return events, truth


def nearest_speed(typists: list[Typist], who: Typist) -> Typist:
    """Speed-matched partner (stand-in for the study's grade-matched proxies)."""
    return min((t for t in typists if t.id != who.id), key=lambda t: abs(t.mu - who.mu))


def main() -> None:
    import argparse
    import json
    from dataclasses import asdict
    from pathlib import Path

    p = argparse.ArgumentParser(description="Write synthetic sessions as JSONL (export format).")
    p.add_argument("--out", default="synthetic")
    p.add_argument("--typists", type=int, default=4)
    p.add_argument("--minutes", type=float, default=30)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pop = population(a.typists, a.seed)
    meta = []
    for i, ty in enumerate(pop):
        for j, cond in enumerate(CONDITIONS):
            other = nearest_speed(pop, ty) if cond in ("proxy", "takeover") else None
            events, truth = generate_session(ty, cond, other=other, duration_s=a.minutes * 60,
                                             seed=a.seed * 100_000 + i * 100 + j)
            sid = f"{ty.id}-{cond}"
            with open(out / f"{sid}.jsonl", "w", encoding="utf-8") as f:
                for ev in events:
                    f.write(json.dumps(ev) + "\n")
            meta.append({"id": sid, "truth": asdict(truth), "n_events": len(events)})
    (out / "sessions.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (out / "typists.json").write_text(json.dumps([asdict(t) for t in pop], indent=1), encoding="utf-8")
    print(f"wrote {len(meta)} sessions to {out}")


if __name__ == "__main__":
    main()

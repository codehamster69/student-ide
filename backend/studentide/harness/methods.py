"""Scorers compared by the harness: the thesis detector and three baselines.

Every method turns a session into one or more channels of standardised
window scores x_t (higher = less like the student's own baseline). The
alarm stage (`alarms.py`) is shared: the same CUSUM, the same threshold
calibration and the same metrics, so differences come from the scores.

- `ChannelMethod`  the thesis detector: per-student median/MAD baseline per
  habit feature, two channels (identity, process); also used for ablations
  and for the Nosi-style baseline (one channel, L-scale of log IAT only).
- `ScaledManhattan` free-text keystroke verification in the style of
  Killourhy and Maxion (2009): mean log latency of the most common
  digraphs and mean log hold of the most common keys per window, scaled
  Manhattan distance to the student's template.
- `TypeNetStyle`  deep metric learning on keystroke sequences (Acien et al.
  2021): an LSTM trained with triplet loss on dev students, distance of a
  window's sequences to the student's enrollment sequences.

Each per-student score is standardised by the student's own honest level
(mean and sd of the score on their baseline sessions, leave-one-session-out),
exactly as the thesis detector does, so all methods see the same CUSUM input.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np

from ..detector.detector import (CHANNELS, Baseline, channel_features, feature_weights, pair_block_weights,
                                 population_prior)
from ..detector.features import PAIR_PREFIX, PAUSE_MS, add_pair_features, pair_vocabulary
from .corpus import Corpus, Session
from .lstm import LSTMEmbedder, train


@dataclass
class Series:
    start: np.ndarray  # window start, s
    end: np.ndarray
    x: np.ndarray  # standardised score, NaN = inactive window


@dataclass
class ChannelSpec:
    features: list[str]
    weighting: str = "equal"  # equal | icc
    k: float = 0.5
    window_s: float = 30.0


class Method:
    name = "method"
    comments = "separate"
    channels: dict[str, ChannelSpec]

    def k(self) -> dict[str, float]:
        return {ch: c.k for ch, c in self.channels.items()}

    def fit_population(self, corpus: Corpus, students: list[str], n_base: int) -> None:
        pass

    def fit_student(self, corpus: Corpus, student: str, sessions: list[Session]):
        raise NotImplementedError

    def score(self, corpus: Corpus, model, s: Session) -> dict[str, Series]:
        raise NotImplementedError

    def loso_series(self, corpus: Corpus, student: str, sessions: list[Session]) -> list[dict[str, Series]]:
        """Each baseline session scored against a baseline of the others: honest
        sessions every student has, usable to calibrate h without staged data."""
        if len(sessions) < 2:
            return []
        out = []
        for i, s in enumerate(sessions):
            model = self.fit_student(corpus, student, sessions[:i] + sessions[i + 1:])
            out.append(self.score(corpus, model, s))
        return out


def _standardise(dist: np.ndarray, mu0: float, sd0: float) -> np.ndarray:
    return (dist - mu0) / sd0


# --------------------------------------------------------------- thesis detector

class ChannelMethod(Method):
    """`pairs` (optional) adds per-key-pair timing features:
    {"n": vocabulary size, "normalise": relative to the window's pace,
    "min_count": typings of a pair needed in a window, "channel": "identity"
    (join the identity channel, the pairs together weighted `block` times the
    other identity features) or "pairs" (a channel of their own, CUSUM `k`)}."""

    def __init__(self, name: str, channels: dict[str, ChannelSpec], comments: str = "separate",
                 prior_n: float = 0.0, pairs: dict | None = None):
        self.name, self.channels, self.comments, self.prior_n = name, channels, comments, prior_n
        self.pairs = dict(pairs) if pairs else None
        self.vocab: list[str] = []
        if self.pairs and self.pairs.get("channel", "identity") == "pairs":
            W = channels["identity"].window_s if "identity" in channels else 30.0
            self.channels = {**channels, "pairs": ChannelSpec([], "equal", self.pairs.get("k", 1.0), W)}
        self._base = {ch: list(c.features) for ch, c in self.channels.items()}
        self.weights: dict[str, dict | None] = {}
        self.prior: dict[str, dict | None] = {}

    def windows(self, corpus, s, W):
        w = corpus.windows(s, W, self.comments)
        if not self.vocab:
            return w
        # not cached: cheap, and the vocabulary differs between folds
        return add_pair_features(w, self.vocab, self.pairs.get("normalise", True), self.pairs.get("min_count", 1))

    def _bw(self, corpus, sessions, W):
        return [self.windows(corpus, s, W) for s in sessions]

    def fit_population(self, corpus, students, n_base):
        target = None
        if self.pairs:
            target = self.pairs.get("channel", "identity")
            W = self.channels[target].window_s
            self.vocab = pair_vocabulary([corpus.windows(s, W, self.comments) for st in students
                                          for s in corpus.baseline(st, n_base)], self.pairs.get("n", 40))
            self.channels[target].features = self._base[target] + [PAIR_PREFIX + p for p in self.vocab]
        for ch, c in self.channels.items():
            bw = {st: self._bw(corpus, corpus.baseline(st, n_base), c.window_s) for st in students}
            w = feature_weights(bw, c.features) if c.weighting == "icc" else None
            if ch == target and target != "pairs":
                w = pair_block_weights(c.features, w, self.pairs.get("block", 1.0))
            self.weights[ch] = w
            self.prior[ch] = None
            if self.prior_n > 0:
                # the prior comes from students with the full baseline (all their baseline weeks)
                full = {st: Baseline.fit(st, self._bw(corpus, corpus.baseline(st), c.window_s), c.features,
                                         self.weights[ch]) for st in students}
                self.prior[ch] = population_prior(full, self.prior_n)

    def fit_student(self, corpus, student, sessions):
        return {ch: Baseline.fit(student, self._bw(corpus, sessions, c.window_s), c.features,
                                 self.weights.get(ch), self.prior.get(ch)) for ch, c in self.channels.items()}

    def score(self, corpus, model, s):
        out = {}
        for ch, c in self.channels.items():
            w = self.windows(corpus, s, c.window_s)
            b = model[ch]
            d = np.array(b.distances(w), float)
            out[ch] = Series(np.array([x["start"] for x in w]), np.array([x["end"] for x in w]),
                             _standardise(d, b.mu0, b.sd0))
        return out


def thesis_detector(features: list[str] | None = None, identity_w: float = 30, process_w: float = 30,
                    prior_n: float = 0.0, comments: str = "separate", name: str = "two-channel CUSUM",
                    k: dict[str, float] | None = None, pairs: dict | None = None) -> ChannelMethod:
    chans = {}
    for ch, (_, weighting, k0) in CHANNELS.items():
        feats = channel_features(ch, features)
        if feats:
            chans[ch] = ChannelSpec(feats, weighting, (k or {}).get(ch, k0),
                                    identity_w if ch == "identity" else process_w)
    return ChannelMethod(name, chans, comments, prior_n, pairs)


def nosi_style(window_s: float = 150, k: float = 0.5) -> ChannelMethod:
    """Lueder et al. (Nosi): L-scale of log inter-key time, all keys (comments included)."""
    return ChannelMethod("Nosi-style L-scale", {"rhythm": ChannelSpec(["dg_lscale"], "equal", k, window_s)},
                         comments="mixed")


# --------------------------------------------------------------- keystroke streams

def _pairs(corpus: Corpus, s: Session):
    """Adjacent code keystrokes typed in flow: (time, pair id, log latency),
    plus (time, key, log hold) for every code key press."""
    key = ("pairs", s.id)
    if key not in corpus._win:
        st = s.st
        code = ~st.k_comment
        idx = np.flatnonzero(code)
        is_del = np.array([st.k_cls[i] in ("backspace", "delete") for i in idx], bool)
        a, b = idx[:-1], idx[1:]
        ok = (b - a == 1) & ~is_del[:-1] & ~is_del[1:]
        a, b = a[ok], b[ok]
        lat = st.k_t[b] - st.k_t[a]
        flow = (lat < PAUSE_MS) & (lat > 0)
        a, b, lat = a[flow], b[flow], lat[flow]
        pid = [f"{st.k_code[i]}>{st.k_code[j]}" for i, j in zip(a, b)]
        keys = idx[~is_del]
        hold = st.k_hold[keys]
        okh = ~np.isnan(hold) & (hold > 0)
        corpus._win[key] = (st.k_t[b], pid, np.log(lat), st.k_t[keys][okh],
                            [st.k_code[i] for i in keys[okh]], np.log(hold[okh]))
    return corpus._win[key]


def _grid(duration_s: float, W: float) -> tuple[np.ndarray, np.ndarray]:
    n = int((duration_s * 1000 + 1e-6) // (W * 1000))
    start = np.arange(n) * W
    return start, start + W


def _active(corpus: Corpus, s: Session, W: float) -> np.ndarray:
    return np.array([w["active"] for w in corpus.windows(s, W)], bool)


# --------------------------------------------------------------- scaled Manhattan

class ScaledManhattan(Method):
    """Template = per-feature mean and mean absolute deviation over baseline
    windows; score = mean over the features present of |x - mean| / mad."""

    name = "scaled Manhattan"

    def __init__(self, window_s: float = 30, k: float = 1.0, n_digraphs: int = 40, n_keys: int = 15,
                 min_count: int = 2, min_dims: int = 5):
        self.W, self.n_dg, self.n_keys, self.min_count, self.min_dims = window_s, n_digraphs, n_keys, min_count, min_dims
        self.channels = {"keystroke": ChannelSpec([], "equal", k, window_s)}

    def fit_population(self, corpus, students, n_base):
        dg, ky = {}, {}
        for st in students:
            for s in corpus.baseline(st, n_base):
                _, pid, _, _, keys, _ = _pairs(corpus, s)
                for p in pid:
                    dg[p] = dg.get(p, 0) + 1
                for k in keys:
                    ky[k] = ky.get(k, 0) + 1
        self.digraphs = {p: i for i, p in enumerate(sorted(dg, key=lambda p: -dg[p])[: self.n_dg])}
        self.keys = {k: i for i, k in enumerate(sorted(ky, key=lambda k: -ky[k])[: self.n_keys])}

    def vectors(self, corpus, s: Session) -> np.ndarray:
        key = ("sm", id(self), s.id)
        if key in corpus._win:
            return corpus._win[key]
        start, _ = _grid(s.duration_s, self.W)
        n = len(start)
        D = len(self.digraphs) + len(self.keys)
        tot = np.zeros((n, D))
        cnt = np.zeros((n, D))
        t, pid, ll, th, keys, lh = _pairs(corpus, s)
        for times, names, vals, vocab, off in ((t, pid, ll, self.digraphs, 0), (th, keys, lh, self.keys, len(self.digraphs))):
            wi = (np.asarray(times) // (self.W * 1000)).astype(int)
            col = np.array([vocab.get(p, -1) for p in names], int)
            ok = (col >= 0) & (wi < n)
            np.add.at(tot, (wi[ok], col[ok] + off), np.asarray(vals)[ok])
            np.add.at(cnt, (wi[ok], col[ok] + off), 1)
        with np.errstate(invalid="ignore", divide="ignore"):
            v = np.where(cnt >= self.min_count, tot / cnt, np.nan)
        act = _active(corpus, s, self.W)[:n]
        v[~act] = np.nan
        corpus._win[key] = v
        return v

    def _template(self, V: np.ndarray):
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                m = np.nanmean(V, 0)
                a = np.nanmean(np.abs(V - m), 0)
        return m, np.maximum(np.nan_to_num(a, nan=1.0), 0.03)

    def _dist(self, m, a, V):
        z = np.abs(V - m) / a
        n = np.sum(~np.isnan(z), 1)
        with np.errstate(invalid="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                d = np.nanmean(np.minimum(z, 6.0), 1)
        d[n < self.min_dims] = np.nan
        return d

    def fit_student(self, corpus, student, sessions):
        Vs = [self.vectors(corpus, s) for s in sessions]
        m, a = self._template(np.concatenate(Vs))
        held = []
        if len(Vs) >= 2:
            for i in range(len(Vs)):
                m2, a2 = self._template(np.concatenate(Vs[:i] + Vs[i + 1:]))
                held.append(self._dist(m2, a2, Vs[i]))
        else:
            held.append(self._dist(m, a, Vs[0]))
        h = np.concatenate(held)
        h = h[~np.isnan(h)]
        mu0, sd0 = (float(h.mean()), max(float(h.std()), 0.05)) if len(h) >= 3 else (0.0, 1.0)
        return (m, a, mu0, sd0)

    def score(self, corpus, model, s):
        m, a, mu0, sd0 = model
        start, end = _grid(s.duration_s, self.W)
        return {"keystroke": Series(start, end, _standardise(self._dist(m, a, self.vectors(corpus, s)), mu0, sd0))}


# --------------------------------------------------------------- TypeNet-style

def _keycode(code: str) -> float:
    if code.startswith("Key"):
        return ord(code[3]) / 255
    if code.startswith("Digit"):
        return ord(code[5]) / 255
    return {"Space": 32, "Enter": 13, "Tab": 9, "Backspace": 8, "Delete": 127}.get(code, 200 + zlib.crc32(code.encode()) % 50) / 255


class TypeNetStyle(Method):
    name = "TypeNet-style LSTM"

    def __init__(self, window_s: float = 30, k: float = 1.0, M: int = 30, stride: int = 10, hidden: int = 32,
                 steps: int = 1500, seed: int = 0, n_enroll: int = 300, log=None):
        self.W, self.M, self.stride, self.hidden, self.steps, self.seed = window_s, M, stride, hidden, steps, seed
        self.n_enroll, self.log = n_enroll, log
        self.channels = {"keystroke": ChannelSpec([], "equal", k, window_s)}
        self.model: LSTMEmbedder | None = None

    def sequences(self, corpus, s: Session):
        """(start ms, end ms, (n, M, 5) features) for code keystroke sequences."""
        key = ("tn-seq", self.M, self.stride, s.id)
        if key not in corpus._win:
            st = s.st
            idx = np.flatnonzero(~st.k_comment)
            t = st.k_t[idx]
            hold = np.nan_to_num(st.k_hold[idx], nan=100.0)
            rel = t + hold
            kc = np.array([_keycode(st.k_code[i]) for i in idx])
            nxt_t = np.r_[t[1:], t[-1:]] if len(t) else t
            nxt_rel = np.r_[rel[1:], rel[-1:]] if len(t) else rel
            cap = lambda v: np.clip(v / 1000.0, -1.0, 1.5)  # noqa: E731 - seconds, long pauses capped
            F = np.stack([cap(hold), cap(nxt_t - rel), cap(nxt_t - t), cap(nxt_rel - rel), kc], 1) if len(t) else np.zeros((0, 5))
            starts = np.arange(0, max(0, len(t) - self.M + 1), self.stride)
            X = np.stack([F[i:i + self.M] for i in starts]) if len(starts) else np.zeros((0, self.M, 5))
            corpus._win[key] = (t[starts] if len(starts) else np.zeros(0),
                                t[starts + self.M - 1] if len(starts) else np.zeros(0), X)
        return corpus._win[key]

    def embeddings(self, corpus, s):
        key = ("tn-emb", id(self), s.id)
        if key not in corpus._win:
            a, b, X = self.sequences(corpus, s)
            corpus._win[key] = (a, b, self.model.embed(X))
        return corpus._win[key]

    def fit_population(self, corpus, students, n_base):
        seqs, owner = [], []
        for st in students:
            for s in corpus.baseline(st, n_base):
                X = self.sequences(corpus, s)[2]
                seqs.append(X)
                owner += [st] * len(X)
        seqs = np.concatenate(seqs)
        self.model = LSTMEmbedder(5, self.hidden, 32, self.seed)
        train(self.model, seqs, np.array(owner), steps=self.steps, seed=self.seed, log=self.log)
        for k in [k for k in corpus._win if k[0] == "tn-emb"]:
            del corpus._win[k]

    def _dist(self, enroll, corpus, s):
        a, b, E = self.embeddings(corpus, s)
        start, end = _grid(s.duration_s, self.W)
        d = np.full(len(start), np.nan)
        if len(E) and len(enroll):
            seq_d = np.sqrt(((E[:, None, :] - enroll[None]) ** 2).sum(-1)).mean(1)
            wi_a = (a // (self.W * 1000)).astype(int)
            wi_b = (b // (self.W * 1000)).astype(int)
            inside = (wi_a == wi_b) & (wi_a < len(start))
            tot = np.bincount(wi_a[inside], seq_d[inside], len(start))
            cnt = np.bincount(wi_a[inside], None, len(start))
            with np.errstate(invalid="ignore"):
                d = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)
        act = _active(corpus, s, self.W)[: len(d)]
        d[~act] = np.nan
        return start, end, d

    def _enroll(self, corpus, sessions, r):
        E = np.concatenate([self.embeddings(corpus, s)[2] for s in sessions])
        if len(E) > self.n_enroll:
            E = E[r.choice(len(E), self.n_enroll, replace=False)]
        return E

    def fit_student(self, corpus, student, sessions):
        r = np.random.default_rng(zlib.crc32(student.encode()))
        enroll = self._enroll(corpus, sessions, r)
        held = []
        if len(sessions) >= 2:
            for i in range(len(sessions)):
                e2 = self._enroll(corpus, sessions[:i] + sessions[i + 1:], r)
                held.append(self._dist(e2, corpus, sessions[i])[2])
        else:
            held.append(self._dist(enroll, corpus, sessions[0])[2])
        h = np.concatenate(held)
        h = h[~np.isnan(h)]
        mu0, sd0 = (float(h.mean()), max(float(h.std()), 0.05)) if len(h) >= 3 else (0.0, 1.0)
        return (enroll, mu0, sd0)

    def score(self, corpus, model, s):
        enroll, mu0, sd0 = model
        start, end, d = self._dist(enroll, corpus, s)
        return {"keystroke": Series(start, end, _standardise(d, mu0, sd0))}


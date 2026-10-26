"""A small LSTM with triplet loss in NumPy, for the TypeNet-style baseline.

TypeNet (Acien et al. 2022) embeds sequences of M keystrokes, each described
by hold, inter-key, press-press and release-release latency plus the key
code, with a two-layer LSTM trained by triplet loss, and verifies a user by
the Euclidean distance between a test sequence and their enrollment
sequences. This is the same recipe scaled down to one LSTM layer (the
synthetic and lab populations are a few hundred students, not 168 000), and
written in NumPy so the harness needs no deep-learning framework.
"""

from __future__ import annotations

import numpy as np


def _sig(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


class LSTMEmbedder:
    def __init__(self, n_in: int, hidden: int = 32, emb: int = 32, seed: int = 0):
        r = np.random.default_rng(seed)
        H = hidden
        s = 1.0 / np.sqrt(H)
        self.p = {
            "Wx": r.uniform(-s, s, (n_in, 4 * H)),
            "Wh": r.uniform(-s, s, (H, 4 * H)),
            "b": np.zeros(4 * H),
            "Wo": r.uniform(-s, s, (H, emb)),
            "bo": np.zeros(emb),
        }
        self.p["b"][H:2 * H] = 1.0  # forget-gate bias
        self.H = H
        self.mean = np.zeros(n_in)
        self.std = np.ones(n_in)

    # x: (N, T, D) already normalised
    def forward(self, x: np.ndarray, keep: bool = False):
        p, H = self.p, self.H
        N, T, _ = x.shape
        h = np.zeros((N, H))
        c = np.zeros((N, H))
        cache = []
        for t in range(T):
            z = x[:, t] @ p["Wx"] + h @ p["Wh"] + p["b"]
            i, f, o, g = _sig(z[:, :H]), _sig(z[:, H:2 * H]), _sig(z[:, 2 * H:3 * H]), np.tanh(z[:, 3 * H:])
            c_new = f * c + i * g
            tc = np.tanh(c_new)
            h_new = o * tc
            if keep:
                cache.append((x[:, t], h, c, i, f, o, g, tc))
            h, c = h_new, c_new
        e = h @ p["Wo"] + p["bo"]
        return (e, h, cache) if keep else e

    def backward(self, de: np.ndarray, hT: np.ndarray, cache) -> dict:
        p, H = self.p, self.H
        g_ = {k: np.zeros_like(v) for k, v in p.items()}
        g_["Wo"] = hT.T @ de
        g_["bo"] = de.sum(0)
        dh = de @ p["Wo"].T
        dc = np.zeros_like(dh)
        for xt, h_prev, c_prev, i, f, o, g, tc in reversed(cache):
            do = dh * tc
            dc = dc + dh * o * (1 - tc * tc)
            di, dg, df = dc * g, dc * i, dc * c_prev
            dz = np.concatenate([di * i * (1 - i), df * f * (1 - f), do * o * (1 - o), dg * (1 - g * g)], axis=1)
            g_["Wx"] += xt.T @ dz
            g_["Wh"] += h_prev.T @ dz
            g_["b"] += dz.sum(0)
            dh = dz @ p["Wh"].T
            dc = dc * f
        return g_

    def embed(self, seqs: np.ndarray, batch: int = 2048) -> np.ndarray:
        if not len(seqs):
            return np.zeros((0, self.p["bo"].shape[0]))
        z = (seqs - self.mean) / self.std
        return np.concatenate([self.forward(z[i:i + batch]) for i in range(0, len(z), batch)])


def triplet_loss(a, p, n, margin: float):
    """Mean max(0, |a-p| - |a-n| + margin) and its gradients wrt a, p, n."""
    dp = a - p
    dn = a - n
    lp = np.sqrt((dp * dp).sum(1) + 1e-9)
    ln = np.sqrt((dn * dn).sum(1) + 1e-9)
    loss = lp - ln + margin
    act = (loss > 0).astype(float)[:, None] / len(a)
    gp = dp / lp[:, None] * act
    gn = dn / ln[:, None] * act
    return float(np.maximum(loss, 0).mean()), gp - gn, -gp, gn


def train(model: LSTMEmbedder, seqs: np.ndarray, owner: np.ndarray, steps: int = 1500, batch: int = 64,
          lr: float = 3e-3, margin: float = 1.5, seed: int = 0, log=None) -> list[float]:
    """Triplet training: anchor and positive from the same student, negative from another."""
    r = np.random.default_rng(seed)
    model.mean = seqs.reshape(-1, seqs.shape[-1]).mean(0)
    model.std = seqs.reshape(-1, seqs.shape[-1]).std(0) + 1e-6
    z = (seqs - model.mean) / model.std
    by = {o: np.flatnonzero(owner == o) for o in np.unique(owner)}
    by = {o: ix for o, ix in by.items() if len(ix) >= 2}
    people = np.array(list(by))
    m = {k: np.zeros_like(v) for k, v in model.p.items()}
    v = {k: np.zeros_like(v) for k, v in model.p.items()}
    hist = []
    for step in range(1, steps + 1):
        who = r.choice(people, batch)
        other = r.choice(people, batch)
        clash = other == who
        while clash.any():
            other[clash] = r.choice(people, int(clash.sum()))
            clash = other == who
        ia, ip, ineg = [], [], []
        for w, o in zip(who, other):
            a, b = r.choice(by[w], 2, replace=False)
            ia.append(a)
            ip.append(b)
            ineg.append(r.choice(by[o]))
        X = z[np.r_[ia, ip, ineg]]
        e, hT, cache = model.forward(X, keep=True)
        B = len(ia)
        loss, ga, gp, gn = triplet_loss(e[:B], e[B:2 * B], e[2 * B:], margin)
        grads = model.backward(np.concatenate([ga, gp, gn]), hT, cache)
        for k in model.p:  # Adam
            gk = np.clip(grads[k], -5, 5)
            m[k] = 0.9 * m[k] + 0.1 * gk
            v[k] = 0.999 * v[k] + 0.001 * gk * gk
            model.p[k] -= lr * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(v[k] / (1 - 0.999 ** step)) + 1e-8)
        hist.append(loss)
        if log and step % 250 == 0:
            log(f"    typenet step {step}: triplet loss {np.mean(hist[-250:]):.3f}")
    return hist

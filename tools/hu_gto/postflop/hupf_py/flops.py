"""Suit-isomorphic flop classes (1755) and flop samplers for per-class aggregation.

Two samplers, both returning (canonical flop, weight) with weights summing to 1 and already
carrying the iso-multiplicity m_f (sum m_f = 22100):

* `herding_sample(K)` (default in the pipeline): deterministic herding (Welling 2009) on flop
  features - rank presence, high card, suit pattern, pairing, rank-pair co-presence - so the
  sample's feature frequencies match the population at O(1/K).  Measured on exact class equity
  (all 1755 flops, 3 lines): K=30 error RMS 0.6-1.2 pp, max 1.7-3.8 pp.
* `systematic_sample(K, u)`: flops sorted by texture (suit pattern, pairing, high, middle, low
  rank), laid on [0, 1) proportionally to m_f, drawn at (k + u)/K (systematic PPS; unbiased over a
  uniform u).  Prone to periodicity: K=30, u=0.5 has 2/30 deuce flops vs 21.7% in the population;
  K=30 error RMS 1.2-2.6 pp, max 2.9-6.4 pp (mean over u).
"""

from __future__ import annotations

import itertools
from functools import lru_cache

import numpy as np

from .cards import RANKS, SUITS

PERMS = list(itertools.permutations(range(4)))


def _canon(cards: tuple[int, int, int]) -> tuple[int, int, int]:
    best = None
    for p in PERMS:
        t = tuple(sorted(4 * (c // 4) + p[c % 4] for c in cards))
        if best is None or t > best:
            best = t
    return best  # type: ignore[return-value]


@lru_cache(maxsize=1)
def canonical_flops() -> tuple[list[tuple[int, int, int]], np.ndarray]:
    counts: dict[tuple[int, int, int], int] = {}
    for f in itertools.combinations(range(52), 3):
        k = _canon(f)
        counts[k] = counts.get(k, 0) + 1
    flops = sorted(counts)
    mult = np.array([counts[f] for f in flops], dtype=np.float64)
    assert len(flops) == 1755 and mult.sum() == 22100
    return flops, mult


def flop_str(f) -> str:
    cs = sorted(f, reverse=True)
    return "".join(RANKS[c // 4] + SUITS[c % 4] for c in cs)


def texture(f) -> dict:
    ranks = sorted((c // 4 for c in f), reverse=True)
    suits = [c % 4 for c in f]
    ns = len(set(suits))
    nr = len(set(ranks))
    return {
        "suit": {1: "monotone", 2: "twotone", 3: "rainbow"}[ns],
        "pair": {1: "trips", 2: "paired", 3: "unpaired"}[nr],
        "high": RANKS[ranks[0]],
        "ranks": ranks,
    }


def _sort_key(f):
    t = texture(f)
    suit_o = {"rainbow": 0, "twotone": 1, "monotone": 2}[t["suit"]]
    pair_o = {"unpaired": 0, "paired": 1, "trips": 2}[t["pair"]]
    r = t["ranks"]
    return (suit_o, pair_o, -r[0], -r[1], -r[2])


def systematic_draws(k: int, u: float = 0.5) -> list[str]:
    """Flop string at each of the K systematic points (j + u) / K (may repeat)."""
    flops, mult = canonical_flops()
    order = sorted(range(len(flops)), key=lambda i: _sort_key(flops[i]))
    cum = np.cumsum(mult[order]) / mult.sum()
    out = []
    for j in range(k):
        pos = int(np.searchsorted(cum, (j + u) / k, side="right"))
        out.append(flop_str(flops[order[min(pos, len(order) - 1)]]))
    return out


def systematic_sample(k: int, u: float = 0.5) -> list[tuple[str, float]]:
    """K draws -> list of (flop string, weight) with weights summing to 1."""
    picks: dict[str, float] = {}
    for f in systematic_draws(k, u):
        picks[f] = picks.get(f, 0.0) + 1.0 / k
    return list(picks.items())


def all_flops() -> list[tuple[str, float]]:
    flops, mult = canonical_flops()
    return [(flop_str(f), m / mult.sum()) for f, m in zip(flops, mult, strict=True)]


def features(f: str) -> np.ndarray:
    """Calibration features of a flop: presence of each rank (13), monotone, two-tone, paired."""
    ranks = [RANKS.index(f[i]) for i in (0, 2, 4)]
    suits = {f[1], f[3], f[5]}
    x = np.zeros(16)
    for r in set(ranks):
        x[r] = 1.0
    x[13] = len(suits) == 1
    x[14] = len(suits) == 2
    x[15] = len(set(ranks)) == 2
    return x


@lru_cache(maxsize=1)
def population_features() -> np.ndarray:
    fl, mult = canonical_flops()
    X = np.array([features(flop_str(f)) for f in fl])
    return (X * mult[:, None]).sum(0) / mult.sum()


def calibrate(sample: list[tuple[str, float]], iters: int = 100) -> list[tuple[str, float]]:
    """Entropy raking: reweight the draws so the weighted flop features match the population.

    Minimises KL(w || design weights) subject to sum_d w_d x_d = population mean (dual Newton with
    backtracking; the rank-presence features are collinear with `paired`, hence lstsq).  Features
    with no variation in the sample cannot be matched and are dropped."""
    X = np.array([features(f) for f, _ in sample])
    w0 = np.array([w for _, w in sample])
    w0 = w0 / w0.sum()
    mu = population_features()
    keep = X.max(0) > X.min(0)
    X, mu = X[:, keep], mu[keep]

    def dual(lam):
        z = X @ lam
        m = z.max()
        return m + np.log((w0 * np.exp(z - m)).sum()) - lam @ mu

    lam = np.zeros(X.shape[1])
    for _ in range(iters):
        z = X @ lam
        w = w0 * np.exp(z - z.max())
        w /= w.sum()
        g = w @ X - mu
        if np.abs(g).max() < 1e-9:
            break
        Xc = X - w @ X
        H = (Xc * w[:, None]).T @ Xc
        step = np.linalg.lstsq(H, g, rcond=1e-10)[0]
        t, f0 = 1.0, dual(lam)
        while dual(lam - t * step) > f0 - 1e-4 * t * (g @ step) and t > 1e-8:
            t *= 0.5
        lam -= t * step
    z = X @ lam
    w = w0 * np.exp(z - z.max())
    w /= w.sum()
    return [(f, float(x)) for (f, _), x in zip(sample, w, strict=True)]


def herding_features(f: str) -> np.ndarray:
    """Rank presence (13), high-card rank (13), suit pattern (3), pairing (3),
    rank-pair co-presence (78)."""
    rs = [RANKS.index(f[i]) for i in (0, 2, 4)]
    ranks = sorted(set(rs))
    nsuit = len({f[1], f[3], f[5]})
    pres = np.zeros(13)
    pres[ranks] = 1.0
    high = np.zeros(13)
    high[max(rs)] = 1.0
    co = np.outer(pres, pres)[np.triu_indices(13, 1)]
    return np.concatenate(
        [
            pres,
            high,
            [nsuit == 1, nsuit == 2, nsuit == 3],
            [len(ranks) == 1, len(ranks) == 2, len(ranks) == 3],
            co,
        ]
    )


BLOCK_WEIGHTS = (1.0, 1.0, 1.0, 1.0, 1.0)  # presence, high card, suit pattern, pairing, co-presence


def herding_sample(k: int, block_weights=BLOCK_WEIGHTS) -> list[tuple[str, float]]:
    """Deterministic herding sample of K flops (weight 1/K each), Welling (2009).

    w_0 = mu; x_t = argmax_x <w_{t-1}, phi(x)>; w_t = w_{t-1} + mu - phi(x_t), over the 1755
    canonical flops, with mu the multiplicity-weighted population mean of `herding_features`
    (each block scaled to unit variance).  The running mean of phi converges to mu at O(1/K), so
    rank, high-card, suit-pattern, pairing and rank-pair frequencies are balanced - the
    texture-sorted systematic sample is not (its K=30, u=0.5 draw has 2/30 deuce flops vs 21.7%
    in the population).  Repeats are allowed (weight accumulates)."""
    fl, mult = canonical_flops()
    names = [flop_str(f) for f in fl]
    X = np.array([herding_features(n) for n in names])
    mu = (X * mult[:, None]).sum(0) / mult.sum()
    scale = 1.0 / np.sqrt(np.maximum(mu * (1 - mu), 1e-4))
    sizes = (13, 13, 3, 3, 78)
    scale = scale * np.repeat(np.asarray(block_weights, dtype=float), sizes)
    Xs, mus = X * scale, mu * scale
    w = mus.copy()
    picks: dict[str, float] = {}
    for _ in range(k):
        j = int(np.argmax(Xs @ w))
        w += mus - Xs[j]
        picks[names[j]] = picks.get(names[j], 0.0) + 1.0 / k
    return list(picks.items())

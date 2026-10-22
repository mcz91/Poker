"""Placeholder preflop ranges (169-class weights) for standalone pipeline/live runs; the
integration loop (integ/) passes the ranges of the preflop solve instead.

Hands are ordered by all-in equity vs a random hand (repo matrix poker.preflop_equity,
SE ~1.1 pp per cell, card removal by disjoint-combo counts); `band(lo, hi)` takes
the classes whose cumulative combo share falls in [lo, hi), with fractional weight
at the borders.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .cards import CLASS_NCOMBOS, COMBO_CLASS, COMBOS


@lru_cache(maxsize=1)
def equity_matrix() -> tuple[np.ndarray, np.ndarray]:
    """(E, W): E[i,j] all-in equity class i vs j, W[i,j] number of disjoint combo pairs."""
    from poker.preflop import ALL_CLASSES
    from poker.preflop_equity import equity

    from .cards import check_against_repo

    check_against_repo()
    n = len(ALL_CLASSES)
    E = np.array([[equity(ALL_CLASSES[i], ALL_CLASSES[j]) for j in range(n)] for i in range(n)])
    masks = np.zeros((1326, 52), dtype=bool)
    masks[np.arange(1326), COMBOS[:, 0]] = True
    masks[np.arange(1326), COMBOS[:, 1]] = True
    disjoint = (masks.astype(np.int32) @ masks.T.astype(np.int32)) == 0
    W = np.zeros((169, 169))
    np.add.at(W, (COMBO_CLASS[:, None], COMBO_CLASS[None, :]), disjoint.astype(np.float64))
    return E, W


@lru_cache(maxsize=1)
def strength_order() -> np.ndarray:
    E, W = equity_matrix()
    eq_rand = (E * W).sum(1) / W.sum(1)
    return np.argsort(-eq_rand, kind="stable")


def band(lo: float, hi: float) -> np.ndarray:
    order = strength_order()
    w = np.zeros(169)
    total = CLASS_NCOMBOS.sum()
    cum = 0.0
    for i in order:
        a, b = cum / total, (cum + CLASS_NCOMBOS[i]) / total
        overlap = max(0.0, min(b, hi) - max(a, lo))
        if b > a:
            w[i] = overlap / (b - a)
        cum += CLASS_NCOMBOS[i]
    return w


def equity_vs_range(w_hero: np.ndarray, w_villain: np.ndarray) -> np.ndarray:
    """Preflop all-in equity of each class vs the villain range (repo matrix)."""
    E, W = equity_matrix()
    num = (E * W) @ w_villain
    den = W @ w_villain
    return np.where(den > 0, num / np.maximum(den, 1e-12), 0.0)


PLACEHOLDERS = {
    # line: (description, SB/IP range, BB/OOP range, pot_bb, contrib_bb)
    "limp_check": (
        "SB limps bottom 50% [50%,100%); BB iso-raises top 20%, checks [20%,100%)",
        lambda: band(0.50, 1.0),
        lambda: band(0.20, 1.0),
        2.0,
        1.0,
    ),
    "raise2x_call": (
        "SB raises 2x top 40%; BB 3bet-jams top 7%, calls [7%,57%)",
        lambda: band(0.0, 0.40),
        lambda: band(0.07, 0.57),
        4.0,
        2.0,
    ),
    "iso3x_call": (
        "SB limps [50%,100%); BB isos to 3bb with top 20%; SB calls [50%,80%)",
        lambda: band(0.50, 0.80),
        lambda: band(0.0, 0.20),
        6.0,
        3.0,
    ),
}

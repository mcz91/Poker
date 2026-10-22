"""Per-class aggregation of per-flop solver outputs.

For a canonical flop f the solver returns, per combo c and player p, the normalised weight
nw_f(c) = w_p(c) * sum of opponent weights disjoint from c and f (joint deal count), the
equity eq_f(c) vs the opponent range and the EV ev_f(c) = expected share of the starting pot
minus postflop investment (chips).  Because the inputs are suit-symmetric (169-class
weights), the class sum over all raw flops in the iso-orbit of f equals m_f times the class
sum on the canonical flop, so with draw weights w_d from the sampler (which already
carry m_f) the class estimates are ratios
    EV_class = sum_d w_d sum_{c in class} nw*ev / sum_d w_d sum_{c in class} nw
and EQR_class = EV_class / (pot * EQ_class).
"""

from __future__ import annotations

import numpy as np

from .cards import BB_CHIPS, CLASS_MATRIX


def per_flop_arrays(res: dict) -> dict[str, np.ndarray]:
    out = {}
    for k in ("nw", "ev", "eq", "weight"):
        out[k] = np.array([res["players"][p][k] for p in (0, 1)], dtype=np.float64)
    return out


def class_sums(res: dict) -> np.ndarray:
    """(3, 2, 169): [sum nw, sum nw*ev, sum nw*eq] per player and class on one flop."""
    a = per_flop_arrays(res)
    nw, ev, eq = a["nw"], a["ev"], a["eq"]
    return np.stack([nw @ CLASS_MATRIX.T, (nw * ev) @ CLASS_MATRIX.T, (nw * eq) @ CLASS_MATRIX.T])


def aggregate(
    results: list[dict], weights: list[float], pot_bb: float, eq_exact: np.ndarray | None = None
) -> dict[str, np.ndarray]:
    S = np.zeros((3, 2, 169))
    for r, w in zip(results, weights, strict=True):
        S += w * class_sums(r)
    mass, evs, eqs = S
    with np.errstate(invalid="ignore", divide="ignore"):
        ev = np.where(mass > 0, evs / mass, np.nan) / BB_CHIPS
        eq = np.where(mass > 0, eqs / mass, np.nan)
        eqr = ev / (pot_bb * eq)
    out = {
        "mass": mass,
        "ev_bb": ev,
        "eq": eq,
        "eqr": eqr,
        "range_ev_bb": evs.sum(1) / mass.sum(1) / BB_CHIPS,
        "range_eq": eqs.sum(1) / mass.sum(1),
    }
    if eq_exact is not None:
        # ratio estimator: EQR from the sample, equity from the full flop population
        out["eq_exact"] = eq_exact
        out["ev_bb_ratio"] = eqr * pot_bb * eq_exact
    return out

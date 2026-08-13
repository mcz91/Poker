"""Malmuth–Harville ICM and winner-take-all chip EV."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache


def _validate(
    stacks: Sequence[int],
    prizes: Sequence[float] | None = None,
) -> None:
    if not stacks:
        raise ValueError("stacki nie mogą być puste")
    if any(stack < 0 for stack in stacks):
        raise ValueError("stack nie może być ujemny")
    if prizes is not None and len(prizes) != len(stacks):
        raise ValueError("nagród musi być tyle, ile miejsc")


def chip_shares(stacks: Sequence[int]) -> tuple[float, ...]:
    _validate(stacks)
    total = sum(stacks)
    if total == 0:
        n = len(stacks)
        return tuple(1.0 / n for _ in stacks)
    return tuple(stack / total for stack in stacks)


def place_probabilities(stacks: Sequence[int]) -> tuple[tuple[float, ...], ...]:
    """P[i][k] = P(miejsce i kończy na pozycji k), k=0 pierwsze."""
    _validate(stacks)
    n = len(stacks)
    matrix = [[0.0] * n for _ in range(n)]
    out_seats = [i for i, stack in enumerate(stacks) if stack == 0]
    place = n - 1
    for seat in reversed(out_seats):
        matrix[seat][place] = 1.0
        place -= 1
    alive = tuple((i, stacks[i]) for i in range(n) if stacks[i] > 0)
    for seat, probs in _remaining(alive).items():
        for k, prob in enumerate(probs):
            matrix[seat][k] = prob
    return tuple(tuple(row) for row in matrix)


@lru_cache(maxsize=None)
def _remaining(active: tuple[tuple[int, int], ...]) -> dict[int, tuple[float, ...]]:
    if not active:
        return {}
    if len(active) == 1:
        return {active[0][0]: (1.0,)}
    total = sum(stack for _, stack in active)
    acc: dict[int, list[float]] = {seat: [0.0] * len(active) for seat, _ in active}
    for seat, stack in active:
        p_first = stack / total
        rest = tuple(item for item in active if item[0] != seat)
        acc[seat][0] += p_first
        for other, dist in _remaining(rest).items():
            for k, prob in enumerate(dist):
                acc[other][k + 1] += p_first * prob
    return {seat: tuple(vals) for seat, vals in acc.items()}


def icm_equities(
    stacks: Sequence[int],
    prizes: Sequence[float],
) -> tuple[float, ...]:
    _validate(stacks, prizes)
    probs = place_probabilities(stacks)
    return tuple(
        sum(probs[i][k] * prizes[k] for k in range(len(prizes))) for i in range(len(stacks))
    )


def wta_equities(stacks: Sequence[int], prize: float) -> tuple[float, ...]:
    """WTA: $EV = prize * chips / total. Equals ICM with (prize, 0, …, 0)."""
    _validate(stacks)
    if prize < 0:
        raise ValueError("pula nagród nie może być ujemna")
    return tuple(prize * share for share in chip_shares(stacks))


def risk_premium(
    stacks: Sequence[int],
    prizes: Sequence[float],
) -> tuple[float, ...]:
    """chipEV − ICM. Dodatnie u chip leadera (żetony przecenione)."""
    pool = sum(prizes)
    chips = tuple(pool * share for share in chip_shares(stacks))
    money = icm_equities(stacks, prizes)
    return tuple(chip - ev for chip, ev in zip(chips, money, strict=True))

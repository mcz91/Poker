"""Spin & Go: wypłaty 3-max, role blindów, rozliczenie all-in, EV shove UTG."""

from __future__ import annotations

from dataclasses import dataclass

from poker.icm import icm_equities

STARTING_CHIPS = 50
SMALL_BLIND = 1
BIG_BLIND = 2


@dataclass(frozen=True, slots=True)
class SpinPayout:
    name: str
    multiplier: int
    prizes: tuple[float, float, float]
    winner_take_all: bool


PAYOUTS: dict[str, SpinPayout] = {
    "2x": SpinPayout("2x WTA", 2, (2.0, 0.0, 0.0), True),
    "3x": SpinPayout("3x WTA", 3, (3.0, 0.0, 0.0), True),
    "10x": SpinPayout("10x 80/20", 10, (8.0, 2.0, 0.0), False),
}

Stacks3 = tuple[int, int, int]


def roles(button: int) -> tuple[int, int, int]:
    """(utg, btn_sb, bb). Button posts SB; left of button is BB; other acts first."""
    if button not in (0, 1, 2):
        raise ValueError(f"button poza 3 miejscami: {button}")
    btn = button
    bb = (button + 1) % 3
    utg = (button + 2) % 3
    return utg, btn, bb


def post_blinds(stacks: Stacks3, button: int) -> tuple[Stacks3, int]:
    _, btn, bb = roles(button)
    behind = list(stacks)
    sb = min(stacks[btn], SMALL_BLIND)
    bb_amt = min(stacks[bb], BIG_BLIND)
    behind[btn] -= sb
    behind[bb] -= bb_amt
    return (behind[0], behind[1], behind[2]), sb + bb_amt


def award_allin(contributions: tuple[int, ...], ranks: tuple[int, ...]) -> tuple[int, ...]:
    """Niższy rank wygrywa. Nadpłata wraca. Side poty po poziomach wpłaty."""
    if len(contributions) != len(ranks):
        raise ValueError("wkłady i rangi muszą mieć tę samą długość")
    if any(amount < 0 for amount in contributions):
        raise ValueError("wkład nie może być ujemny")
    n = len(contributions)
    payouts = [0] * n
    contrib = list(contributions)
    ordered = sorted(contrib)
    uncalled = ordered[-1] - ordered[-2] if n >= 2 else (ordered[0] if ordered else 0)
    if uncalled:
        big = max(range(n), key=lambda i: contrib[i])
        payouts[big] += uncalled
        contrib[big] -= uncalled
    levels = sorted({amount for amount in contrib if amount > 0})
    prev = 0
    eligible = [i for i, amount in enumerate(contrib) if amount > 0]
    for level in levels:
        pot = (level - prev) * len(eligible)
        if pot:
            best = min(ranks[i] for i in eligible)
            winners = [i for i in eligible if ranks[i] == best]
            share, rem = divmod(pot, len(winners))
            for winner in winners:
                payouts[winner] += share
            if rem:
                payouts[min(winners)] += rem
        eligible = [i for i in eligible if contrib[i] > level]
        prev = level
    return tuple(payouts)


def utg_shove_both_fold(stacks: Stacks3, button: int) -> Stacks3:
    behind, pot = post_blinds(stacks, button)
    utg, _, _ = roles(button)
    out = list(behind)
    out[utg] += pot
    return (out[0], out[1], out[2])


def utg_shove_called(
    stacks: Stacks3,
    button: int,
    caller: int,
    winner: int,
) -> Stacks3:
    utg, btn, bb = roles(button)
    if caller == utg:
        raise ValueError("caller nie może być UTG")
    contrib = [0, 0, 0]
    contrib[btn] += min(stacks[btn], SMALL_BLIND)
    contrib[bb] += min(stacks[bb], BIG_BLIND)
    contrib[utg] = stacks[utg]
    already = contrib[caller]
    target = contrib[utg]
    add = max(0, min(stacks[caller] - already, target - already))
    contrib[caller] = already + add
    ranks = [1, 1, 1]
    ranks[winner] = 0
    awarded = award_allin((contrib[0], contrib[1], contrib[2]), (ranks[0], ranks[1], ranks[2]))
    return (
        stacks[0] - contrib[0] + awarded[0],
        stacks[1] - contrib[1] + awarded[1],
        stacks[2] - contrib[2] + awarded[2],
    )


def utg_shove_ev(
    stacks: Stacks3,
    button: int,
    prizes: tuple[float, float, float],
    caller: int,
    equity: float,
) -> tuple[float, float, float]:
    """$EV UTG: fold / jam obie fold / jam caller woła z danym equity."""
    if not 0.0 <= equity <= 1.0:
        raise ValueError(f"equity poza [0, 1]: {equity}")
    utg, _, _ = roles(button)
    behind, _ = post_blinds(stacks, button)
    fold = icm_equities(behind, prizes)[utg]
    shove_fold = icm_equities(utg_shove_both_fold(stacks, button), prizes)[utg]
    win = icm_equities(utg_shove_called(stacks, button, caller, utg), prizes)[utg]
    lose = icm_equities(utg_shove_called(stacks, button, caller, caller), prizes)[utg]
    return fold, shove_fold, equity * win + (1.0 - equity) * lose

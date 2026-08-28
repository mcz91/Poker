"""Spin ROI arena. Hero vs scripted fish. Unit is buy-in, not BB/100."""

from __future__ import annotations

import random
from dataclasses import dataclass

from poker.cards import Card
from poker.dealing import shuffled_deck
from poker.evaluation import HandValue, evaluate_best
from poker.openfold import WEIGHTS, _hu
from poker.preflop import CLASS_INDEX, classify
from poker.spin import (
    STARTING_CHIPS,
    award_allin,
    blinds_for_hand,
    is_jam_fold_depth,
    open_amount,
    roles,
)

N_HANDS = 169
ZERO = [0.0] * N_HANDS
ONE = [1.0] * N_HANDS


@dataclass(frozen=True)
class SeatBook:
    open: list[float]
    overjam: list[float]
    vs_open: list[float]
    vs_jam: list[float]
    jf_first: list[float]
    jf_vs_jam: list[float]


def always_jam() -> SeatBook:
    return SeatBook(ZERO, ONE, ONE, ONE, ONE, ONE)


def always_fold() -> SeatBook:
    return SeatBook(ZERO, ZERO, ZERO, ZERO, ZERO, ZERO)


def call_vs_random(thresh: float = 0.50) -> list[float]:
    """Call a 100% jammer when equity vs random ≥ thresh."""
    tot = float(sum(WEIGHTS))
    out = [0.0] * N_HANDS
    for i in range(N_HANDS):
        eq = sum(WEIGHTS[j] * _hu(i, j) for j in range(N_HANDS)) / tot
        out[i] = 1.0 if eq >= thresh else 0.0
    return out


def range_vs_random(thresh: float) -> list[float]:
    return call_vs_random(thresh)


def field_exploit() -> SeatBook:
    """Population exploit for $1: steal wide, 3bet wide, call jams vs random."""
    steal = range_vs_random(0.50)
    premium = range_vs_random(0.62)
    three = range_vs_random(0.53)
    call = range_vs_random(0.50)
    short = range_vs_random(0.48)
    return SeatBook(steal, premium, three, call, short, call)


def dollar_fish() -> SeatBook:
    """$1-ish: opens too wide, under-3bets (would flat), calls jams too wide."""
    open_r = range_vs_random(0.485)
    three = range_vs_random(0.58)
    call = range_vs_random(0.51)
    short = range_vs_random(0.46)
    return SeatBook(open_r, ZERO, three, call, short, call)


def wide_call(p: float = 0.45) -> SeatBook:
    freq = [p] * N_HANDS
    return SeatBook(freq, freq, freq, freq, freq, freq)


def _alive(stacks: list[int]) -> list[int]:
    return [i for i in range(3) if stacks[i] > 0]


def _next_button(stacks: list[int], current: int, first: bool) -> int:
    if first:
        return current
    for k in range(1, 4):
        b = (current + k) % 3
        if stacks[b] > 0:
            return b
    return current


def pick(
    book: SeatBook,
    idx: int,
    *,
    jamfold: bool,
    opened: bool,
    jammed: bool,
    rng: random.Random,
) -> str:
    if jammed:
        freq = book.jf_vs_jam if jamfold else book.vs_jam
        return "jam" if rng.random() < freq[idx] else "fold"
    if opened:
        return "jam" if rng.random() < book.vs_open[idx] else "fold"
    if jamfold:
        return "jam" if rng.random() < book.jf_first[idx] else "fold"
    x = rng.random()
    j = book.overjam[idx]
    o = book.open[idx]
    if x < j:
        return "jam"
    if x < j + o:
        return "open"
    return "fold"


def run_spin(
    books: tuple[SeatBook, SeatBook, SeatBook],
    seed: int,
) -> tuple[tuple[int, int, int], str]:
    """Stacki końcowe i powód końca: "bust" (≤1 żywy) albo "guard" (limit rąk)."""
    rng = random.Random(seed)
    stacks = [STARTING_CHIPS, STARTING_CHIPS, STARTING_CHIPS]
    button = 1
    hand_i = 0
    first = True
    guard = 0
    while len(_alive(stacks)) >= 2 and guard < 80:
        guard += 1
        sb, bb, _ = blinds_for_hand(hand_i)
        button = _next_button(stacks, button, first)
        first = False
        stacks = _play_hand(stacks, button, sb, bb, books, rng)
        hand_i += 1
    reason = "bust" if len(_alive(stacks)) <= 1 else "guard"
    return (stacks[0], stacks[1], stacks[2]), reason


def play_spin(
    books: tuple[SeatBook, SeatBook, SeatBook],
    prizes: tuple[float, float, float],
    seed: int,
) -> tuple[float, float, float]:
    stacks, _ = run_spin(books, seed)
    order = sorted(range(3), key=lambda i: (-stacks[i], i))
    money = [0.0, 0.0, 0.0]
    for place, seat in enumerate(order):
        money[seat] = prizes[place]
    return (money[0], money[1], money[2])


def _play_hand(
    stacks: list[int],
    button: int,
    sb: int,
    bb: int,
    books: tuple[SeatBook, SeatBook, SeatBook],
    rng: random.Random,
) -> list[int]:
    live = _alive(stacks)
    if len(live) <= 2:
        # Heads-up po wybiciu: role z żywych miejsc, nie z nominalnego układu 3-max.
        bb_seat = next(s for s in live if s != button)
        order = [button, bb_seat]
    else:
        utg, _, bb_seat = roles(button)
        order = [utg, button, bb_seat]
    contrib = [0, 0, 0]
    folded = [stacks[i] <= 0 for i in range(3)]
    acted = list(folded)
    contrib[button] = min(stacks[button], sb)
    contrib[bb_seat] = min(stacks[bb_seat], bb)
    deck = shuffled_deck(rng)
    holes: list[tuple[Card, Card] | None] = [None, None, None]
    n = 0
    for owner in range(3):
        if stacks[owner] > 0:
            holes[owner] = (deck[n], deck[n + 1])
            n += 2
    board = deck[n : n + 5]
    jammed = False
    opened = False
    jamfold = is_jam_fold_depth((stacks[0], stacks[1], stacks[2]), bb)

    def to_act() -> int | None:
        remaining = [s for s in range(3) if not folded[s] and stacks[s] > 0]
        if len(remaining) <= 1:
            return None
        raised = jammed or opened or max(contrib) > bb
        for candidate in order:
            if folded[candidate] or stacks[candidate] <= 0:
                continue
            if acted[candidate]:
                continue
            if contrib[candidate] >= stacks[candidate]:
                continue
            if not raised and candidate == bb_seat and len(live) > 2:
                continue
            return candidate
        return None

    steps = 0
    while steps < 12:
        steps += 1
        seat = to_act()
        if seat is None:
            break
        hole = holes[seat]
        if hole is None:
            folded[seat] = True
            acted[seat] = True
            continue
        idx = CLASS_INDEX[classify(hole[0], hole[1])]
        act = pick(
            books[seat],
            idx,
            jamfold=jamfold,
            opened=opened,
            jammed=jammed,
            rng=rng,
        )
        acted[seat] = True
        if act == "fold":
            folded[seat] = True
        elif act == "open":
            contrib[seat] = max(contrib[seat], min(stacks[seat], open_amount(bb)))
            opened = True
        else:
            contrib[seat] = stacks[seat]
            jammed = True
            for s in range(3):
                if folded[s] or stacks[s] <= 0 or s == seat:
                    continue
                if contrib[s] < stacks[s] and contrib[s] < contrib[seat]:
                    acted[s] = False
        remaining = [s for s in range(3) if not folded[s] and stacks[s] > 0]
        if len(remaining) <= 1:
            break

    live_now = [s for s in range(3) if not folded[s] and stacks[s] > 0]
    ranks = [99, 99, 99]
    if len(live_now) == 1:
        ranks[live_now[0]] = 0
    else:
        vals: list[tuple[int, HandValue]] = []
        for s in range(3):
            hole = holes[s]
            if s in live_now and hole is not None:
                vals.append((s, evaluate_best((*hole, *board))))
        top = max((v for _, v in vals), default=None)
        for s, val in vals:
            ranks[s] = 0 if val == top else 1
    awarded = award_allin((contrib[0], contrib[1], contrib[2]), (ranks[0], ranks[1], ranks[2]))
    return [
        stacks[0] - contrib[0] + awarded[0],
        stacks[1] - contrib[1] + awarded[1],
        stacks[2] - contrib[2] + awarded[2],
    ]


def sample(
    hero: SeatBook,
    villain: SeatBook,
    prizes: tuple[float, float, float],
    n: int,
    seed: int = 1,
) -> dict[str, float]:
    if n < 2:
        raise ValueError("n")
    books = (hero, villain, villain)
    xs = [play_spin(books, prizes, seed + i)[0] for i in range(n)]
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    se = (var / n) ** 0.5
    roi = mean - 1.0
    return {
        "n": float(n),
        "mean_bi": mean,
        "roi": roi,
        "se": se,
        "ci_lo": roi - 1.96 * se,
        "ci_hi": roi + 1.96 * se,
    }

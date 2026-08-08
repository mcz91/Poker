"""Deterministyczna symulacja equity all-in klasa vs klasa (INV-P1: RNG wstrzyknięty)."""

import random

from poker.cards import FULL_DECK
from poker.evaluation import evaluate_best
from poker.preflop import ALL_CLASSES, PreflopClass, class_combos

_CLASS_COUNT = len(ALL_CLASSES)
_DECK = tuple(sorted(FULL_DECK, key=lambda card: (card.rank.value, card.suit.value)))


def pair_seed(master_seed: int, index_a: int, index_b: int) -> int:
    """Seed pary klas pochodny od seeda macierzy — niezależny od kolejności generacji."""
    return master_seed * _CLASS_COUNT * _CLASS_COUNT + index_a * _CLASS_COUNT + index_b


def simulate_pair_units(
    class_a: PreflopClass, class_b: PreflopClass, rng: random.Random, trials: int
) -> int:
    """Jednostki pół-puli klasy A (2·wygrane + splity) z `trials` prób all-in preflop."""
    if trials < 1:
        raise ValueError(f"liczba prób musi być dodatnia: {trials}")
    combos_a = class_combos(class_a)
    combos_b = class_combos(class_b)
    units = 0
    for _ in range(trials):
        hole_a = combos_a[rng.randrange(len(combos_a))]
        while True:
            hole_b = combos_b[rng.randrange(len(combos_b))]
            if hole_a[0] not in hole_b and hole_a[1] not in hole_b:
                break
        used = {*hole_a, *hole_b}
        remaining = [card for card in _DECK if card not in used]
        board = tuple(rng.sample(remaining, 5))
        value_a = evaluate_best(hole_a + board)
        value_b = evaluate_best(hole_b + board)
        if value_a > value_b:
            units += 2
        elif value_a == value_b:
            units += 1
    return units

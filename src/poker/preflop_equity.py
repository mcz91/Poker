"""Czysty odczyt utrwalonej macierzy equity all-in preflop klasa vs klasa."""

from poker.preflop import ALL_CLASSES, CLASS_INDEX, PreflopClass
from poker.preflop_equity_data import HALF_POT_UNITS, TRIALS_PER_PAIR

_CLASS_COUNT = len(ALL_CLASSES)
_DENOMINATOR = 2 * TRIALS_PER_PAIR


def equity(class_a: PreflopClass, class_b: PreflopClass) -> float:
    """Udział oczekiwany puli klasy A przeciw klasie B (wygrana + połowa splitu)."""
    index = CLASS_INDEX[class_a] * _CLASS_COUNT + CLASS_INDEX[class_b]
    return HALF_POT_UNITS[index] / _DENOMINATOR

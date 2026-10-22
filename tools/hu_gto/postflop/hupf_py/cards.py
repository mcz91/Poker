"""Card/combo/class indexing shared with the Rust driver (b-inary layout).

card id = 4*rank + suit, rank 0 = deuce .. 12 = ace, suit order c, d, h, s.
combo index (1326) = c1*(101-c1)//2 + c2 - 1 for c1 < c2.
169 classes are ordered exactly like poker.preflop.ALL_CLASSES (AA, AKs, AKo, AQs, ...).
"""

from __future__ import annotations

import numpy as np

RANKS = "23456789TJQKA"
SUITS = "cdhs"
BB_CHIPS = 100


def card_id(s: str) -> int:
    return 4 * RANKS.index(s[0].upper()) + SUITS.index(s[1].lower())


def card_str(c: int) -> str:
    return RANKS[c // 4] + SUITS[c % 4]


def board_ids(board: str) -> list[int]:
    return [card_id(board[i : i + 2]) for i in range(0, len(board), 2)]


def pair_index(c1: int, c2: int) -> int:
    a, b = min(c1, c2), max(c1, c2)
    return a * (101 - a) // 2 + b - 1


COMBOS = np.zeros((1326, 2), dtype=np.int64)
for _a in range(52):
    for _b in range(_a + 1, 52):
        COMBOS[pair_index(_a, _b)] = (_a, _b)


def _class_list() -> list[tuple[int, int, bool]]:
    out = []
    for hi in range(12, -1, -1):
        for lo in range(hi, -1, -1):
            if hi == lo:
                out.append((hi, lo, False))
            else:
                out.append((hi, lo, True))
                out.append((hi, lo, False))
    return out


CLASSES = _class_list()
CLASS_NAMES = [
    RANKS[hi] + RANKS[lo] + ("" if hi == lo else ("s" if s else "o")) for hi, lo, s in CLASSES
]
_CLASS_INDEX = {c: i for i, c in enumerate(CLASSES)}


def combo_class(c1: int, c2: int) -> int:
    r1, r2 = c1 // 4, c2 // 4
    hi, lo = max(r1, r2), min(r1, r2)
    suited = (c1 % 4 == c2 % 4) and hi != lo
    return _CLASS_INDEX[(hi, lo, suited)]


COMBO_CLASS = np.array([combo_class(int(a), int(b)) for a, b in COMBOS], dtype=np.int64)
CLASS_NCOMBOS = np.bincount(COMBO_CLASS, minlength=169).astype(np.float64)
# class -> combo membership matrix (169 x 1326)
CLASS_MATRIX = np.zeros((169, 1326))
CLASS_MATRIX[COMBO_CLASS, np.arange(1326)] = 1.0


def class_to_combo(w169) -> np.ndarray:
    return np.asarray(w169, dtype=np.float64)[COMBO_CLASS]


def combo_to_class_mean(w1326) -> np.ndarray:
    return CLASS_MATRIX @ np.asarray(w1326, dtype=np.float64) / CLASS_NCOMBOS


def board_mask(board: str) -> np.ndarray:
    """1326 bool: combo does not intersect board."""
    ids = set(board_ids(board))
    return np.array([(a not in ids) and (b not in ids) for a, b in COMBOS])


def check_against_repo() -> None:
    """Order check vs poker.preflop.ALL_CLASSES (needs the repo package `poker`)."""
    from poker.preflop import ALL_CLASSES

    for i, cls in enumerate(ALL_CLASSES):
        hi, lo, s = CLASSES[i]
        assert (int(cls.high) - 2, int(cls.low) - 2, cls.suited) == (hi, lo, s), (i, cls)

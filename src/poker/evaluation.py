"""Ewaluator układów pokerowych: klasyfikacja 5 kart i wybór najlepszego z 5-7."""

from collections import Counter
from collections.abc import Iterable
from enum import IntEnum, unique
from itertools import combinations
from typing import NamedTuple

from poker.cards import Card


@unique
class HandCategory(IntEnum):
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9


class HandValue(NamedTuple):
    """Porządek zupełny siły układów: krotki porównują się leksykograficznie."""

    category: HandCategory
    tiebreakers: tuple[int, ...]


def evaluate_five(cards: Iterable[Card]) -> HandValue:
    hand = tuple(cards)
    if len(hand) != 5:
        raise ValueError(f"układ to dokładnie 5 kart, otrzymano {len(hand)}")
    if len(set(hand)) != 5:
        raise ValueError("karty w układzie nie mogą się powtarzać")

    ranks = sorted((card.rank.value for card in hand), reverse=True)
    is_flush = len({card.suit for card in hand}) == 1
    straight_high = _straight_high(ranks)

    if straight_high is not None:
        category = HandCategory.STRAIGHT_FLUSH if is_flush else HandCategory.STRAIGHT
        return HandValue(category, (straight_high,))
    if is_flush:
        return HandValue(HandCategory.FLUSH, tuple(ranks))

    groups = sorted(Counter(ranks).items(), key=lambda group: (group[1], group[0]), reverse=True)
    counts = tuple(count for _, count in groups)
    tiebreakers = tuple(rank for rank, _ in groups)
    match counts:
        case (4, 1):
            return HandValue(HandCategory.FOUR_OF_A_KIND, tiebreakers)
        case (3, 2):
            return HandValue(HandCategory.FULL_HOUSE, tiebreakers)
        case (3, 1, 1):
            return HandValue(HandCategory.THREE_OF_A_KIND, tiebreakers)
        case (2, 2, 1):
            return HandValue(HandCategory.TWO_PAIR, tiebreakers)
        case (2, 1, 1, 1):
            return HandValue(HandCategory.ONE_PAIR, tiebreakers)
        case _:
            return HandValue(HandCategory.HIGH_CARD, tuple(ranks))


def evaluate_best(cards: Iterable[Card]) -> HandValue:
    pool = tuple(cards)
    if not 5 <= len(pool) <= 7:
        raise ValueError(f"najlepszy układ wybiera się z 5-7 kart, otrzymano {len(pool)}")
    return max(evaluate_five(combo) for combo in combinations(pool, 5))


def _straight_high(ranks: list[int]) -> int | None:
    distinct = sorted(set(ranks), reverse=True)
    if len(distinct) != 5:
        return None
    if distinct[0] - distinct[4] == 4:
        return distinct[0]
    # Koło A-2-3-4-5: as gra jako 1, więc najwyższą kartą stritu jest 5.
    if distinct == [14, 5, 4, 3, 2]:
        return 5
    return None

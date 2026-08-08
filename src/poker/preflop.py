"""Kanoniczne klasy preflop: 169 klas dwóch kart (13 par, 78 suited, 78 offsuit)."""

from dataclasses import dataclass

from poker.cards import Card, Rank, Suit

_RANKS_DESC = tuple(sorted(Rank, reverse=True))
_SUITS = tuple(sorted(Suit, key=lambda suit: suit.value))


@dataclass(frozen=True, slots=True)
class PreflopClass:
    high: Rank
    low: Rank
    suited: bool

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError("ranga wyższa klasy nie może być niższa od niższej")
        if self.high == self.low and self.suited:
            raise ValueError("para nie ma wariantu suited")


def classify(first: Card, second: Card) -> PreflopClass:
    if first == second:
        raise ValueError("klasa preflop wymaga dwóch różnych kart")
    high, low = sorted((first.rank, second.rank), reverse=True)
    if high == low:
        return PreflopClass(high=high, low=low, suited=False)
    return PreflopClass(high=high, low=low, suited=first.suit == second.suit)


def class_combos(cls: PreflopClass) -> tuple[tuple[Card, Card], ...]:
    if cls.high == cls.low:
        return tuple(
            (Card(cls.high, first), Card(cls.low, second))
            for index, first in enumerate(_SUITS)
            for second in _SUITS[index + 1 :]
        )
    if cls.suited:
        return tuple((Card(cls.high, suit), Card(cls.low, suit)) for suit in _SUITS)
    return tuple(
        (Card(cls.high, first), Card(cls.low, second))
        for first in _SUITS
        for second in _SUITS
        if first is not second
    )


ALL_CLASSES: tuple[PreflopClass, ...] = tuple(
    PreflopClass(high=high, low=low, suited=suited)
    for index, high in enumerate(_RANKS_DESC)
    for low in _RANKS_DESC[index:]
    for suited in ((False,) if high == low else (True, False))
)

CLASS_INDEX: dict[PreflopClass, int] = {cls: index for index, cls in enumerate(ALL_CLASSES)}

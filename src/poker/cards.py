"""Karty do gry: 13 rang x 4 kolory, niemutowalne wartości."""

from dataclasses import dataclass
from enum import Enum, IntEnum, unique


@unique
class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14


@unique
class Suit(Enum):
    CLUBS = "c"
    DIAMONDS = "d"
    HEARTS = "h"
    SPADES = "s"


@dataclass(frozen=True, slots=True)
class Card:
    rank: Rank
    suit: Suit

    def __post_init__(self) -> None:
        if not isinstance(self.rank, Rank):
            raise TypeError(f"ranga spoza talii: {self.rank!r}")
        if not isinstance(self.suit, Suit):
            raise TypeError(f"kolor spoza talii: {self.suit!r}")


FULL_DECK: frozenset[Card] = frozenset(Card(rank, suit) for rank in Rank for suit in Suit)

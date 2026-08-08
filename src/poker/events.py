"""Zdarzenia rozdania: niemutowalne, typowane, z zadeklarowaną widocznością."""

from dataclasses import dataclass
from enum import Enum, unique

from poker.cards import Card


@unique
class BlindType(Enum):
    SMALL = "small"
    BIG = "big"


@unique
class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"


@dataclass(frozen=True, slots=True)
class Public:
    pass


@dataclass(frozen=True, slots=True)
class PrivateToSeat:
    seat: int


@dataclass(frozen=True, slots=True)
class EngineOnly:
    """Dane wyłącznie silnika i operatora — niewidoczne dla żadnego miejsca."""


EventVisibility = Public | PrivateToSeat | EngineOnly


def _validate_seat(seat: int) -> None:
    if seat < 0:
        raise ValueError(f"indeks miejsca nie może być ujemny: {seat}")


def _validate_amount(amount: int) -> None:
    if amount < 0:
        raise ValueError(f"kwota żetonów nie może być ujemna: {amount}")


def _validate_distinct(cards: tuple[Card, ...]) -> None:
    if len(set(cards)) != len(cards):
        raise ValueError("karty w zdarzeniu nie mogą się powtarzać")


@dataclass(frozen=True, slots=True)
class HandConfig:
    small_blind: int
    big_blind: int
    stacks: tuple[int, ...]
    button: int

    def __post_init__(self) -> None:
        if self.small_blind <= 0 or self.big_blind <= 0:
            raise ValueError("blindy muszą być dodatnie")
        if not self.stacks or any(stack < 0 for stack in self.stacks):
            raise ValueError("stacki muszą być niepustą krotką nieujemnych żetonów")
        if not 0 <= self.button < len(self.stacks):
            raise ValueError(f"button poza miejscami: {self.button}")


@dataclass(frozen=True, slots=True)
class HandStarted:
    config: HandConfig

    def visibility(self) -> EventVisibility:
        return Public()


@dataclass(frozen=True, slots=True)
class DeckSeeded:
    seed: int

    def visibility(self) -> EventVisibility:
        return EngineOnly()


@dataclass(frozen=True, slots=True)
class BlindPosted:
    seat: int
    blind: BlindType
    amount: int

    def __post_init__(self) -> None:
        _validate_seat(self.seat)
        _validate_amount(self.amount)

    def visibility(self) -> EventVisibility:
        return Public()


@dataclass(frozen=True, slots=True)
class HoleCardsDealt:
    seat: int
    cards: tuple[Card, Card]

    def __post_init__(self) -> None:
        _validate_seat(self.seat)
        _validate_distinct(self.cards)

    def visibility(self) -> EventVisibility:
        return PrivateToSeat(seat=self.seat)


@dataclass(frozen=True, slots=True)
class FlopDealt:
    cards: tuple[Card, Card, Card]

    def __post_init__(self) -> None:
        _validate_distinct(self.cards)

    def visibility(self) -> EventVisibility:
        return Public()


@dataclass(frozen=True, slots=True)
class TurnDealt:
    card: Card

    def visibility(self) -> EventVisibility:
        return Public()


@dataclass(frozen=True, slots=True)
class RiverDealt:
    card: Card

    def visibility(self) -> EventVisibility:
        return Public()


@dataclass(frozen=True, slots=True)
class ActionTaken:
    seat: int
    action: ActionType
    amount: int

    def __post_init__(self) -> None:
        _validate_seat(self.seat)
        _validate_amount(self.amount)

    def visibility(self) -> EventVisibility:
        return Public()


@dataclass(frozen=True, slots=True)
class CardsRevealed:
    seat: int
    cards: tuple[Card, Card]

    def __post_init__(self) -> None:
        _validate_seat(self.seat)
        _validate_distinct(self.cards)

    def visibility(self) -> EventVisibility:
        return Public()


@dataclass(frozen=True, slots=True)
class UncalledBetReturned:
    seat: int
    amount: int

    def __post_init__(self) -> None:
        _validate_seat(self.seat)
        _validate_amount(self.amount)

    def visibility(self) -> EventVisibility:
        return Public()


@dataclass(frozen=True, slots=True)
class PotAwarded:
    seat: int
    amount: int

    def __post_init__(self) -> None:
        _validate_seat(self.seat)
        _validate_amount(self.amount)

    def visibility(self) -> EventVisibility:
        return Public()


@dataclass(frozen=True, slots=True)
class HandEnded:
    def visibility(self) -> EventVisibility:
        return Public()


HandEvent = (
    HandStarted
    | DeckSeeded
    | BlindPosted
    | HoleCardsDealt
    | FlopDealt
    | TurnDealt
    | RiverDealt
    | ActionTaken
    | CardsRevealed
    | UncalledBetReturned
    | PotAwarded
    | HandEnded
)

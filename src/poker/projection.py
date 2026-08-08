"""Projekcja stanu stołu: czysta funkcja z sekwencji zdarzeń, bez własnej prawdy."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import Enum, unique

from poker.cards import Card
from poker.events import (
    ActionTaken,
    BlindPosted,
    CardsRevealed,
    DeckSeeded,
    FlopDealt,
    HandEnded,
    HandEvent,
    HandStarted,
    HoleCardsDealt,
    PotAwarded,
    RiverDealt,
    TurnDealt,
    UncalledBetReturned,
)


@unique
class Phase(Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    ENDED = "ended"


@dataclass(frozen=True, slots=True)
class TableState:
    stacks: tuple[int, ...]
    pot: int
    board: tuple[Card, ...]
    hole_cards: tuple[tuple[Card, ...] | None, ...]
    phase: Phase


def project(events: Iterable[HandEvent]) -> TableState:
    sequence = tuple(events)
    if not sequence or not isinstance(sequence[0], HandStarted):
        raise ValueError("projekcja wymaga zdarzenia startu rozdania na początku sekwencji")
    if any(isinstance(event, HandStarted) for event in sequence[1:]):
        raise ValueError("start rozdania może wystąpić wyłącznie jako pierwsze zdarzenie")

    config = sequence[0].config
    state = TableState(
        stacks=config.stacks,
        pot=0,
        board=(),
        hole_cards=(None,) * len(config.stacks),
        phase=Phase.PREFLOP,
    )
    for event in sequence[1:]:
        state = _apply(state, event)
    return state


def _apply(state: TableState, event: HandEvent) -> TableState:
    match event:
        case DeckSeeded():
            return state
        case BlindPosted(seat=seat, amount=amount) | ActionTaken(seat=seat, amount=amount):
            return replace(
                state, stacks=_move(state.stacks, seat, -amount), pot=state.pot + amount
            )
        case HoleCardsDealt(seat=seat, cards=cards):
            hole = list(state.hole_cards)
            hole[seat] = cards
            return replace(state, hole_cards=tuple(hole))
        case FlopDealt(cards=cards):
            return replace(state, board=state.board + cards, phase=Phase.FLOP)
        case TurnDealt(card=card):
            return replace(state, board=(*state.board, card), phase=Phase.TURN)
        case RiverDealt(card=card):
            return replace(state, board=(*state.board, card), phase=Phase.RIVER)
        case CardsRevealed():
            return replace(state, phase=Phase.SHOWDOWN)
        case PotAwarded(seat=seat, amount=amount) | UncalledBetReturned(seat=seat, amount=amount):
            return replace(
                state, stacks=_move(state.stacks, seat, amount), pot=state.pot - amount
            )
        case HandEnded():
            return replace(state, phase=Phase.ENDED)
        case _:
            raise ValueError(f"zdarzenie bez reguły projekcji: {type(event).__name__}")


def _move(stacks: tuple[int, ...], seat: int, delta: int) -> tuple[int, ...]:
    if not 0 <= seat < len(stacks):
        raise ValueError(f"zdarzenie wskazuje miejsce spoza stołu: {seat}")
    updated = list(stacks)
    updated[seat] += delta
    return tuple(updated)

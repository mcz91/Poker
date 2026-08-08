"""Widok gracza: wyłącznie informacje widoczne z danego miejsca (INV-P3)."""

from collections.abc import Sequence
from dataclasses import dataclass

from poker.betting import HeadsUpHand, LegalActions
from poker.cards import Card
from poker.events import (
    ActionTaken,
    BlindPosted,
    CardsRevealed,
    EngineOnly,
    HandEvent,
    HandStarted,
    HoleCardsDealt,
    PrivateToSeat,
    Public,
)
from poker.projection import Phase, project


def visible_events(events: Sequence[HandEvent], seat: int) -> tuple[HandEvent, ...]:
    visible: list[HandEvent] = []
    for event in events:
        match event.visibility():
            case Public():
                visible.append(event)
            case PrivateToSeat(seat=owner):
                if owner == seat:
                    visible.append(event)
            case EngineOnly():
                pass
    return tuple(visible)


@dataclass(frozen=True, slots=True)
class PlayerView:
    seat: int
    button: int
    small_blind: int
    big_blind: int
    hole_cards: tuple[Card, Card] | None
    board: tuple[Card, ...]
    stacks: tuple[int, ...]
    pot: int
    phase: Phase
    visible_actions: tuple[BlindPosted | ActionTaken, ...]
    revealed_cards: tuple[tuple[Card, Card] | None, ...]
    to_act: int | None
    legal_actions: LegalActions | None


def player_view(hand: HeadsUpHand, seat: int) -> PlayerView:
    events = hand.events()
    start = events[0]
    if not isinstance(start, HandStarted):
        raise ValueError("historia rozdania nie zaczyna się od startu")
    seat_count = len(start.config.stacks)
    if not 0 <= seat < seat_count:
        raise ValueError(f"widok wymaga miejsca przy stole, otrzymano {seat}")

    visible = visible_events(events, seat)
    state = project(visible)
    hole = next(
        (e.cards for e in visible if isinstance(e, HoleCardsDealt) and e.seat == seat), None
    )
    revealed: list[tuple[Card, Card] | None] = [None] * seat_count
    for event in visible:
        if isinstance(event, CardsRevealed):
            revealed[event.seat] = event.cards
    to_act = hand.to_act()
    legal = hand.legal_actions() if to_act == seat else None
    return PlayerView(
        seat=seat,
        button=start.config.button,
        small_blind=start.config.small_blind,
        big_blind=start.config.big_blind,
        hole_cards=hole,
        board=state.board,
        stacks=state.stacks,
        pot=state.pot,
        phase=state.phase,
        visible_actions=tuple(
            e for e in visible if isinstance(e, BlindPosted | ActionTaken)
        ),
        revealed_cards=tuple(revealed),
        to_act=to_act,
        legal_actions=legal,
    )

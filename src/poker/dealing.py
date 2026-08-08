"""Talia i rozdanie kart: deterministyczne z wstrzykniętego, seedowanego RNG."""

import random
from collections.abc import Sequence
from dataclasses import dataclass

from poker.cards import FULL_DECK, Card
from poker.events import FlopDealt, HoleCardsDealt, RiverDealt, TurnDealt

BOARD_SIZE = 5
HOLE_CARDS_PER_SEAT = 2


@dataclass(frozen=True, slots=True)
class DealtHand:
    hole_cards: tuple[HoleCardsDealt, ...]
    flop: FlopDealt
    turn: TurnDealt
    river: RiverDealt


def shuffled_deck(rng: random.Random) -> tuple[Card, ...]:
    # Iteracja po frozenset zależy od procesu; determinizm wymaga kanonicznej bazy.
    deck = sorted(FULL_DECK, key=lambda card: (card.rank.value, card.suit.value))
    rng.shuffle(deck)
    return tuple(deck)


def deal_hand(deck: Sequence[Card], seat_count: int) -> DealtHand:
    if seat_count < 2:
        raise ValueError(f"rozdanie wymaga co najmniej 2 miejsc, otrzymano {seat_count}")
    needed = HOLE_CARDS_PER_SEAT * seat_count + BOARD_SIZE
    if len(deck) < needed:
        raise ValueError(f"talia ma {len(deck)} kart, rozdanie wymaga {needed}")
    if len(set(deck)) != len(deck):
        raise ValueError("talia nie może zawierać powtórzonych kart")

    hole_cards = tuple(
        HoleCardsDealt(seat=seat, cards=(deck[seat], deck[seat_count + seat]))
        for seat in range(seat_count)
    )
    board = deck[HOLE_CARDS_PER_SEAT * seat_count : HOLE_CARDS_PER_SEAT * seat_count + BOARD_SIZE]
    return DealtHand(
        hole_cards=hole_cards,
        flop=FlopDealt(cards=(board[0], board[1], board[2])),
        turn=TurnDealt(card=board[3]),
        river=RiverDealt(card=board[4]),
    )

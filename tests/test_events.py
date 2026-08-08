"""Testy zdarzeń rozdania (POKER-3): konstrukcja, niemutowalność, widoczność."""

from dataclasses import FrozenInstanceError, fields

import pytest

from poker.cards import Card, Rank, Suit
from poker.events import (
    ActionTaken,
    ActionType,
    BlindPosted,
    BlindType,
    CardsRevealed,
    FlopDealt,
    HandConfig,
    HandEnded,
    HandEvent,
    HandStarted,
    HoleCardsDealt,
    PotAwarded,
    PrivateToSeat,
    Public,
    RiverDealt,
    TurnDealt,
    UncalledBetReturned,
)

AS, KS = Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES)
QH, JH = Card(Rank.QUEEN, Suit.HEARTS), Card(Rank.JACK, Suit.HEARTS)
FLOP = (Card(Rank.TWO, Suit.CLUBS), Card(Rank.SEVEN, Suit.DIAMONDS), Card(Rank.NINE, Suit.HEARTS))

CONFIG = HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0)

KATALOG_CYKLU: list[HandEvent] = [
    HandStarted(config=CONFIG, seed=7),
    BlindPosted(seat=0, blind=BlindType.SMALL, amount=1),
    BlindPosted(seat=1, blind=BlindType.BIG, amount=2),
    HoleCardsDealt(seat=0, cards=(AS, KS)),
    FlopDealt(cards=FLOP),
    TurnDealt(card=Card(Rank.FIVE, Suit.SPADES)),
    RiverDealt(card=Card(Rank.TEN, Suit.HEARTS)),
    ActionTaken(seat=1, action=ActionType.BET, amount=4),
    CardsRevealed(seat=0, cards=(AS, KS)),
    UncalledBetReturned(seat=0, amount=20),
    PotAwarded(seat=0, amount=12),
    HandEnded(),
]


@pytest.mark.parametrize("event", KATALOG_CYKLU, ids=[type(e).__name__ for e in KATALOG_CYKLU])
def test_zdarzenie_cyklu_daje_sie_skonstruowac_i_jest_niemutowalne(event: HandEvent) -> None:
    for field in fields(event):
        with pytest.raises(FrozenInstanceError):
            setattr(event, field.name, getattr(event, field.name))


def test_karty_wlasne_sa_prywatne_dla_miejsca() -> None:
    assert HoleCardsDealt(seat=1, cards=(QH, JH)).visibility() == PrivateToSeat(seat=1)


@pytest.mark.parametrize(
    "event",
    [e for e in KATALOG_CYKLU if not isinstance(e, HoleCardsDealt)],
    ids=[type(e).__name__ for e in KATALOG_CYKLU if not isinstance(e, HoleCardsDealt)],
)
def test_board_akcje_i_przebieg_sa_publiczne(event: HandEvent) -> None:
    assert event.visibility() == Public()


def test_konfiguracja_rozdania_waliduje_wejscie() -> None:
    with pytest.raises(ValueError, match="blind"):
        HandConfig(small_blind=0, big_blind=2, stacks=(100, 100), button=0)
    with pytest.raises(ValueError, match="stack"):
        HandConfig(small_blind=1, big_blind=2, stacks=(), button=0)
    with pytest.raises(ValueError, match="stack"):
        HandConfig(small_blind=1, big_blind=2, stacks=(100, -5), button=0)
    with pytest.raises(ValueError, match="button"):
        HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=2)


def test_zdarzenia_waliduja_miejsce_i_kwote() -> None:
    with pytest.raises(ValueError, match="miejsc"):
        BlindPosted(seat=-1, blind=BlindType.SMALL, amount=1)
    with pytest.raises(ValueError, match="kwot"):
        ActionTaken(seat=0, action=ActionType.BET, amount=-4)
    with pytest.raises(ValueError, match="kwot"):
        PotAwarded(seat=0, amount=-1)
    with pytest.raises(ValueError, match="kwot"):
        UncalledBetReturned(seat=0, amount=-1)


def test_zdarzenia_kart_wymagaja_roznych_kart() -> None:
    with pytest.raises(ValueError, match="powt"):
        HoleCardsDealt(seat=0, cards=(AS, AS))
    with pytest.raises(ValueError, match="powt"):
        FlopDealt(cards=(AS, AS, KS))

"""Testy projekcji stanu (POKER-3): replay, prefiksy, suma żetonów, fazy."""

import pytest

from poker.cards import Card, Rank, Suit
from poker.events import (
    ActionTaken,
    ActionType,
    BlindPosted,
    BlindType,
    CardsRevealed,
    DeckSeeded,
    FlopDealt,
    HandConfig,
    HandEnded,
    HandEvent,
    HandStarted,
    HoleCardsDealt,
    PotAwarded,
    RiverDealt,
    TurnDealt,
    UncalledBetReturned,
)
from poker.projection import Phase, TableState, project

AS, KS = Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.SPADES)
QH, JH = Card(Rank.QUEEN, Suit.HEARTS), Card(Rank.JACK, Suit.HEARTS)
FLOP = (Card(Rank.TWO, Suit.CLUBS), Card(Rank.SEVEN, Suit.DIAMONDS), Card(Rank.NINE, Suit.HEARTS))
TURN = Card(Rank.FIVE, Suit.SPADES)
RIVER = Card(Rank.TEN, Suit.HEARTS)

CONFIG = HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0)

HAND: list[HandEvent] = [
    HandStarted(config=CONFIG),
    BlindPosted(seat=0, blind=BlindType.SMALL, amount=1),
    BlindPosted(seat=1, blind=BlindType.BIG, amount=2),
    HoleCardsDealt(seat=0, cards=(AS, KS)),
    HoleCardsDealt(seat=1, cards=(QH, JH)),
    ActionTaken(seat=0, action=ActionType.CALL, amount=1),
    ActionTaken(seat=1, action=ActionType.CHECK, amount=0),
    FlopDealt(cards=FLOP),
    ActionTaken(seat=1, action=ActionType.BET, amount=4),
    ActionTaken(seat=0, action=ActionType.CALL, amount=4),
    TurnDealt(card=TURN),
    ActionTaken(seat=1, action=ActionType.CHECK, amount=0),
    ActionTaken(seat=0, action=ActionType.CHECK, amount=0),
    RiverDealt(card=RIVER),
    ActionTaken(seat=1, action=ActionType.CHECK, amount=0),
    ActionTaken(seat=0, action=ActionType.CHECK, amount=0),
    CardsRevealed(seat=0, cards=(AS, KS)),
    CardsRevealed(seat=1, cards=(QH, JH)),
    PotAwarded(seat=0, amount=12),
    HandEnded(),
]


def test_stan_koncowy_pelnego_rozdania() -> None:
    assert project(HAND) == TableState(
        stacks=(106, 94),
        pot=0,
        board=(*FLOP, TURN, RIVER),
        hole_cards=((AS, KS), (QH, JH)),
        phase=Phase.ENDED,
    )


def test_projekcja_prefiksu_daje_stan_posredni() -> None:
    assert project(HAND[:8]) == TableState(
        stacks=(98, 98),
        pot=4,
        board=FLOP,
        hole_cards=((AS, KS), (QH, JH)),
        phase=Phase.FLOP,
    )


def test_ta_sama_sekwencja_daje_identyczny_stan() -> None:
    assert project(HAND) == project(HAND)
    assert project(tuple(HAND)) == project(list(HAND))


def test_suma_zetonow_jest_stala_w_kazdym_prefiksie() -> None:
    total = sum(CONFIG.stacks)
    for length in range(1, len(HAND) + 1):
        state = project(HAND[:length])
        assert sum(state.stacks) + state.pot == total


def test_fazy_rozdania_postepuja_ze_zdarzeniami() -> None:
    assert project(HAND[:1]).phase is Phase.PREFLOP
    assert project(HAND[:8]).phase is Phase.FLOP
    assert project(HAND[:11]).phase is Phase.TURN
    assert project(HAND[:14]).phase is Phase.RIVER
    assert project(HAND[:17]).phase is Phase.SHOWDOWN
    assert project(HAND).phase is Phase.ENDED


def test_projekcja_wymaga_startu_rozdania_na_poczatku() -> None:
    with pytest.raises(ValueError, match="start"):
        project([])
    with pytest.raises(ValueError, match="start"):
        project([BlindPosted(seat=0, blind=BlindType.SMALL, amount=1)])
    with pytest.raises(ValueError, match="start"):
        project([HAND[0], HAND[0]])


def test_seed_talii_nie_zmienia_stanu_stolu() -> None:
    assert project([HAND[0], DeckSeeded(seed=7)]) == project([HAND[0]])


def test_zwrot_nadplaty_wraca_z_puli_do_stacka() -> None:
    events: list[HandEvent] = [
        HandStarted(config=CONFIG),
        BlindPosted(seat=0, blind=BlindType.SMALL, amount=1),
        BlindPosted(seat=1, blind=BlindType.BIG, amount=2),
        UncalledBetReturned(seat=1, amount=1),
        PotAwarded(seat=0, amount=2),
        HandEnded(),
    ]
    state = project(events)
    assert state.stacks == (101, 99)
    assert state.pot == 0


def test_trzy_miejsca_bez_zaszytej_dwojki() -> None:
    config = HandConfig(small_blind=1, big_blind=2, stacks=(50, 60, 70), button=2)
    events: list[HandEvent] = [
        HandStarted(config=config),
        BlindPosted(seat=0, blind=BlindType.SMALL, amount=1),
        BlindPosted(seat=1, blind=BlindType.BIG, amount=2),
        HoleCardsDealt(seat=2, cards=(AS, KS)),
        PotAwarded(seat=2, amount=3),
        HandEnded(),
    ]
    state = project(events)
    assert state.stacks == (49, 58, 73)
    assert state.hole_cards == (None, None, (AS, KS))
    assert state.pot == 0

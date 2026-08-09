"""Testy enkodowania przykładów (POKER-15): cechy z widoku decydującego, przeciek, wersja v1."""

import pytest

from poker.cards import Card, Rank, Suit
from poker.encoding import (
    DATASET_VERSION,
    FEATURE_NAMES,
    encode_hand,
)
from poker.events import (
    ActionTaken,
    ActionType,
    BlindPosted,
    BlindType,
    DeckSeeded,
    FlopDealt,
    HandConfig,
    HandEnded,
    HandEvent,
    HandStarted,
    HoleCardsDealt,
    PotAwarded,
)

AS, KH = Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)
QC, QD = Card(Rank.QUEEN, Suit.CLUBS), Card(Rank.QUEEN, Suit.DIAMONDS)
TWO_C, SEVEN_D = Card(Rank.TWO, Suit.CLUBS), Card(Rank.SEVEN, Suit.DIAMONDS)
FLOP = (
    Card(Rank.NINE, Suit.HEARTS),
    Card(Rank.FIVE, Suit.CLUBS),
    Card(Rank.THREE, Suit.DIAMONDS),
)
CONFIG = HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0)


def naglowek(
    seed: int, cards_1: tuple[Card, Card]
) -> tuple[HandEvent, ...]:
    return (
        HandStarted(config=CONFIG),
        DeckSeeded(seed=seed),
        BlindPosted(seat=0, blind=BlindType.SMALL, amount=1),
        BlindPosted(seat=1, blind=BlindType.BIG, amount=2),
        HoleCardsDealt(seat=0, cards=(AS, KH)),
        HoleCardsDealt(seat=1, cards=cards_1),
    )


def test_kazda_akcja_daje_przyklad_a_blindy_nie() -> None:
    history = (
        *naglowek(7, (TWO_C, SEVEN_D)),
        ActionTaken(seat=0, action=ActionType.CALL, amount=1),
        ActionTaken(seat=1, action=ActionType.CHECK, amount=0),
        FlopDealt(cards=FLOP),
        ActionTaken(seat=1, action=ActionType.BET, amount=2),
        ActionTaken(seat=0, action=ActionType.FOLD, amount=0),
        PotAwarded(seat=1, amount=6),
        HandEnded(),
    )
    examples = encode_hand(history)
    assert len(examples) == 4
    assert [example.action for example in examples] == [
        ActionType.CALL, ActionType.CHECK, ActionType.BET, ActionType.FOLD,
    ]
    assert [example.seat for example in examples] == [0, 1, 1, 0]


def test_cechy_v1_pierwszej_decyzji_preflop_przybite() -> None:
    history = (
        *naglowek(7, (TWO_C, SEVEN_D)),
        ActionTaken(seat=0, action=ActionType.CALL, amount=1),
        ActionTaken(seat=1, action=ActionType.CHECK, amount=0),
        PotAwarded(seat=1, amount=4),
        HandEnded(),
    )
    example = encode_hand(history)[0]
    assert len(FEATURE_NAMES) == len(example.features) == 23
    assert example.features[:21] == (
        1,          # is_button
        1, 2,       # blindy
        99, 98, 3,  # stack własny, przeciwnika, pula (po blindach)
        0,          # faza preflop
        14, 3,      # As
        13, 2,      # Kh
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # pusty board
    )
    assert example.seat == 0
    assert example.action is ActionType.CALL
    assert example.amount == 1


def test_cechy_decyzji_postflop_widza_board_i_pozycje() -> None:
    history = (
        *naglowek(7, (QC, QD)),
        ActionTaken(seat=0, action=ActionType.CALL, amount=1),
        ActionTaken(seat=1, action=ActionType.CHECK, amount=0),
        FlopDealt(cards=FLOP),
        ActionTaken(seat=1, action=ActionType.BET, amount=2),
        ActionTaken(seat=0, action=ActionType.FOLD, amount=0),
        PotAwarded(seat=1, amount=6),
        HandEnded(),
    )
    bet = encode_hand(history)[2]
    assert bet.seat == 1
    assert bet.action is ActionType.BET
    assert bet.amount == 2
    assert bet.features[:21] == (
        0,          # miejsce 1 bez buttona
        1, 2,
        98, 98, 4,
        1,          # flop
        12, 1,      # Qd (wyższy kolorem przy tej samej randze)
        12, 0,      # Qc
        9, 2, 5, 0, 3, 1, 0, 0, 0, 0,  # 9h 5c 3d + dwa puste sloty
    )


def test_przeciek_karty_przeciwnika_i_seed_nie_wplywaja_na_przyklady() -> None:
    fold_tylko_miejsca_0 = (
        ActionTaken(seat=0, action=ActionType.FOLD, amount=0),
        PotAwarded(seat=1, amount=3),
        HandEnded(),
    )
    first = encode_hand((*naglowek(7, (TWO_C, SEVEN_D)), *fold_tylko_miejsca_0))
    second = encode_hand((*naglowek(123456789, (QC, QD)), *fold_tylko_miejsca_0))
    assert first == second
    assert len(first) == 1


def test_wersja_zbioru_jest_jawna() -> None:
    assert DATASET_VERSION == 2
    assert len(FEATURE_NAMES) == 23
    assert FEATURE_NAMES[21] == "hole_equity_mille"
    assert FEATURE_NAMES[22] == "hand_category"


def test_cechy_v2_equity_preflop_i_sila_ukladu() -> None:
    from poker.evaluation import evaluate_best
    from poker.preflop import ALL_CLASSES, class_combos, classify
    from poker.preflop_equity import equity

    preflop_only = (
        *naglowek(7, (TWO_C, SEVEN_D)),
        ActionTaken(seat=0, action=ActionType.FOLD, amount=0),
        PotAwarded(seat=1, amount=3),
        HandEnded(),
    )
    example = encode_hand(preflop_only)[0]
    klasa = classify(AS, KH)
    oczekiwana_equity = round(
        1000 * sum(len(class_combos(inna)) * equity(klasa, inna) for inna in ALL_CLASSES) / 1326
    )
    assert example.features[21] == oczekiwana_equity
    assert example.features[22] == 0  # preflop: brak układu z boardu

    postflop = (
        *naglowek(7, (QC, QD)),
        ActionTaken(seat=0, action=ActionType.CALL, amount=1),
        ActionTaken(seat=1, action=ActionType.CHECK, amount=0),
        FlopDealt(cards=FLOP),
        ActionTaken(seat=1, action=ActionType.BET, amount=2),
        ActionTaken(seat=0, action=ActionType.FOLD, amount=0),
        PotAwarded(seat=1, amount=6),
        HandEnded(),
    )
    bet = encode_hand(postflop)[2]
    assert bet.features[21] == round(
        1000
        * sum(
            len(class_combos(inna)) * equity(classify(QC, QD), inna) for inna in ALL_CLASSES
        )
        / 1326
    )
    assert bet.features[22] == evaluate_best((QC, QD, *FLOP)).category.value


def test_decyzja_przed_kartami_wlasnymi_jest_bledem() -> None:
    history = (
        HandStarted(config=CONFIG),
        BlindPosted(seat=0, blind=BlindType.SMALL, amount=1),
        BlindPosted(seat=1, blind=BlindType.BIG, amount=2),
        ActionTaken(seat=0, action=ActionType.FOLD, amount=0),
    )
    with pytest.raises(ValueError, match="kart"):
        encode_hand(history)

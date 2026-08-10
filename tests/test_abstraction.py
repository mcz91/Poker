"""Testy abstrakcji (POKER-22): kubełki, akcje w obie strony, infoset, przeciek, złote przypadki."""

import pytest

from poker.abstraction import (
    ABSTRACTION_VERSION,
    AbstractAction,
    AbstractActionKind,
    AbstractionConfig,
    abstract_actions,
    decision_for,
    infoset,
    postflop_bucket,
    preflop_bucket,
)
from poker.betting import ActionBounds, HeadsUpHand, LegalActions
from poker.cards import Card, Rank, Suit
from poker.events import ActionTaken, ActionType, BlindPosted, BlindType, HandConfig
from poker.preflop import ALL_CLASSES, PreflopClass, classify
from poker.projection import Phase
from poker.views import PlayerView, player_view

AS, KH = Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)
AH, AD = Card(Rank.ACE, Suit.HEARTS), Card(Rank.ACE, Suit.DIAMONDS)
TWO_C, SEVEN_D = Card(Rank.TWO, Suit.CLUBS), Card(Rank.SEVEN, Suit.DIAMONDS)
FLOP = (
    Card(Rank.NINE, Suit.HEARTS),
    Card(Rank.FIVE, Suit.CLUBS),
    Card(Rank.THREE, Suit.DIAMONDS),
)
DOMYSLNA = AbstractionConfig()


def widok(
    hole: tuple[Card, Card],
    board: tuple[Card, ...],
    legal: LegalActions | None,
    visible: tuple[BlindPosted | ActionTaken, ...] = (),
    revealed: tuple[tuple[Card, Card] | None, ...] = (None, None),
    pot: int = 4,
) -> PlayerView:
    return PlayerView(
        seat=0,
        button=0,
        small_blind=1,
        big_blind=2,
        hole_cards=hole,
        board=board,
        stacks=(98, 98),
        pot=pot,
        phase=Phase.PREFLOP if not board else Phase.FLOP,
        visible_actions=visible,
        revealed_cards=revealed,
        to_act=0,
        legal_actions=legal,
    )


LEGAL_BET = LegalActions(
    seat=0, fold_allowed=True, check_allowed=True, call_amount=None,
    bet_range=ActionBounds(minimum=2, maximum=98), raise_range=None,
)
LEGAL_CALL_RAISE = LegalActions(
    seat=0, fold_allowed=True, check_allowed=False, call_amount=6,
    bet_range=None, raise_range=ActionBounds(minimum=12, maximum=98),
)
LEGAL_CALL_ONLY = LegalActions(
    seat=0, fold_allowed=True, check_allowed=False, call_amount=6,
    bet_range=None, raise_range=None,
)


def test_wersja_abstrakcji_i_kubelki_preflop_pokrywaja_169_klas() -> None:
    assert ABSTRACTION_VERSION == 1
    buckets = {preflop_bucket(cls, DOMYSLNA) for cls in ALL_CLASSES}
    assert buckets == set(range(DOMYSLNA.preflop_buckets))
    aa = PreflopClass(high=Rank.ACE, low=Rank.ACE, suited=False)
    assert preflop_bucket(aa, DOMYSLNA) == DOMYSLNA.preflop_buckets - 1  # AA najmocniejsze
    assert preflop_bucket(classify(TWO_C, SEVEN_D), DOMYSLNA) == 0  # 72o najsłabsze


def test_kubelki_postflop_deterministyczne_z_ewaluatora() -> None:
    para_asow = postflop_bucket((AS, AH), FLOP, DOMYSLNA)
    board_bez_pary = (FLOP[0], FLOP[1], Card(Rank.JACK, Suit.CLUBS))
    smieci = postflop_bucket((TWO_C, SEVEN_D), board_bez_pary, DOMYSLNA)
    assert 0 <= para_asow < DOMYSLNA.postflop_buckets
    assert 0 <= smieci < DOMYSLNA.postflop_buckets
    assert para_asow > smieci  # para asów w mocniejszym kubełku niż wysoka karta
    assert postflop_bucket((AS, AH), FLOP, DOMYSLNA) == para_asow  # determinizm


def test_zbior_akcji_abstrakcyjnych_i_mapowanie_na_legalne_decyzje() -> None:
    view = widok((AS, KH), (), LEGAL_BET)
    actions = abstract_actions(view, DOMYSLNA)
    kinds = {action.kind for action in actions}
    assert AbstractActionKind.FOLD in kinds
    assert AbstractActionKind.CHECK_CALL in kinds
    assert AbstractActionKind.BET in kinds
    assert AbstractActionKind.ALL_IN in kinds
    for action in actions:
        decision = decision_for(action, view)
        if decision.action in (ActionType.BET, ActionType.RAISE):
            assert 2 <= decision.amount <= 98
    all_in = decision_for(AbstractAction(kind=AbstractActionKind.ALL_IN), view)
    assert all_in.action is ActionType.BET
    assert all_in.amount == 98
    pol_puli = decision_for(
        AbstractAction(kind=AbstractActionKind.BET, size="half"), view
    )
    assert pol_puli.action is ActionType.BET
    assert pol_puli.amount == max(2, view.pot // 2)


def test_akcja_niedostepna_ma_deterministyczny_fallback() -> None:
    view = widok((AS, KH), (), LEGAL_CALL_ONLY)
    actions = abstract_actions(view, DOMYSLNA)
    assert {action.kind for action in actions} == {
        AbstractActionKind.FOLD, AbstractActionKind.CHECK_CALL,
    }
    bet = decision_for(AbstractAction(kind=AbstractActionKind.BET, size="pot"), view)
    assert bet.action is ActionType.CALL  # fallback: check-call


def test_wlasciwosciowy_na_widokach_realnych_rozdan() -> None:
    for seed in range(12):
        hand = HeadsUpHand(
            config=HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0),
            seed=seed,
        )
        licznik = 0
        while (seat := hand.to_act()) is not None:
            view = player_view(hand, seat)
            actions = abstract_actions(view, DOMYSLNA)
            assert actions, "zbiór akcji abstrakcyjnych musi być niepusty"
            wybrana = actions[licznik % len(actions)]
            decision = decision_for(wybrana, view)
            hand.act(seat, decision.action, decision.amount)  # maszyna przyjmuje
            licznik += 1


def test_infoset_stabilny_i_bez_informacji_niewidocznych() -> None:
    bez_showdownu = widok((AS, KH), (), LEGAL_CALL_RAISE)
    po_showdownie = widok(
        (AS, KH), (), LEGAL_CALL_RAISE, revealed=((None), (TWO_C, SEVEN_D)),
    )
    assert infoset(bez_showdownu, DOMYSLNA) == infoset(po_showdownie, DOMYSLNA)
    assert infoset(bez_showdownu, DOMYSLNA) == infoset(bez_showdownu, DOMYSLNA)


def test_infoset_identyczny_dla_roznych_seedow_przy_tych_samych_kartach() -> None:
    config = HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0)
    widoki: dict[PreflopClass, tuple[int, PlayerView]] = {}
    for seed in range(400):
        hand = HeadsUpHand(config=config, seed=seed)
        view = player_view(hand, 0)
        assert view.hole_cards is not None
        klasa = classify(*view.hole_cards)
        if klasa in widoki and widoki[klasa][0] != seed:
            inny_seed, inny_widok = widoki[klasa]
            assert infoset(view, DOMYSLNA) == infoset(inny_widok, DOMYSLNA), (
                f"seedy {inny_seed} i {seed}: ta sama klasa kart musi dać ten sam infoset"
            )
            return
        widoki[klasa] = (seed, view)
    pytest.fail("nie znaleziono pary seedów o tej samej klasie kart")


def test_zlote_przypadki_przybite_z_wersja() -> None:
    preflop = widok(
        (AS, KH), (), LEGAL_CALL_RAISE,
        visible=(
            BlindPosted(seat=0, blind=BlindType.SMALL, amount=1),
            BlindPosted(seat=1, blind=BlindType.BIG, amount=2),
            ActionTaken(seat=0, action=ActionType.CALL, amount=1),
            ActionTaken(seat=1, action=ActionType.RAISE, amount=6),
        ),
        pot=10,
    )
    postflop = widok((AS, AH), FLOP, LEGAL_BET)
    # AKo w kubełku 7/8 (top oktyl equity); podbicie 6 przy puli 4 sprzed akcji = "A"
    assert infoset(preflop, DOMYSLNA) == (
        f"a{ABSTRACTION_VERSION}|preflop|k7|btn|c.rA"
    )
    # para asów na flopie: kategoria ONE_PAIR -> kubełek 1/9
    assert infoset(postflop, DOMYSLNA) == f"a{ABSTRACTION_VERSION}|flop|k1|btn|"

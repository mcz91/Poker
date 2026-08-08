"""Testy maszyny licytacji heads-up (POKER-5): legalność, przebieg, rozliczenie."""

import pytest

from poker.betting import ActionBounds, HeadsUpHand, LegalActions, split_pot
from poker.cards import Card
from poker.evaluation import HandValue, evaluate_best
from poker.events import (
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
from poker.projection import project

CONFIG = HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0)


def nowa_reka(seed: int = 7, config: HandConfig = CONFIG) -> HeadsUpHand:
    return HeadsUpHand(config=config, seed=seed)


def dojdz_do_flopa(hand: HeadsUpHand) -> None:
    hand.act(0, ActionType.CALL)
    hand.act(1, ActionType.CHECK)


def rozegraj_checkami_do_konca(hand: HeadsUpHand) -> None:
    dojdz_do_flopa(hand)
    for _ in range(3):
        hand.act(1, ActionType.CHECK)
        hand.act(0, ActionType.CHECK)


def board_z(events: tuple[HandEvent, ...]) -> tuple[Card, ...]:
    flop = next(e for e in events if isinstance(e, FlopDealt))
    turn = next(e for e in events if isinstance(e, TurnDealt))
    river = next(e for e in events if isinstance(e, RiverDealt))
    return (*flop.cards, turn.card, river.card)


def karty_wlasne(events: tuple[HandEvent, ...]) -> dict[int, tuple[Card, Card]]:
    return {e.seat: e.cards for e in events if isinstance(e, HoleCardsDealt)}


def sily_na_showdownie(events: tuple[HandEvent, ...]) -> dict[int, HandValue]:
    board = board_z(events)
    return {
        seat: evaluate_best(cards + board) for seat, cards in karty_wlasne(events).items()
    }


def zetony_stale_w_kazdym_prefiksie(events: tuple[HandEvent, ...], total: int) -> None:
    for length in range(1, len(events) + 1):
        state = project(events[:length])
        assert sum(state.stacks) + state.pot == total
        assert all(isinstance(chips, int) for chips in (*state.stacks, state.pot))


def test_sekwencja_startowa_blindy_od_buttona_i_karty() -> None:
    events = nowa_reka().events()
    assert isinstance(events[0], HandStarted)
    assert events[1] == DeckSeeded(seed=7)
    assert events[2] == BlindPosted(seat=0, blind=BlindType.SMALL, amount=1)
    assert events[3] == BlindPosted(seat=1, blind=BlindType.BIG, amount=2)
    assert sorted(karty_wlasne(events)) == [0, 1]


def test_button_dziala_pierwszy_przed_flopem_i_ostatni_po_flopie() -> None:
    hand = nowa_reka()
    assert hand.to_act() == 0
    dojdz_do_flopa(hand)
    assert hand.to_act() == 1
    hand.act(1, ActionType.CHECK)
    assert hand.to_act() == 0


def test_granice_akcji_preflop_dla_buttona() -> None:
    legal = nowa_reka().legal_actions()
    assert legal is not None
    assert legal.seat == 0
    assert legal.fold_allowed
    assert not legal.check_allowed
    assert legal.call_amount == 1
    assert legal.bet_range is None
    assert legal.raise_range == ActionBounds(minimum=3, maximum=99)


def test_granice_akcji_na_flopie_i_po_zakladzie() -> None:
    hand = nowa_reka()
    dojdz_do_flopa(hand)
    otwarcie = hand.legal_actions()
    assert otwarcie is not None
    assert otwarcie.seat == 1
    assert otwarcie.check_allowed
    assert otwarcie.call_amount is None
    assert otwarcie.bet_range == ActionBounds(minimum=2, maximum=98)
    assert otwarcie.raise_range is None
    hand.act(1, ActionType.BET, 10)
    odpowiedz = hand.legal_actions()
    assert odpowiedz is not None
    assert odpowiedz.seat == 0
    assert odpowiedz.call_amount == 10
    assert odpowiedz.raise_range == ActionBounds(minimum=20, maximum=98)


def test_granice_akcji_na_turnie_i_riverze() -> None:
    hand = nowa_reka()
    dojdz_do_flopa(hand)
    hand.act(1, ActionType.CHECK)
    hand.act(0, ActionType.CHECK)
    assert hand.legal_actions() == LegalActions(
        seat=1,
        fold_allowed=True,
        check_allowed=True,
        call_amount=None,
        bet_range=ActionBounds(minimum=2, maximum=98),
        raise_range=None,
    )
    hand.act(1, ActionType.BET, 10)
    assert hand.legal_actions() == LegalActions(
        seat=0,
        fold_allowed=True,
        check_allowed=False,
        call_amount=10,
        bet_range=None,
        raise_range=ActionBounds(minimum=20, maximum=98),
    )
    hand.act(0, ActionType.CALL)
    assert hand.legal_actions() == LegalActions(
        seat=1,
        fold_allowed=True,
        check_allowed=True,
        call_amount=None,
        bet_range=ActionBounds(minimum=2, maximum=88),
        raise_range=None,
    )
    hand.act(1, ActionType.BET, 20)
    assert hand.legal_actions() == LegalActions(
        seat=0,
        fold_allowed=True,
        check_allowed=False,
        call_amount=20,
        bet_range=None,
        raise_range=ActionBounds(minimum=40, maximum=88),
    )


def test_big_blind_ma_opcje_check_albo_podbicie() -> None:
    hand = nowa_reka()
    hand.act(0, ActionType.CALL)
    legal = hand.legal_actions()
    assert legal is not None
    assert legal.seat == 1
    assert legal.check_allowed
    assert legal.call_amount is None
    assert legal.raise_range == ActionBounds(minimum=2, maximum=98)


def test_nielegalna_akcja_jest_bledem_bez_sladu_w_historii() -> None:
    hand = nowa_reka()
    before = hand.events()
    with pytest.raises(ValueError, match="ruchu"):
        hand.act(1, ActionType.CHECK)
    with pytest.raises(ValueError, match="check"):
        hand.act(0, ActionType.CHECK)
    with pytest.raises(ValueError, match="podbici"):
        hand.act(0, ActionType.RAISE, 2)
    with pytest.raises(ValueError, match="podbici"):
        hand.act(0, ActionType.RAISE, 100)
    with pytest.raises(ValueError, match="zakład"):
        hand.act(0, ActionType.BET, 10)
    assert hand.events() == before


def test_min_raise_jest_egzekwowany() -> None:
    hand = nowa_reka()
    hand.act(0, ActionType.RAISE, 3)
    assert project(hand.events()).pot == 6


def test_krotki_allin_nie_otwiera_licytacji_ponownie() -> None:
    hand = nowa_reka(config=HandConfig(small_blind=1, big_blind=2, stacks=(100, 5), button=0))
    hand.act(0, ActionType.RAISE, 3)
    krotki = hand.legal_actions()
    assert krotki is not None
    assert krotki.raise_range == ActionBounds(minimum=3, maximum=3)
    hand.act(1, ActionType.RAISE, 3)
    po_krotkim = hand.legal_actions()
    assert po_krotkim is not None
    assert po_krotkim.seat == 0
    assert po_krotkim.call_amount == 1
    assert po_krotkim.raise_range is None
    hand.act(0, ActionType.CALL)
    assert any(isinstance(e, HandEnded) for e in hand.events())


def test_allin_krotszego_stacka_wymusza_zwrot_nadplaty() -> None:
    hand = nowa_reka(config=HandConfig(small_blind=1, big_blind=2, stacks=(100, 30), button=0))
    hand.act(0, ActionType.RAISE, 49)
    hand.act(1, ActionType.CALL)
    events = hand.events()
    assert UncalledBetReturned(seat=0, amount=20) in events
    assert any(isinstance(e, CardsRevealed) for e in events)
    assert any(isinstance(e, HandEnded) for e in events)
    zetony_stale_w_kazdym_prefiksie(events, total=130)


def test_stack_krotszy_niz_blind_gra_o_pomniejszona_pule() -> None:
    hand = nowa_reka(config=HandConfig(small_blind=1, big_blind=2, stacks=(100, 1), button=0))
    events = hand.events()
    assert BlindPosted(seat=1, blind=BlindType.BIG, amount=1) in events
    assert hand.to_act() is None
    assert any(isinstance(e, CardsRevealed) for e in events)
    wygrane = [e.amount for e in events if isinstance(e, PotAwarded)]
    assert sum(wygrane) == 2
    zetony_stale_w_kazdym_prefiksie(events, total=101)


def test_fold_konczy_rozdanie_bez_showdownu() -> None:
    hand = nowa_reka()
    dojdz_do_flopa(hand)
    hand.act(1, ActionType.BET, 10)
    hand.act(0, ActionType.FOLD)
    events = hand.events()
    assert not any(isinstance(e, CardsRevealed) for e in events)
    assert PotAwarded(seat=1, amount=14) in events
    assert isinstance(events[-1], HandEnded)
    assert project(events).stacks == (98, 102)


def test_showdown_pokazuje_najpierw_agresora_z_rivera() -> None:
    hand = nowa_reka()
    dojdz_do_flopa(hand)
    hand.act(1, ActionType.CHECK)
    hand.act(0, ActionType.CHECK)
    hand.act(1, ActionType.CHECK)
    hand.act(0, ActionType.CHECK)
    hand.act(1, ActionType.CHECK)
    hand.act(0, ActionType.BET, 2)
    hand.act(1, ActionType.CALL)
    reveals = [e.seat for e in hand.events() if isinstance(e, CardsRevealed)]
    assert reveals == [0, 1]


def test_showdown_bez_zakladu_pokazuje_najpierw_miejsce_po_buttonie() -> None:
    hand = nowa_reka()
    rozegraj_checkami_do_konca(hand)
    reveals = [e.seat for e in hand.events() if isinstance(e, CardsRevealed)]
    assert reveals == [1, 0]


def test_wyrownany_river_prowadzi_do_showdownu_wedlug_ewaluatora() -> None:
    hand = nowa_reka()
    rozegraj_checkami_do_konca(hand)
    events = hand.events()
    sily = sily_na_showdownie(events)
    wygrane = {e.seat: e.amount for e in events if isinstance(e, PotAwarded)}
    if sily[0] == sily[1]:
        assert wygrane == {0: 2, 1: 2}
    else:
        zwyciezca = max(sily, key=lambda seat: sily[seat])
        assert wygrane == {zwyciezca: 4}
    zetony_stale_w_kazdym_prefiksie(events, total=200)


def test_split_pot_dzieli_pule_przy_rownej_sile() -> None:
    for seed in range(3000):
        hand = nowa_reka(seed=seed)
        rozegraj_checkami_do_konca(hand)
        events = hand.events()
        wygrane = [e for e in events if isinstance(e, PotAwarded)]
        if len(wygrane) == 2:
            sily = sily_na_showdownie(events)
            assert sily[0] == sily[1]
            assert sorted((e.seat, e.amount) for e in wygrane) == [(0, 2), (1, 2)]
            assert project(events).stacks == CONFIG.stacks
            return
    pytest.fail("w 3000 seedów nie znaleziono remisu — nieprawdopodobne")


def test_niepodzielna_reszta_trafia_kolejno_od_miejsca_po_buttonie() -> None:
    assert split_pot(7, [0, 1], button=0, seat_count=2) == ((1, 4), (0, 3))
    assert split_pot(7, [0, 1], button=1, seat_count=2) == ((0, 4), (1, 3))
    assert split_pot(10, [0, 1, 2], button=1, seat_count=3) == ((2, 4), (0, 3), (1, 3))
    assert split_pot(9, [1], button=0, seat_count=2) == ((1, 9),)


def test_suma_zetonow_stala_po_kazdym_zdarzeniu_rozdania_z_akcjami() -> None:
    hand = nowa_reka()
    dojdz_do_flopa(hand)
    hand.act(1, ActionType.BET, 10)
    hand.act(0, ActionType.RAISE, 30)
    hand.act(1, ActionType.CALL)
    hand.act(1, ActionType.CHECK)
    hand.act(0, ActionType.BET, 20)
    hand.act(1, ActionType.FOLD)
    zetony_stale_w_kazdym_prefiksie(hand.events(), total=200)


def test_maszyna_wymaga_dokladnie_dwoch_miejsc() -> None:
    config = HandConfig(small_blind=1, big_blind=2, stacks=(50, 60, 70), button=0)
    with pytest.raises(ValueError, match="2 miejsc"):
        HeadsUpHand(config=config, seed=7)

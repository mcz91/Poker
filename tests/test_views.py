"""Testy widoku gracza (POKER-6): filtr widoczności, szczelność informacji."""

from dataclasses import asdict
from typing import Any

import pytest

from poker.betting import HeadsUpHand
from poker.cards import Card
from poker.events import (
    ActionType,
    CardsRevealed,
    DeckSeeded,
    EngineOnly,
    HandConfig,
    HandEvent,
    HoleCardsDealt,
)
from poker.projection import Phase
from poker.views import PlayerView, player_view, visible_events

CONFIG = HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0)
SEED = 424242424242


def nowa_reka() -> HeadsUpHand:
    return HeadsUpHand(config=CONFIG, seed=SEED)


def karty_miejsca(events: tuple[HandEvent, ...], seat: int) -> tuple[Card, Card]:
    return next(e.cards for e in events if isinstance(e, HoleCardsDealt) and e.seat == seat)


def pary_rang_i_kolorow(value: Any) -> set[tuple[Any, Any]]:
    """Zbiera każdą parę (ranga, kolor) osiągalną w zserializowanym widoku."""
    found: set[tuple[Any, Any]] = set()
    if isinstance(value, dict):
        if set(value) == {"rank", "suit"}:
            found.add((value["rank"], value["suit"]))
        for nested in value.values():
            found |= pary_rang_i_kolorow(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found |= pary_rang_i_kolorow(nested)
    return found


def zadnych_przeciekow(view: PlayerView, cudze: tuple[Card, Card], seed: int) -> None:
    serialized = asdict(view)
    cards_in_view = pary_rang_i_kolorow(serialized)
    for card in cudze:
        assert (card.rank, card.suit) not in cards_in_view
        assert repr(card) not in repr(view)
    assert str(seed) not in repr(view)
    assert seed not in _liczby(serialized)


def _liczby(value: Any) -> set[int]:
    if isinstance(value, bool):
        return set()
    if isinstance(value, int):
        return {value}
    if isinstance(value, dict):
        return set().union(*(_liczby(v) for v in value.values()), set())
    if isinstance(value, (list, tuple)):
        return set().union(*(_liczby(v) for v in value), set())
    return set()


def test_filtr_nie_wydaje_seeda_zadnemu_miejscu() -> None:
    assert DeckSeeded(seed=7).visibility() == EngineOnly()
    events = nowa_reka().events()
    for seat in (0, 1):
        assert not any(isinstance(e, DeckSeeded) for e in visible_events(events, seat))


def test_filtr_wydaje_karty_wlasne_tylko_wlascicielowi() -> None:
    events = nowa_reka().events()
    for seat in (0, 1):
        visible = visible_events(events, seat)
        seats_of_holes = {e.seat for e in visible if isinstance(e, HoleCardsDealt)}
        assert seats_of_holes == {seat}


def test_widok_zawiera_stan_publiczny_i_wlasne_karty() -> None:
    hand = nowa_reka()
    hand.act(0, ActionType.CALL)
    view = player_view(hand, seat=1)
    events = hand.events()
    assert view.seat == 1
    assert view.button == 0
    assert (view.small_blind, view.big_blind) == (1, 2)
    assert view.hole_cards == karty_miejsca(events, 1)
    assert view.board == ()
    assert view.stacks == (98, 98)
    assert view.pot == 4
    assert view.phase is Phase.PREFLOP
    assert view.to_act == 1
    assert view.legal_actions is not None
    assert view.legal_actions.check_allowed
    widok_buttona = player_view(hand, seat=0)
    assert widok_buttona.legal_actions is None
    assert widok_buttona.hole_cards == karty_miejsca(events, 0)


def test_widok_nie_przecieka_kart_przeciwnika_ani_seeda_w_zadnej_fazie() -> None:
    hand = nowa_reka()
    events = hand.events()
    cudze = {0: karty_miejsca(events, 1), 1: karty_miejsca(events, 0)}

    def sprawdz_oba() -> None:
        for seat in (0, 1):
            zadnych_przeciekow(player_view(hand, seat), cudze[seat], SEED)

    sprawdz_oba()
    hand.act(0, ActionType.CALL)
    hand.act(1, ActionType.CHECK)
    sprawdz_oba()
    hand.act(1, ActionType.CHECK)
    hand.act(0, ActionType.BET, 10)
    sprawdz_oba()
    hand.act(1, ActionType.CALL)
    sprawdz_oba()
    hand.act(1, ActionType.CHECK)
    hand.act(0, ActionType.CHECK)
    sprawdz_oba()
    hand.act(1, ActionType.BET, 2)
    hand.act(0, ActionType.CALL)
    assert any(isinstance(e, CardsRevealed) for e in hand.events())
    for seat in (0, 1):
        view = player_view(hand, seat)
        assert str(SEED) not in repr(view)
        assert view.revealed_cards[1 - seat] == cudze[seat]


def test_karty_jawne_po_showdownie_sa_publiczne() -> None:
    hand = nowa_reka()
    hand.act(0, ActionType.CALL)
    hand.act(1, ActionType.CHECK)
    for _ in range(3):
        hand.act(1, ActionType.CHECK)
        hand.act(0, ActionType.CHECK)
    events = hand.events()
    for seat in (0, 1):
        view = player_view(hand, seat)
        assert view.phase is Phase.ENDED
        assert view.revealed_cards == (karty_miejsca(events, 0), karty_miejsca(events, 1))


def test_widok_wymaga_miejsca_przy_stole() -> None:
    with pytest.raises(ValueError, match="miejsc"):
        player_view(nowa_reka(), seat=2)

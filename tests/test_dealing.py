"""Testy talii i rozdania kart (POKER-3): determinizm z wstrzykniętego RNG."""

import random

import pytest

from poker.cards import FULL_DECK
from poker.dealing import deal_hand, shuffled_deck


def test_ten_sam_seed_daje_identyczna_talie() -> None:
    assert shuffled_deck(random.Random(42)) == shuffled_deck(random.Random(42))


def test_rozne_seedy_roznia_talie() -> None:
    assert shuffled_deck(random.Random(42)) != shuffled_deck(random.Random(43))


def test_talia_jest_permutacja_pelnej_talii() -> None:
    deck = shuffled_deck(random.Random(7))
    assert len(deck) == 52
    assert frozenset(deck) == FULL_DECK


def test_ten_sam_seed_daje_identyczne_zdarzenia_kart() -> None:
    first = deal_hand(shuffled_deck(random.Random(7)), seat_count=2)
    second = deal_hand(shuffled_deck(random.Random(7)), seat_count=2)
    assert first == second


def test_rozne_seedy_roznia_zdarzenia_kart() -> None:
    first = deal_hand(shuffled_deck(random.Random(7)), seat_count=2)
    second = deal_hand(shuffled_deck(random.Random(8)), seat_count=2)
    assert first != second


def test_rozdane_karty_sa_rozlaczne_i_pochodza_z_talii() -> None:
    deck = shuffled_deck(random.Random(7))
    dealt = deal_hand(deck, seat_count=2)
    cards = [card for event in dealt.hole_cards for card in event.cards]
    cards.extend(dealt.flop.cards)
    cards.append(dealt.turn.card)
    cards.append(dealt.river.card)
    assert len(cards) == 2 * 2 + 5
    assert len(set(cards)) == len(cards)
    assert set(cards) <= set(deck)


def test_rozdanie_dla_trzech_miejsc_bez_zaszytej_dwojki() -> None:
    dealt = deal_hand(shuffled_deck(random.Random(7)), seat_count=3)
    assert [event.seat for event in dealt.hole_cards] == [0, 1, 2]
    assert all(len(event.cards) == 2 for event in dealt.hole_cards)


def test_rozdanie_wymaga_wystarczajacej_talii() -> None:
    deck = shuffled_deck(random.Random(7))
    with pytest.raises(ValueError, match="tali"):
        deal_hand(deck[:8], seat_count=2)
    with pytest.raises(ValueError, match="miejsc"):
        deal_hand(deck, seat_count=1)

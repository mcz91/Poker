"""Testy kart (POKER-2): 52 unikatowe, niemutowalne, pełna talia."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from poker.cards import FULL_DECK, Card, Rank, Suit


def test_talia_to_dokladnie_52_unikatowe_karty() -> None:
    assert len(FULL_DECK) == 52
    assert FULL_DECK == frozenset(Card(rank, suit) for rank in Rank for suit in Suit)


def test_karta_jest_niemutowalna() -> None:
    card = Card(Rank.ACE, Suit.SPADES)
    with pytest.raises(FrozenInstanceError):
        card.rank = Rank.KING  # type: ignore[misc]


def test_karta_spoza_zbioru_jest_bledem() -> None:
    with pytest.raises(TypeError):
        Card(cast(Rank, 15), Suit.HEARTS)
    with pytest.raises(TypeError):
        Card(Rank.TWO, cast(Suit, "pik"))


def test_rowne_karty_sa_ta_sama_karta() -> None:
    assert Card(Rank.QUEEN, Suit.DIAMONDS) == Card(Rank.QUEEN, Suit.DIAMONDS)
    assert Card(Rank.QUEEN, Suit.DIAMONDS) != Card(Rank.QUEEN, Suit.CLUBS)

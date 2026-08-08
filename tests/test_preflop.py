"""Testy klas preflop (POKER-12): 169 klas kanonicznych, mapowanie kart, liczności kombinacji."""

import pytest

from poker.cards import Card, Rank, Suit
from poker.preflop import ALL_CLASSES, CLASS_INDEX, PreflopClass, class_combos, classify

AA = PreflopClass(high=Rank.ACE, low=Rank.ACE, suited=False)
AKS = PreflopClass(high=Rank.ACE, low=Rank.KING, suited=True)
AKO = PreflopClass(high=Rank.ACE, low=Rank.KING, suited=False)


def test_dokladnie_169_klas_w_trzech_rodzajach() -> None:
    assert len(ALL_CLASSES) == 169
    assert len(set(ALL_CLASSES)) == 169
    pary = [c for c in ALL_CLASSES if c.high == c.low]
    suited = [c for c in ALL_CLASSES if c.suited]
    offsuit = [c for c in ALL_CLASSES if c.high != c.low and not c.suited]
    assert len(pary) == 13
    assert len(suited) == 78
    assert len(offsuit) == 78


def test_licznosci_kombinacji_i_suma_1326() -> None:
    for cls in ALL_CLASSES:
        combos = class_combos(cls)
        expected = 6 if cls.high == cls.low else (4 if cls.suited else 12)
        assert len(combos) == expected
        assert len(set(combos)) == expected
        for combo in combos:
            assert classify(*combo) == cls
    assert sum(len(class_combos(cls)) for cls in ALL_CLASSES) == 1326


def test_mapowanie_kart_do_klasy_niezalezne_od_kolejnosci() -> None:
    as_, kh = Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)
    ks = Card(Rank.KING, Suit.SPADES)
    ah = Card(Rank.ACE, Suit.HEARTS)
    assert classify(as_, kh) == AKO
    assert classify(kh, as_) == AKO
    assert classify(as_, ks) == AKS
    assert classify(as_, ah) == AA
    assert ALL_CLASSES[CLASS_INDEX[AA]] == AA


def test_ta_sama_karta_dwa_razy_jest_bledem() -> None:
    karta = Card(Rank.QUEEN, Suit.DIAMONDS)
    with pytest.raises(ValueError, match="różnych kart"):
        classify(karta, karta)


def test_klasa_wymaga_kanonicznego_porzadku_rang() -> None:
    with pytest.raises(ValueError, match="wyższa"):
        PreflopClass(high=Rank.KING, low=Rank.ACE, suited=True)
    with pytest.raises(ValueError, match="para"):
        PreflopClass(high=Rank.ACE, low=Rank.ACE, suited=True)

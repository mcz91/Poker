"""Testy ewaluatora rąk (POKER-2): katalog kategorii, kickery, remisy, 5 z 6/7 kart."""

import random
from itertools import combinations, permutations

import pytest

from poker.cards import Card, Rank, Suit
from poker.evaluation import HandCategory, HandValue, evaluate_best, evaluate_five

C, D, H, S = Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES


def hand(*cards: tuple[Rank, Suit]) -> tuple[Card, ...]:
    return tuple(Card(rank, suit) for rank, suit in cards)


KATALOG: list[tuple[HandCategory, tuple[Card, ...]]] = [
    (
        HandCategory.HIGH_CARD,
        hand((Rank.ACE, S), (Rank.JACK, H), (Rank.NINE, D), (Rank.SEVEN, C), (Rank.FIVE, S)),
    ),
    (
        HandCategory.ONE_PAIR,
        hand((Rank.KING, S), (Rank.KING, H), (Rank.NINE, D), (Rank.SEVEN, C), (Rank.FIVE, S)),
    ),
    (
        HandCategory.TWO_PAIR,
        hand((Rank.KING, S), (Rank.KING, H), (Rank.NINE, D), (Rank.NINE, C), (Rank.FIVE, S)),
    ),
    (
        HandCategory.THREE_OF_A_KIND,
        hand((Rank.KING, S), (Rank.KING, H), (Rank.KING, D), (Rank.NINE, C), (Rank.FIVE, S)),
    ),
    (
        HandCategory.STRAIGHT,
        hand((Rank.NINE, S), (Rank.EIGHT, H), (Rank.SEVEN, D), (Rank.SIX, C), (Rank.FIVE, S)),
    ),
    (
        HandCategory.FLUSH,
        hand((Rank.ACE, H), (Rank.JACK, H), (Rank.NINE, H), (Rank.SEVEN, H), (Rank.FIVE, H)),
    ),
    (
        HandCategory.FULL_HOUSE,
        hand((Rank.KING, S), (Rank.KING, H), (Rank.KING, D), (Rank.NINE, C), (Rank.NINE, S)),
    ),
    (
        HandCategory.FOUR_OF_A_KIND,
        hand((Rank.KING, S), (Rank.KING, H), (Rank.KING, D), (Rank.KING, C), (Rank.FIVE, S)),
    ),
    (
        HandCategory.STRAIGHT_FLUSH,
        hand((Rank.NINE, H), (Rank.EIGHT, H), (Rank.SEVEN, H), (Rank.SIX, H), (Rank.FIVE, H)),
    ),
]


@pytest.mark.parametrize(("category", "cards"), KATALOG, ids=[c.name for c, _ in KATALOG])
def test_katalog_kategorii_przyklad_pozytywny(
    category: HandCategory, cards: tuple[Card, ...]
) -> None:
    assert evaluate_five(cards).category is category


def test_kategorie_tworza_scisly_porzadek_sil() -> None:
    values = [evaluate_five(cards) for _, cards in KATALOG]
    for weaker, stronger in zip(values, values[1:], strict=False):
        assert weaker < stronger


def test_kolo_a5_jest_najnizszym_stritem() -> None:
    wheel = hand((Rank.ACE, S), (Rank.TWO, H), (Rank.THREE, D), (Rank.FOUR, C), (Rank.FIVE, S))
    six_high = hand((Rank.SIX, S), (Rank.FIVE, H), (Rank.FOUR, D), (Rank.THREE, C), (Rank.TWO, S))
    assert evaluate_five(wheel) == HandValue(HandCategory.STRAIGHT, (5,))
    assert evaluate_five(wheel) < evaluate_five(six_high)


def test_strit_z_asem_na_gorze_jest_najwyzszy() -> None:
    broadway = hand(
        (Rank.ACE, S), (Rank.KING, H), (Rank.QUEEN, D), (Rank.JACK, C), (Rank.TEN, S)
    )
    king_high = hand(
        (Rank.KING, S), (Rank.QUEEN, H), (Rank.JACK, D), (Rank.TEN, C), (Rank.NINE, S)
    )
    assert evaluate_five(broadway) == HandValue(HandCategory.STRAIGHT, (14,))
    assert evaluate_five(king_high) < evaluate_five(broadway)


def test_kolor_bije_strit() -> None:
    flush = hand((Rank.SEVEN, H), (Rank.SIX, H), (Rank.FOUR, H), (Rank.THREE, H), (Rank.TWO, H))
    broadway = hand(
        (Rank.ACE, S), (Rank.KING, H), (Rank.QUEEN, D), (Rank.JACK, C), (Rank.TEN, S)
    )
    assert evaluate_five(broadway) < evaluate_five(flush)


def test_pelne_porownanie_po_kickerach() -> None:
    kicker_ten = hand(
        (Rank.KING, S), (Rank.KING, H), (Rank.ACE, D), (Rank.QUEEN, C), (Rank.TEN, S)
    )
    kicker_jack = hand(
        (Rank.KING, D), (Rank.KING, C), (Rank.ACE, S), (Rank.QUEEN, H), (Rank.JACK, D)
    )
    assert evaluate_five(kicker_ten) < evaluate_five(kicker_jack)


def test_identyczna_sila_w_roznych_kolorach_to_remis() -> None:
    hearts = hand((Rank.ACE, H), (Rank.JACK, H), (Rank.NINE, H), (Rank.SEVEN, H), (Rank.FIVE, H))
    spades = hand((Rank.ACE, S), (Rank.JACK, S), (Rank.NINE, S), (Rank.SEVEN, S), (Rank.FIVE, S))
    assert evaluate_five(hearts) == evaluate_five(spades)


def test_wynik_nie_zalezy_od_kolejnosci_kart() -> None:
    cards = hand((Rank.KING, S), (Rank.KING, H), (Rank.NINE, D), (Rank.NINE, C), (Rank.FIVE, S))
    expected = evaluate_five(cards)
    for permutation in permutations(cards):
        assert evaluate_five(permutation) == expected


def test_najlepszy_uklad_z_siedmiu_nie_zalezy_od_kolejnosci() -> None:
    seven = hand(
        (Rank.ACE, S),
        (Rank.KING, H),
        (Rank.QUEEN, H),
        (Rank.JACK, H),
        (Rank.TEN, H),
        (Rank.NINE, H),
        (Rank.NINE, S),
    )
    expected = evaluate_best(seven)
    rng = random.Random(7)
    shuffled = list(seven)
    for _ in range(20):
        rng.shuffle(shuffled)
        assert evaluate_best(tuple(shuffled)) == expected


def test_najlepszy_z_szesciu_kart() -> None:
    six = hand(
        (Rank.KING, S),
        (Rank.KING, H),
        (Rank.NINE, D),
        (Rank.NINE, C),
        (Rank.NINE, S),
        (Rank.FIVE, S),
    )
    assert evaluate_best(six) == HandValue(HandCategory.FULL_HOUSE, (9, 13))


def test_najlepszy_z_siedmiu_to_maksimum_nie_pierwszy_znaleziony() -> None:
    seven = hand(
        (Rank.NINE, S),
        (Rank.EIGHT, S),
        (Rank.SEVEN, S),
        (Rank.SIX, S),
        (Rank.FIVE, H),
        (Rank.FIVE, S),
        (Rank.FIVE, D),
    )
    best = evaluate_best(seven)
    assert best == HandValue(HandCategory.STRAIGHT_FLUSH, (9,))
    assert best == max(evaluate_five(combo) for combo in combinations(seven, 5))


def test_ewaluator_odrzuca_zly_rozmiar_i_duplikaty() -> None:
    four = hand((Rank.ACE, S), (Rank.KING, H), (Rank.QUEEN, D), (Rank.JACK, C))
    with pytest.raises(ValueError, match="5"):
        evaluate_five(four)
    with pytest.raises(ValueError, match="5"):
        evaluate_best(four)
    duplicated = hand(
        (Rank.ACE, S), (Rank.ACE, S), (Rank.QUEEN, D), (Rank.JACK, C), (Rank.TEN, H)
    )
    with pytest.raises(ValueError, match="powt"):
        evaluate_five(duplicated)

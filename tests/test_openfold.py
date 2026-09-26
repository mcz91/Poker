"""Open 2.2x tree: first-in is the product. 3bet in this tree is not shipped."""

from __future__ import annotations

from poker.openfold import N_HANDS, solve, threebet, threebet_vs_range
from poker.preflop import ALL_CLASSES
from poker.spin import PAYOUTS

JUNK_72O = next(
    i
    for i, cls in enumerate(ALL_CLASSES)
    if cls.high.name == "SEVEN" and cls.low.name == "TWO" and not cls.suited
)


def test_utg_otwiera_nie_shoveuje_na_25bb() -> None:
    hit = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=12)
    assert 12.0 <= hit.utg_open_pct <= 45.0
    assert hit.utg_jam_pct < hit.utg_open_pct * 0.25
    # Częstości z rozkładu strategii i próg testu, nie werdykt produkcyjny.
    assert hit.utg_open[0] + hit.utg_jam[0] > 0.85
    assert hit.utg_open[JUNK_72O] + hit.utg_jam[JUNK_72O] < 0.25


def test_10x_nie_wybucha_open() -> None:
    wta = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=10)
    icm = solve((50, 50, 50), PAYOUTS["10x"].prizes, button=1, iterations=10)
    assert icm.utg_open_pct <= wta.utg_open_pct


def test_threebet_ciasny_nie_artefakt() -> None:
    hit = threebet((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=12)
    assert 6.0 <= hit.btn_vs_open_pct <= 18.0
    assert hit.btn_vs_open[0] > 0.85
    assert hit.btn_vs_open[JUNK_72O] < 0.25
    tight = threebet((50, 50, 50), PAYOUTS["10x"].prizes, button=1, iterations=10)
    assert tight.btn_vs_open_pct <= hit.btn_vs_open_pct


def test_koniec_turnieju_nie_zalezy_od_numeracji_miejsc() -> None:
    """BTN all-in z samego SB odpada razem z przegranym all-in UTG–BB.

    Te same role i stacki (UTG, BTN, BB) = (89, 1, 60) pod dwiema numeracjami
    miejsc dają tę samą strategię, bo drugie miejsce bierze większy stack
    wejściowy, nie niższy indeks miejsca. Przed POKER-70 (finding I-21 audytu
    09-26) BB 3-betował tu szeroki open w 8,7% przy guziku 1 i w 39,7% przy
    guziku 2.
    """
    prizes = PAYOUTS["10x"].prizes
    first = solve((89, 1, 60), prizes, button=1, iterations=4)
    assert first == solve((60, 89, 1), prizes, button=2, iterations=4)
    wide = [1.0] * N_HANDS
    assert threebet_vs_range(wide, (89, 1, 60), prizes, button=1) == threebet_vs_range(
        wide, (60, 89, 1), prizes, button=2
    )

"""Open 2.2x tree: first-in is the product. 3bet in this tree is not shipped."""

from __future__ import annotations

import pytest

from poker.cards import Rank
from poker.openfold import N_HANDS, _sd, solve, threebet, threebet_vs_range
from poker.preflop import ALL_CLASSES, CLASS_INDEX, PreflopClass
from poker.spin import PAYOUTS

JUNK_72O = next(
    i
    for i, cls in enumerate(ALL_CLASSES)
    if cls.high.name == "SEVEN" and cls.low.name == "TWO" and not cls.suited
)
K2O = CLASS_INDEX[PreflopClass(Rank.KING, Rank.TWO, suited=False)]
J2O = CLASS_INDEX[PreflopClass(Rank.JACK, Rank.TWO, suited=False)]


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


def test_showdown_spasowany_bb_nie_odzyskuje_blinda() -> None:
    """UTG i BTN all-in (BTN z samym SB 1), BB pasuje blind 2, wygrywa BTN.

    Pula główna 3 dla BTN, drugi żeton blinda BB w side pocie, o który gra
    tylko UTG (finding B3 audytu 09-26). Ranga przegranego dla spasowanego
    dzieliła ten side pot: (49, 3, 49).
    """
    assert _sd((50, 1, 50), [50, 1, 2], (0, 1), 1) == (50, 3, 48)


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


def test_bb_odpadajacy_razem_z_btn_bierze_drugie_miejsce() -> None:
    """(UTG, BTN, BB) = (89, 1, 60): BTN ma tylko SB, więc gdy BB przegra all-in
    z pokrywającym go UTG, obaj kończą rękę bez żetonów (150, 0, 0), a drugie
    miejsce (2,0) bierze większy stack wejściowy — BB, nie podział (1,0).

    3-bet BB przeciw otwarciu 100% z kontynuacją 100%: fold daje ICM
    (92, 0, 58) = 4,32, wygrana ICM (29, 0, 121) = 6,84, więc próg equity to
    (4,32 − 2) / (6,84 − 2) ≈ 0,479; przy podziale byłby ≈ 0,568. K2o (equity
    0,504 wobec dowolnych dwóch) jamuje, J2o (0,445) folduje. W pełnym drzewie
    BB 3-betuje open w 47,63% (przy podziale 11,63%, przy ICM z indeksem
    sprzed POKER-70 5,55%).
    """
    prizes = PAYOUTS["10x"].prizes
    against_any = threebet_vs_range(
        [1.0] * N_HANDS, (89, 1, 60), prizes, button=1, continue_frac=1.0
    )
    assert against_any.bb_vs_open[K2O] == 1.0
    assert against_any.bb_vs_open[J2O] == 0.0
    tree = solve((89, 1, 60), prizes, button=1, iterations=4)
    assert tree.bb_vs_open_pct == pytest.approx(47.632, abs=1e-3)

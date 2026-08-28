"""Open 2.2x tree: first-in is the product. 3bet in this tree is not shipped."""

from __future__ import annotations

from poker.openfold import solve, threebet
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

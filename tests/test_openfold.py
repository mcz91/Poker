"""Open 2.2x tree: first-in is the product. 3bet in this tree is not shipped."""

from __future__ import annotations

from poker.openfold import solve
from poker.spin import PAYOUTS


def test_utg_otwiera_nie_shoveuje_na_25bb() -> None:
    hit = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=12)
    open_pct = float(hit["utg_open_pct"])
    jam_pct = float(hit["utg_jam_pct"])
    assert 12.0 <= open_pct <= 45.0
    assert jam_pct < open_pct * 0.25
    assert hit["aa_plays"]
    assert hit["junk_folds"]


def test_10x_nie_wybucha_open() -> None:
    wta = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=10)
    icm = solve((50, 50, 50), PAYOUTS["10x"].prizes, button=1, iterations=10)
    assert float(icm["utg_open_pct"]) < float(wta["utg_open_pct"]) + 8.0

"""ICM Malmuth–Harville: tożsamości i złote przypadki 3-max."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from poker.icm import chip_shares, icm_equities, place_probabilities, risk_premium, wta_equities


def test_rowne_stacki_wta_to_rowny_podzial() -> None:
    ev = icm_equities((25, 25, 25), (3.0, 0.0, 0.0))
    assert ev == pytest.approx((1.0, 1.0, 1.0))
    assert wta_equities((25, 25, 25), 3.0) == pytest.approx(ev)


def test_rowne_stacki_niewta_tez_rowny_podzial() -> None:
    ev = icm_equities((25, 25, 25), (50.0, 30.0, 20.0))
    assert ev == pytest.approx((100.0 / 3.0,) * 3)


def test_zlote_trzy_stacki_harville() -> None:
    ev = icm_equities((5000, 3000, 2000), (50.0, 30.0, 20.0))
    assert ev == pytest.approx((38.392857142857146, 32.75, 28.857142857142854))
    assert sum(ev) == pytest.approx(100.0)


def test_wta_rowna_udzialowi_zetonow() -> None:
    stacks = (40, 25, 10)
    ev = wta_equities(stacks, 3.0)
    assert ev == pytest.approx(tuple(3.0 * s / 75.0 for s in stacks))
    assert icm_equities(stacks, (3.0, 0.0, 0.0)) == pytest.approx(ev)
    assert risk_premium(stacks, (3.0, 0.0, 0.0)) == pytest.approx((0.0, 0.0, 0.0))


def test_zero_stack_bierze_ostatnie_miejsce() -> None:
    ev = icm_equities((50, 30, 0), (50.0, 30.0, 20.0))
    assert ev == pytest.approx((42.5, 37.5, 20.0))
    probs = place_probabilities((50, 30, 0))
    assert probs[2][2] == 1.0


def test_dwoch_graczy_symetrycznie() -> None:
    ev = icm_equities((100, 100), (70.0, 30.0))
    assert ev == pytest.approx((50.0, 50.0))


def test_chip_leader_ma_dodatnia_premie_gdy_placa_drugiego() -> None:
    premium = risk_premium((70, 20, 10), (8.0, 2.0, 0.0))
    assert premium[0] > 0
    assert premium[2] < 0
    assert sum(premium) == pytest.approx(0.0)


def test_odrzuca_ujemny_stack_i_rozjazd_nagrod() -> None:
    with pytest.raises(ValueError, match="ujemny"):
        icm_equities((10, -1, 5), (1.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="nagród"):
        icm_equities((10, 10), (1.0, 0.0, 0.0))


def test_chip_shares_sumuja_sie_do_jedynki() -> None:
    shares = chip_shares((15, 25, 35))
    assert sum(shares) == pytest.approx(1.0)


def test_icm_nie_importuje_silnika() -> None:
    path = Path(__file__).resolve().parent.parent / "src" / "poker" / "icm.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    assert not any(name.startswith("poker") for name in names)

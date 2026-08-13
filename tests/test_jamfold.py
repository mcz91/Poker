"""3-max jam/fold: próg calla i fictitious play na 25 bb."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from poker.jamfold import call_beats_fold, solve
from poker.preflop import ALL_CLASSES
from poker.spin import PAYOUTS


def test_call_beats_fold_wta_25bb() -> None:
    # BB fold vs UTG jam: 48/150 * 3 = 0.96; win 101/150*3; lose 0.
    fold_ev = 48 / 150 * 3
    win_ev = 101 / 150 * 3
    assert call_beats_fold(0.50, fold_ev, win_ev, 0.0)
    assert not call_beats_fold(0.40, fold_ev, win_ev, 0.0)


def test_call_beats_fold_odrzuca_equity_poza_zakresem() -> None:
    with pytest.raises(ValueError, match="equity"):
        call_beats_fold(1.1, 1.0, 2.0, 0.0)


def test_wta_25bb_aa_jamuje_72o_folduje() -> None:
    result = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=20)
    junk = next(
        i
        for i, cls in enumerate(ALL_CLASSES)
        if cls.high.name == "SEVEN" and cls.low.name == "TWO" and not cls.suited
    )
    assert result["aa_jams"] is True
    assert result["junk_folds"] is True
    assert result["utg_jam"][0] > 0.85
    assert result["utg_jam"][junk] < 0.25


def test_wta_25bb_zakresy_w_pasie_nash() -> None:
    result = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=20)
    utg = result["utg_jam_pct"]
    btn = result["btn_call_pct"]
    bb = result["bb_call_pct"]
    assert isinstance(utg, float) and isinstance(btn, float) and isinstance(bb, float)
    assert 10.0 <= utg <= 22.0
    assert 4.0 <= btn <= 14.0
    assert 5.0 <= bb <= 16.0
    assert btn < utg
    assert bb < utg


def test_icm_10x_zaciska_call_wzgledem_wta() -> None:
    wta = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=20)
    icm = solve((50, 50, 50), PAYOUTS["10x"].prizes, button=1, iterations=20)
    assert icm["btn_call_pct"] < wta["btn_call_pct"]
    assert icm["bb_call_pct"] < wta["bb_call_pct"]


def test_solve_jest_deterministyczny() -> None:
    a = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=8)
    b = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=8)
    assert a["utg_jam"] == b["utg_jam"]
    assert a["btn_call"] == b["btn_call"]


def test_jamfold_importuje_tylko_icm_spin_preflop() -> None:
    path = Path(__file__).resolve().parent.parent / "src" / "poker" / "jamfold.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
    poker = {name for name in names if name.startswith("poker")}
    assert poker <= {
        "poker.icm",
        "poker.preflop",
        "poker.preflop_equity",
        "poker.spin",
    }
    assert "poker.betting" not in poker
    assert "poker.table" not in poker
    assert "poker.strategy_table" not in poker

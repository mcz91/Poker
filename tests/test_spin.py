"""Spin 3-max: role, side pot all-in, EV shove UTG."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from poker.spin import (
    BIG_BLIND,
    PAYOUTS,
    SMALL_BLIND,
    STARTING_CHIPS,
    award_allin,
    post_blinds,
    roles,
    utg_shove_both_fold,
    utg_shove_called,
    utg_shove_ev,
)


def test_role_button_jeden() -> None:
    utg, btn, bb = roles(1)
    assert (utg, btn, bb) == (0, 1, 2)


def test_post_blinds_25bb() -> None:
    behind, pot = post_blinds((STARTING_CHIPS,) * 3, 1)
    assert pot == SMALL_BLIND + BIG_BLIND
    assert behind == (50, 49, 48)


def test_award_rowny_trzy_way() -> None:
    assert award_allin((10, 10, 10), (0, 1, 2)) == (30, 0, 0)


def test_award_side_pot_krotki_wygrywa() -> None:
    assert award_allin((5, 10, 10), (0, 1, 2)) == (15, 10, 0)


def test_award_side_pot_krotki_przegrywa() -> None:
    assert award_allin((5, 10, 10), (2, 0, 1)) == (0, 25, 0)


def test_award_zwrot_nadplaty() -> None:
    assert award_allin((20, 10, 0), (0, 1, 2)) == (30, 0, 0)


def test_utg_shove_obie_fold_zabiera_blindy() -> None:
    assert utg_shove_both_fold((50, 50, 50), 1) == (53, 49, 48)


def test_utg_shove_bb_wola_rowne_stacki() -> None:
    win = utg_shove_called((50, 50, 50), 1, caller=2, winner=0)
    lose = utg_shove_called((50, 50, 50), 1, caller=2, winner=2)
    assert win == (101, 49, 0)
    assert lose == (0, 49, 101)


def test_wta_shove_fold_jest_dodatnie() -> None:
    fold, shove_fold, _ = utg_shove_ev(
        (50, 50, 50),
        1,
        PAYOUTS["3x"].prizes,
        caller=2,
        equity=0.5,
    )
    assert shove_fold > fold


def test_icm_10x_zmienia_ev_wzgledem_wta() -> None:
    stacks = (70, 20, 10)
    wta = utg_shove_ev(stacks, 1, PAYOUTS["3x"].prizes, caller=2, equity=0.5)
    icm = utg_shove_ev(stacks, 1, PAYOUTS["10x"].prizes, caller=2, equity=0.5)
    assert wta != icm


def test_spin_importuje_wylacznie_icm() -> None:
    path = Path(__file__).resolve().parent.parent / "src" / "poker" / "spin.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
    poker = {name for name in names if name.startswith("poker")}
    assert poker <= {"poker.icm"}

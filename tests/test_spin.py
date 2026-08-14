"""Spin 3-max: role, side pot all-in, EV shove UTG."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from poker.spin import (
    BIG_BLIND,
    HANDS_PER_LEVEL,
    JAM_FOLD_BB,
    PAYOUTS,
    SMALL_BLIND,
    STARTING_CHIPS,
    award_allin,
    blinds_for_hand,
    effective_bb,
    is_jam_fold_depth,
    open_amount,
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


def test_zegar_eskaluje_co_trzy_rece() -> None:
    assert HANDS_PER_LEVEL == 3
    assert blinds_for_hand(0) == (1, 2, 0)
    assert blinds_for_hand(2) == (1, 2, 0)
    assert blinds_for_hand(3) == (2, 4, 1)
    assert blinds_for_hand(20)[0] == 10
    with pytest.raises(ValueError, match="ujemny"):
        blinds_for_hand(-1)


def test_push_fold_dopiero_przy_siedmiu_bb() -> None:
    assert JAM_FOLD_BB == 7
    assert open_amount(2) == 4
    assert not is_jam_fold_depth((50, 50, 50), 2)
    assert not is_jam_fold_depth((50, 50, 50), 6)
    assert is_jam_fold_depth((50, 50, 50), 8)
    assert is_jam_fold_depth((14, 50, 50), 2)
    assert effective_bb((50, 50, 50), 2) == 25.0
    assert effective_bb((50, 50, 50), 8) == 6.25


def test_post_blinds_poziom_dwa() -> None:
    behind, pot = post_blinds((50, 50, 50), 1, 2, 4)
    assert pot == 6
    assert behind == (50, 48, 46)


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

"""Reguła miejsc Spin (POKER-70): arena i modele końca gry dzielą jedną funkcję.

Kotwica krzyżowa porównuje ją z regułą solvera (`tools/blueprint/solve_grid.py`,
`_game_over_payout`), ładowaną przez importlib jak w testach pilota.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from poker.icm import icm_equities
from poker.spin import PAYOUTS, place_payouts, terminal_equities

BLUEPRINT = Path(__file__).resolve().parent.parent / "tools" / "blueprint"
TEN = PAYOUTS["10x"].prizes


def _load(name: str) -> Any:
    """Ładuje moduł z tools/blueprint pod nazwą stem — jak testy pilota."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_pozniej_wybity_wyzej_niezaleznie_od_stacku_wejsciowego() -> None:
    assert place_payouts((0, 0, 150), ((0, 50), (2, 47), None), TEN) == (0.0, 2.0, 8.0)
    assert place_payouts((0, 0, 150), ((7, 3), (2, 90), None), TEN) == (2.0, 0.0, 8.0)


def test_w_jednej_rece_wyzej_wiekszy_stack_wejsciowy() -> None:
    assert place_payouts((0, 0, 150), ((19, 12), (19, 66), None), TEN) == (0.0, 2.0, 8.0)
    assert place_payouts((150, 0, 0), (None, (4, 66), (4, 12)), TEN) == (8.0, 2.0, 0.0)


def test_rowne_stacki_wejsciowe_jednej_reki_dziela_nagrody() -> None:
    assert place_payouts((0, 0, 150), ((0, 50), (0, 50), None), TEN) == (1.0, 1.0, 8.0)
    assert place_payouts((0, 150, 0), ((3, 20), None, (3, 20)), (7.0, 2.0, 1.0)) == (
        1.5,
        7.0,
        1.5,
    )


def test_zywi_wyzej_od_wybitych_i_szeregowani_stackiem_koncowym() -> None:
    """Koniec limitem rąk: żywi stackiem końcowym, remis stacków — niższy indeks."""
    assert place_payouts((60, 40, 50), (None, None, None), TEN) == (8.0, 0.0, 2.0)
    assert place_payouts((100, 0, 50), (None, (40, 3), None), TEN) == (8.0, 0.0, 2.0)
    assert place_payouts((5, 140, 5), (None, None, None), TEN) == (2.0, 8.0, 0.0)


@pytest.mark.parametrize(
    ("stacks", "busts"),
    [
        ((0, 0, 150), ((0, 50), None, None)),
        ((0, 10, 140), ((0, 50), (1, 20), None)),
    ],
)
def test_wybicie_ma_dokladnie_kazde_miejsce_bez_zetonow(
    stacks: tuple[int, int, int],
    busts: tuple[tuple[int, int] | None, tuple[int, int] | None, tuple[int, int] | None],
) -> None:
    with pytest.raises(ValueError, match="wybicie ma dokładnie każde miejsce bez żetonów"):
        place_payouts(stacks, busts, TEN)


def test_stan_z_dwoma_zywymi_wyceniany_icm() -> None:
    for after in ((0, 100, 50), (30, 60, 60), (149, 1, 0)):
        assert terminal_equities((50, 50, 50), after, TEN) == icm_equities(after, TEN)


def test_miejsce_puste_na_wejsciu_konczy_ponizej_wybitego_w_rece() -> None:
    assert terminal_equities((0, 1, 149), (0, 0, 150), TEN) == (0.0, 2.0, 8.0)
    assert terminal_equities((149, 1, 0), (150, 0, 0), TEN) == (8.0, 2.0, 0.0)


@pytest.mark.parametrize("pay", ["10x", "3x"])
def test_kotwica_krzyzowa_z_regula_solvera(pay: str) -> None:
    """Każde wejście o sumie 150 (krok 1, co najmniej dwaj żywi) i każdy żywy
    jako jedyny ocalały: reguła `poker.spin` = `_game_over_payout` solvera, co do bitu."""
    game_over_payout = _load("solve_grid")._game_over_payout
    prizes = PAYOUTS[pay].prizes
    cases = 0
    for a in range(151):
        for b in range(151 - a):
            entering = (a, b, 150 - a - b)
            alive = [seat for seat in range(3) if entering[seat] > 0]
            if len(alive) < 2:
                continue
            for survivor in alive:
                after = [0, 0, 0]
                after[survivor] = 150
                after_t = (after[0], after[1], after[2])
                expected = tuple(game_over_payout(entering, after_t, prizes).tolist())
                assert terminal_equities(entering, after_t, prizes) == expected, entering
                cases += 1
    assert cases == 33_972

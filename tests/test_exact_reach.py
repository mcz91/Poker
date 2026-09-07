"""Testy łańcucha dokładnego vs treningowego (POKER-58)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BLUEPRINT = REPO / "tools" / "blueprint"


def _load(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _tiny() -> Any:
    """Siatka ręcznie policzalna: 6 żetonów, krok 2, start na siatce, 2 ręce."""
    solve_grid = _load("solve_grid")
    return solve_grid.GridConfig(
        prizes=(1.0, 0.0, 0.0),
        levels=((1, 1),),
        hands_per_level=2,
        total_chips=6,
        start_stacks=(2, 2, 2),
        grid_step=2,
    )


def test_kwantyzacja_na_siatce_jest_identycznoscia() -> None:
    solve_grid = _load("solve_grid")
    assert solve_grid.quantize_stacks((2, 2, 2), 2) == (2, 2, 2)
    out = solve_grid.quantize_stacks((3, 2, 1), 2)
    assert sum(out) == 6
    assert all(value % 2 == 0 for value in out)
    assert all(value >= 0 for value in out)


def test_start_na_siatce_daje_ten_sam_klucz_w_obu_lancuchach() -> None:
    reach = _load("exact_reach")
    config = _tiny()
    exact = reach.exact_layers(config, through_hand=0)
    trained = reach.quantized_layers(config, through_hand=0)
    assert exact[0] == ((2, 2, 2),)
    assert trained[0] == ((2, 2, 2),)


def test_lancuch_dokladny_po_jednej_rece_ma_stany_poza_krokiem() -> None:
    reach = _load("exact_reach")
    config = _tiny()
    exact = reach.exact_layers(config, through_hand=1)
    assert exact[1], "drzewo z (2,2,2) musi mieć przynajmniej jeden stan kontynuacji"
    off_grid = [state for state in exact[1] if any(chip % 2 for chip in state)]
    assert off_grid, (
        "łańcuch dokładny ma trzymać reszty z licytacji — inaczej nie różni się "
        "od treningu i nie tłumaczy fallbacku areny"
    )
    keys = set(reach.grid_keys(exact[1], 2))
    assert keys
    assert all(sum(key) == 6 and all(chip % 2 == 0 for chip in key) for key in keys)


def test_luka_na_starcie_jest_pusta_a_raport_niesie_wycene() -> None:
    reach = _load("exact_reach")
    config = _tiny()
    report = reach.difference_report(config, through_hand=1)
    assert report["per_hand"][0]["missing_keys"] == 0
    assert report["per_hand"][0]["exact_keys"] == 1
    assert "missing_core_hours" in report
    assert report["cost_stop_core_hours"] == reach.COST_STOP_CORE_HOURS
    assert report["stop"] is False
    assert report["missing_states"] == sum(
        row["missing_keys"] for row in report["per_hand"]
    )


def test_bezpiecznik_kosztu_nie_zgaduje_progu() -> None:
    reach = _load("exact_reach")
    assert reach.COST_STOP_CORE_HOURS == 15.0

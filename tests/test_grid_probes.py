"""Sonda P-6(a): krok siatki vs tryb drzewa (POKER-60 plaster 1)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tools" / "blueprint" / "grid_probes.py"


def _load():
    name = "grid_probes"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_regula_czytania_prerejestrowana() -> None:
    probes = _load()
    assert probes.IMPORT_TRIGGER == 5e-4
    assert probes.reading_rule(5e-4, 0)["step1"] == "NIE"
    assert probes.reading_rule(5e-4 + 1e-12, 0)["step1"] == "TAK"
    assert probes.reading_rule(0.0, 1)["step1"] == "TAK"


def test_off_grid_wymaga_dwoch_skladowych_poza_krokiem() -> None:
    probes = _load()
    assert probes.off_grid_state((51, 49, 50), 2)
    assert not probes.off_grid_state((50, 50, 50), 2)
    assert not probes.off_grid_state((52, 50, 48), 2)


def test_quantize_przestawia_prog_jamfold() -> None:
    probes = _load()
    spec = importlib.util.spec_from_file_location(
        "solve_grid", REPO / "tools" / "blueprint" / "solve_grid.py"
    )
    assert spec is not None and spec.loader is not None
    if "solve_grid" not in sys.modules:
        module = importlib.util.module_from_spec(spec)
        sys.modules["solve_grid"] = module
        spec.loader.exec_module(module)
    sg = sys.modules["solve_grid"]
    exact = (85, 50, 15)
    neighbor = sg.quantize_stacks(exact, 2)
    assert neighbor == (86, 50, 14)
    assert probes.mode_flip(exact, neighbor, bb=2)
    assert not probes.is_jam_fold_depth(exact, 2)
    assert probes.is_jam_fold_depth(neighbor, 2)


def test_spis_flipow_cli() -> None:
    raw = subprocess.check_output(
        [sys.executable, str(SCRIPT), "--n", "40", "--seed", "60", "--step", "2"],
        cwd=REPO,
        text=True,
    )
    report = json.loads(raw)
    assert report["n"] == 40
    assert "flips" in report
    assert report["reading"]["threshold"] == 5e-4
    assert report["reading"]["step1"] in {"TAK", "NIE"}

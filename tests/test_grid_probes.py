"""Sonda P-6(a): krok siatki vs tryb drzewa i ε importu (POKER-60)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tools" / "blueprint" / "grid_probes.py"
TENSOR = REPO / "tools" / "blueprint" / "control" / "tensor"


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


def test_import_flip_ma_eps_none() -> None:
    probes = _load()
    sg_spec = importlib.util.spec_from_file_location(
        "solve_grid", REPO / "tools" / "blueprint" / "solve_grid.py"
    )
    assert sg_spec is not None and sg_spec.loader is not None
    if "solve_grid" not in sys.modules:
        module = importlib.util.module_from_spec(sg_spec)
        sys.modules["solve_grid"] = module
        sg_spec.loader.exec_module(module)
    cc_spec = importlib.util.spec_from_file_location(
        "control_chain", REPO / "tools" / "blueprint" / "control_chain.py"
    )
    assert cc_spec is not None and cc_spec.loader is not None
    if "control_chain" not in sys.modules:
        module = importlib.util.module_from_spec(cc_spec)
        sys.modules["control_chain"] = module
        cc_spec.loader.exec_module(module)
    sg = sys.modules["solve_grid"]
    cc = sys.modules["control_chain"]
    config = cc.control_config(jobs=1)
    tensors = sg.load_tensors(TENSOR, config.classes)
    row = probes.import_gap(tensors, config, (85, 50, 15), 0, (1, 2))
    assert row["flipped"]
    assert row["import_eps"] is None
    assert row["triggers_step1"]


def test_import_na_kontroli_nie_wywraca_sie() -> None:
    probes = _load()
    report = probes.measure_import(
        TENSOR, n=1, seed=60, hand=0, blinds=(1, 2), jobs=1
    )
    assert report["n"] == 1
    assert report["reading"]["threshold"] == 5e-4
    assert report["v_next"] == "icm-quantized"
    row = report["rows"][0]
    assert list(row["exact"]) != list(row["grid"])
    assert "triggers_step1" in row

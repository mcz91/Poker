"""Spike POKER-68: call w slocie 3, drzewo solvera zamrożone."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tools" / "blueprint" / "tree_spike.py"


def _load():
    name = "tree_spike"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_slot_call_to_dopelnienie_v2() -> None:
    from poker.blueprint_reader import DERIVED_SLOT_V2, N_SLOTS_V2

    spike = _load()
    assert spike.SLOT_CALL == DERIVED_SLOT_V2 == 3
    assert N_SLOTS_V2 == 4


def test_liczby_lisci_i_koszt() -> None:
    payload = _load().report()
    assert payload["current_leaves_3"] == 17
    assert payload["proposed_leaves_3"] == 23
    assert payload["proposed_leaves_hu"] == 7
    assert payload["squeeze_leaves"] == 4
    assert payload["ok_ratio"]
    assert payload["ok_payload"]
    assert payload["wired"] is False
    assert payload["solver_leaves_3"] == 17
    assert payload["ok_frozen"]


def test_cli_exit_0() -> None:
    raw = subprocess.check_output([sys.executable, str(SCRIPT)], cwd=REPO, text=True)
    payload = json.loads(raw)
    assert payload["fidelity"] == 0
    assert payload["deep_cost"] == 1.6

"""Spike gałęzi call — POKER-68, decyzja 31. Nie zmienia drzewa solvera.

Call = slot 3 (dopełnienie v2). First-in bez limpa. Wierność 0: liść
call to checkdown (`sd`). Squeeze = T call UTG, potem BB.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from poker.blueprint_reader import DERIVED_SLOT_V2, N_SLOTS_V2

SLOT_CALL = 3
CURRENT_LEAVES_3 = 17
CURRENT_LEAVES_HU = 6
PROD_CLASSES = 169
PAYLOAD_CAP = 80 * 1024 * 1024
LEAF_RATIO_LO = 1.30
LEAF_RATIO_HI = 1.45
DEEP_COST = 1.6

# +6 liści 3-max. Kolejność = dokument decyzji 31.
EXTRA_3 = (
    ("B_call_T_open", "sd2"),
    ("B_call_U_open_T_fold", "sd2"),
    ("T_call_U_open_B_fold", "sd2"),
    ("T_call_U_open_B_call", "sd3"),
    ("T_call_U_open_B_jam_U_fold", "fold"),
    ("T_call_U_open_B_jam_U_call", "sd2"),
)
EXTRA_HU = (("B_call_N_open", "sd2"),)
SQUEEZE = frozenset(name for name, _kind in EXTRA_3 if name.startswith("T_call_"))


def _sibling(name: str) -> ModuleType:
    module = sys.modules.get(name)
    if module is not None:
        return module
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"brak {name}")
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def extra_3way_bytes(n_classes: int = PROD_CLASSES) -> int:
    n_sd3 = sum(1 for _name, kind in EXTRA_3 if kind == "sd3")
    return n_sd3 * (n_classes**3) * 3 * 4


def report() -> dict[str, object]:
    proposed_3 = CURRENT_LEAVES_3 + len(EXTRA_3)
    proposed_hu = CURRENT_LEAVES_HU + len(EXTRA_HU)
    ratio = proposed_3 / CURRENT_LEAVES_3
    payload = extra_3way_bytes()
    solver = _sibling("solve_grid")
    return {
        "slot_call": SLOT_CALL,
        "derived_slot_v2": DERIVED_SLOT_V2,
        "n_slots_v2": N_SLOTS_V2,
        "current_leaves_3": CURRENT_LEAVES_3,
        "proposed_leaves_3": proposed_3,
        "current_leaves_hu": CURRENT_LEAVES_HU,
        "proposed_leaves_hu": proposed_hu,
        "leaf_ratio_3": ratio,
        "deep_cost": DEEP_COST,
        "squeeze_leaves": len(SQUEEZE),
        "extra_3way_bytes": payload,
        "payload_cap": PAYLOAD_CAP,
        "solver_leaves_3": len(solver._LEAF_DEFS_3),
        "solver_leaves_hu": len(solver._LEAF_DEFS_HU),
        "wired": False,
        "fidelity": 0,
        "ok_ratio": LEAF_RATIO_LO <= ratio <= LEAF_RATIO_HI,
        "ok_payload": payload < PAYLOAD_CAP,
        "ok_slot": SLOT_CALL == DERIVED_SLOT_V2 and N_SLOTS_V2 == 4,
        "ok_frozen": len(solver._LEAF_DEFS_3) == CURRENT_LEAVES_3,
    }


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    payload = report()
    print(json.dumps(payload, ensure_ascii=False))
    if not all(payload[key] for key in ("ok_ratio", "ok_payload", "ok_slot", "ok_frozen")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""POKER-68b: drzewo call-v0 za tree_id, iso nie rusza hasha kontroli."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTROL = REPO / "tools" / "blueprint" / "control"
TENSOR = CONTROL / "tensor"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, REPO / "tools" / "blueprint" / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _icm(sg, prizes):
    import numpy as np

    from poker.icm import icm_equities

    def lookup(state: tuple[int, int, int]):
        return np.asarray(icm_equities(state, prizes), dtype=np.float64)

    return lookup


def test_iso_hash_kontroli_nietkniety() -> None:
    sg = _load("solve_grid")
    cc = _load("control_chain")
    expected = json.loads((CONTROL / "chain_control.json").read_text(encoding="utf-8"))
    tensors = sg.load_tensors(TENSOR, cc.control_config().classes)
    digest = sg.config_hash(cc.control_config(), tensors.manifest)
    assert digest == expected["control"]["config_hash"]
    assert cc.control_config().tree_id == sg.TREE_ISO


def test_call_v0_ma_23_liscie_i_slot_3() -> None:
    sg = _load("solve_grid")
    cc = _load("control_chain")
    config = dataclasses.replace(cc.control_config(), tree_id=sg.TREE_CALL)
    tensors = sg.load_tensors(TENSOR, config.classes)
    lookup = _icm(sg, config.prizes)
    problem, _roles, mode = sg.build_stage_problem(
        tensors, config, (12, 10, 12), 0, 1, 1, lookup
    )
    assert mode == "deep"
    assert problem.n_slots == 4
    assert sg.SLOT_CALL in problem.allowed[sg.N_B_VS_T_OPEN]
    leaves = sg._tree_leaves(problem.tree, problem.allowed)
    assert len(leaves) == 23
    assert problem.n_slots == 4


def test_call_v0_fp_konczy_sie() -> None:
    sg = _load("solve_grid")
    cc = _load("control_chain")
    config = dataclasses.replace(
        cc.control_config(jobs=1), tree_id=sg.TREE_CALL, fp_max_iters=8, fp_check_every=4
    )
    tensors = sg.load_tensors(TENSOR, config.classes)
    lookup = _icm(sg, config.prizes)
    problem, _roles, _mode = sg.build_stage_problem(
        tensors, config, (12, 10, 12), 0, 1, 1, lookup
    )
    _sigma, eps, iters = sg._fp_solve(problem, config)
    assert iters >= 1
    assert eps == eps  # skończone


def test_iso_nadal_17() -> None:
    sg = _load("solve_grid")
    assert len(sg._LEAF_DEFS_3) == 17
    cc = _load("control_chain")
    config = cc.control_config()
    tensors = sg.load_tensors(TENSOR, config.classes)
    lookup = _icm(sg, config.prizes)
    problem, _roles, _mode = sg.build_stage_problem(
        tensors, config, (12, 10, 12), 0, 1, 1, lookup
    )
    assert problem.n_slots == 3
    assert len(sg._tree_leaves(problem.tree, problem.allowed)) == 17

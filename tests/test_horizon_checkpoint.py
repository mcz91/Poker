"""Checkpoint horyzontu per cykl (POKER-59)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
BLUEPRINT = REPO / "tools" / "blueprint"
CONTROL = BLUEPRINT / "control"

PRIZES = (0.8, 0.2, 0.0)


def _load(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _toy_classes() -> tuple[int, ...]:
    from poker.cards import Rank
    from poker.preflop import CLASS_INDEX, PreflopClass

    names = (
        PreflopClass(Rank.ACE, Rank.ACE, False),
        PreflopClass(Rank.KING, Rank.KING, False),
        PreflopClass(Rank.QUEEN, Rank.SEVEN, True),
        PreflopClass(Rank.SEVEN, Rank.TWO, False),
    )
    return tuple(sorted(CLASS_INDEX[item] for item in names))


def _tensor(tmp: Path) -> Path:
    pilot = _load("rollout_tensor")
    np = pilot.np
    classes = _toy_classes()
    multisets = pilot.multisets_for(classes)
    counts3 = np.zeros((len(multisets), 13), dtype=np.uint32)
    trials = 64
    for row, triple in enumerate(multisets):
        remaining = trials
        for out in range(13):
            share = (row + out * 7 + triple[0]) % 11 + 1
            take = min(remaining, share)
            counts3[row, out] = take
            remaining -= take
        counts3[row, 0] += remaining
    pairs = pilot.pairs_for(classes)
    counts2 = np.zeros((len(pairs), 3), dtype=np.uint32)
    for row, pair in enumerate(pairs):
        win = (row * 5 + pair[0]) % (trials - 2) + 1
        split = (row * 3) % (trials - win)
        counts2[row] = (win, split, trials - win - split)
    out = tmp / "tensor"
    out.mkdir(parents=True, exist_ok=True)
    pilot.write_artifacts(
        out,
        classes=classes,
        multisets=multisets,
        counts3=counts3,
        pairs=pairs,
        counts2=counts2,
        manifest_extra={
            "method": "synthetic-test",
            "master_seed": 0,
            "trials": trials,
            "hu_trials": trials,
            "backend": "synthetic",
        },
    )
    return out


def _config(sg: Any, **overrides: Any) -> Any:
    base: dict[str, Any] = {
        "prizes": PRIZES,
        "levels": ((1, 2), (2, 4)),
        "hands_per_level": 1,
        "total_chips": 150,
        "start_stacks": (50, 50, 50),
        "grid_step": 25,
        "classes": _toy_classes(),
        "fp_max_iters": 6,
        "fp_check_every": 3,
        "fp_tol": 0.0,
        "fp_restarts": 2,
        "cfr_iters": 8,
        "tail_max_cycles": 3,
        "tail_tol": 0.0,
        "jobs": 1,
    }
    base.update(overrides)
    return sg.GridConfig(**base)


def test_przerwanie_po_k_cyklach_wznawia_bajt_w_bajt(tmp_path: Path) -> None:
    """k = 1, 2 i cykl ostatni; jobs 1 i 2 — boundary.npz identyczny z biegiem ciągłym."""
    sg = _load("solve_grid")
    tensor = _tensor(tmp_path)
    last = 3
    for jobs in (1, 2):
        config = _config(sg, jobs=jobs)
        full = tmp_path / f"full{jobs}"
        sg.solve(config, tensor, full, layers_limit=0)
        full_bytes = (full / "boundary.npz").read_bytes()
        for k in (1, 2, last):
            work = tmp_path / f"resume{jobs}_{k}"
            first = sg.solve(
                config, tensor, work, layers_limit=0, horizon_cycles_limit=k
            )
            if k < last:
                assert first["boundary"] is None
                assert first["horizon"]["cycles_done"] == k
                assert first["horizon"]["complete"] is False
                assert first["horizon"]["cycles"][k - 1]["complete"] is True
                assert first["horizon"]["config_hash"] == first["config_hash"]
            sg.solve(config, tensor, work, layers_limit=0)
            assert (work / "boundary.npz").read_bytes() == full_bytes, (jobs, k)


def test_obcy_hash_checkpointu_odmawia_wznowienia(tmp_path: Path) -> None:
    sg = _load("solve_grid")
    tensor = _tensor(tmp_path)
    config = _config(sg)
    work = tmp_path / "tamper"
    sg.solve(config, tensor, work, layers_limit=0, horizon_cycles_limit=1)
    manifest_path = work / "solve_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["horizon"]["config_hash"] = "0" * 64
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checkpointu horyzontu"):
        sg.solve(config, tensor, work, layers_limit=0)


def test_bezpiecznik_widzi_cykle_horyzontu(tmp_path: Path) -> None:
    sg = _load("solve_grid")
    tensor = _tensor(tmp_path)
    config = _config(sg)
    work = tmp_path / "fuse"
    sg.solve(config, tensor, work, layers_limit=0, horizon_cycles_limit=1)
    manifest = json.loads((work / "solve_manifest.json").read_text(encoding="utf-8"))
    reachable = sg._reachable_sets(config)
    report = sg._cost_fuse_report(config, manifest, reachable)
    assert report["horizon_cycles_done"] == 1
    assert report["remaining_states"] > 0
    assert manifest["horizon"]["cycles"][0]["seconds"] >= 0.0
    assert manifest["horizon"]["deltas"]


def test_hash_lancucha_kontrolnego_nietkniety() -> None:
    """Checkpoint nie wchodzi do hasha — kotwica chain_control.json zostaje."""
    sg = _load("solve_grid")
    cc = _load("control_chain")
    expected = json.loads((CONTROL / "chain_control.json").read_text(encoding="utf-8"))
    tensor_manifest = json.loads(
        (CONTROL / "tensor" / "rollout_manifest.json").read_text(encoding="utf-8")
    )
    digest = sg.config_hash(cc.control_config(), tensor_manifest)
    assert digest == expected["control"]["config_hash"]
    assert digest == sg.config_hash(cc.control_config(jobs=4), tensor_manifest)

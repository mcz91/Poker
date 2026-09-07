"""Runner Colab rdzenia GTO (POKER-69)."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
BLUEPRINT = REPO / "tools" / "blueprint"
CONTROL = BLUEPRINT / "control"
NOTEBOOK = BLUEPRINT / "colab" / "train_gto.ipynb"


def _load(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_notes_ma_trzy_kroki_i_nie_importuje_gpu() -> None:
    raw = NOTEBOOK.read_text(encoding="utf-8")
    payload = json.loads(raw)
    sources = "\n".join("".join(cell.get("source", [])) for cell in payload["cells"])
    assert "allow-fresh" in sources
    assert "session-hours" in sources
    assert "colab_run.py pack" in sources
    assert "identity" in sources
    assert "cupy" not in sources.lower()
    assert "cuda" not in sources.lower() or "CPU" in sources
    runner = (BLUEPRINT / "colab_run.py").read_text(encoding="utf-8")
    assert "import cupy" not in runner
    assert "import cuda" not in runner


def test_cpu_only_odrzuca_zaladowany_modul_gpu() -> None:
    runner = _load("colab_run")
    runner.assert_cpu_only()
    sys.modules["cupy"] = sys.modules[__name__]
    try:
        with pytest.raises(RuntimeError, match="CPU"):
            runner.assert_cpu_only()
    finally:
        del sys.modules["cupy"]


def test_swiezy_katalog_wymaga_flagi(tmp_path: Path) -> None:
    runner = _load("colab_run")
    with pytest.raises(SystemExit, match="allow-fresh"):
        runner.run_solve(CONTROL / "tensor", tmp_path / "out", control=True)


def test_hash_lancucha_kontrolnego_z_runnera() -> None:
    runner = _load("colab_run")
    sg = _load("solve_grid")
    expected = json.loads((CONTROL / "chain_control.json").read_text(encoding="utf-8"))
    tensor_manifest = json.loads(
        (CONTROL / "tensor" / "rollout_manifest.json").read_text(encoding="utf-8")
    )
    config = _load("control_chain").control_config()
    assert sg.config_hash(config, tensor_manifest) == expected["control"]["config_hash"]
    assert runner.FORBIDDEN_GPU == ("cupy", "cudf", "pycuda")


def test_sesja_przerywa_i_wznawia_bajt_w_bajt(tmp_path: Path) -> None:
    """Bezpiecznik ściany zapisuje postęp; ta sama komenda dokańcza identycznie."""
    sg = _load("solve_grid")
    from poker.cards import Rank
    from poker.preflop import CLASS_INDEX, PreflopClass

    def classes() -> tuple[int, ...]:
        names = (
            PreflopClass(Rank.ACE, Rank.ACE, False),
            PreflopClass(Rank.KING, Rank.KING, False),
            PreflopClass(Rank.QUEEN, Rank.SEVEN, True),
            PreflopClass(Rank.SEVEN, Rank.TWO, False),
        )
        return tuple(sorted(CLASS_INDEX[item] for item in names))

    rt = _load("rollout_tensor")
    np = rt.np
    toy = classes()
    trials = 64
    multisets = rt.multisets_for(toy)
    counts3 = np.zeros((len(multisets), 13), dtype=np.uint32)
    for row, triple in enumerate(multisets):
        remaining = trials
        for out in range(13):
            share = (row + out * 7 + triple[0]) % 11 + 1
            take = min(remaining, share)
            counts3[row, out] = take
            remaining -= take
        counts3[row, 0] += remaining
    pairs = rt.pairs_for(toy)
    counts2 = np.zeros((len(pairs), 3), dtype=np.uint32)
    for row, pair in enumerate(pairs):
        win = (row * 5 + pair[0]) % (trials - 2) + 1
        split = (row * 3) % (trials - win)
        counts2[row] = (win, split, trials - win - split)
    tensor = tmp_path / "tensor"
    tensor.mkdir()
    rt.write_artifacts(
        tensor,
        classes=toy,
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
    config = sg.GridConfig(
        prizes=(0.8, 0.2, 0.0),
        levels=((1, 2), (2, 4)),
        hands_per_level=1,
        total_chips=150,
        start_stacks=(50, 50, 50),
        grid_step=25,
        classes=toy,
        fp_max_iters=6,
        fp_check_every=3,
        fp_tol=0.0,
        fp_restarts=2,
        cfr_iters=8,
        tail_max_cycles=3,
        tail_tol=0.0,
        jobs=1,
    )
    full = tmp_path / "full"
    sg.solve(config, tensor, full)
    names = sorted(path.name for path in full.glob("*.npz"))
    work = tmp_path / "session"
    first = sg.solve(config, tensor, work, session_deadline=time.perf_counter())
    assert first["status"] in {"aborted-session", "partial"}
    sg.solve(config, tensor, work)
    assert names == sorted(path.name for path in work.glob("*.npz"))
    for name in names:
        assert (full / name).read_bytes() == (work / name).read_bytes(), name

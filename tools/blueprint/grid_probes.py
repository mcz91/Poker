"""Sondy błędu modelu P-6(a) — krok siatki (POKER-60).

Plaster 1: flip trybu drzewa. Plaster 2: ε importu σ sąsiada na stanie
dokładnym (V_next = ICM po kwancie — nie pełne V DAG-u produkcji).

Reguła: maks importu > 5e−4 LUB flip trybu → krok 1 = TAK.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import statistics
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from poker.icm import icm_equities
from poker.spin import JAM_FOLD_BB, is_jam_fold_depth

STAGE_TOL = 5e-5
READ_K = 10
IMPORT_TRIGGER = STAGE_TOL * READ_K


def _sibling(name: str) -> ModuleType:
    module = sys.modules.get(name)
    if module is not None:
        return module
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"brak {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def off_grid_state(stacks: tuple[int, int, int], step: int) -> bool:
    if sum(1 for value in stacks if value % step != 0) < 2:
        return False
    if any(value < 0 for value in stacks):
        return False
    return sum(1 for value in stacks if value > 0) >= 2


def sample_off_grid(
    total: int,
    step: int,
    *,
    n: int,
    seed: int,
) -> list[tuple[int, int, int]]:
    rng = random.Random(seed)
    found: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    attempts = 0
    while len(found) < n and attempts < n * 400:
        attempts += 1
        a = rng.randint(0, total)
        b = rng.randint(0, total - a)
        state = (a, b, total - a - b)
        if state in seen or not off_grid_state(state, step):
            continue
        seen.add(state)
        found.append(state)
    if len(found) < n:
        raise SystemExit(f"wylosowano {len(found)} stanów poza siatką, żądano {n}")
    return found


def mode_flip(
    exact: tuple[int, int, int], quantized: tuple[int, int, int], bb: int
) -> bool:
    return is_jam_fold_depth(exact, bb) != is_jam_fold_depth(quantized, bb)


def census_mode_flips(
    states: list[tuple[int, int, int]],
    step: int,
    blinds: tuple[int, ...],
) -> dict[str, Any]:
    solve_grid = _sibling("solve_grid")
    flips = 0
    rows: list[dict[str, Any]] = []
    for state in states:
        neighbor = solve_grid.quantize_stacks(state, step)
        hit = [bb for bb in blinds if mode_flip(state, neighbor, bb)]
        if hit:
            flips += 1
            rows.append(
                {
                    "exact": list(state),
                    "grid": list(neighbor),
                    "bb": hit,
                    "effective_bb_exact": min(s for s in state if s > 0) / hit[0],
                    "threshold_bb": JAM_FOLD_BB,
                }
            )
    return {
        "n": len(states),
        "flips": flips,
        "flip_rate": flips / max(len(states), 1),
        "trigger_import": IMPORT_TRIGGER,
        "examples": rows[:20],
    }


def import_gap(
    tensors: Any,
    config: Any,
    exact: tuple[int, int, int],
    hand: int,
    blinds: tuple[int, int],
) -> dict[str, Any]:
    """ε BR na stanie dokładnym przy σ sąsiada; V_next = ICM po kwancie."""
    solve_grid = _sibling("solve_grid")
    neighbor = solve_grid.quantize_stacks(exact, config.grid_step)
    sb, bb_amt = blinds

    def lookup(target: tuple[int, int, int]) -> Any:
        snapped = solve_grid.quantize_stacks(target, config.grid_step)
        return np.asarray(icm_equities(snapped, config.prizes), dtype=np.float64)

    exact_p, _roles, exact_mode = solve_grid.build_stage_problem(
        tensors, config, exact, hand, sb, bb_amt, lookup
    )
    near_p, _near, near_mode = solve_grid.build_stage_problem(
        tensors, config, neighbor, hand, sb, bb_amt, lookup
    )
    flipped = exact_mode != near_mode
    solver = (
        solve_grid._fp_solve if exact_p.n_roles == 3 else solve_grid._cfr_plus_solve
    )
    sigma_near, _, _ = solver(near_p, config)
    _own, own_eps, _ = solver(exact_p, config)
    imported = {
        node_id: sigma_near[node_id]
        for node_id in exact_p.nodes
        if node_id in sigma_near
    }
    if flipped or len(imported) != len(exact_p.nodes):
        gap = float("inf")
    else:
        gap = float(solve_grid._internal_eps(exact_p, imported))
    finite = gap != float("inf")
    return {
        "exact": list(exact),
        "grid": list(neighbor),
        "mode_exact": exact_mode,
        "mode_grid": near_mode,
        "flipped": flipped,
        "own_eps": float(own_eps),
        "import_eps": gap if finite else None,
        "triggers_step1": flipped or (finite and gap > IMPORT_TRIGGER),
    }


def summarize_imports(rows: list[dict[str, Any]]) -> dict[str, Any]:
    finite = [float(row["import_eps"]) for row in rows if row["import_eps"] is not None]
    flips = sum(1 for row in rows if row["flipped"])
    max_import = max(finite) if finite else 0.0
    return {
        "n": len(rows),
        "flips": flips,
        "n_finite": len(finite),
        "max_import": max_import,
        "median_import": statistics.median(finite) if finite else 0.0,
        "n_trigger": sum(1 for row in rows if row["triggers_step1"]),
        "v_next": "icm-quantized",
        "reading": reading_rule(max_import, flips),
        "rows": rows,
    }


def reading_rule(max_import: float, flips: int) -> dict[str, Any]:
    step1 = bool(max_import > IMPORT_TRIGGER or flips > 0)
    return {
        "max_import": max_import,
        "flips": flips,
        "threshold": IMPORT_TRIGGER,
        "step1": "TAK" if step1 else "NIE",
        "basis": "import>5e-4 lub flip trybu na próbce",
    }


def measure_import(
    tensor_dir: Path,
    *,
    n: int,
    seed: int,
    hand: int,
    blinds: tuple[int, int],
    jobs: int = 1,
) -> dict[str, Any]:
    """ε importu na łańcuchu kontrolnym (4 klasy, 34 żetony, krok 2)."""
    solve_grid = _sibling("solve_grid")
    control = _sibling("control_chain")
    config = control.control_config(jobs=jobs)
    tensors = solve_grid.load_tensors(tensor_dir, config.classes)
    states = sample_off_grid(config.total_chips, config.grid_step, n=n, seed=seed)
    rows = [import_gap(tensors, config, state, hand, blinds) for state in states]
    report = summarize_imports(rows)
    report["total"] = config.total_chips
    report["step"] = config.grid_step
    report["seed"] = seed
    report["hand"] = hand
    report["blinds"] = list(blinds)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--total", type=int, default=150)
    parser.add_argument("--step", type=int, default=2)
    parser.add_argument("--n", type=int, default=300)
    parser.add_argument("--seed", type=int, default=60)
    parser.add_argument("--blinds", default="2,4,6,8,10,16,20")
    parser.add_argument(
        "--measure",
        action="store_true",
        help="ε importu (wymaga --tensor); default to spis flipów",
    )
    parser.add_argument("--tensor", type=Path, default=None)
    parser.add_argument("--hand", type=int, default=0)
    parser.add_argument("--sb", type=int, default=1)
    parser.add_argument("--bb", type=int, default=2)
    parser.add_argument("--jobs", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.measure:
        if args.tensor is None:
            raise SystemExit("--measure wymaga --tensor")
        blinds = (args.sb, args.bb)
        report = measure_import(
            args.tensor,
            n=args.n,
            seed=args.seed,
            hand=args.hand,
            blinds=blinds,
            jobs=args.jobs,
        )
        print(json.dumps(report, ensure_ascii=False))
        return 0
    blinds_all = tuple(int(part) for part in args.blinds.split(","))
    states = sample_off_grid(args.total, args.step, n=args.n, seed=args.seed)
    report = census_mode_flips(states, args.step, blinds_all)
    report["reading"] = reading_rule(0.0, report["flips"])
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

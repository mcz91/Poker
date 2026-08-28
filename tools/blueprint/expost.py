"""Ex-post best-response check i raporty pilota blueprintu (POKER-46, decyzja 25).

Ex-post (Ganzfried, Algorithm 6): strategie wszystkich miejsc zamrożone
z artefaktu solvera; trzeci gracz optymalizuje po całym DAG-u — to MDP,
więc liczymy go tą samą indukcją wsteczną na tych samych tablicach:
V_BR(n) = best response w grze etapowej przy zamrożonych przeciwnikach
i kontynuacji V_BR(n+1). Horyzont: V_BR(N) = warunek brzegowy biegu
(nieskończony ogon ostatniego poziomu traktujemy jako stały dla obu stron).
ε stanu i miejsca = V_BR − V, w jednostkach puli (pula nagród = 1);
z konstrukcji ε ≥ 0 z dokładnością do arytmetyki f32.

Raporty:
- `icm` — różnica V vs ICM per stan/warstwa, z wyszczególnieniem stanów
  krótkiego BB (< 5 bb — tam Ganzfried mierzył największy błąd ICM);
- `sanity` — strategia jam/fold pilota na równych stackach 25 bb
  (drzewo jam/fold wymuszone, kontynuacja dokładnym ICM) obok
  `poker.jamfold.solve`: inne modele (tensor trójek z card removal vs
  macierz par i para znormalizowana), więc oczekujemy zgodności
  kierunkowej, nie identyczności.

Uruchomienie (venv z extras train):

    python tools/blueprint/expost.py expost --out KATALOG
    python tools/blueprint/expost.py icm --out KATALOG
    python tools/blueprint/expost.py sanity --tensor KATALOG
"""

import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from poker.icm import icm_equities
from poker.jamfold import WEIGHTS
from poker.jamfold import solve as jamfold_solve
from poker.preflop import ALL_CLASSES
from poker.spin import roles


def _sibling(name: str) -> ModuleType:
    """Moduł siostrzany z tools/blueprint — tools nie jest pakietem (jak testy reprodukcji)."""
    module = sys.modules.get(name)
    if module is not None:
        return module
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"brak modułu siostrzanego {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


artifacts = _sibling("artifacts")
solve_grid = _sibling("solve_grid")

_RANK_SYMBOLS = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}


def _class_name(index: int) -> str:
    cls = ALL_CLASSES[index]
    high = _RANK_SYMBOLS.get(cls.high.value, str(cls.high.value))
    low = _RANK_SYMBOLS.get(cls.low.value, str(cls.low.value))
    if cls.high == cls.low:
        return f"{high}{low}"
    return f"{high}{low}{'s' if cls.suited else 'o'}"


def _load_run(out_dir: Path) -> tuple[Any, Any, dict[int, dict[str, np.ndarray]], np.ndarray]:
    manifest = artifacts.read_json(out_dir / "solve_manifest.json")
    if manifest["status"] != "done":
        raise ValueError("bieg solvera nie jest zakończony — ex-post wymaga pełnego DAG-u")
    config = solve_grid.config_from_dict(manifest["config"])
    tensors = solve_grid.load_tensors(Path(manifest["tensor_dir"]), config.classes)
    layers = solve_grid.load_layers(out_dir)
    boundary = artifacts.read_npz(out_dir / "boundary.npz")
    return config, tensors, layers, boundary["v"]


_EWORK: dict[str, Any] = {}


def _expost_state_job(index: int) -> tuple[int, np.ndarray]:
    config = _EWORK["config"]
    tensors = _EWORK["tensors"]
    hand: int = _EWORK["hand"]
    sb, bb_amt = _EWORK["blinds"]
    states = _EWORK["states"]
    sigma_all: np.ndarray = _EWORK["sigma"]
    v_br_index: dict[tuple[int, int, int], int] = _EWORK["v_br_index"]
    v_br_next: np.ndarray = _EWORK["v_br_next"]
    state = states[index]

    def lookup(target: tuple[int, int, int]) -> np.ndarray:
        return v_br_next[v_br_index[solve_grid.quantize_stacks(target, config.grid_step)]]

    problem, role_seats, _ = solve_grid.build_stage_problem(
        tensors, config, state, hand, sb, bb_amt, lookup
    )
    sigma = {node_id: sigma_all[index, node_id] for node_id in problem.nodes}
    row = np.full(3, config.prizes[2], dtype=np.float64)
    for hero, seat in enumerate(role_seats):
        _, root = solve_grid._hero_action_values(problem, hero, sigma, "best")
        row[seat] = float(root.sum()) / problem.total_weight
    return index, row


def run_expost(out_dir: Path, jobs: int | None = None) -> dict[str, Any]:
    config, tensors, layers, boundary_v = _load_run(out_dir)
    total = solve_grid.n_hands(config)
    full_states = solve_grid.grid_states(config.total_chips, config.grid_step)
    v_br_states: tuple[tuple[int, int, int], ...] = full_states
    v_br_next = boundary_v
    workers = config.jobs if jobs is None else jobs
    eps_arrays: dict[str, np.ndarray] = {}
    pool_prize = float(sum(config.prizes))
    samples: list[tuple[float, int, tuple[int, int, int], int]] = []
    for hand in range(total - 1, -1, -1):
        layer = layers[hand]
        states = tuple((int(a), int(b), int(c)) for a, b, c in layer["states"].tolist())
        _EWORK.update(
            config=config,
            tensors=tensors,
            hand=hand,
            blinds=solve_grid.level_blinds(config, hand),
            states=states,
            sigma=layer["sigma"],
            v_br_index={state: pos for pos, state in enumerate(v_br_states)},
            v_br_next=v_br_next,
        )
        rows = solve_grid.forked_map(_expost_state_job, range(len(states)), workers)
        rows.sort(key=lambda item: item[0])
        v_br = np.stack([row for _, row in rows], axis=0)
        eps = (v_br - layer["v"]) / pool_prize
        eps_arrays[f"eps_{hand:02d}"] = eps
        for position, state in enumerate(states):
            for seat in range(3):
                if state[seat] > 0:
                    samples.append((float(eps[position, seat]), hand, state, seat))
        v_br_states, v_br_next = states, v_br
    values = [value for value, _, _, _ in samples]
    worst = sorted(samples, key=lambda item: -item[0])[:10]
    report: dict[str, Any] = {
        "pool": pool_prize,
        "states": sum(layer["states"].shape[0] for layer in layers.values()),
        "epsilon_max": max(values),
        "epsilon_median": float(statistics.median(values)),
        "epsilon_min": min(values),
        "worst": [
            {"hand": hand, "state": list(state), "seat": seat, "epsilon": value}
            for value, hand, state, seat in worst
        ],
    }
    artifacts.write_npz(out_dir / "expost.npz", eps_arrays)
    artifacts.write_json(out_dir / "expost_report.json", report)
    return report


def icm_report(out_dir: Path, short_bb_threshold: float = 5.0) -> dict[str, Any]:
    manifest = artifacts.read_json(out_dir / "solve_manifest.json")
    config = solve_grid.config_from_dict(manifest["config"])
    layers = solve_grid.load_layers(out_dir)
    pool_prize = float(sum(config.prizes))
    per_layer: list[dict[str, Any]] = []
    short_bb: list[float] = []
    worst: list[tuple[float, int, tuple[int, int, int]]] = []
    for hand in sorted(layers):
        layer = layers[hand]
        _, bb_amt = solve_grid.level_blinds(config, hand)
        deltas: list[float] = []
        for position, row in enumerate(layer["states"].tolist()):
            state = (int(row[0]), int(row[1]), int(row[2]))
            icm = np.asarray(icm_equities(state, config.prizes), dtype=np.float64)
            delta = float(np.max(np.abs(layer["v"][position] - icm))) / pool_prize
            deltas.append(delta)
            worst.append((delta, hand, state))
            alive = [seat for seat in range(3) if state[seat] > 0]
            if len(alive) == 3:
                bb_seat = roles(hand % 3)[2]
            else:
                ordered = sorted(alive)
                bb_seat = ordered[1 - hand % 2]
            if state[bb_seat] < short_bb_threshold * bb_amt:
                short_bb.append(delta)
        per_layer.append(
            {
                "hand": hand,
                "n_states": len(deltas),
                "max_abs_delta": max(deltas),
                "mean_abs_delta": float(np.mean(deltas)),
            }
        )
    worst.sort(key=lambda item: -item[0])
    report: dict[str, Any] = {
        "pool": pool_prize,
        "layers": per_layer,
        "short_bb": {
            "threshold_bb": short_bb_threshold,
            "n_states": len(short_bb),
            "max_abs_delta": max(short_bb) if short_bb else 0.0,
            "mean_abs_delta": float(np.mean(short_bb)) if short_bb else 0.0,
        },
        "worst": [
            {"hand": hand, "state": list(state), "delta": delta}
            for delta, hand, state in worst[:10]
        ],
    }
    artifacts.write_json(out_dir / "icm_report.json", report)
    return report


def jamfold_sanity(
    tensor_dir: Path,
    prizes: tuple[float, float, float] = (0.8, 0.2, 0.0),
    stacks: tuple[int, int, int] = (50, 50, 50),
    button: int = 1,
    sb: int = 1,
    bb_amt: int = 2,
    fp_iters: int = 64,
    jamfold_iters: int = 80,
) -> dict[str, Any]:
    """Pilot (drzewo jam/fold wymuszone, kontynuacja ICM) obok poker.jamfold.solve."""
    manifest = artifacts.read_json(tensor_dir / "rollout_manifest.json")
    classes = tuple(manifest["classes"])
    if len(classes) != len(ALL_CLASSES):
        raise ValueError("sanity jam/fold wymaga tensora pełnych 169 klas")
    config = solve_grid.GridConfig(
        prizes=prizes,
        classes=classes,
        fp_max_iters=fp_iters,
        fp_check_every=8,
        fp_tol=1e-4,
        fp_restarts=2,
    )
    tensors = solve_grid.load_tensors(tensor_dir, classes)
    pilot = solve_grid.solve_single_state(
        config, tensors, stacks, button, sb, bb_amt, v_next=None, force_jamfold=True
    )
    reference = jamfold_solve(stacks, prizes, button=button, iterations=jamfold_iters)
    comparisons = (
        ("utg_jam", solve_grid.N_U_ROOT, solve_grid.SLOT_JAM, reference.utg_jam),
        ("btn_call_vs_utg_jam", solve_grid.N_T_VS_U_JAM, solve_grid.SLOT_MID,
         reference.btn_call),
        ("bb_call_vs_utg_jam", solve_grid.N_B_VS_U_JAM_T_FOLD, solve_grid.SLOT_MID,
         reference.bb_call),
        ("btn_first_in_jam", solve_grid.N_T_FI, solve_grid.SLOT_JAM, reference.btn_open),
        ("bb_call_vs_btn_jam", solve_grid.N_B_VS_T_JAM, solve_grid.SLOT_MID,
         reference.bb_vs_btn),
    )
    weights = np.asarray(WEIGHTS, dtype=np.float64)
    nodes: dict[str, Any] = {}
    for name, node_id, slot, reference_probs in comparisons:
        pilot_probs = pilot.sigma[node_id, :, slot].astype(np.float64)
        reference_arr = np.asarray(reference_probs, dtype=np.float64)
        disagreement = np.abs(pilot_probs - reference_arr) >= 0.5
        nodes[name] = {
            "pilot_pct": float(100.0 * (weights @ pilot_probs) / weights.sum()),
            "jamfold_pct": float(100.0 * (weights @ reference_arr) / weights.sum()),
            "agreement": float(1.0 - disagreement.mean()),
            "disagreements": [
                _class_name(index) for index in np.flatnonzero(disagreement)[:20]
            ],
        }
    report = {
        "stacks": list(stacks),
        "prizes": list(prizes),
        "pilot_eps_internal": pilot.eps,
        "pilot_iterations": pilot.iterations,
        "jamfold_iterations": jamfold_iters,
        "nodes": nodes,
    }
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("expost", "icm"):
        sub = commands.add_parser(name)
        sub.add_argument("--out", type=Path, required=True)
        if name == "expost":
            sub.add_argument("--jobs", type=int, default=None)
    sanity = commands.add_parser("sanity")
    sanity.add_argument("--tensor", type=Path, required=True)
    sanity.add_argument("--prizes", type=str, default="0.8,0.2,0.0")
    sanity.add_argument("--fp-iters", type=int, default=64)
    args = parser.parse_args(argv)
    if args.command == "expost":
        report = run_expost(args.out, jobs=args.jobs)
    elif args.command == "icm":
        report = icm_report(args.out)
    else:
        prize_parts = tuple(float(part) for part in args.prizes.split(","))
        report = jamfold_sanity(
            args.tensor,
            prizes=(prize_parts[0], prize_parts[1], prize_parts[2]),
            fp_iters=args.fp_iters,
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print(json.dumps({key: report[key] for key in report if key not in ("worst", "layers")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

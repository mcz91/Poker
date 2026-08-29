"""Wrażliwość blueprintu na warunek brzegowy horyzontu (POKER-49, decyzja 25 pkt 1 i 7).

Ex-post ε zamraża ogon dla obu stron, więc błąd warunku brzegowego jest dla tej
metryki niewidzialny: bieg stojący na niezbieżnym horyzoncie potrafi mieć ε
poniżej progu i mimo to liczyć inną grę. Ten pomiar zamienia to zdanie na
liczbę — zestawia bieg odniesienia z biegiem o jawnie zaburzonym brzegu
(`solve_grid.py --perturb ... --boundary-from ODNIESIENIE`, żeby jedyną różnicą
było zaburzenie) i podaje, o ile różnią się ex-post ε oraz strategie
w warstwach przed horyzontem.

Zmiana dominującej akcji liczona jest tylko na infosetach osiągalnych w drzewie
biegu odniesienia (wiersze pozostałych są zerowe z konstrukcji tablicy `sigma`).

Uruchomienie (venv z extras train):

    python tools/blueprint/boundary_sensitivity.py \\
        --reference KATALOG/grid5 --perturbed KATALOG/grid5_tilt
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


def _start_epsilon(out_dir: Path, layers: dict[int, dict[str, np.ndarray]]) -> float:
    """ε ex-post stanu startowego — eksploatowalność całego blueprintu (POKER-47 pkt 1)."""
    eps = artifacts.read_npz(out_dir / "expost.npz")["eps_00"]
    state = [int(value) for value in layers[0]["states"][0]]
    return max(float(eps[0, seat]) for seat in range(3) if state[seat] > 0)


def _layer_delta(
    reference: dict[str, np.ndarray], perturbed: dict[str, np.ndarray]
) -> dict[str, Any]:
    if reference["states"].tolist() != perturbed["states"].tolist():
        raise ValueError("warstwy biegów mają różne zbiory stanów")
    value_delta = np.abs(perturbed["v"] - reference["v"])
    live = reference["sigma"].sum(axis=3) > 0.5
    if not bool(live.any()):
        raise ValueError("warstwa bez osiągalnych infosetów")
    ref_rows = reference["sigma"][live]
    new_rows = perturbed["sigma"][live]
    changed = ref_rows.argmax(axis=1) != new_rows.argmax(axis=1)
    row_delta = np.abs(new_rows - ref_rows).max(axis=1)
    return {
        "n_states": int(reference["states"].shape[0]),
        "v_max_abs_delta": float(value_delta.max()),
        "v_mean_abs_delta": float(value_delta.mean()),
        "infosets": int(ref_rows.shape[0]),
        "sigma_max_abs_delta": float(row_delta.max()),
        "sigma_mean_abs_delta": float(row_delta.mean()),
        "action_changes": int(changed.sum()),
        "action_change_share": float(changed.mean()),
    }


def compare(reference_dir: Path, perturbed_dir: Path) -> dict[str, Any]:
    """Różnica dwóch zamkniętych biegów różniących się warunkiem brzegowym."""
    reference_manifest = artifacts.read_json(reference_dir / "solve_manifest.json")
    perturbed_manifest = artifacts.read_json(perturbed_dir / "solve_manifest.json")
    for manifest in (reference_manifest, perturbed_manifest):
        if manifest["status"] != "done":
            raise ValueError("porównanie wymaga dwóch zakończonych biegów")
    reference_layers = solve_grid.load_layers(reference_dir)
    perturbed_layers = solve_grid.load_layers(perturbed_dir)
    if sorted(reference_layers) != sorted(perturbed_layers):
        raise ValueError("biegi mają różne zbiory warstw")
    boundary_delta = np.abs(
        artifacts.read_npz(perturbed_dir / "boundary.npz")["v"]
        - artifacts.read_npz(reference_dir / "boundary.npz")["v"]
    )
    layers = [
        dict(hand=hand, **_layer_delta(reference_layers[hand], perturbed_layers[hand]))
        for hand in sorted(reference_layers)
    ]
    reference_expost = artifacts.read_json(reference_dir / "expost_report.json")
    perturbed_expost = artifacts.read_json(perturbed_dir / "expost_report.json")
    start = (
        _start_epsilon(reference_dir, reference_layers),
        _start_epsilon(perturbed_dir, perturbed_layers),
    )
    report: dict[str, Any] = {
        "reference": str(reference_dir.resolve()),
        "perturbed": str(perturbed_dir.resolve()),
        "boundary": {
            "perturb": perturbed_manifest["config"]["boundary_perturb"],
            "kind": perturbed_manifest["config"]["boundary_perturb_kind"],
            "max_abs_delta": float(boundary_delta.max()),
            "reference_converged": reference_manifest["boundary"]["converged"],
            "reference_delta": reference_manifest["boundary"]["delta"],
        },
        "epsilon": {
            "reference_max": reference_expost["epsilon_max"],
            "perturbed_max": perturbed_expost["epsilon_max"],
            "reference_median": reference_expost["epsilon_median"],
            "perturbed_median": perturbed_expost["epsilon_median"],
            "start_state_reference": start[0],
            "start_state_perturbed": start[1],
            "start_state_delta": start[1] - start[0],
        },
        "strategy": {
            "v_max_abs_delta": max(row["v_max_abs_delta"] for row in layers),
            "sigma_max_abs_delta": max(row["sigma_max_abs_delta"] for row in layers),
            "sigma_mean_abs_delta": float(
                statistics.mean([row["sigma_mean_abs_delta"] for row in layers])
            ),
            "infosets": sum(row["infosets"] for row in layers),
            "action_changes": sum(row["action_changes"] for row in layers),
            "action_change_share": (
                sum(row["action_changes"] for row in layers)
                / sum(row["infosets"] for row in layers)
            ),
        },
        "layers": layers,
    }
    artifacts.write_json(perturbed_dir / "boundary_sensitivity.json", report)
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--perturbed", type=Path, required=True)
    args = parser.parse_args(argv)
    report = compare(args.reference, args.perturbed)
    print(json.dumps(
        {key: report[key] for key in ("boundary", "epsilon", "strategy")},
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
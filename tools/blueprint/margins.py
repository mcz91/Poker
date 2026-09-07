"""Marginesy indyferencji per infoset artefaktu solvera (POKER-57, decyzja 29 pkt 3).

Margines infosetu (stan, węzeł, klasa) = różnica wartości DWÓCH NAJLEPSZYCH
akcji bohatera, który w tym węźle decyduje, przy zamrożonym profilu artefaktu
i jego własnej kontynuacji V. Jednostka jest ta sama co ε: udział SUMY WEKTORA
WYPŁAT (`GridConfig` wymusza sumę 1, więc jeden turniej). Wartość jest
WARUNKOWA — dzielimy przez masę rozdań klasy docierających do węzła — więc
mówi „o ile lepsza jest najlepsza akcja na jedną rękę tej klasy", a nie „ile
ta decyzja waży w wartości stanu"; komórka rzadko odwiedzana może mieć duży
margines i znikomy wpływ na ε.

Po co: zmierzona patologia wrażliwości brzegu (POKER-49) — przy zaburzeniu
0,002 ε rusza się o 1,7%, ale pojedyncze komórki bliskie obojętności
przełączają akcję całkowicie. Warstwa eksploatacyjna (DBR, P-13) musi wiedzieć,
które komórki to takie komórki, zanim je ruszy.

Czego to NIE jest: re-solve. Liczy się jeden przechód po zapisanych V i σ,
tą samą maszynerią gry etapowej co `expost` (`build_stage_problem` +
`_hero_action_values`), więc koszt jest kosztem jednego ex-post, a nie kosztem
biegu solvera.

Uruchomienie (venv z extras train):

    python tools/blueprint/margins.py margins --out KATALOG [--jobs N]

Wynik: `margins.npz` (`margin_HH` — stany × węzły × klasy, float32;
`decision_HH` — stany × węzły, bool: węzeł jest DECYZJĄ, czyli ma co najmniej
dwie legalne akcje; `defined_HH` — stany × węzły × klasy, bool: klasa dociera
do węzła, więc margines jest OKREŚLONY) i `margins_report.json`. Oba pliki
czyta konwerter `pack_blueprint.py --format-version 2`, który zapisuje
marginesy zgrubnie (uint8 na skali stanu, bajt 0 = nieokreślony).
"""

import argparse
import gc
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

_MWORK: dict[str, Any] = {}


def state_margins(problem: Any, sigma: dict[int, np.ndarray],
                  n_nodes: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Marginesy jednego stanu, maska węzłów-decyzji i maska OKREŚLONOŚCI.

    Trzy stany, nie dwa. Węzeł z jedną legalną akcją nie jest decyzją — nie ma
    tam czego porównać, więc zostaje poza maską węzłów zamiast dostać margines
    zero. W węźle, który decyzją jest, klasa o zerowej masie rozdań docierających
    (przy tym profilu nigdy tej decyzji nie podejmuje) nie ma warunkowego EV —
    zostaje poza maską określoności, znów zamiast dostać zero. Zero jest
    zarezerwowane na jedną rzecz: zmierzoną obojętność.
    """
    margin = np.zeros((n_nodes, problem.count), dtype=np.float32)
    decision = np.zeros(n_nodes, dtype=bool)
    defined = np.zeros((n_nodes, problem.count), dtype=bool)
    for hero in range(problem.n_roles):
        reach_record: dict[int, dict[int, np.ndarray]] = {}
        record, _, _ = solve_grid._hero_action_values(
            problem, hero, sigma, "profile", reach_record
        )
        for node_id, values in record.items():
            if len(problem.allowed[node_id]) < 2:
                continue
            ordered = np.sort(np.stack(values, axis=0).astype(np.float64), axis=0)
            gap = ordered[-1] - ordered[-2]
            mass = np.asarray(
                solve_grid._contract_hero(
                    problem.deal, reach_record[node_id], hero, problem.count, problem.n_roles
                ),
                dtype=np.float64,
            )
            live = mass > 0.0
            margin[node_id] = np.where(live, gap / np.where(live, mass, 1.0), 0.0)
            defined[node_id] = live
            decision[node_id] = True
    return margin, decision, defined


def _margin_state_job(index: int) -> tuple[int, np.ndarray, np.ndarray, np.ndarray]:
    config = _MWORK["config"]
    tensors = _MWORK["tensors"]
    hand: int = _MWORK["hand"]
    sb, bb_amt = _MWORK["blinds"]
    states = _MWORK["states"]
    sigma_all: np.ndarray = _MWORK["sigma"]
    v_index: dict[tuple[int, int, int], int] = _MWORK["v_index"]
    v_next: np.ndarray = _MWORK["v_next"]

    def lookup(target: tuple[int, int, int]) -> np.ndarray:
        return np.asarray(v_next[v_index[solve_grid.quantize_stacks(target, config.grid_step)]])

    problem, _, _ = solve_grid.build_stage_problem(
        tensors, config, states[index], hand, sb, bb_amt, lookup
    )
    sigma = {node_id: sigma_all[index, node_id] for node_id in problem.nodes}
    margin, decision, defined = state_margins(problem, sigma, sigma_all.shape[1])
    # Jak w solverze i w ex-post: cykle domknięć trzymają tensory wypłat do gc.
    del problem
    gc.collect()
    return index, margin, decision, defined


def run_margins(out_dir: Path, jobs: int | None = None) -> dict[str, Any]:
    """Marginesy całego biegu: `margins.npz` + raport. Kontynuacja jak w solverze.

    Kontynuacją stanu jest V WARSTWY NASTĘPNEJ z tego samego biegu (dla
    ostatniej ręki — warunek brzegowy), czyli dokładnie ta, na której solver
    liczył profil. Ex-post podstawia w to miejsce V najlepszej odpowiedzi i
    dlatego mierzy co innego.
    """
    manifest = artifacts.read_json(out_dir / "solve_manifest.json")
    if manifest["status"] != "done":
        raise ValueError("marginesy liczy się na zakończonym biegu solvera")
    config = solve_grid.config_from_dict(manifest["config"])
    tensors = solve_grid.load_tensors(Path(manifest["tensor_dir"]), config.classes)
    layers = solve_grid.load_layers(out_dir)
    boundary = artifacts.read_npz(out_dir / "boundary.npz")
    total = solve_grid.n_hands(config)
    workers = config.jobs if jobs is None else jobs
    v_states: tuple[tuple[int, int, int], ...] = solve_grid.grid_states(
        config.total_chips, config.grid_step
    )
    v_next = boundary["v"]
    arrays: dict[str, np.ndarray] = {}
    per_layer: list[dict[str, Any]] = []
    all_values: list[float] = []
    for hand in range(total - 1, -1, -1):
        layer = layers[hand]
        states = tuple((int(a), int(b), int(c)) for a, b, c in layer["states"].tolist())
        _MWORK.update(
            config=config,
            tensors=tensors,
            hand=hand,
            blinds=solve_grid.level_blinds(config, hand),
            states=states,
            sigma=layer["sigma"],
            v_index={state: position for position, state in enumerate(v_states)},
            v_next=v_next,
        )
        rows = solve_grid.forked_map(_margin_state_job, range(len(states)), workers)
        rows.sort(key=lambda item: item[0])
        margin = np.stack([row[1] for row in rows], axis=0)
        decision = np.stack([row[2] for row in rows], axis=0)
        defined = np.stack([row[3] for row in rows], axis=0)
        arrays[f"margin_{hand:02d}"] = margin
        arrays[f"decision_{hand:02d}"] = decision
        arrays[f"defined_{hand:02d}"] = defined
        live = decision[:, :, None] & defined
        values = margin[live].reshape(-1).tolist()
        all_values.extend(values)
        per_layer.append(
            {
                "hand": hand,
                "n_states": len(states),
                "n_infosets": len(values),
                "n_undefined": int((decision[:, :, None] & ~defined).sum()),
                "margin_max": max(values) if values else 0.0,
                "margin_median": float(statistics.median(values)) if values else 0.0,
            }
        )
        v_states, v_next = states, layer["v"]
    report: dict[str, Any] = {
        "pool": float(sum(config.prizes)),
        "states": sum(layer["states"].shape[0] for layer in layers.values()),
        "n_infosets": len(all_values),
        "n_undefined": sum(int(layer["n_undefined"]) for layer in per_layer),
        "margin_max": max(all_values) if all_values else 0.0,
        "margin_median": float(statistics.median(all_values)) if all_values else 0.0,
        "layers": sorted(per_layer, key=lambda item: item["hand"]),
    }
    artifacts.write_npz(out_dir / "margins.npz", arrays)
    artifacts.write_json(out_dir / "margins_report.json", report)
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sub = commands.add_parser("margins")
    sub.add_argument("--out", type=Path, required=True)
    sub.add_argument("--jobs", type=int, default=None)
    args = parser.parse_args(argv)
    report = run_margins(args.out, jobs=args.jobs)
    print(json.dumps({key: report[key] for key in report if key != "layers"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Łańcuch kontrolny biegu produkcyjnego blueprintu (POKER-50, decyzja 06 pkt 3).

Dwustopniowy dowód odtwarzalności artefaktu produkcyjnego:

1. **W bramce** — mały łańcuch kontrolny: tensor czterech klas (backend
   `table` jak w produkcji) → solver siatki 2-żetonowej → ex-post,
   porównywany z artefaktem kontrolnym w `tools/blueprint/control/`
   (jedynym artefaktem blueprintu w repo — decyzja 25 pkt 6). Zmiana kodu
   przesuwająca wynik zapala bramkę, zamiast po cichu unieważnić artefakt
   produkcyjny (PUŁAPKA regeneracji artefaktu).
2. **Poza bramką** — pełna regeneracja artefaktu produkcyjnego komendami
   z `docs/CURRENT_STATE.md` (blok POKER-50).

Parametry produkcyjne są tu przybite jako stałe: dokument je cytuje, testy
pilnują zgodności (PUŁAPKA: liczba w dokumencie = niezmiennik w teście).
Tablice tensora są całkowite, więc porównanie z artefaktem kontrolnym jest
dokładne; liczby łańcucha solvera niosą arytmetykę f32 (BLAS), więc
porównanie ma tolerancję `CONTROL_ABS_TOL` — identyczność bajt w bajt na
tej samej maszynie dowodzą testy wznowień.

Regeneracja artefaktu kontrolnego (venv z extras train):

    python tools/blueprint/control_chain.py --dir tools/blueprint/control
"""

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from poker.cards import Rank
from poker.preflop import CLASS_INDEX, PreflopClass


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
rollout_tensor = _sibling("rollout_tensor")
solve_grid = _sibling("solve_grid")
expost = _sibling("expost")

# Parametry tensora produkcyjnego (kontrakt POKER-50): 15 000 prób na
# multizbiór trójek; pary HU proporcjonalnie do pilota POKER-46/49
# (8 000 x 7,5 = 60 000, ponad podłogą kontraktu 32 000); seed jawny.
PROD_TRIALS = 15_000
PROD_HU_TRIALS = 60_000
PROD_SEED = 50
# Siatka produkcyjna: krok 2 żetony, pełny zegar (decyzja 25 pkt 5).
PROD_GRID_STEP = 2

# Podzbiór tensora produkcyjnego reprodukowany w bramce: jedna trójka
# i jedna para o rozstrzelonych siłach (kotwica orientacji jak w POKER-49).
PROD_SUBSET_TRIPLE = ("AA", "KK", "72o")
PROD_SUBSET_PAIR = ("AA", "72o")

# Łańcuch kontrolny: cztery klasy, mała siatka o produkcyjnym kroku 2.
# Blindy (1,1) w pierwszej ręce trzymają stan startowy powyżej progu
# jam/fold (deep), a 34 żetony mieszczą na brzegu stan HU (0,16,18)
# o 8 bb efektywnych (hu-deep) — wycinek pokrywa wszystkie cztery tryby.
CONTROL_CLASSES = ("AA", "KK", "J8o", "72o")
CONTROL_TRIALS = 400
CONTROL_HU_TRIALS = 300
CONTROL_SEED = 50
CONTROL_ABS_TOL = 1e-5
CONTROL_DIR = Path(__file__).resolve().with_name("control")

_RANKS = {
    "A": Rank.ACE, "K": Rank.KING, "Q": Rank.QUEEN, "J": Rank.JACK, "T": Rank.TEN,
    "9": Rank.NINE, "8": Rank.EIGHT, "7": Rank.SEVEN, "6": Rank.SIX, "5": Rank.FIVE,
    "4": Rank.FOUR, "3": Rank.THREE, "2": Rank.TWO,
}


def class_index(name: str) -> int:
    """Indeks klasy preflop po nazwie w rodzaju 'AKs', 'QQ', '72o'."""
    high, low = _RANKS[name[0]], _RANKS[name[1]]
    suited = len(name) == 3 and name[2] == "s"
    return CLASS_INDEX[PreflopClass(high=high, low=low, suited=suited)]


def control_classes() -> tuple[int, ...]:
    return tuple(sorted(class_index(name) for name in CONTROL_CLASSES))


def control_config(jobs: int = 1) -> Any:
    """Konfiguracja wycinka produkcyjnego: krok siatki 2, wszystkie cztery tryby."""
    return solve_grid.GridConfig(
        levels=((1, 1), (1, 2)),
        hands_per_level=1,
        total_chips=34,
        start_stacks=(12, 10, 12),
        grid_step=PROD_GRID_STEP,
        classes=control_classes(),
        fp_max_iters=24,
        fp_check_every=8,
        fp_tol=1e-4,
        fp_restarts=2,
        cfr_iters=64,
        cfr_check_every=16,
        cfr_tol=1e-4,
        # Jeden cykl trzyma łańcuch w koszcie bramki; delta jest zapisana
        # w manifeście i porównywana, więc kotwica nie traci na skróceniu.
        tail_max_cycles=1,
        tail_tol=2e-3,
        jobs=jobs,
    )


def generate_control_tensor(out_dir: Path, table: np.ndarray | None = None) -> dict[str, Any]:
    manifest: dict[str, Any] = rollout_tensor.generate_artifacts(
        out_dir,
        trials=CONTROL_TRIALS,
        hu_trials=CONTROL_HU_TRIALS,
        master_seed=CONTROL_SEED,
        classes=control_classes(),
        jobs=1,
        backend="table",
        table=table,
    )
    return manifest


def run_control_chain(tensor_dir: Path, work_dir: Path, jobs: int = 1) -> dict[str, Any]:
    """Solver + ex-post na tensorze kontrolnym; zwraca liczby do porównania."""
    config = control_config(jobs)
    manifest = solve_grid.solve(config, tensor_dir, work_dir)
    report = expost.run_expost(work_dir, jobs=jobs)
    layers = solve_grid.load_layers(work_dir)
    start_v = layers[0]["v"][0]
    return {
        "config_hash": manifest["config_hash"],
        "boundary_cycles": manifest["boundary"]["cycles"],
        "boundary_delta": manifest["boundary"]["delta"],
        "start_v": [float(value) for value in start_v],
        "epsilon_max": report["epsilon_max"],
        "epsilon_median": report["epsilon_median"],
    }


def production_subset(table: np.ndarray | None) -> dict[str, Any]:
    """Zliczenia podzbioru tensora produkcyjnego — seed i próby produkcji."""
    triple = tuple(sorted(class_index(name) for name in PROD_SUBSET_TRIPLE))
    rng3 = np.random.Generator(np.random.PCG64(rollout_tensor.triple_seed(PROD_SEED, *triple)))
    counts3 = rollout_tensor.simulate_triple(triple, PROD_TRIALS, rng3, table)
    pair = tuple(sorted(class_index(name) for name in PROD_SUBSET_PAIR))
    rng2 = np.random.Generator(np.random.PCG64(rollout_tensor.pair_seed(PROD_SEED, *pair)))
    counts2 = rollout_tensor.simulate_pair(pair, PROD_HU_TRIALS, rng2, table)
    return {
        "triple": {"classes": list(triple), "counts": [int(x) for x in counts3]},
        "pair": {"classes": list(pair), "counts": [int(x) for x in counts2]},
    }


def regenerate(control_dir: Path, jobs: int = 1) -> dict[str, Any]:
    """Artefakt kontrolny w repo: tensor + liczby łańcucha + podzbiór produkcji."""
    table = rollout_tensor.build_value_table()
    generate_control_tensor(control_dir / "tensor", table=table)
    with tempfile.TemporaryDirectory() as raw:
        summary = run_control_chain(control_dir / "tensor", Path(raw) / "solve", jobs=jobs)
    payload: dict[str, Any] = {
        "control": summary,
        "production": {
            "trials": PROD_TRIALS,
            "hu_trials": PROD_HU_TRIALS,
            "master_seed": PROD_SEED,
            "grid_step": PROD_GRID_STEP,
            **production_subset(table),
        },
        "tolerance_abs": CONTROL_ABS_TOL,
    }
    artifacts.write_json(control_dir / "chain_control.json", payload)
    return payload


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=CONTROL_DIR)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args(argv)
    payload = regenerate(args.dir, jobs=args.jobs)
    print(json.dumps(payload["control"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

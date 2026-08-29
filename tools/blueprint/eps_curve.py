"""Krzywa ex-post ε vs budżet iteracji solvera gry etapowej (POKER-47/49, decyzja 25).

Mierzy na artefaktach zamkniętego biegu solvera to, czego pilot POKER-46 nie
rozstrzygał:

1. `curve` — dla próbki stanów `deep` (najgorsze ex-post z biegu plus losowa
   próbka o jawnym seedzie) przebieg **ε ex-post gry etapowej** po iteracjach
   PI-FP. ε etapowe = best response każdego miejsca przy zamrożonym profilu
   pozostałych i zamrożonej kontynuacji V biegu; to ten sam operator co ex-post
   po DAG-u z `expost.py`, obcięty do jednej warstwy. Tolerancja biegu jest
   w pomiarze wyłączona (`NO_TOLERANCE`), bo inaczej PI-FP kończy na niej,
   a nie na sufcie — i sufit nie mierzy niczego. Jeden bieg do najwyższego
   sufitu drabinki obsługuje całą drabinkę naraz: przy wyłączonej tolerancji
   ciąg profili nie zależy od sufitu, więc profil zwracany przez PI-FP
   z sufitem k to średnia z kroku k+1 tego samego ciągu (pilnuje tego test
   zgodności z `_fp_solve`). Przy okazji tego biegu zbierane są trzy testy
   odróżniające wolną zbieżność od cyklu fictitious play: nachylenie log ε vs
   log t, długości runów identycznego best response i stosunek ε ostatniej
   iteracji do ε najlepszej napotkanej.
2. `decompose` — rozkład ε ex-post po DAG-u na część **etapową** (naprawialną
   iteracjami w tym stanie) i **odziedziczoną** z warstw późniejszych. To ta
   część, której nie widać w self-ε solvera: self-ε jest dokładnie ε etapowym
   zapisanego profilu (raport to sprawdza polem `eps_stage_reported`), a ε
   ex-post dokłada do niego dług wszystkich warstw za nim.
3. `budget` — odczyt z zapisanej krzywej: najmniejszy sufit, przy którym stan
   schodzi do zadanego progu ε, z kosztem tego sufitu.
4. `cost` — koszt rozwiązania stanu per tryb pod KONFIGURACJĄ BIEGU (tolerancja
   działa, więc to koszt produkcyjny), podkład pod ekstrapolację siatki.

Uruchomienie (venv z extras train):

    python tools/blueprint/eps_curve.py curve --out KATALOG \\
        --ladder 24,48,96,192,384 --worst 10 --extra 10 --seed 47 --jobs 4
    python tools/blueprint/eps_curve.py decompose --out KATALOG --worst 10
    python tools/blueprint/eps_curve.py budget --report KATALOG/eps_curve.json
    python tools/blueprint/eps_curve.py cost --out KATALOG --per-mode 10 --jobs 1

`--mode` przestawia próbkę na inny tryb gry etapowej (domyślnie `deep`); tryby
`hu-*` mierzą CFR+, a nie PI-FP — solverem drabinki jest ten, którym bieg
rozwiązuje dany tryb. `--dense N` dokłada ocenę ε po każdej z pierwszych N
iteracji, żeby na jednym złym stanie było widać kształt przebiegu, a nie tylko
punkty drabinki (wyłącznie dla PI-FP: CFR+ mierzy każdy sufit osobnym biegiem).
"""

import argparse
import dataclasses
import gc
import importlib.util
import json
import math
import random
import statistics
import sys
import time
from dataclasses import dataclass
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
expost = _sibling("expost")

DEFAULT_LADDER = (24, 48, 96, 192, 384)

# ε ex-post jest z konstrukcji nieujemne, więc ujemna tolerancja nigdy nie kończy
# PI-FP: w pomiarze krzywej sufit iteracji ma być jedynym ogranicznikiem.
NO_TOLERANCE = -1.0

DEEP = solve_grid.MODE_NAMES.index("deep")


@dataclass(frozen=True)
class SampleState:
    hand: int
    state: tuple[int, int, int]
    eps_dag: float
    source: str


def deep_entries(
    layers: dict[int, dict[str, np.ndarray]], eps_arrays: dict[str, np.ndarray],
    mode: str = "deep",
) -> list[SampleState]:
    """Stany danego trybu, malejąco po ε ex-post po DAG-u (maksimum po żywych miejscach)."""
    wanted = solve_grid.MODE_NAMES.index(mode)
    entries: list[SampleState] = []
    for hand in sorted(layers):
        layer = layers[hand]
        eps = eps_arrays[f"eps_{hand:02d}"]
        for position, row in enumerate(layer["states"].tolist()):
            if int(layer["mode"][position]) != wanted:
                continue
            state = (int(row[0]), int(row[1]), int(row[2]))
            alive = [seat for seat in range(3) if state[seat] > 0]
            worst = max(float(eps[position, seat]) for seat in alive)
            entries.append(SampleState(hand, state, worst, "worst"))
    entries.sort(key=lambda item: (-item.eps_dag, item.hand, item.state))
    return entries


def sample_states(
    layers: dict[int, dict[str, np.ndarray]], eps_arrays: dict[str, np.ndarray],
    worst: int, extra: int, seed: int, mode: str = "deep",
) -> tuple[SampleState, ...]:
    entries = deep_entries(layers, eps_arrays, mode)
    if not entries:
        raise ValueError(f"bieg nie ma stanów {mode} — krzywa nie ma czego mierzyć")
    chosen = list(entries[:worst])
    rest = entries[worst:]
    picks = random.Random(seed).sample(range(len(rest)), min(extra, len(rest)))
    chosen.extend(
        dataclasses.replace(rest[index], source="random") for index in sorted(picks)
    )
    return tuple(chosen)


def _continuation(
    config: Any, layers: dict[int, dict[str, np.ndarray]], boundary_v: np.ndarray,
    full_states: tuple[tuple[int, int, int], ...], hand: int,
) -> Any:
    """Kontynuacja V zamrożona na wartościach biegu — tak jak widział ją solver."""
    if hand >= solve_grid.n_hands(config) - 1:
        states, values = full_states, boundary_v
    else:
        layer = layers[hand + 1]
        states = tuple((int(a), int(b), int(c)) for a, b, c in layer["states"].tolist())
        values = layer["v"]
    index = {state: position for position, state in enumerate(states)}
    step = config.grid_step

    def lookup(target: tuple[int, int, int]) -> np.ndarray:
        return np.asarray(values[index[solve_grid.quantize_stacks(target, step)]])

    return lookup


class _Recorder:
    """Bierny obserwator PI-FP: ε w punktach drabinki, runy best response, koszt CPU.

    Zegar jest osobny dla każdego restartu i zerowany na jego początku, bo bieg
    z sufitem k płaci k iteracji w KAŻDYM restarcie, a nie pełny pierwszy
    restart plus k iteracji drugiego; koszt punktu to suma po restartach. Czas
    oceny ε z zegara wypada — koszt punktu ma być kosztem samego solvera.
    """

    def __init__(self, problem: Any, budgets: tuple[int, ...]) -> None:
        self.problem = problem
        self.checkpoints = {budget + 1: budget for budget in budgets}
        self.eps: dict[str, dict[int, float]] = {}
        self.seconds: dict[str, dict[int, float]] = {}
        self.runs: dict[str, list[int]] = {}
        self._style: str | None = None
        self._spent = 0.0
        self._mark = time.process_time()
        self._previous: dict[int, np.ndarray] | None = None
        self._run = 0

    def __call__(self, style: str, step: int, average: dict[int, np.ndarray],
                 reply: dict[int, np.ndarray]) -> None:
        elapsed = time.process_time() - self._mark
        if style != self._style:
            if self._style is not None and self._run:
                self.runs[self._style].append(self._run)
            self._style = style
            self._spent = elapsed
            self._previous = None
            self._run = 0
            self.eps[style] = {}
            self.seconds[style] = {}
            self.runs[style] = []
        else:
            self._spent += elapsed
        if self._previous is not None and all(
            np.array_equal(reply[node_id], self._previous[node_id]) for node_id in reply
        ):
            self._run += 1
        else:
            if self._run:
                self.runs[style].append(self._run)
            self._run = 1
        self._previous = {node_id: matrix.copy() for node_id, matrix in reply.items()}
        budget = self.checkpoints.get(step)
        if budget is not None:
            self.eps[style][budget] = float(solve_grid._internal_eps(self.problem, average))
            self.seconds[style][budget] = self._spent
        self._mark = time.process_time()

    def close(self) -> None:
        if self._style is not None and self._run:
            self.runs[self._style].append(self._run)

    def merged(self, budgets: tuple[int, ...]) -> tuple[list[float], list[float]]:
        """ε to minimum po restartach (tak wybiera profil `_fp_solve`), koszt to ich suma."""
        eps = [min(self.eps[style][budget] for style in self.eps) for budget in budgets]
        seconds = [
            sum(self.seconds[style][budget] for style in self.seconds) for budget in budgets
        ]
        return eps, seconds


class _CfrClock:
    """Zegar solvera CFR+: sumuje czas iteracji, pomijając ocenę ε po ostatniej."""

    def __init__(self) -> None:
        self.spent = 0.0
        self._mark = time.process_time()

    def __call__(self, step: int, current: dict[int, np.ndarray]) -> None:
        self.spent += time.process_time() - self._mark
        self._mark = time.process_time()


def _cfr_ladder(problem: Any, config: Any,
                budgets: tuple[int, ...]) -> tuple[list[float], list[float]]:
    """Drabinka dla endgame'u HU: CFR+ nie ma restartów, więc każdy sufit osobnym biegiem.

    Ciąg profili CFR+ zależy od własnej średniej tylko przez ε, a tolerancja jest
    w pomiarze wyłączona, więc bieg z sufitem k to prefiks biegu dłuższego —
    osobny bieg mierzy dokładnie koszt tego sufitu.
    """
    eps: list[float] = []
    seconds: list[float] = []
    for budget in budgets:
        capped = dataclasses.replace(
            config, cfr_iters=budget, cfr_check_every=budget, cfr_tol=NO_TOLERANCE
        )
        clock = _CfrClock()
        _, value, iterations = solve_grid._cfr_plus_solve(problem, capped, observer=clock)
        if iterations != budget:
            raise AssertionError(f"CFR+ skrócił pomiar do {iterations} przy sufcie {budget}")
        eps.append(value)
        seconds.append(clock.spent)
    return eps, seconds


_CWORK: dict[str, Any] = {}


def _curve_job(index: int) -> dict[str, Any]:
    entry: SampleState = _CWORK["sample"][index]
    config = _CWORK["config"]
    budgets: tuple[int, ...] = _CWORK["budgets"]
    sb, bb_amt = solve_grid.level_blinds(config, entry.hand)
    problem, _, mode = solve_grid.build_stage_problem(
        _CWORK["tensors"], config, entry.state, entry.hand, sb, bb_amt,
        _CWORK["lookups"][entry.hand],
    )
    recorder: _Recorder | None = None
    if problem.n_roles == 2:
        eps, seconds = _cfr_ladder(problem, config, budgets)
    else:
        recorder = _Recorder(problem, budgets)
        capped = dataclasses.replace(
            config, fp_max_iters=max(budgets) + 1, fp_check_every=max(budgets) + 1,
            fp_tol=NO_TOLERANCE,
        )
        solve_grid._fp_solve(problem, capped, observer=recorder)
        recorder.close()
        eps, seconds = recorder.merged(budgets)
    best = min(range(len(budgets)), key=lambda position: eps[position])
    row = {
        "index": index,
        "hand": entry.hand,
        "state": list(entry.state),
        "source": entry.source,
        "mode": mode,
        "eps_dag": entry.eps_dag,
        "budgets": list(budgets),
        "eps": eps,
        "core_seconds": seconds,
        "eps_best": eps[best],
        "budget_best": budgets[best],
        "run_lengths": (
            {} if recorder is None else {style: recorder.runs[style] for style in recorder.runs}
        ),
    }
    del problem
    gc.collect()
    return row


def _slope(first: tuple[float, float], second: tuple[float, float]) -> float:
    """Nachylenie log ε vs log t; −0,5 to tempo 1/√t, płasko to plateau albo cykl."""
    (t_a, e_a), (t_b, e_b) = first, second
    if e_a <= 0.0 or e_b <= 0.0 or t_a <= 0.0 or t_b <= 0.0 or t_a == t_b:
        return float("nan")
    return math.log(e_b / e_a) / math.log(t_b / t_a)


def eps_curve(
    out_dir: Path, ladder: tuple[int, ...] = DEFAULT_LADDER, worst: int = 10,
    extra: int = 10, seed: int = 47, jobs: int = 1, dense: int = 0,
    mode: str = "deep", report_name: str = "eps_curve.json",
) -> dict[str, Any]:
    config, tensors, layers, boundary_v = expost.load_run(out_dir)
    eps_arrays = artifacts.read_npz(out_dir / "expost.npz")
    full_states = solve_grid.grid_states(config.total_chips, config.grid_step)
    sample = sample_states(layers, eps_arrays, worst, extra, seed, mode)
    budgets = tuple(sorted(set(ladder) | set(range(1, dense + 1))))
    _CWORK.update(
        config=config,
        tensors=tensors,
        sample=sample,
        budgets=budgets,
        lookups={
            entry.hand: _continuation(config, layers, boundary_v, full_states, entry.hand)
            for entry in sample
        },
    )
    rows = solve_grid.forked_map(_curve_job, range(len(sample)), jobs)
    rows.sort(key=lambda row: row["index"])
    points: list[dict[str, Any]] = []
    for cap in ladder:
        position = budgets.index(cap)
        values = [row["eps"][position] for row in rows]
        seconds = [row["core_seconds"][position] for row in rows]
        points.append(
            {
                "iters": cap,
                "eps_max": max(values),
                "eps_median": float(statistics.median(values)),
                "eps_min": min(values),
                "core_seconds_per_state": float(statistics.mean(seconds)),
                "core_seconds_total": float(sum(seconds)),
            }
        )
    for previous, point in zip(points, points[1:], strict=False):
        point["log_slope_vs_previous"] = _slope(
            (float(previous["iters"]), previous["eps_max"]),
            (float(point["iters"]), point["eps_max"]),
        )
    # Gdyby PI-FP oscylował, najlepszy napotkany profil bywałby wcześniejszy niż ostatni.
    earlier_best = [row for row in rows if row["budget_best"] != max(row["budgets"])]
    report: dict[str, Any] = {
        "run": str(out_dir.resolve()),
        "tensor_dir": str(Path(artifacts.read_json(out_dir / "solve_manifest.json")["tensor_dir"])),
        "ladder": list(ladder),
        "mode": mode,
        "dense": dense,
        "seed": seed,
        "restarts": config.fp_restarts,
        "n_states": len(sample),
        "sample": [
            {"hand": entry.hand, "state": list(entry.state), "eps_dag": entry.eps_dag,
             "source": entry.source}
            for entry in sample
        ],
        "points": points,
        "per_state": rows,
        "diagnosis": {
            "log_slope_overall": _slope(
                (float(ladder[0]), points[0]["eps_max"]),
                (float(ladder[-1]), points[-1]["eps_max"]),
            ),
            "states_with_better_earlier_budget": len(earlier_best),
            "max_eps_last_over_best": max(
                (row["eps"][-1] / row["eps_best"] if row["eps_best"] > 0.0 else 1.0)
                for row in rows
            ),
            "max_run_length": max(
                max((max(runs) for runs in row["run_lengths"].values() if runs), default=0)
                for row in rows
            ),
        },
    }
    artifacts.write_json(out_dir / report_name, report)
    return report


def _cost_job(index: int) -> dict[str, Any]:
    entry: SampleState = _CWORK["sample"][index]
    config = _CWORK["config"]
    sb, bb_amt = solve_grid.level_blinds(config, entry.hand)
    problem, _, mode = solve_grid.build_stage_problem(
        _CWORK["tensors"], config, entry.state, entry.hand, sb, bb_amt,
        _CWORK["lookups"][entry.hand],
    )
    started = time.process_time()
    if problem.n_roles == 3:
        _, eps, iterations = solve_grid._fp_solve(problem, config)
    else:
        _, eps, iterations = solve_grid._cfr_plus_solve(problem, config)
    seconds = time.process_time() - started
    del problem
    gc.collect()
    return {"index": index, "mode": mode, "core_seconds": seconds,
            "iterations": iterations, "eps": eps}


def mode_costs(
    out_dir: Path, per_mode: int = 10, seed: int = 47, jobs: int = 1
) -> dict[str, Any]:
    """Koszt rozwiązania stanu per tryb pod KONFIGURACJĄ BIEGU — podkład ekstrapolacji.

    Budżet bierze się z manifestu biegu, nie z pomiaru krzywej: tolerancja
    działa, więc mierzony jest koszt produkcyjny, a nie koszt pełnego sufitu.
    """
    config, tensors, layers, boundary_v = expost.load_run(out_dir)
    eps_arrays = artifacts.read_npz(out_dir / "expost.npz")
    full_states = solve_grid.grid_states(config.total_chips, config.grid_step)
    sample: list[SampleState] = []
    for name in solve_grid.MODE_NAMES:
        entries = deep_entries(layers, eps_arrays, name)
        if not entries:
            continue
        picks = random.Random(seed).sample(range(len(entries)), min(per_mode, len(entries)))
        sample.extend(entries[index] for index in sorted(picks))
    _CWORK.update(
        config=config,
        tensors=tensors,
        sample=tuple(sample),
        lookups={
            entry.hand: _continuation(config, layers, boundary_v, full_states, entry.hand)
            for entry in sample
        },
    )
    rows = solve_grid.forked_map(_cost_job, range(len(sample)), jobs)
    rows.sort(key=lambda row: row["index"])
    modes = []
    for name in solve_grid.MODE_NAMES:
        picked = [row for row in rows if row["mode"] == name]
        if not picked:
            continue
        seconds = [row["core_seconds"] for row in picked]
        modes.append(
            {
                "mode": name,
                "n_states": len(picked),
                "core_seconds_median": float(statistics.median(seconds)),
                "core_seconds_max": max(seconds),
                "iterations_median": float(
                    statistics.median([row["iterations"] for row in picked])
                ),
                "eps_max": max(row["eps"] for row in picked),
            }
        )
    report = {
        "run": str(out_dir.resolve()),
        "seed": seed,
        "per_mode": per_mode,
        "fp_max_iters": config.fp_max_iters,
        "fp_tol": config.fp_tol,
        "cfr_iters": config.cfr_iters,
        "cfr_tol": config.cfr_tol,
        "modes": modes,
    }
    artifacts.write_json(out_dir / "mode_costs.json", report)
    return report


DEFAULT_TARGETS = (1e-3, 5e-4, 1e-4, 5e-5, 1e-5)


def budgets_for_targets(
    report: dict[str, Any], targets: tuple[float, ...] = DEFAULT_TARGETS
) -> list[dict[str, Any]]:
    """Najmniejszy sufit drabinki, przy którym stan schodzi do progu ε — próbka jak w raporcie.

    To jest odczyt krzywej, nie nowy pomiar: budżet produkcyjny bierze się
    z tej tabeli, a nie z założenia (PUŁAPKA o kryteriach ilościowych).
    """
    rows: list[dict[str, Any]] = []
    for target in targets:
        reached: list[int] = []
        seconds: list[float] = []
        missed = 0
        for state in report["per_state"]:
            hits = [
                position for position, value in enumerate(state["eps"])
                if value <= target and state["budgets"][position] in report["ladder"]
            ]
            if not hits:
                missed += 1
                continue
            reached.append(state["budgets"][hits[0]])
            seconds.append(state["core_seconds"][hits[0]])
        rows.append(
            {
                "epsilon": target,
                "n_reached": len(reached),
                "n_unreached": missed,
                "budget_median": None if not reached else statistics.median(reached),
                "budget_max": None if not reached else max(reached),
                "core_seconds_median": None if not seconds else statistics.median(seconds),
                "core_seconds_max": None if not seconds else max(seconds),
            }
        )
    return rows


_DWORK: dict[str, Any] = {}


def _decompose_job(index: int) -> dict[str, Any]:
    entry: SampleState = _DWORK["sample"][index]
    config = _DWORK["config"]
    layer = _DWORK["layers"][entry.hand]
    states = [tuple(int(x) for x in row) for row in layer["states"].tolist()]
    position = states.index(entry.state)
    sb, bb_amt = solve_grid.level_blinds(config, entry.hand)
    problem, role_seats, mode = solve_grid.build_stage_problem(
        _DWORK["tensors"], config, entry.state, entry.hand, sb, bb_amt,
        _DWORK["lookups"][entry.hand],
    )
    sigma = {node_id: layer["sigma"][position, node_id] for node_id in problem.nodes}
    values = solve_grid._profile_values(problem, sigma)
    stage = np.full(3, 0.0)
    for role, seat in enumerate(role_seats):
        _, _, root = solve_grid._hero_action_values(problem, role, sigma, "best")
        stage[seat] = float(root.sum()) / problem.total_weight - float(values[role])
    dag = _DWORK["eps"][f"eps_{entry.hand:02d}"][position]
    alive = [seat for seat in range(3) if entry.state[seat] > 0]
    dag_max = max(float(dag[seat]) for seat in alive)
    stage_max = max(float(stage[seat]) for seat in alive)
    del problem
    gc.collect()
    return {
        "index": index,
        "hand": entry.hand,
        "state": list(entry.state),
        "mode": mode,
        "eps_dag": [float(dag[seat]) for seat in range(3)],
        "eps_stage": [float(stage[seat]) for seat in range(3)],
        "eps_dag_max": dag_max,
        "eps_stage_max": stage_max,
        "eps_stage_reported": float(layer["eps"][position]),
        "inherited_share": 0.0 if dag_max <= 0.0 else max(0.0, 1.0 - stage_max / dag_max),
        "iterations": int(layer["iters"][position]),
    }


def decompose(out_dir: Path, worst: int = 10, jobs: int = 1) -> dict[str, Any]:
    config, tensors, layers, boundary_v = expost.load_run(out_dir)
    eps_arrays = artifacts.read_npz(out_dir / "expost.npz")
    full_states = solve_grid.grid_states(config.total_chips, config.grid_step)
    sample = deep_entries(layers, eps_arrays)[:worst]
    _DWORK.update(
        config=config,
        tensors=tensors,
        layers=layers,
        sample=sample,
        eps=eps_arrays,
        lookups={
            entry.hand: _continuation(config, layers, boundary_v, full_states, entry.hand)
            for entry in sample
        },
    )
    rows = solve_grid.forked_map(_decompose_job, range(len(sample)), jobs)
    rows.sort(key=lambda row: row["index"])
    per_layer: list[dict[str, Any]] = []
    by_mode: dict[str, list[tuple[float, int]]] = {name: [] for name in solve_grid.MODE_NAMES}
    for hand in sorted(layers):
        layer = layers[hand]
        eps = eps_arrays[f"eps_{hand:02d}"]
        alive = layer["states"] > 0
        for value, mode, iterations in zip(
            layer["eps"], layer["mode"], layer["iters"], strict=True
        ):
            by_mode[solve_grid.MODE_NAMES[int(mode)]].append((float(value), int(iterations)))
        per_layer.append(
            {
                "hand": hand,
                "n_states": int(layer["states"].shape[0]),
                "n_deep": int((layer["mode"] == DEEP).sum()),
                "eps_dag_max": float(eps[alive].max()),
                "eps_dag_median": float(np.median(eps[alive])),
                "eps_stage_max": float(layer["eps"].max()),
                "eps_stage_median": float(np.median(layer["eps"])),
                "at_tolerance": int((layer["eps"] <= config.fp_tol).sum()),
                "at_iteration_cap": int((layer["iters"] == config.fp_max_iters).sum()),
            }
        )
    modes = [
        {
            "mode": name,
            "n_states": len(rows),
            "eps_stage_max": max(value for value, _ in rows),
            "eps_stage_median": float(statistics.median([value for value, _ in rows])),
            "above_tolerance": sum(1 for value, _ in rows if value > config.fp_tol),
            "at_iteration_cap": sum(1 for _, it in rows if it == config.fp_max_iters),
            "iterations_median": float(statistics.median([it for _, it in rows])),
        }
        for name, rows in by_mode.items()
        if rows
    ]
    report = {
        "run": str(out_dir.resolve()),
        "fp_max_iters": config.fp_max_iters,
        "fp_tol": config.fp_tol,
        "states": rows,
        "inherited_share_median": float(
            statistics.median([row["inherited_share"] for row in rows])
        ),
        "modes": modes,
        "layers": per_layer,
    }
    artifacts.write_json(out_dir / "eps_decomposition.json", report)
    return report


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    curve = commands.add_parser("curve")
    curve.add_argument("--out", type=Path, required=True)
    curve.add_argument("--ladder", type=str, default=",".join(str(x) for x in DEFAULT_LADDER))
    curve.add_argument("--worst", type=int, default=10)
    curve.add_argument("--extra", type=int, default=10)
    curve.add_argument("--seed", type=int, default=47)
    curve.add_argument("--jobs", type=int, default=1)
    curve.add_argument("--dense", type=int, default=0)
    curve.add_argument("--mode", type=str, default="deep", choices=solve_grid.MODE_NAMES)
    curve.add_argument("--report", type=str, default="eps_curve.json")
    split = commands.add_parser("decompose")
    split.add_argument("--out", type=Path, required=True)
    split.add_argument("--worst", type=int, default=10)
    split.add_argument("--jobs", type=int, default=1)
    cost = commands.add_parser("cost")
    cost.add_argument("--out", type=Path, required=True)
    cost.add_argument("--per-mode", type=int, default=10)
    cost.add_argument("--seed", type=int, default=47)
    cost.add_argument("--jobs", type=int, default=1)
    budget = commands.add_parser("budget")
    budget.add_argument("--report", type=Path, required=True)
    budget.add_argument("--targets", type=str,
                        default=",".join(str(x) for x in DEFAULT_TARGETS))
    args = parser.parse_args(argv)
    if args.command == "budget":
        rows = budgets_for_targets(
            artifacts.read_json(args.report),
            tuple(float(part) for part in args.targets.split(",")),
        )
        print(json.dumps(rows, ensure_ascii=False))
    elif args.command == "cost":
        print(json.dumps(
            mode_costs(args.out, per_mode=args.per_mode, seed=args.seed, jobs=args.jobs),
            ensure_ascii=False))
    elif args.command == "curve":
        report = eps_curve(
            args.out,
            ladder=tuple(int(part) for part in args.ladder.split(",")),
            worst=args.worst, extra=args.extra, seed=args.seed, jobs=args.jobs,
            dense=args.dense, mode=args.mode, report_name=args.report,
        )
        print(json.dumps({"points": report["points"], "diagnosis": report["diagnosis"]},
                         ensure_ascii=False))
    else:
        report = decompose(args.out, worst=args.worst, jobs=args.jobs)
        print(json.dumps(
            {"inherited_share_median": report["inherited_share_median"],
             "modes": report["modes"],
             "states": [{key: row[key] for key in ("hand", "state", "eps_dag_max",
                                                   "eps_stage_max", "inherited_share")}
                        for row in report["states"]]},
            ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

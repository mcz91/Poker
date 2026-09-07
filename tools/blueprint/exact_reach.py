"""Łańcuch dokładny warstw 0–5 (POKER-58, decyzja 29 P-3).

Trening kwantyzuje stacki po każdej ręce i idzie tylko po tych kluczach.
Arena trzyma stacki dokładne i kwantyzuje dopiero przy odczycie artefaktu.
Po dwóch-trzech rękach dokładny łańcuch ląduje na kluczu, którego trening
nie odwiedził — to jest fallback „stan spoza warstwy".

Ten moduł liczy oba zbiory, ich różnicę per ręka i wycenę solve'a różnicy
z temp per-mode POKER-56. Bezpiecznik: wycena > 15 rdzenio-h → STOP.

    python tools/blueprint/exact_reach.py report --through 5 --grid-step 2
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from poker.spin import SOLVER_MODES, solver_mode

COST_STOP_CORE_HOURS = 15.0


def _sibling(name: str) -> ModuleType:
    module = sys.modules.get(name)
    if module is not None:
        return module
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"brak modułu siostrzanego {name}")
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


solve_grid = _sibling("solve_grid")
mode_census = _sibling("mode_census")


def enumerate_exact_transitions(
    config: Any,
    seat_stacks: tuple[int, int, int],
    hand: int,
    sb: int,
    bb_amt: int,
) -> set[tuple[int, int, int]]:
    """Dokładne stany następne (żywi ≥ 2) — kwantyzacja dopiero u konsumenta."""
    found: set[tuple[int, int, int]] = set()

    def collecting_lookup(state: tuple[int, int, int]) -> np.ndarray:
        if sum(1 for value in state if value > 0) >= 2:
            found.add((int(state[0]), int(state[1]), int(state[2])))
        return np.zeros(3, dtype=np.float64)

    solve_grid.build_stage_problem(
        solve_grid._transition_tensors(),
        config,
        seat_stacks,
        hand,
        sb,
        bb_amt,
        collecting_lookup,
    )
    return found


def quantized_layers(config: Any, through_hand: int) -> list[tuple[tuple[int, int, int], ...]]:
    """Łańcuch treningowy: kwantyzacja na każdym przejściu (to, co liczy solver)."""
    if through_hand < 0:
        raise ValueError(f"through_hand nie może być ujemny: {through_hand}")
    layers = solve_grid._reachable_sets(config)
    return [tuple(layer) for layer in layers[: through_hand + 1]]


def exact_layers(config: Any, through_hand: int) -> list[tuple[tuple[int, int, int], ...]]:
    """Łańcuch dokładny: stacki bez kwantyzacji między rękami."""
    if through_hand < 0:
        raise ValueError(f"through_hand nie może być ujemny: {through_hand}")
    start = (
        int(config.start_stacks[0]),
        int(config.start_stacks[1]),
        int(config.start_stacks[2]),
    )
    layers: list[tuple[tuple[int, int, int], ...]] = [(start,)]
    for hand in range(through_hand):
        sb, bb_amt = solve_grid.level_blinds(config, hand)
        found: set[tuple[int, int, int]] = set()
        for state in layers[hand]:
            found |= enumerate_exact_transitions(config, state, hand, sb, bb_amt)
        layers.append(tuple(sorted(found)))
    return layers


def grid_keys(
    exact: tuple[tuple[int, int, int], ...], step: int
) -> tuple[tuple[int, int, int], ...]:
    """Klucze siatki, pod którymi arena odczyta te dokładne stany."""
    return tuple(sorted({solve_grid.quantize_stacks(state, step) for state in exact}))


@dataclass(frozen=True, slots=True)
class HandGap:
    hand: int
    exact_states: int
    exact_keys: int
    trained_keys: int
    missing_keys: tuple[tuple[int, int, int], ...]
    extra_trained: int
    missing_modes: dict[str, int]
    missing_core_hours: float


def hand_gap(
    config: Any,
    hand: int,
    exact: tuple[tuple[int, int, int], ...],
    trained: tuple[tuple[int, int, int], ...],
) -> HandGap:
    keys = set(grid_keys(exact, config.grid_step))
    trained_set = set(trained)
    missing = tuple(sorted(keys - trained_set))
    extra = len(trained_set - keys)
    _, bb_amt = solve_grid.level_blinds(config, hand)
    modes = dict.fromkeys(SOLVER_MODES, 0)
    for state in missing:
        modes[solver_mode(state, bb_amt)] += 1
    return HandGap(
        hand=hand,
        exact_states=len(exact),
        exact_keys=len(keys),
        trained_keys=len(trained_set),
        missing_keys=missing,
        extra_trained=extra,
        missing_modes=modes,
        missing_core_hours=mode_census.core_hours(modes),
    )


def difference_report(config: Any, through_hand: int = 5) -> dict[str, Any]:
    """Różnica łańcucha dokładnego wobec treningowego, z wyceną solve'a luki."""
    exact = exact_layers(config, through_hand)
    trained = quantized_layers(config, through_hand)
    gaps = [
        hand_gap(config, hand, exact[hand], trained[hand])
        for hand in range(through_hand + 1)
    ]
    total_modes = dict.fromkeys(SOLVER_MODES, 0)
    for gap in gaps:
        for mode, count in gap.missing_modes.items():
            total_modes[mode] += count
    total_hours = mode_census.core_hours(total_modes)
    return {
        "total_chips": config.total_chips,
        "grid_step": config.grid_step,
        "start_stacks": list(config.start_stacks),
        "through_hand": through_hand,
        "per_hand": [
            {
                "hand": gap.hand,
                "exact_states": gap.exact_states,
                "exact_keys": gap.exact_keys,
                "trained_keys": gap.trained_keys,
                "missing_keys": len(gap.missing_keys),
                "extra_trained": gap.extra_trained,
                "missing_modes": gap.missing_modes,
                "missing_core_hours": gap.missing_core_hours,
            }
            for gap in gaps
        ],
        "missing_modes": total_modes,
        "missing_states": sum(len(gap.missing_keys) for gap in gaps),
        "missing_core_hours": total_hours,
        "cost_stop_core_hours": COST_STOP_CORE_HOURS,
        "stop": total_hours > COST_STOP_CORE_HOURS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Różnica łańcucha dokładnego wobec treningowego przed solve'em."
    )
    parser.add_argument("--through", type=int, default=5, help="ostatnia ręka (domyślnie 5)")
    parser.add_argument("--grid-step", type=int, default=2)
    args = parser.parse_args(argv)
    config = solve_grid.GridConfig(grid_step=args.grid_step)
    report = difference_report(config, through_hand=args.through)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["stop"]:
        print(
            f"STOP: wycena luki {report['missing_core_hours']:.2f} rdzenio-h "
            f"> {COST_STOP_CORE_HOURS} — nie ruszamy solve'a",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

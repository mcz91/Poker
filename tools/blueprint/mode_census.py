"""Wycena przebiegu solvera PER TRYB (POKER-56, decyzja 29 P-1).

Panel projektowy wyceniał kolejne przebiegi mnożnikiem liczby stanów — a koszt
stanu różni się między trybami o trzy rzędy wielkości (zmierzone w POKER-50:
`deep` 50,8 rdzenio-s/stan wobec `hu-jamfold` 0,018). Mnożnik liczby stanów
myli się więc w obie strony: siatka o mniejszej liczbie stanów bywa droższa,
jeśli ma więcej stanów głębokich, i odwrotnie. Ten moduł liczy MIESZANKĘ
TRYBÓW konfiguracji i dopiero z niej koszt.

Trzy rzeczy, których ta wycena NIE zgaduje:

1. **Osiągalność.** Wczesne warstwy nie są pełną siatką (bieg produkcyjny:
   1/18/147/691/2143/2920 stanów zamiast 2 923) i są najbardziej „głębokie",
   więc pełna siatka zamiast osiągalnej zawyżałaby koszt wielokrotnie.
   Osiągalność liczy `solve_grid._reachable_sets` — ta sama funkcja, którą
   idzie bieg, a nie jej kopia.
2. **Tryb stanu.** `poker.spin.solver_mode` — ta sama reguła, którą bieg
   zapisuje do manifestu i którą arena liczy udział decyzyjny trybów.
3. **Tempo.** `MEASURED_RATES` to tempa ZMIERZONE w biegu produkcyjnym
   (POKER-50 pkt 3), a nie priory pilota z bezpiecznika kosztu.

Kalibracja: na konfiguracji biegu produkcyjnego wycena daje 64,3 rdzenio-h
solvera wobec 65,4 zmierzonych (−1,7%); różnicę robi narzut forka i zbiórki,
którego tempa per stan nie niosą. Wycena jest więc dolnym oszacowaniem o kilka
procent, nie prognozą z przedziałem.

Uruchomienie (venv z extras train, z katalogu repozytorium):

    python tools/blueprint/mode_census.py table
    python tools/blueprint/mode_census.py table --preset T-MODAL
"""

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any

from poker.spin import SOLVER_MODES, solver_mode, tier_for_run


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


solve_grid = _sibling("solve_grid")

# Tempa ZMIERZONE w biegu produkcyjnym (POKER-50 pkt 3: rdzenio-sekundy na
# stan, warstwy plus horyzont). To nie są priory pilota z bezpiecznika kosztu
# (`solve_grid.MODE_COST_PRIORS`), który skaluje je kalibracją bieżącego biegu.
MEASURED_RATES: dict[str, float] = {
    "deep": 50.8,
    "jamfold": 1.83,
    "hu-deep": 0.054,
    "hu-jamfold": 0.018,
}

# Horyzont zbiegł w 6 cyklach na siatce 2 (POKER-50 pkt 2) — liczba cykli jest
# własnością zbieżności, nie siatki, więc dla innej konfiguracji to założenie,
# a nie pomiar; dlatego jest parametrem, a nie stałą wpisaną w koszt.
PRODUCTION_TAIL_CYCLES = 6

# Tensor rolloutów jest kartowy: nie zależy od siatki stacków ani od wypłat,
# więc kolejne tiery liczą się na TYM SAMYM tensorze i nie płacą go ponownie
# (11,2 rdzenio-h, POKER-50 pkt 1).
TENSOR_CORE_HOURS = 11.2


@dataclass(frozen=True)
class Census:
    """Mieszanka trybów przebiegu: warstwy osobno, horyzont osobno."""

    layers: tuple[dict[str, int], ...]
    boundary: dict[str, int]

    def layer_totals(self) -> dict[str, int]:
        return _merge(self.layers)

    def totals(self) -> dict[str, int]:
        return _merge((*self.layers, self.boundary))


def _merge(parts: tuple[dict[str, int], ...]) -> dict[str, int]:
    out = dict.fromkeys(SOLVER_MODES, 0)
    for part in parts:
        for mode, count in part.items():
            out[mode] += count
    return out


def _count_modes(states: tuple[tuple[int, int, int], ...], bb_amt: int) -> dict[str, int]:
    counts = dict.fromkeys(SOLVER_MODES, 0)
    for state in states:
        counts[solver_mode(state, bb_amt)] += 1
    return counts


@cache
def reachable_layers(config: Any) -> tuple[tuple[tuple[int, int, int], ...], ...]:
    """Osiągalne stany każdej warstwy — pamiętane, bo jedna konfiguracja to sekundy pracy."""
    return tuple(solve_grid._reachable_sets(config))


def layer_census(config: Any) -> tuple[dict[str, int], ...]:
    """Mieszanka trybów każdej warstwy przebiegu, z osiągalnością wczesnych warstw."""
    reachable = reachable_layers(config)
    out: list[dict[str, int]] = []
    for hand in range(solve_grid.n_hands(config)):
        _, bb_amt = solve_grid.level_blinds(config, hand)
        out.append(_count_modes(reachable[hand], bb_amt))
    return tuple(out)


def full_grid_census(config: Any, hand: int) -> dict[str, int]:
    """Mieszanka trybów PEŁNEJ siatki przy blindach tej ręki — górne ograniczenie warstwy."""
    _, bb_amt = solve_grid.level_blinds(config, hand)
    states = solve_grid.grid_states(config.total_chips, config.grid_step)
    return _count_modes(states, bb_amt)


def boundary_census(config: Any, cycles: int = PRODUCTION_TAIL_CYCLES) -> dict[str, int]:
    """Horyzont: `cycles` cykli po trzy warstwy pełnej siatki przy blindach ostatniego poziomu."""
    if cycles < 1:
        raise ValueError(f"horyzont liczy co najmniej jeden cykl: {cycles}")
    total = solve_grid.n_hands(config)
    _, bb_amt = solve_grid.level_blinds(config, total)
    states = solve_grid.grid_states(config.total_chips, config.grid_step)
    per_layer = _count_modes(states, bb_amt)
    return {mode: count * 3 * cycles for mode, count in per_layer.items()}


def census(config: Any, cycles: int = PRODUCTION_TAIL_CYCLES) -> Census:
    return Census(layers=layer_census(config), boundary=boundary_census(config, cycles))


def early_layers_gap(config: Any, through_hand: int) -> dict[str, int]:
    """Ile stanów-warstw brakuje do PEŁNEJ siatki w warstwach 1..`through_hand`.

    Ręka 0 zostaje poza rachunkiem: stan startowy jest jeden z definicji, a nie
    z przycięcia osiągalnością.
    """
    reachable = layer_census(config)
    gap = dict.fromkeys(SOLVER_MODES, 0)
    for hand in range(1, through_hand + 1):
        full = full_grid_census(config, hand)
        for mode in SOLVER_MODES:
            gap[mode] += full[mode] - reachable[hand][mode]
    return gap


def core_hours(counts: dict[str, int], rates: dict[str, float] | None = None) -> float:
    """Koszt mieszanki trybów w rdzenio-godzinach ze zmierzonych temp per stan."""
    table = MEASURED_RATES if rates is None else rates
    return sum(table[mode] * count for mode, count in counts.items()) / 3600.0


def tier_config(key: str, grid_step: int = 2, **overrides: Any) -> Any:
    """`GridConfig` tieru — wycena buduje tę samą konfigurację, którą puściłby bieg.

    Dlatego przechodzi przez `tier_for_run` z JAWNĄ flagą niepotwierdzonej
    tabeli: wycena nie pali rdzenio-godzin, ale liczba, która z niej wychodzi,
    trafia do decyzji o ich spaleniu.
    """
    tier = tier_for_run(key, allow_unconfirmed=True)
    fields: dict[str, Any] = {
        "prizes": tier.prizes,
        "hands_per_level": tier.hands_per_level,
        "total_chips": tier.total_chips,
        "start_stacks": (tier.start_stack,) * 3,
        "grid_step": grid_step,
    }
    fields.update(overrides)
    return solve_grid.GridConfig(**fields)


def presets() -> dict[str, Any]:
    """Konfiguracje z mapy kontraktów decyzji 29 — jedno miejsce, jedna definicja."""
    modal = tier_config("T-MODAL")
    return {
        # Bieg produkcyjny POKER-50 — wiersz kalibracyjny: jedyny, dla którego
        # istnieje zmierzony koszt, więc jedyny, który sprawdza samą wycenę.
        "prod-10x": tier_config("T-DEEP"),
        # P-7: jednozmienny A/B wypłat na siatce biegu produkcyjnego.
        "WTA@25bb": tier_config("T-DEEP", prizes=(1.0, 0.0, 0.0)),
        "T-MODAL": modal,
        "T-MID": tier_config("T-MID"),
        # P-6(a)/P-15: siatka kroku 1 na dzisiejszych żetonach.
        "krok-1": tier_config("T-DEEP", grid_step=1),
    }


def report(config: Any, cycles: int = PRODUCTION_TAIL_CYCLES) -> dict[str, Any]:
    hit = census(config, cycles)
    layers = hit.layer_totals()
    boundary = hit.boundary
    return {
        "total_chips": config.total_chips,
        "grid_step": config.grid_step,
        "prizes": list(config.prizes),
        "n_layers": len(hit.layers),
        "states_per_layer": [sum(counts.values()) for counts in hit.layers],
        "layer_modes": layers,
        "boundary_modes": boundary,
        "boundary_cycles": cycles,
        "layers_core_hours": core_hours(layers),
        "boundary_core_hours": core_hours(boundary),
        "solver_core_hours": core_hours(hit.totals()),
        "with_tensor_core_hours": core_hours(hit.totals()) + TENSOR_CORE_HOURS,
    }


def table(cycles: int = PRODUCTION_TAIL_CYCLES) -> dict[str, Any]:
    """Wycena wszystkich pozycji mapy kontraktów naraz — to, co wchodzi do dokumentu."""
    rows = {name: report(config, cycles) for name, config in presets().items()}
    prod = presets()["prod-10x"]
    gap = early_layers_gap(prod, 5)
    rows["warstwy-1-5-do-pelnej-siatki"] = {
        "gap_modes": gap,
        "gap_states": sum(gap.values()),
        "core_hours": core_hours(gap),
    }
    # DBR seat-restricted to TRZY przebiegi hero (decyzja 29 pkt 3B) na tym
    # samym tensorze — mnoży się koszt solvera, nie koszt tensora.
    rows["DBR-T-MODAL"] = {
        "hero_runs": 3,
        "solver_core_hours": 3 * rows["T-MODAL"]["solver_core_hours"],
        "with_tensor_core_hours": 3 * rows["T-MODAL"]["solver_core_hours"] + TENSOR_CORE_HOURS,
    }
    return {"rates_core_seconds_per_state": MEASURED_RATES, "rows": rows}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("table",))
    parser.add_argument("--preset", choices=sorted(presets()), default=None)
    parser.add_argument("--tail-cycles", type=int, default=PRODUCTION_TAIL_CYCLES)
    return parser


def main(argv: Any = None) -> int:
    args = build_parser().parse_args(argv)
    if args.preset is not None:
        out: dict[str, Any] = {args.preset: report(presets()[args.preset], args.tail_cycles)}
    else:
        out = table(args.tail_cycles)
    print(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

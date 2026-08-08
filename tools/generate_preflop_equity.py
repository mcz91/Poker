"""Generator macierzy equity preflop: deterministyczne Monte Carlo, moduł danych Pythona.

Uruchomienie (z korzenia repozytorium, w venv z zainstalowanym pakietem):

    python tools/generate_preflop_equity.py

Jedyna losowość to przybity seed macierzy; seed każdej pary klas pochodzi
z niego deterministycznie (poker.preflop_sim.pair_seed), więc wynik nie
zależy od liczby procesów ani kolejności wykonania. Przekątna (klasa vs
ta sama klasa) to z symetrii dokładnie 0.5, a lustro e(b,a) = 1 - e(a,b)
— oba zapisywane z konstrukcji, symulowany jest górny trójkąt macierzy.
"""

import argparse
import random
import sys
from multiprocessing import Pool
from pathlib import Path

from poker.preflop import ALL_CLASSES
from poker.preflop_sim import pair_seed, simulate_pair_units

CLASS_COUNT = len(ALL_CLASSES)
UNITS_PER_LINE = 12


def _simulate_task(task: tuple[int, int, int, int]) -> tuple[int, int, int]:
    master_seed, trials, index_a, index_b = task
    rng = random.Random(pair_seed(master_seed, index_a, index_b))
    units = simulate_pair_units(
        ALL_CLASSES[index_a], ALL_CLASSES[index_b], rng=rng, trials=trials
    )
    return index_a, index_b, units


def generate_matrix(master_seed: int, trials: int, jobs: int) -> list[list[int]]:
    matrix = [[trials] * CLASS_COUNT for _ in range(CLASS_COUNT)]
    tasks = [
        (master_seed, trials, index_a, index_b)
        for index_a in range(CLASS_COUNT)
        for index_b in range(index_a + 1, CLASS_COUNT)
    ]
    with Pool(jobs) as pool:
        for done, (index_a, index_b, units) in enumerate(
            pool.imap_unordered(_simulate_task, tasks, chunksize=8), start=1
        ):
            matrix[index_a][index_b] = units
            matrix[index_b][index_a] = 2 * trials - units
            if done % 500 == 0 or done == len(tasks):
                print(f"pary: {done}/{len(tasks)}", file=sys.stderr, flush=True)
    return matrix


def render_module(matrix: list[list[int]], master_seed: int, trials: int) -> str:
    flat = [units for row in matrix for units in row]
    lines = [
        '"""Wygenerowana macierz equity all-in preflop (POKER-12) — nie edytować ręcznie.',
        "",
        "Regeneracja: python tools/generate_preflop_equity.py",
        "Jednostki pół-puli (2·wygrane + splity) na 2·TRIALS_PER_PAIR; indeks",
        "wiersza/kolumny zgodny z poker.preflop.ALL_CLASSES (płaska macierz",
        "wiersz·169 + kolumna). Przekątna 0.5 i lustro e(b,a) = 1 - e(a,b)",
        "zapisane z konstrukcji; symulowany był górny trójkąt macierzy.",
        '"""',
        "",
        'METHOD = "monte-carlo"',
        f"SEED = {master_seed}",
        f"TRIALS_PER_PAIR = {trials}",
        "",
        "HALF_POT_UNITS: tuple[int, ...] = (",
    ]
    for start in range(0, len(flat), UNITS_PER_LINE):
        chunk = flat[start : start + UNITS_PER_LINE]
        lines.append("    " + " ".join(f"{units}," for units in chunk))
    lines.append(")")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=12, help="seed macierzy (domyślnie 12)")
    parser.add_argument(
        "--trials",
        type=int,
        default=2048,
        help="liczba prób na parę klas (domyślnie 2048; potęga dwójki daje "
        "dokładne ułamki equity)",
    )
    parser.add_argument("--jobs", type=int, default=4, help="liczba procesów (domyślnie 4)")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/poker/preflop_equity_data.py"),
        help="ścieżka generowanego modułu danych",
    )
    args = parser.parse_args(argv)
    matrix = generate_matrix(args.seed, args.trials, args.jobs)
    args.output.write_text(render_module(matrix, args.seed, args.trials), encoding="utf-8")
    print(f"zapisano: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

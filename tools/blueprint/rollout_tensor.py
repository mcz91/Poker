"""Tensor rozstrzygnięć all-in preflop dla pilota blueprintu (POKER-46, decyzja 25).

Dla trójki klas preflop (pozycje 0/1/2) tensor daje rozkład 13 zdarzeń —
wszystkich słabych porządków trzech rąk na showdownie. Zdarzenie kodujemy
wektorem u = (u0, u1, u2), gdzie u_i to liczba graczy ściśle lepszych od
gracza i (remisy dzielą pozycję): 6 porządków ścisłych, 3 z remisem na
szczycie (u zawiera 0,0,2), 3 z remisem na dole (0,1,1) i remis potrójny
(0,0,0). Wektor u podany wprost do `poker.spin.award_allin` rozlicza main
i side poty — dlatego pełny porządek, nie sam zwycięzca. Ten sam tensor
obsługuje też pule 2-way przy trzech żywych (karty foldującego są martwe,
więc board z 46 kart jest właściwy) — wystarczy zsumować zdarzenia po
pozycji folda.

Monte Carlo na prawdziwych kartach: dla klas losujemy konkretne kombinacje
bez kolizji (card removal wbudowane), rozdajemy 5 kart boardu z reszty talii
i oceniamy istniejącym `poker.evaluation`. Dwa backendy o identycznym
strumieniu RNG (losowanie wspólne, różni się tylko ocena):

- ``direct`` — `evaluate_five` na każdym z 21 pięciokartowych podzbiorów
  7 kart (wierny, wolny; zmierzony ~550 µs/próbę — do raportu pilota);
- ``table`` — jednorazowa tablica wartości wszystkich C(52,5) układów,
  budowana w całości `evaluate_five` i pakowana zachowując porządek
  (`pack_value`), potem ocena wektorowa numpy.

Symetria permutacji trójki: liczymy raz na multizbiór klas (i ≤ j ≤ k),
konsument permutuje wynik. Seed multizbioru pochodny deterministycznie od
seeda głównego (wzorzec `poker.preflop_sim.pair_seed`), więc reprodukcja
podzbioru i zrównoleglenie nie zmieniają wyniku.

Endgame HU po odpadnięciu gracza dostaje osobny tensor par (wygrana/split/
przegrana): rozdane są tylko dwie ręce, board z 48 kart — inna talia niż
w puli 2-way przy trzech żywych.

Uruchomienie pilota (venv z extras train):

    python tools/blueprint/rollout_tensor.py --out KATALOG \
        --trials 1000 --hu-trials 4000 --seed 7 --jobs 4
"""

import argparse
import importlib.util
import itertools
import json
import sys
import time
from collections.abc import Sequence
from multiprocessing import Pool
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from poker.cards import Card, Rank, Suit
from poker.evaluation import HandValue, evaluate_five
from poker.preflop import ALL_CLASSES, class_combos


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

N_CLASSES = len(ALL_CLASSES)

_SUITS = tuple(sorted(Suit, key=lambda suit: suit.value))
_SUIT_INDEX = {suit: index for index, suit in enumerate(_SUITS)}
INT_TO_CARD: tuple[Card, ...] = tuple(
    Card(rank, suit) for rank in Rank for suit in _SUITS
)
_CARD_TO_INT = {card: index for index, card in enumerate(INT_TO_CARD)}


def _weak_orderings(players: int) -> tuple[tuple[int, ...], ...]:
    found = {
        tuple(sum(1 for w in values if w > v) for v in values)
        for values in itertools.product(range(players), repeat=players)
    }
    return tuple(sorted(found))


OUTCOMES_3: tuple[tuple[int, ...], ...] = _weak_orderings(3)
OUTCOMES_2: tuple[tuple[int, ...], ...] = _weak_orderings(2)

_KEY_TO_OUTCOME_3 = np.full(27, -1, dtype=np.int64)
for _index, _ranks in enumerate(OUTCOMES_3):
    _KEY_TO_OUTCOME_3[_ranks[0] * 9 + _ranks[1] * 3 + _ranks[2]] = _index
_KEY_TO_OUTCOME_2 = np.full(4, -1, dtype=np.int64)
for _index, _ranks2 in enumerate(OUTCOMES_2):
    _KEY_TO_OUTCOME_2[_ranks2[0] * 2 + _ranks2[1]] = _index


def class_combo_ints(class_index: int) -> np.ndarray:
    combos = class_combos(ALL_CLASSES[class_index])
    return np.array(
        [[_CARD_TO_INT[first], _CARD_TO_INT[second]] for first, second in combos],
        dtype=np.int64,
    )


_COMBO_INTS: tuple[np.ndarray, ...] = tuple(class_combo_ints(index) for index in range(N_CLASSES))
_COMBO_MASKS: tuple[np.ndarray, ...] = tuple(
    (np.uint64(1) << combos[:, 0].astype(np.uint64))
    | (np.uint64(1) << combos[:, 1].astype(np.uint64))
    for combos in _COMBO_INTS
)


def deal_weights3(triple: Sequence[int]) -> int:
    """Liczba rozłącznych przypisań kombinacji dla trójki klas (łączna waga rozdania).

    Dokładna kombinatoryka, nie Monte Carlo: to nienormalizowany łączny rozkład
    trójek klas z decyzji 25 (card removal w wagach). Zero oznacza multizbiór
    nierozdawalny (np. trzy razy ta sama para wymaga sześciu kart jednej rangi).
    """
    mask_a, mask_b, mask_c = (_COMBO_MASKS[index] for index in triple)
    pair_or = mask_a[:, None] | mask_b[None, :]
    pair_ok = (mask_a[:, None] & mask_b[None, :]) == 0
    disjoint = (pair_or[:, :, None] & mask_c[None, None, :]) == 0
    return int((disjoint & pair_ok[:, :, None]).sum())


def deal_weights2(pair: Sequence[int]) -> int:
    """Liczba rozłącznych przypisań kombinacji dla pary klas (endgame HU)."""
    mask_a, mask_b = (_COMBO_MASKS[index] for index in pair)
    return int(((mask_a[:, None] & mask_b[None, :]) == 0).sum())


def pack_value(value: HandValue) -> int:
    """HandValue jako int zachowujący porządek: kategoria i do 5 rang po 4 bity."""
    packed = int(value.category)
    tiebreakers = tuple(value.tiebreakers) + (0,) * (5 - len(value.tiebreakers))
    for rank in tiebreakers:
        packed = (packed << 4) | rank
    return packed


_BINOM = np.zeros((53, 6), dtype=np.int64)
_BINOM[:, 0] = 1
for _n in range(1, 53):
    for _k in range(1, 6):
        _BINOM[_n, _k] = _BINOM[_n - 1, _k - 1] + _BINOM[_n - 1, _k]

_SUBSETS_7C5 = np.array(list(itertools.combinations(range(7), 5)), dtype=np.int64)


def build_value_table() -> np.ndarray:
    """Wartości wszystkich C(52,5) układów, indeks kombinatoryczny (colex) posortowanej piątki."""
    table = np.empty(int(_BINOM[52, 5]), dtype=np.int64)
    for combo in itertools.combinations(range(52), 5):
        index = (
            _BINOM[combo[0], 1] + _BINOM[combo[1], 2] + _BINOM[combo[2], 3]
            + _BINOM[combo[3], 4] + _BINOM[combo[4], 5]
        )
        table[index] = pack_value(evaluate_five(INT_TO_CARD[card] for card in combo))
    return table


def triple_seed(master_seed: int, index_a: int, index_b: int, index_c: int) -> int:
    """Seed multizbioru trójki pochodny od seeda głównego (wzorzec poker.preflop_sim)."""
    return ((master_seed * N_CLASSES + index_a) * N_CLASSES + index_b) * N_CLASSES + index_c


def pair_seed(master_seed: int, index_a: int, index_b: int) -> int:
    """Seed pary HU; trzecia współrzędna N_CLASSES leży poza zakresem trójek — brak kolizji."""
    return ((master_seed * N_CLASSES + index_a) * N_CLASSES + index_b) * N_CLASSES + N_CLASSES


def _sample_deal(
    rng: np.random.Generator, class_indices: Sequence[int], trials: int
) -> tuple[list[np.ndarray], np.ndarray]:
    """Kombinacje bez kolizji dla klas i board z reszty talii; wspólny strumień RNG."""
    combos = [_COMBO_INTS[index] for index in class_indices]
    masks = [_COMBO_MASKS[index] for index in class_indices]
    picks = [rng.integers(0, len(combo), size=trials) for combo in combos]
    guard = 0
    while True:
        guard += 1
        if guard > 10_000:
            raise ValueError(f"klasy nierozdawalne bez kolizji: {tuple(class_indices)}")
        hole_masks = [mask[pick] for mask, pick in zip(masks, picks, strict=True)]
        overlap = np.zeros(trials, dtype=np.uint64)
        taken = np.zeros(trials, dtype=np.uint64)
        for hole in hole_masks:
            overlap |= taken & hole
            taken |= hole
        bad = overlap != 0
        if not bool(bad.any()):
            break
        redraw = int(bad.sum())
        for position, combo in enumerate(combos):
            picks[position][bad] = rng.integers(0, len(combo), size=redraw)
    used = taken
    board = rng.integers(0, 52, size=(trials, 5))
    while True:
        board_masks = np.bitwise_or.reduce(
            np.uint64(1) << board.astype(np.uint64), axis=1
        )
        distinct = np.bitwise_count(board_masks) == 5
        clean = (board_masks & used) == 0
        bad = ~(distinct & clean)
        if not bool(bad.any()):
            break
        board[bad] = rng.integers(0, 52, size=(int(bad.sum()), 5))
    holes = [combo[pick] for combo, pick in zip(combos, picks, strict=True)]
    return holes, board


def _seven_card_values(
    hole: np.ndarray, board: np.ndarray, table: np.ndarray | None
) -> np.ndarray:
    seven = np.sort(np.concatenate([hole, board], axis=1), axis=1)
    fives = seven[:, _SUBSETS_7C5]
    if table is not None:
        indices = (
            _BINOM[fives[:, :, 0], 1] + _BINOM[fives[:, :, 1], 2] + _BINOM[fives[:, :, 2], 3]
            + _BINOM[fives[:, :, 3], 4] + _BINOM[fives[:, :, 4], 5]
        )
        return np.asarray(table[indices].max(axis=1))
    flat = fives.reshape(-1, 5)
    packed = np.fromiter(
        (
            pack_value(evaluate_five(INT_TO_CARD[card] for card in row))
            for row in flat.tolist()
        ),
        dtype=np.int64,
        count=len(flat),
    )
    return np.asarray(packed.reshape(fives.shape[:2]).max(axis=1))


def _simulate(
    class_indices: Sequence[int],
    trials: int,
    rng: np.random.Generator,
    table: np.ndarray | None,
) -> np.ndarray:
    if trials < 1:
        raise ValueError(f"liczba prób musi być dodatnia: {trials}")
    holes, board = _sample_deal(rng, class_indices, trials)
    values = np.stack(
        [_seven_card_values(hole, board, table) for hole in holes], axis=1
    )
    better = (values[:, None, :] > values[:, :, None]).sum(axis=2)
    if len(class_indices) == 3:
        keys = better[:, 0] * 9 + better[:, 1] * 3 + better[:, 2]
        outcomes = _KEY_TO_OUTCOME_3[keys]
        length = len(OUTCOMES_3)
    else:
        keys = better[:, 0] * 2 + better[:, 1]
        outcomes = _KEY_TO_OUTCOME_2[keys]
        length = len(OUTCOMES_2)
    if bool((outcomes < 0).any()):
        raise AssertionError("nieznany słaby porządek — błąd konstrukcji zdarzeń")
    return np.bincount(outcomes, minlength=length).astype(np.int64)


def simulate_triple(
    triple: Sequence[int], trials: int, rng: np.random.Generator, table: np.ndarray | None
) -> np.ndarray:
    """Zliczenia 13 zdarzeń dla trójki klas na pozycjach 0/1/2 (board z 46 kart)."""
    if len(triple) != 3:
        raise ValueError("trójka klas musi mieć trzy indeksy")
    return _simulate(triple, trials, rng, table)


def simulate_pair(
    pair: Sequence[int], trials: int, rng: np.random.Generator, table: np.ndarray | None
) -> np.ndarray:
    """Zliczenia wygrana/split/przegrana dla pary klas HU (board z 48 kart)."""
    if len(pair) != 2:
        raise ValueError("para klas musi mieć dwa indeksy")
    return _simulate(pair, trials, rng, table)


def multisets_for(classes: Sequence[int]) -> tuple[tuple[int, int, int], ...]:
    ordered = sorted(classes)
    return tuple(
        (a, b, c) for a, b, c in itertools.combinations_with_replacement(ordered, 3)
    )


def pairs_for(classes: Sequence[int]) -> tuple[tuple[int, int], ...]:
    ordered = sorted(classes)
    return tuple((a, b) for a, b in itertools.combinations_with_replacement(ordered, 2))


_WORKER_TABLE: np.ndarray | None = None
_WORKER_TRIALS = 0
_WORKER_SEED = 0


def _triple_job(triple: tuple[int, int, int]) -> tuple[int, np.ndarray]:
    weight = deal_weights3(triple)
    if weight == 0:
        return 0, np.zeros(len(OUTCOMES_3), dtype=np.int64)
    rng = np.random.Generator(np.random.PCG64(triple_seed(_WORKER_SEED, *triple)))
    return weight, simulate_triple(triple, _WORKER_TRIALS, rng, _WORKER_TABLE)


def _pair_job(pair: tuple[int, int]) -> tuple[int, np.ndarray]:
    weight = deal_weights2(pair)
    if weight == 0:
        return 0, np.zeros(len(OUTCOMES_2), dtype=np.int64)
    rng = np.random.Generator(np.random.PCG64(pair_seed(_WORKER_SEED, *pair)))
    return weight, simulate_pair(pair, _WORKER_TRIALS, rng, _WORKER_TABLE)


def _run_jobs(
    items: Sequence[tuple[int, ...]],
    job: Any,
    jobs: int,
    trials: int,
    master_seed: int,
    table: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray]:
    global _WORKER_TABLE, _WORKER_TRIALS, _WORKER_SEED
    _WORKER_TABLE, _WORKER_TRIALS, _WORKER_SEED = table, trials, master_seed
    if jobs <= 1:
        rows = [job(item) for item in items]
    else:
        # Fork dziedziczy tablicę wartości bez kopii; wynik nie zależy od
        # szeregowania, bo seed każdego elementu pochodzi z jego indeksów klas.
        with Pool(processes=jobs) as pool:
            rows = list(pool.imap(job, items, chunksize=256))
    weights = np.array([weight for weight, _ in rows], dtype=np.int64)
    counts = np.stack([count for _, count in rows], axis=0)
    return weights, counts


def write_artifacts(
    out_dir: Path,
    classes: Sequence[int],
    multisets: Sequence[tuple[int, int, int]],
    counts3: np.ndarray,
    pairs: Sequence[tuple[int, int]],
    counts2: np.ndarray,
    manifest_extra: dict[str, Any],
    weights3: np.ndarray | None = None,
    weights2: np.ndarray | None = None,
) -> dict[str, Any]:
    if weights3 is None:
        weights3 = np.array([deal_weights3(triple) for triple in multisets], dtype=np.int64)
    if weights2 is None:
        weights2 = np.array([deal_weights2(pair) for pair in pairs], dtype=np.int64)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts.write_npz(
        out_dir / "rollout3.npz",
        {
            "multisets": np.array(multisets, dtype=np.int16),
            "counts3": counts3.astype(np.uint32),
            "weights3": weights3.astype(np.int64),
        },
    )
    artifacts.write_npz(
        out_dir / "rollout_hu.npz",
        {
            "pairs": np.array(pairs, dtype=np.int16),
            "counts2": counts2.astype(np.uint32),
            "weights2": weights2.astype(np.int64),
        },
    )
    manifest: dict[str, Any] = {
        "artifact": "rollout-tensor-pilot",
        "classes": [int(index) for index in classes],
        "outcomes3": [list(ranks) for ranks in OUTCOMES_3],
        "outcomes2": [list(ranks) for ranks in OUTCOMES_2],
        "numpy": np.__version__,
        "sha256": {
            "rollout3.npz": artifacts.sha256_file(out_dir / "rollout3.npz"),
            "rollout_hu.npz": artifacts.sha256_file(out_dir / "rollout_hu.npz"),
        },
    }
    manifest.update(manifest_extra)
    artifacts.write_json(out_dir / "rollout_manifest.json", manifest)
    return manifest


def read_artifacts(out_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    data.update(artifacts.read_npz(out_dir / "rollout3.npz"))
    data.update(artifacts.read_npz(out_dir / "rollout_hu.npz"))
    data["manifest"] = artifacts.read_json(out_dir / "rollout_manifest.json")
    return data


def generate_artifacts(
    out_dir: Path,
    trials: int,
    hu_trials: int,
    master_seed: int,
    classes: Sequence[int] | None = None,
    jobs: int = 1,
    backend: str = "table",
) -> dict[str, Any]:
    if backend not in ("table", "direct"):
        raise ValueError(f"nieznany backend oceny: {backend}")
    chosen = tuple(sorted(classes)) if classes is not None else tuple(range(N_CLASSES))
    started = time.perf_counter()
    table = build_value_table() if backend == "table" else None
    table_seconds = time.perf_counter() - started
    multisets = multisets_for(chosen)
    pairs = pairs_for(chosen)
    triples_started = time.perf_counter()
    weights3, counts3 = _run_jobs(multisets, _triple_job, jobs, trials, master_seed, table)
    triples_seconds = time.perf_counter() - triples_started
    pairs_started = time.perf_counter()
    weights2, counts2 = _run_jobs(pairs, _pair_job, jobs, hu_trials, master_seed, table)
    pairs_seconds = time.perf_counter() - pairs_started
    return write_artifacts(
        out_dir,
        chosen,
        multisets,
        counts3,
        pairs,
        counts2,
        weights3=weights3,
        weights2=weights2,
        manifest_extra={
            "method": "monte-carlo-all-in-preflop",
            "backend": backend,
            "master_seed": master_seed,
            "trials": trials,
            "hu_trials": hu_trials,
            "jobs": jobs,
            "seconds": {
                "value_table": round(table_seconds, 3),
                "triples": round(triples_seconds, 3),
                "pairs": round(pairs_seconds, 3),
            },
        },
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=1000)
    parser.add_argument("--hu-trials", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--backend", choices=("table", "direct"), default="table")
    args = parser.parse_args(argv)
    manifest = generate_artifacts(
        args.out,
        trials=args.trials,
        hu_trials=args.hu_trials,
        master_seed=args.seed,
        jobs=args.jobs,
        backend=args.backend,
    )
    print(json.dumps(manifest["seconds"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

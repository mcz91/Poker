"""Solver siatki DAG-u zegara — pilot blueprintu (POKER-46, decyzja 25).

Przestrzeń stanów: warstwa n = numer ręki (0..3L−1, poziomy z `poker.spin`,
button = n mod 3) × wektor stacków na siatce (suma stała, rozdzielczość
`grid_step`). Backward induction: warstwa n czyta V warstwy n+1; horyzont to
punkt stały ostatniego poziomu zegara (cykl trzech rąk iterowany od ICM —
mała V-iteration z decyzji 25), bo po końcu drabinki blindy stoją, a gra
trwa do wybicia.

Gra etapowa jednej ręki: preflop-only drzewo decyzji 25 — 14 węzłów
publicznych przy trzech żywych (fold / open 2.2x / jam; vs open fold /
3bet-jam; vs jam fold/call), a przy ≤7 bb efektywnych
(`poker.spin.is_jam_fold_depth`) jam/fold przez maskę akcji open (drzewo
redukuje się do 6 węzłów jak `poker.jamfold`). Gracz all-in z blinda ma
wymuszone wejście (koszt 0 → maska folda). Solver 3-osobowy: fictitious
play z pełnym best response po 169 klasach i ŁĄCZNYCH rozkładach trójek
klas z tensora rolloutu (nigdy iloczyn marginałów); restarty z różnych
inicjalizacji, wybór profilu z najmniejszym wewnętrznym ε. Endgame HU po
odpadnięciu gracza (gra o stałej sumie — wartość wybitego to stała
`prizes[2]`): CFR+ na tensorze par. Pula 2-way przy trzech żywych zawsze
pełnym wektorem trzech graczy — karty folda są martwe, więc rozstrzyga ją
tensor trójek zsumowany po pozycji folda.

Terminal ręki → wartość = V(n+1, kwantyzacja nowych stacków). Kwantyzacja:
metoda największych reszt zachowująca sumę żetonów, z korektą „żywy zostaje
żywy" (niedobitek dostaje krok od największego stacka). Gdy po ręce zostaje
jeden żywy, wypłaty rozstrzygamy w ręce (znamy stacki wejściowe): zwycięzca
prizes[0], wybici w tej ręce w kolejności stacków wejściowych, remis dzieli
nagrody po równo, wcześniej wybity jest trzeci.

Zapis atomowy per warstwa (tmp → os.replace) z manifestem (konfiguracja,
hash, sha artefaktów tensora); wznowienie po przerwaniu liczy tylko
brakujące warstwy i daje pliki bajt w bajt identyczne z biegiem ciągłym.

Uruchomienie pilota (venv z extras train):

    python tools/blueprint/solve_grid.py --tensor KATALOG --out KATALOG \
        --grid-step 5 --jobs 4
"""

import argparse
import hashlib
import importlib.util
import itertools
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from poker.icm import icm_equities
from poker.preflop import ALL_CLASSES
from poker.spin import (
    HANDS_PER_LEVEL,
    LEVELS,
    STARTING_CHIPS,
    award_allin,
    is_jam_fold_depth,
    open_amount,
    roles,
)


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

# Węzły publiczne drzewa 3-max (14) — nazwy ról: U=UTG, T=BTN (płaci SB), B=BB.
(
    N_U_ROOT,
    N_T_FI,
    N_B_VS_T_OPEN,
    N_T_VS_B_3BET,
    N_B_VS_T_JAM,
    N_T_VS_U_OPEN,
    N_B_VS_U_OPEN,
    N_U_VS_B_3BET,
    N_B_VS_U_OPEN_T_JAM,
    N_U_VS_T_3BET_B_FOLD,
    N_U_VS_T_3BET_B_CALL,
    N_T_VS_U_JAM,
    N_B_VS_U_JAM_T_FOLD,
    N_B_VS_U_JAM_T_CALL,
) = range(14)
N_NODES = 14

# Węzły HU (endgame po odpadnięciu gracza) — zapisywane w slotach 0..3.
H_ROOT, H_B_VS_OPEN, H_N_VS_3BET, H_B_VS_JAM = range(4)

# Sloty akcji: 0 = fold, 1 = open (w korzeniach) albo call/jam-continue, 2 = jam w korzeniach.
SLOT_FOLD, SLOT_MID, SLOT_JAM = 0, 1, 2

MODE_NAMES = ("deep", "jamfold", "hu-deep", "hu-jamfold")

_AXIS_PAIRS = ((0, 1), (0, 2), (1, 2))


@dataclass(frozen=True)
class GridConfig:
    prizes: tuple[float, float, float] = (0.8, 0.2, 0.0)
    levels: tuple[tuple[int, int], ...] | None = None
    hands_per_level: int = HANDS_PER_LEVEL
    total_chips: int = 3 * STARTING_CHIPS
    start_stacks: tuple[int, int, int] = (STARTING_CHIPS,) * 3
    grid_step: int = 5
    classes: tuple[int, ...] = tuple(range(len(ALL_CLASSES)))
    fp_max_iters: int = 24
    fp_check_every: int = 8
    fp_tol: float = 1e-3
    fp_restarts: int = 2
    cfr_iters: int = 128
    tail_max_cycles: int = 3
    tail_tol: float = 1e-3
    jobs: int = 1


def config_from_dict(payload: dict[str, Any]) -> GridConfig:
    """Konfiguracja z manifestu biegu (JSON zamienia krotki na listy)."""
    levels = payload["levels"]
    return GridConfig(
        prizes=(payload["prizes"][0], payload["prizes"][1], payload["prizes"][2]),
        levels=None if levels is None else tuple((pair[0], pair[1]) for pair in levels),
        hands_per_level=payload["hands_per_level"],
        total_chips=payload["total_chips"],
        start_stacks=tuple(payload["start_stacks"]),
        grid_step=payload["grid_step"],
        classes=tuple(payload["classes"]),
        fp_max_iters=payload["fp_max_iters"],
        fp_check_every=payload["fp_check_every"],
        fp_tol=payload["fp_tol"],
        fp_restarts=payload["fp_restarts"],
        cfr_iters=payload["cfr_iters"],
        tail_max_cycles=payload["tail_max_cycles"],
        tail_tol=payload["tail_tol"],
        jobs=payload["jobs"],
    )


def config_levels(config: GridConfig) -> tuple[tuple[int, int], ...]:
    return LEVELS if config.levels is None else config.levels


def level_blinds(config: GridConfig, hand: int) -> tuple[int, int]:
    levels = config_levels(config)
    level = min(hand // config.hands_per_level, len(levels) - 1)
    return levels[level]


def n_hands(config: GridConfig) -> int:
    return len(config_levels(config)) * config.hands_per_level


def config_hash(config: GridConfig, tensor_manifest: dict[str, Any]) -> str:
    payload = {
        "config": asdict(config),
        "tensor_sha256": tensor_manifest["sha256"],
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def grid_states(total: int, step: int) -> tuple[tuple[int, int, int], ...]:
    """Wszystkie wektory stacków siatki z co najmniej dwoma żywymi (porządek leksykalny)."""
    if total % step != 0:
        raise ValueError(f"suma żetonów {total} niepodzielna przez krok {step}")
    units = total // step
    states = []
    for a in range(units + 1):
        for b in range(units + 1 - a):
            stacks = (a * step, b * step, total - (a + b) * step)
            if sum(1 for value in stacks if value > 0) >= 2:
                states.append(stacks)
    return tuple(states)


def quantize_stacks(stacks: tuple[int, int, int], step: int) -> tuple[int, int, int]:
    """Kwantyzacja największych reszt: suma stała, wielokrotności kroku, żywy zostaje żywy."""
    total = sum(stacks)
    if total % step != 0:
        raise ValueError(f"suma żetonów {total} niepodzielna przez krok {step}")
    base = [value // step for value in stacks]
    remainder = total // step - sum(base)
    order = sorted(range(3), key=lambda seat: (-(stacks[seat] % step), seat))
    quantized = base[:]
    for seat in order[:remainder]:
        quantized[seat] += 1
    result = [units * step for units in quantized]
    for seat in range(3):
        while stacks[seat] > 0 and result[seat] == 0:
            donor = max(
                (index for index in range(3) if result[index] > step),
                key=lambda index: (result[index], -index),
            )
            result[donor] -= step
            result[seat] += step
    return (result[0], result[1], result[2])


# --- drzewa gry etapowej -------------------------------------------------

Tree = tuple[Any, ...]


def _leaf(index: int) -> Tree:
    return ("leaf", index)


def _node(node_id: int, actor: int, children: tuple[tuple[int, Tree], ...]) -> Tree:
    return ("node", node_id, actor, children)


# Liście 3-max: (uczestnicy showdownu | zwycięzca folda, linia).
# Wkłady per rola liczone w _stage_3max; kolejność uczestników rosnąca po osi.
_LEAF_DEFS_3 = (
    ("fold", 2),  # 0  U fold, T fold → BB bierze blindy
    ("fold", 1),  # 1  U fold, T open, B fold
    ("fold", 2),  # 2  U fold, T open, B jam, T fold
    ("sd", (1, 2)),  # 3  U fold, T open, B jam, T call
    ("fold", 1),  # 4  U fold, T jam, B fold
    ("sd", (1, 2)),  # 5  U fold, T jam, B call
    ("fold", 0),  # 6  U open, T fold, B fold
    ("fold", 2),  # 7  U open, T fold, B jam, U fold
    ("sd", (0, 2)),  # 8  U open, T fold, B jam, U call
    ("fold", 1),  # 9  U open, T jam, B fold, U fold
    ("sd", (0, 1)),  # 10 U open, T jam, B fold, U call
    ("sd", (1, 2)),  # 11 U open, T jam, B call, U fold
    ("sd", (0, 1, 2)),  # 12 U open, T jam, B call, U call
    ("fold", 0),  # 13 U jam, T fold, B fold
    ("sd", (0, 1)),  # 14 U jam, T call, B fold
    ("sd", (0, 2)),  # 15 U jam, T fold, B call
    ("sd", (0, 1, 2)),  # 16 U jam, T call, B call
)

_LEAF_DEFS_HU = (
    ("fold", 1),  # 0 N fold
    ("fold", 0),  # 1 N open, B fold
    ("fold", 1),  # 2 N open, B jam, N fold
    ("sd", (0, 1)),  # 3 N open, B jam, N call
    ("fold", 0),  # 4 N jam, B fold
    ("sd", (0, 1)),  # 5 N jam, B call
)


def _tree_3max(deep: bool) -> Tree:
    after_u_fold = _node(
        N_T_FI,
        1,
        (
            (SLOT_FOLD, _leaf(0)),
            *(
                (
                    (
                        SLOT_MID,
                        _node(
                            N_B_VS_T_OPEN,
                            2,
                            (
                                (SLOT_FOLD, _leaf(1)),
                                (
                                    SLOT_MID,
                                    _node(
                                        N_T_VS_B_3BET,
                                        1,
                                        ((SLOT_FOLD, _leaf(2)), (SLOT_MID, _leaf(3))),
                                    ),
                                ),
                            ),
                        ),
                    ),
                )
                if deep
                else ()
            ),
            (
                SLOT_JAM,
                _node(N_B_VS_T_JAM, 2, ((SLOT_FOLD, _leaf(4)), (SLOT_MID, _leaf(5)))),
            ),
        ),
    )
    after_u_open = _node(
        N_T_VS_U_OPEN,
        1,
        (
            (
                SLOT_FOLD,
                _node(
                    N_B_VS_U_OPEN,
                    2,
                    (
                        (SLOT_FOLD, _leaf(6)),
                        (
                            SLOT_MID,
                            _node(
                                N_U_VS_B_3BET,
                                0,
                                ((SLOT_FOLD, _leaf(7)), (SLOT_MID, _leaf(8))),
                            ),
                        ),
                    ),
                ),
            ),
            (
                SLOT_MID,
                _node(
                    N_B_VS_U_OPEN_T_JAM,
                    2,
                    (
                        (
                            SLOT_FOLD,
                            _node(
                                N_U_VS_T_3BET_B_FOLD,
                                0,
                                ((SLOT_FOLD, _leaf(9)), (SLOT_MID, _leaf(10))),
                            ),
                        ),
                        (
                            SLOT_MID,
                            _node(
                                N_U_VS_T_3BET_B_CALL,
                                0,
                                ((SLOT_FOLD, _leaf(11)), (SLOT_MID, _leaf(12))),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    after_u_jam = _node(
        N_T_VS_U_JAM,
        1,
        (
            (
                SLOT_FOLD,
                _node(
                    N_B_VS_U_JAM_T_FOLD,
                    2,
                    ((SLOT_FOLD, _leaf(13)), (SLOT_MID, _leaf(15))),
                ),
            ),
            (
                SLOT_MID,
                _node(
                    N_B_VS_U_JAM_T_CALL,
                    2,
                    ((SLOT_FOLD, _leaf(14)), (SLOT_MID, _leaf(16))),
                ),
            ),
        ),
    )
    children = [(SLOT_FOLD, after_u_fold)]
    if deep:
        children.append((SLOT_MID, after_u_open))
    children.append((SLOT_JAM, after_u_jam))
    return _node(N_U_ROOT, 0, tuple(children))


def _tree_hu(deep: bool) -> Tree:
    children = [(SLOT_FOLD, _leaf(0))]
    if deep:
        children.append(
            (
                SLOT_MID,
                _node(
                    H_B_VS_OPEN,
                    1,
                    (
                        (SLOT_FOLD, _leaf(1)),
                        (
                            SLOT_MID,
                            _node(
                                H_N_VS_3BET,
                                0,
                                ((SLOT_FOLD, _leaf(2)), (SLOT_MID, _leaf(3))),
                            ),
                        ),
                    ),
                ),
            )
        )
    children.append(
        (SLOT_JAM, _node(H_B_VS_JAM, 1, ((SLOT_FOLD, _leaf(4)), (SLOT_MID, _leaf(5)))))
    )
    return _node(H_ROOT, 0, tuple(children))


def _tree_nodes(tree: Tree, allowed: dict[int, tuple[int, ...]]) -> tuple[int, ...]:
    """Węzły osiągalne przy maskach akcji — gałąź za wymuszoną akcją nie istnieje."""
    if tree[0] == "leaf":
        return ()
    found = [tree[1]]
    for slot, child in tree[3]:
        if slot in allowed[tree[1]]:
            found.extend(_tree_nodes(child, allowed))
    return tuple(found)


def _tree_leaves(tree: Tree, allowed: dict[int, tuple[int, ...]]) -> frozenset[int]:
    """Liście osiągalne przy maskach — dla pozostałych nie budujemy tensorów wypłat."""
    if tree[0] == "leaf":
        return frozenset((tree[1],))
    found: frozenset[int] = frozenset()
    for slot, child in tree[3]:
        if slot in allowed[tree[1]]:
            found |= _tree_leaves(child, allowed)
    return found


# --- tensory rozdań ------------------------------------------------------


@dataclass
class Tensors:
    classes: tuple[int, ...]
    count: int
    deal3: np.ndarray  # (C³,) f32 — łączne wagi trójek (card removal)
    wt13: np.ndarray  # (C³, 13) f32 — waga × prawdopodobieństwo zdarzenia
    wt2_fold: dict[tuple[int, int], np.ndarray]  # (C³, 3) — pula 2-way, karty folda martwe
    deal2: np.ndarray  # (C²,) f32 — endgame HU (rozdane tylko dwie ręce)
    wt2_endgame: np.ndarray  # (C², 3) f32
    manifest: dict[str, Any]


def _multiset_rows(count: int) -> np.ndarray:
    """Indeks wiersza multizbioru (p0≤p1≤p2) w porządku leksykalnym, tablica (C,C,C)."""
    rows = np.zeros((count, count, count), dtype=np.int64)
    row = 0
    for a in range(count):
        for b in range(a, count):
            for c in range(b, count):
                rows[a, b, c] = row
                row += 1
    return rows


def _outcome_permutations() -> dict[tuple[int, ...], np.ndarray]:
    outcomes = rollout_tensor.OUTCOMES_3
    index = {ranks: position for position, ranks in enumerate(outcomes)}
    table: dict[tuple[int, ...], np.ndarray] = {}
    for perm in itertools.permutations(range(3)):
        mapped = np.zeros(len(outcomes), dtype=np.int64)
        for position, ranks in enumerate(outcomes):
            ordered = [0, 0, 0]
            for multiset_pos in range(3):
                ordered[perm[multiset_pos]] = ranks[multiset_pos]
            mapped[position] = index[tuple(ordered)]
        table[perm] = mapped
    return table


def load_tensors(tensor_dir: Path, classes: tuple[int, ...]) -> Tensors:
    data = rollout_tensor.read_artifacts(tensor_dir)
    manifest = data["manifest"]
    chosen = tuple(sorted(classes))
    if tuple(manifest["classes"]) != chosen:
        raise ValueError("klasy konfiguracji nie zgadzają się z artefaktem tensora")
    count = len(chosen)
    counts3 = data["counts3"].astype(np.float32)
    weights3 = data["weights3"].astype(np.float32)
    trials3 = counts3.sum(axis=1)
    probs3 = counts3 / np.maximum(trials3, 1.0)[:, None]
    ms_rows = _multiset_rows(count)
    perm_table = _outcome_permutations()
    axes = np.stack(np.meshgrid(np.arange(count), np.arange(count), np.arange(count),
                                indexing="ij"), axis=-1).reshape(-1, 3)
    order = np.argsort(axes, axis=1, kind="stable")
    sorted_axes = np.take_along_axis(axes, order, axis=1)
    rows = ms_rows[sorted_axes[:, 0], sorted_axes[:, 1], sorted_axes[:, 2]]
    perm_ids = order[:, 0] * 9 + order[:, 1] * 3 + order[:, 2]
    perm_rows = np.zeros((27, len(rollout_tensor.OUTCOMES_3)), dtype=np.int64)
    for perm, mapped in perm_table.items():
        perm_ids_key = perm[0] * 9 + perm[1] * 3 + perm[2]
        perm_rows[perm_ids_key] = mapped
    wt13 = probs3[rows[:, None], perm_rows[perm_ids]]
    deal3 = weights3[rows]
    wt13 *= deal3[:, None]
    del axes, order, sorted_axes, rows, perm_ids, counts3, probs3
    pair_index = {ranks: pos for pos, ranks in enumerate(rollout_tensor.OUTCOMES_2)}
    wt2_fold: dict[tuple[int, int], np.ndarray] = {}
    for axis_a, axis_b in _AXIS_PAIRS:
        collapse = np.zeros((len(rollout_tensor.OUTCOMES_3), len(rollout_tensor.OUTCOMES_2)),
                            dtype=np.float32)
        for position3, ranks in enumerate(rollout_tensor.OUTCOMES_3):
            first, second = ranks[axis_a], ranks[axis_b]
            if first == second:
                key = (0, 0)
            elif first < second:
                key = (0, 1)
            else:
                key = (1, 0)
            collapse[position3, pair_index[key]] = 1.0
        wt2_fold[(axis_a, axis_b)] = wt13 @ collapse
    counts2 = data["counts2"].astype(np.float32)
    weights2 = data["weights2"].astype(np.float32)
    trials2 = counts2.sum(axis=1)
    probs2 = counts2 / np.maximum(trials2, 1.0)[:, None]
    pair_rows = np.zeros((count, count), dtype=np.int64)
    row = 0
    for a in range(count):
        for b in range(a, count):
            pair_rows[a, b] = row
            pair_rows[b, a] = row
            row += 1
    axes2 = np.stack(np.meshgrid(np.arange(count), np.arange(count), indexing="ij"),
                     axis=-1).reshape(-1, 2)
    rows2 = pair_rows[axes2[:, 0], axes2[:, 1]]
    swap = axes2[:, 0] > axes2[:, 1]
    swap_map = np.array(
        [pair_index[(ranks[1], ranks[0])] for ranks in rollout_tensor.OUTCOMES_2],
        dtype=np.int64,
    )
    wt2e = probs2[rows2]
    wt2e[swap] = wt2e[swap][:, swap_map]
    deal2 = weights2[rows2]
    wt2e = wt2e * deal2[:, None]
    return Tensors(
        classes=chosen,
        count=count,
        deal3=np.ascontiguousarray(deal3),
        wt13=np.ascontiguousarray(wt13),
        wt2_fold={key: np.ascontiguousarray(value) for key, value in wt2_fold.items()},
        deal2=np.ascontiguousarray(deal2),
        wt2_endgame=np.ascontiguousarray(wt2e),
        manifest=manifest,
    )


# --- gra etapowa ---------------------------------------------------------


@dataclass
class StageProblem:
    n_roles: int
    tree: Tree
    nodes: tuple[int, ...]
    allowed: dict[int, tuple[int, ...]]
    leaf_kind: tuple[str, ...]
    leaf_payload: list[Any]  # fold: (winner, wektor (roli,)); sd: macierz (n_roli, C^r)
    deal: np.ndarray  # (C^r,) f32
    total_weight: float
    count: int


@dataclass
class StageResult:
    sigma: np.ndarray  # (14, C, 3) f32 — węzły nieodwiedzane zerowe
    values: np.ndarray  # (3,) f64 per miejsce
    eps: float
    iterations: int
    mode: str


def _contract_hero(p_flat: np.ndarray, reach: dict[int, np.ndarray], hero: int,
                   count: int, n_roles: int) -> np.ndarray:
    if n_roles == 2:
        matrix = p_flat.reshape(count, count)
        return matrix @ reach[1] if hero == 0 else reach[0] @ matrix
    if hero == 0:
        tmp = (p_flat.reshape(count * count, count) @ reach[2]).reshape(count, count)
        return tmp @ reach[1]
    if hero == 1:
        tmp = (p_flat.reshape(count * count, count) @ reach[2]).reshape(count, count)
        return reach[0] @ tmp
    tmp = (reach[0] @ p_flat.reshape(count, count * count)).reshape(count, count)
    return reach[1] @ tmp


def _leaf_hero_ev(problem: StageProblem, leaf: int, hero: int,
                  reach: dict[int, np.ndarray]) -> np.ndarray:
    if problem.leaf_kind[leaf] == "fold":
        _, payoff = problem.leaf_payload[leaf]
        base = _contract_hero(problem.deal, reach, hero, problem.count, problem.n_roles)
        return np.asarray(base * np.float32(payoff[hero]))
    payload = problem.leaf_payload[leaf]
    return _contract_hero(payload[hero], reach, hero, problem.count, problem.n_roles)


def _walk_hero(problem: StageProblem, tree: Tree, hero: int, reach: dict[int, np.ndarray],
               sigma: dict[int, np.ndarray], propagate: str,
               record: dict[int, list[np.ndarray]]) -> np.ndarray:
    if tree[0] == "leaf":
        return _leaf_hero_ev(problem, tree[1], hero, reach)
    _, node_id, actor, children = tree
    allowed = problem.allowed[node_id]
    if actor == hero:
        values = []
        for slot, child in children:
            if slot not in allowed:
                continue
            values.append(_walk_hero(problem, child, hero, reach, sigma, propagate, record))
        record[node_id] = values
        if propagate == "best":
            return np.max(np.stack(values, axis=0), axis=0)
        own = sigma[node_id]
        total = np.zeros(problem.count, dtype=np.float32)
        for position, slot in enumerate(allowed):
            total += own[:, slot] * values[position]
        return total
    total = np.zeros(problem.count, dtype=np.float32)
    for slot, child in children:
        if slot not in allowed:
            continue
        new_reach = dict(reach)
        new_reach[actor] = reach[actor] * sigma[node_id][:, slot]
        total += _walk_hero(problem, child, hero, new_reach, sigma, propagate, record)
    return total


def _hero_action_values(problem: StageProblem, hero: int, sigma: dict[int, np.ndarray],
                        propagate: str) -> tuple[dict[int, list[np.ndarray]], np.ndarray]:
    reach = {
        role: np.ones(problem.count, dtype=np.float32)
        for role in range(problem.n_roles)
        if role != hero
    }
    record: dict[int, list[np.ndarray]] = {}
    root = _walk_hero(problem, problem.tree, hero, reach, sigma, propagate, record)
    return record, root


def _profile_values(problem: StageProblem, sigma: dict[int, np.ndarray]) -> np.ndarray:
    values = np.zeros(problem.n_roles, dtype=np.float64)

    def descend(tree: Tree, reach: dict[int, np.ndarray]) -> None:
        if tree[0] == "leaf":
            leaf = tree[1]
            if problem.leaf_kind[leaf] == "fold":
                _, payoff = problem.leaf_payload[leaf]
                hero = 0
                vec = _contract_hero(problem.deal, reach, hero, problem.count, problem.n_roles)
                mass = float(vec @ reach[hero])
                for role in range(problem.n_roles):
                    values[role] += mass * float(payoff[role])
            else:
                payload = problem.leaf_payload[leaf]
                for role in range(problem.n_roles):
                    vec = _contract_hero(payload[role], reach, role, problem.count,
                                         problem.n_roles)
                    values[role] += float(vec @ reach[role])
            return
        _, node_id, actor, children = tree
        for slot, child in children:
            if slot not in problem.allowed[node_id]:
                continue
            new_reach = dict(reach)
            new_reach[actor] = reach[actor] * sigma[node_id][:, slot]
            descend(child, new_reach)

    reach = {role: np.ones(problem.count, dtype=np.float32) for role in range(problem.n_roles)}
    descend(problem.tree, reach)
    return values / problem.total_weight


def _best_response_values(problem: StageProblem, sigma: dict[int, np.ndarray]) -> np.ndarray:
    best = np.zeros(problem.n_roles, dtype=np.float64)
    for hero in range(problem.n_roles):
        _, root = _hero_action_values(problem, hero, sigma, "best")
        best[hero] = float(root.sum()) / problem.total_weight
    return best


def _internal_eps(problem: StageProblem, sigma: dict[int, np.ndarray]) -> float:
    values = _profile_values(problem, sigma)
    best = _best_response_values(problem, sigma)
    return float(np.max(best - values))


def _init_profile(problem: StageProblem, style: str) -> dict[int, np.ndarray]:
    sigma: dict[int, np.ndarray] = {}
    for node_id in problem.nodes:
        allowed = problem.allowed[node_id]
        matrix = np.zeros((problem.count, 3), dtype=np.float32)
        if len(allowed) == 1:
            matrix[:, allowed[0]] = 1.0
        elif style == "tight":
            matrix[:, SLOT_FOLD] = 0.8
            share = 0.2 / (len(allowed) - 1)
            for slot in allowed:
                if slot != SLOT_FOLD:
                    matrix[:, slot] = share
        else:
            for slot in allowed:
                matrix[:, slot] = 1.0 / len(allowed)
        sigma[node_id] = matrix
    return sigma


def _fp_solve(problem: StageProblem, config: GridConfig) -> tuple[dict[int, np.ndarray],
                                                                  float, int]:
    styles = ("uniform", "tight", "loose")[: max(1, config.fp_restarts)]
    best_sigma: dict[int, np.ndarray] | None = None
    best_eps = float("inf")
    best_iters = 0
    for style in styles:
        init = _init_profile(problem, "tight" if style == "tight" else "uniform")
        if style == "loose":
            for node_id in problem.nodes:
                allowed = problem.allowed[node_id]
                if len(allowed) > 1:
                    matrix = np.zeros((problem.count, 3), dtype=np.float32)
                    matrix[:, allowed[-1]] = 0.8
                    for slot in allowed[:-1]:
                        matrix[:, slot] = 0.2 / (len(allowed) - 1)
                    init[node_id] = matrix
        cumulative = {node_id: init[node_id].copy() for node_id in problem.nodes}
        weight_sum = 1.0
        iterations = 0
        eps = float("inf")
        accepted: dict[int, np.ndarray] | None = None
        for step in range(1, config.fp_max_iters + 1):
            average = {node_id: cumulative[node_id] / weight_sum for node_id in problem.nodes}
            checking = step % config.fp_check_every == 0 or step == config.fp_max_iters
            reply: dict[int, np.ndarray] = {}
            best_roots = np.zeros(problem.n_roles, dtype=np.float64)
            for hero in range(problem.n_roles):
                record, root = _hero_action_values(problem, hero, average, "best")
                best_roots[hero] = float(root.sum()) / problem.total_weight
                for node_id, values in record.items():
                    allowed = problem.allowed[node_id]
                    stacked = np.stack(values, axis=0)
                    choice = np.argmax(stacked, axis=0)
                    matrix = np.zeros((problem.count, 3), dtype=np.float32)
                    for position, slot in enumerate(allowed):
                        matrix[:, slot] = (choice == position).astype(np.float32)
                    reply[node_id] = matrix
            iterations = step
            if checking:
                # BR policzone względem `average`, więc ε dotyczy dokładnie tego
                # profilu — zwracamy go, nie profil po kolejnej aktualizacji.
                eps = float(np.max(best_roots - _profile_values(problem, average)))
                if eps <= config.fp_tol:
                    accepted = average
                    break
            weight = float(step)
            for node_id in problem.nodes:
                cumulative[node_id] += weight * reply[node_id]
            weight_sum += weight
        if accepted is None:
            accepted = {
                node_id: cumulative[node_id] / weight_sum for node_id in problem.nodes
            }
            eps = _internal_eps(problem, accepted)
        if eps < best_eps:
            best_sigma, best_eps, best_iters = accepted, eps, iterations
        if best_eps <= config.fp_tol:
            # Profil osiągnął próg — kolejne inicjalizacje nic nie wnoszą do wyboru po ε.
            break
    assert best_sigma is not None
    return best_sigma, best_eps, best_iters


def _cfr_plus_solve(problem: StageProblem, config: GridConfig) -> tuple[dict[int, np.ndarray],
                                                                        float, int]:
    regrets = {
        node_id: np.zeros((problem.count, 3), dtype=np.float32) for node_id in problem.nodes
    }
    average = {
        node_id: np.zeros((problem.count, 3), dtype=np.float32) for node_id in problem.nodes
    }

    def policy() -> dict[int, np.ndarray]:
        sigma: dict[int, np.ndarray] = {}
        for node_id in problem.nodes:
            allowed = problem.allowed[node_id]
            matrix = np.zeros((problem.count, 3), dtype=np.float32)
            positive = np.zeros((problem.count, len(allowed)), dtype=np.float32)
            for position, slot in enumerate(allowed):
                positive[:, position] = np.maximum(regrets[node_id][:, slot], 0.0)
            totals = positive.sum(axis=1)
            uniform = 1.0 / len(allowed)
            for position, slot in enumerate(allowed):
                matrix[:, slot] = np.where(
                    totals > 0.0, positive[:, position] / np.maximum(totals, 1e-30), uniform
                )
            sigma[node_id] = matrix
        return sigma

    iterations = 0
    for step in range(1, config.cfr_iters + 1):
        current = policy()
        for hero in range(problem.n_roles):
            record, _ = _hero_action_values(problem, hero, current, "current")
            for node_id, values in record.items():
                allowed = problem.allowed[node_id]
                stacked = np.stack(values, axis=0)  # (n_akcji, C)
                own = np.stack([current[node_id][:, slot] for slot in allowed], axis=0)
                node_value = (own * stacked).sum(axis=0)
                for position, slot in enumerate(allowed):
                    regrets[node_id][:, slot] = np.maximum(
                        regrets[node_id][:, slot] + stacked[position] - node_value, 0.0
                    )
        weight = float(step)
        for node_id in problem.nodes:
            average[node_id] += weight * current[node_id]
        iterations = step
    total = sum(range(1, iterations + 1))
    sigma = {node_id: average[node_id] / float(total) for node_id in problem.nodes}
    eps = _internal_eps(problem, sigma)
    return sigma, eps, iterations


# --- rozliczenia ręki ----------------------------------------------------


def _game_over_payout(entering: tuple[int, int, int], after: tuple[int, int, int],
                      prizes: tuple[float, float, float]) -> np.ndarray:
    alive_after = [seat for seat in range(3) if after[seat] > 0]
    assert len(alive_after) == 1
    payout = np.zeros(3, dtype=np.float64)
    payout[alive_after[0]] = prizes[0]
    busted_now = [seat for seat in range(3) if after[seat] == 0 and entering[seat] > 0]
    already_out = [seat for seat in range(3) if entering[seat] == 0]
    if len(busted_now) == 1:
        payout[busted_now[0]] = prizes[1]
        for seat in already_out:
            payout[seat] = prizes[2]
    else:
        first, second = busted_now
        if entering[first] > entering[second]:
            payout[first], payout[second] = prizes[1], prizes[2]
        elif entering[first] < entering[second]:
            payout[first], payout[second] = prizes[2], prizes[1]
        else:
            shared = (prizes[1] + prizes[2]) / 2.0
            payout[first] = payout[second] = shared
    return payout


def _contribs_3max(stacks_roles: tuple[int, int, int], sb_amt: int, bb_amt: int,
                   open_u: int, open_t: int) -> tuple[tuple[int, int, int], ...]:
    s_u, s_t, s_b = stacks_roles
    return (
        (0, sb_amt, bb_amt),
        (0, open_t, bb_amt),
        (0, open_t, s_b),
        (0, min(s_t, s_b), s_b),
        (0, s_t, bb_amt),
        (0, s_t, min(s_b, s_t)),
        (open_u, sb_amt, bb_amt),
        (open_u, sb_amt, s_b),
        (min(s_u, s_b), sb_amt, s_b),
        (open_u, s_t, bb_amt),
        (min(s_u, s_t), s_t, bb_amt),
        (open_u, s_t, min(s_b, s_t)),
        (min(s_u, s_t), s_t, min(s_b, s_t)),
        (s_u, sb_amt, bb_amt),
        (s_u, min(s_t, s_u), bb_amt),
        (s_u, sb_amt, min(s_b, s_u)),
        (s_u, min(s_t, s_u), min(s_b, s_u)),
    )


def _contribs_hu(stacks_roles: tuple[int, int], sb_amt: int, bb_amt: int,
                 open_n: int) -> tuple[tuple[int, int], ...]:
    s_n, s_b = stacks_roles
    return (
        (sb_amt, bb_amt),
        (open_n, bb_amt),
        (open_n, s_b),
        (min(s_n, s_b), s_b),
        (s_n, bb_amt),
        (s_n, min(s_b, s_n)),
    )


def _settle(entering_seats: tuple[int, int, int], role_seats: tuple[int, ...],
            contribs: tuple[int, ...], ranks: tuple[int, ...],
            prizes: tuple[float, float, float],
            v_lookup: Any) -> np.ndarray:
    """Wektor wypłat per rola dla jednego rozstrzygnięcia liścia (pełny wektor 3 miejsc).

    Kwantyzacja stanu następnego należy do `v_lookup` — tryb sanity porównania
    z `poker.jamfold` używa dokładnego ICM bez siatki.
    """
    awarded = award_allin(contribs, ranks)
    after = list(entering_seats)
    for role, seat in enumerate(role_seats):
        after[seat] = after[seat] - contribs[role] + awarded[role]
    after_t = (after[0], after[1], after[2])
    assert sum(after_t) == sum(entering_seats), "suma żetonów terminala musi być stała"
    alive = sum(1 for value in after_t if value > 0)
    if alive <= 1:
        full = _game_over_payout(entering_seats, after_t, prizes)
    else:
        full = v_lookup(after_t)
    return np.asarray([full[seat] for seat in role_seats], dtype=np.float64)


def _fold_ranks(n_roles: int, winner: int) -> tuple[int, ...]:
    ranks = [3] * n_roles
    ranks[winner] = 0
    return tuple(ranks)


def _sd_ranks(n_roles: int, participants: tuple[int, ...],
              outcome: tuple[int, ...]) -> tuple[int, ...]:
    ranks = [3] * n_roles
    for position, role in enumerate(participants):
        ranks[role] = outcome[position]
    return tuple(ranks)


def build_stage_problem(
    tensors: Tensors,
    config: GridConfig,
    seat_stacks: tuple[int, int, int],
    hand: int,
    sb: int,
    bb_amt: int,
    v_lookup: Any,
    force_jamfold: bool | None = None,
) -> tuple[StageProblem, tuple[int, ...], str]:
    """Problem gry etapowej dla stanu; zwraca też mapę rola→miejsce i tryb.

    `force_jamfold=True` wymusza drzewo jam/fold niezależnie od głębokości —
    tryb sanity porównania z `poker.jamfold` na głębokich stackach.
    """
    prizes = config.prizes
    alive = [seat for seat in range(3) if seat_stacks[seat] > 0]
    jamfold = (
        is_jam_fold_depth(seat_stacks, bb_amt) if force_jamfold is None else force_jamfold
    )
    if len(alive) == 3:
        utg, btn, bb_seat = roles(hand % 3)
        role_seats: tuple[int, ...] = (utg, btn, bb_seat)
        stacks_roles3 = tuple(seat_stacks[seat] for seat in role_seats)
        s_u, s_t, s_b = stacks_roles3
        sb_posted = min(s_t, sb)
        bb_posted = min(s_b, bb_amt)
        open_u = min(open_amount(bb_amt), s_u)
        open_t = min(open_amount(bb_amt), s_t)
        tree = _tree_3max(deep=not jamfold)
        contribs = _contribs_3max((s_u, s_t, s_b), sb_posted, bb_posted, open_u, open_t)
        leaf_defs = _LEAF_DEFS_3
        n_roles = 3
        mode = "jamfold" if jamfold else "deep"
        allowed = {
            N_U_ROOT: (SLOT_FOLD, SLOT_JAM) if jamfold else (SLOT_FOLD, SLOT_MID, SLOT_JAM),
            N_T_FI: (
                (SLOT_JAM,)
                if s_t == sb_posted
                else ((SLOT_FOLD, SLOT_JAM) if jamfold else (SLOT_FOLD, SLOT_MID, SLOT_JAM))
            ),
            N_B_VS_T_OPEN: (SLOT_MID,) if s_b == bb_posted else (SLOT_FOLD, SLOT_MID),
            N_T_VS_B_3BET: (
                (SLOT_MID,) if min(s_t, s_b) <= open_t else (SLOT_FOLD, SLOT_MID)
            ),
            N_B_VS_T_JAM: (
                (SLOT_MID,) if min(s_b, s_t) <= bb_posted else (SLOT_FOLD, SLOT_MID)
            ),
            N_T_VS_U_OPEN: (SLOT_MID,) if s_t == sb_posted else (SLOT_FOLD, SLOT_MID),
            N_B_VS_U_OPEN: (SLOT_MID,) if s_b == bb_posted else (SLOT_FOLD, SLOT_MID),
            N_U_VS_B_3BET: (
                (SLOT_MID,) if min(s_u, s_b) <= open_u else (SLOT_FOLD, SLOT_MID)
            ),
            N_B_VS_U_OPEN_T_JAM: (
                (SLOT_MID,) if min(s_b, s_t) <= bb_posted else (SLOT_FOLD, SLOT_MID)
            ),
            N_U_VS_T_3BET_B_FOLD: (
                (SLOT_MID,) if min(s_u, s_t) <= open_u else (SLOT_FOLD, SLOT_MID)
            ),
            N_U_VS_T_3BET_B_CALL: (
                (SLOT_MID,) if min(s_u, s_t) <= open_u else (SLOT_FOLD, SLOT_MID)
            ),
            N_T_VS_U_JAM: (
                (SLOT_MID,) if min(s_t, s_u) <= sb_posted else (SLOT_FOLD, SLOT_MID)
            ),
            N_B_VS_U_JAM_T_FOLD: (
                (SLOT_MID,) if min(s_b, s_u) <= bb_posted else (SLOT_FOLD, SLOT_MID)
            ),
            N_B_VS_U_JAM_T_CALL: (
                (SLOT_MID,) if min(s_b, s_u) <= bb_posted else (SLOT_FOLD, SLOT_MID)
            ),
        }
        deal = tensors.deal3
        total_weight = float(tensors.deal3.sum())
    else:
        assert len(alive) == 2, "stan gry etapowej wymaga co najmniej dwóch żywych"
        ordered = sorted(alive)
        hu_btn = ordered[hand % 2]
        hu_bb = ordered[1 - hand % 2]
        role_seats = (hu_btn, hu_bb)
        s_n, s_b = seat_stacks[hu_btn], seat_stacks[hu_bb]
        sb_posted = min(s_n, sb)
        bb_posted = min(s_b, bb_amt)
        open_n = min(open_amount(bb_amt), s_n)
        tree = _tree_hu(deep=not jamfold)
        contribs = _contribs_hu((s_n, s_b), sb_posted, bb_posted, open_n)
        leaf_defs = _LEAF_DEFS_HU
        n_roles = 2
        mode = "hu-jamfold" if jamfold else "hu-deep"
        allowed = {
            H_ROOT: (
                (SLOT_JAM,)
                if s_n == sb_posted
                else ((SLOT_FOLD, SLOT_JAM) if jamfold else (SLOT_FOLD, SLOT_MID, SLOT_JAM))
            ),
            H_B_VS_OPEN: (SLOT_MID,) if s_b == bb_posted else (SLOT_FOLD, SLOT_MID),
            H_N_VS_3BET: (
                (SLOT_MID,) if min(s_n, s_b) <= open_n else (SLOT_FOLD, SLOT_MID)
            ),
            H_B_VS_JAM: (
                (SLOT_MID,) if min(s_b, s_n) <= bb_posted else (SLOT_FOLD, SLOT_MID)
            ),
        }
        deal = tensors.deal2
        total_weight = float(tensors.deal2.sum())
    leaf_kind: list[str] = []
    leaf_payload: list[Any] = []
    outcomes2 = rollout_tensor.OUTCOMES_2
    outcomes3 = rollout_tensor.OUTCOMES_3
    reachable_leaves = _tree_leaves(tree, allowed)
    for leaf_index, (kind, meta) in enumerate(leaf_defs):
        leaf_contribs = contribs[leaf_index]
        if leaf_index not in reachable_leaves:
            leaf_kind.append(kind)
            leaf_payload.append(None)
            continue
        if kind == "fold":
            winner = int(meta)
            payoff = _settle(seat_stacks, role_seats, leaf_contribs,
                             _fold_ranks(n_roles, winner), prizes, v_lookup)
            leaf_kind.append("fold")
            leaf_payload.append((winner, payoff))
            continue
        participants = tuple(meta)
        if len(participants) == n_roles and n_roles == 3:
            outcome_list: tuple[tuple[int, ...], ...] = outcomes3
            base = tensors.wt13
        elif n_roles == 3:
            outcome_list = outcomes2
            base = tensors.wt2_fold[participants]
        else:
            outcome_list = outcomes2
            base = tensors.wt2_endgame
        payoffs = np.zeros((len(outcome_list), n_roles), dtype=np.float64)
        for position, outcome in enumerate(outcome_list):
            payoffs[position] = _settle(
                seat_stacks, role_seats, leaf_contribs,
                _sd_ranks(n_roles, participants, outcome), prizes, v_lookup,
            )
        matrix = (base @ payoffs.astype(np.float32)).T
        leaf_kind.append("sd")
        leaf_payload.append(np.ascontiguousarray(matrix))
    problem = StageProblem(
        n_roles=n_roles,
        tree=tree,
        nodes=_tree_nodes(tree, allowed),
        allowed=allowed,
        leaf_kind=tuple(leaf_kind),
        leaf_payload=leaf_payload,
        deal=deal,
        total_weight=total_weight,
        count=tensors.count,
    )
    return problem, role_seats, mode


def solve_single_state(
    config: GridConfig,
    tensors: Tensors,
    stacks: tuple[int, int, int],
    button: int,
    sb: int,
    bb_amt: int,
    v_next: Any = None,
    force_jamfold: bool | None = None,
) -> StageResult:
    """Jedna gra etapowa; v_next=None → kontynuacja dokładnym ICM (tryb sanity vs jamfold)."""
    prizes = config.prizes

    def icm_lookup(state: tuple[int, int, int]) -> np.ndarray:
        return np.asarray(icm_equities(state, prizes), dtype=np.float64)

    lookup = icm_lookup if v_next is None else v_next
    # `hand` steruje wyłącznie rolami — dobieramy najmniejszą rękę o tym buttonie.
    hand = button % 3
    problem, role_seats, mode = build_stage_problem(
        tensors, config, stacks, hand, sb, bb_amt, lookup, force_jamfold=force_jamfold
    )
    if problem.n_roles == 3:
        sigma, eps, iterations = _fp_solve(problem, config)
    else:
        sigma, eps, iterations = _cfr_plus_solve(problem, config)
    role_values = _profile_values(problem, sigma)
    values = np.full(3, prizes[2], dtype=np.float64)
    for role, seat in enumerate(role_seats):
        values[seat] = role_values[role]
    sigma_out = np.zeros((N_NODES, tensors.count, 3), dtype=np.float32)
    for node_id, matrix in sigma.items():
        sigma_out[node_id] = matrix
    return StageResult(sigma=sigma_out, values=values, eps=eps,
                       iterations=iterations, mode=mode)


# --- osiągalność i przejścia --------------------------------------------


def enumerate_transitions(
    config: GridConfig, seat_stacks: tuple[int, int, int], hand: int, sb: int, bb_amt: int
) -> set[tuple[int, int, int]]:
    """Stany następne (żywi ≥ 2) po kwantyzacji — niezależne od strategii."""
    found: set[tuple[int, int, int]] = set()

    def collecting_lookup(state: tuple[int, int, int]) -> np.ndarray:
        found.add(quantize_stacks(state, config.grid_step))
        return np.zeros(3, dtype=np.float64)

    build_stage_problem(_transition_tensors(), config, seat_stacks, hand, sb, bb_amt,
                        collecting_lookup)
    return found


_TRANSITION_TENSORS: Tensors | None = None


def _transition_tensors() -> Tensors:
    """Miniaturowe tensory zastępcze do enumeracji przejść (wartości nieistotne)."""
    global _TRANSITION_TENSORS
    if _TRANSITION_TENSORS is None:
        one3 = np.ones((1, len(rollout_tensor.OUTCOMES_3)), dtype=np.float32)
        one2 = np.ones((1, len(rollout_tensor.OUTCOMES_2)), dtype=np.float32)
        _TRANSITION_TENSORS = Tensors(
            classes=(0,), count=1,
            deal3=np.ones(1, dtype=np.float32), wt13=one3,
            wt2_fold={pair: one2.copy() for pair in _AXIS_PAIRS},
            deal2=np.ones(1, dtype=np.float32), wt2_endgame=one2,
            manifest={},
        )
    return _TRANSITION_TENSORS


# --- pętla po warstwach --------------------------------------------------

_WORK: dict[str, Any] = {}


def _solve_state_job(index: int) -> tuple[int, np.ndarray, np.ndarray, float, int, int]:
    tensors: Tensors = _WORK["tensors"]
    config: GridConfig = _WORK["config"]
    hand: int = _WORK["hand"]
    sb, bb_amt = _WORK["blinds"]
    state = _WORK["states"][index]
    v_next_states: dict[tuple[int, int, int], int] = _WORK["v_next_index"]
    v_next: np.ndarray = _WORK["v_next"]

    def lookup(target: tuple[int, int, int]) -> np.ndarray:
        return v_next[v_next_states[quantize_stacks(target, config.grid_step)]]

    problem, role_seats, mode = build_stage_problem(
        tensors, config, state, hand, sb, bb_amt, lookup
    )
    if problem.n_roles == 3:
        sigma, eps, iterations = _fp_solve(problem, config)
    else:
        sigma, eps, iterations = _cfr_plus_solve(problem, config)
    role_values = _profile_values(problem, sigma)
    values = np.full(3, config.prizes[2], dtype=np.float64)
    for role, seat in enumerate(role_seats):
        values[seat] = role_values[role]
    sigma_out = np.zeros((N_NODES, tensors.count, 3), dtype=np.float32)
    for node_id, matrix in sigma.items():
        sigma_out[node_id] = matrix
    return index, values, sigma_out, eps, iterations, MODE_NAMES.index(mode)


def _solve_layer(
    tensors: Tensors,
    config: GridConfig,
    states: tuple[tuple[int, int, int], ...],
    hand: int,
    blinds: tuple[int, int],
    v_next_states: tuple[tuple[int, int, int], ...],
    v_next: np.ndarray,
) -> dict[str, np.ndarray]:
    _WORK.update(
        tensors=tensors,
        config=config,
        hand=hand,
        blinds=blinds,
        states=states,
        v_next_index={state: index for index, state in enumerate(v_next_states)},
        v_next=v_next,
    )
    indices = range(len(states))
    if config.jobs <= 1:
        rows = [_solve_state_job(index) for index in indices]
    else:
        with Pool(processes=config.jobs) as pool:
            rows = list(pool.imap(_solve_state_job, indices, chunksize=4))
    rows.sort(key=lambda row: row[0])
    values = np.stack([row[1] for row in rows], axis=0)
    sigma = np.stack([row[2] for row in rows], axis=0)
    eps = np.array([row[3] for row in rows], dtype=np.float32)
    iters = np.array([row[4] for row in rows], dtype=np.int32)
    modes = np.array([row[5] for row in rows], dtype=np.uint8)
    return {
        "states": np.array(states, dtype=np.int16),
        "v": values,
        "sigma": sigma,
        "eps": eps,
        "iters": iters,
        "mode": modes,
    }


def _reachable_sets(config: GridConfig) -> list[tuple[tuple[int, int, int], ...]]:
    layers = [
        (quantize_stacks(config.start_stacks, config.grid_step),)
    ]
    total = n_hands(config)
    for hand in range(total - 1):
        sb, bb_amt = level_blinds(config, hand)
        found: set[tuple[int, int, int]] = set()
        for state in layers[hand]:
            found |= enumerate_transitions(config, state, hand, sb, bb_amt)
        layers.append(tuple(sorted(found)))
    return layers


def _boundary(
    tensors: Tensors, config: GridConfig, states: tuple[tuple[int, int, int], ...]
) -> tuple[np.ndarray, int, float]:
    """Punkt stały ostatniego poziomu: cykl trzech rąk iterowany od ICM."""
    total = n_hands(config)
    sb, bb_amt = level_blinds(config, total)
    current = np.stack(
        [np.asarray(icm_equities(state, config.prizes), dtype=np.float64) for state in states]
    )
    delta = float("inf")
    cycles = 0
    for cycle in range(config.tail_max_cycles):
        next_v = current
        for offset in (2, 1, 0):
            layer = _solve_layer(
                tensors, config, states, total + offset, (sb, bb_amt), states, next_v
            )
            next_v = layer["v"]
        delta = float(np.max(np.abs(next_v - current)))
        current = next_v
        cycles = cycle + 1
        if delta <= config.tail_tol:
            break
    return current, cycles, delta


def solve(
    config: GridConfig,
    tensor_dir: Path,
    out_dir: Path,
    layers_limit: int | None = None,
) -> dict[str, Any]:
    tensors = load_tensors(tensor_dir, config.classes)
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = config_hash(config, tensors.manifest)
    manifest_path = out_dir / "solve_manifest.json"
    if manifest_path.exists():
        manifest = artifacts.read_json(manifest_path)
        if manifest["config_hash"] != digest:
            raise ValueError("konfiguracja wznowienia różni się od manifestu biegu")
    else:
        manifest = {
            "artifact": "blueprint-grid-pilot",
            "config": asdict(config),
            "config_hash": digest,
            "tensor_dir": str(tensor_dir.resolve()),
            "tensor_sha256": tensors.manifest["sha256"],
            "boundary": None,
            "layers": {},
            "status": "partial",
        }
    total = n_hands(config)
    full_states = grid_states(config.total_chips, config.grid_step)
    started = time.perf_counter()
    boundary_path = out_dir / "boundary.npz"
    if manifest["boundary"] is None or not boundary_path.exists():
        boundary_started = time.perf_counter()
        boundary_v, cycles, delta = _boundary(tensors, config, full_states)
        artifacts.write_npz(
            boundary_path,
            {"states": np.array(full_states, dtype=np.int16), "v": boundary_v},
        )
        manifest["boundary"] = {
            "file": "boundary.npz",
            "sha256": artifacts.sha256_file(boundary_path),
            "cycles": cycles,
            "delta": delta,
            "seconds": round(time.perf_counter() - boundary_started, 3),
        }
        artifacts.write_json(manifest_path, manifest)
    else:
        loaded = artifacts.read_npz(boundary_path)
        boundary_v = loaded["v"]
    reachable = _reachable_sets(config)
    v_next_states: tuple[tuple[int, int, int], ...] = full_states
    v_next = boundary_v
    computed = 0
    for hand in range(total - 1, -1, -1):
        layer_path = out_dir / f"layer_{hand:02d}.npz"
        key = str(hand)
        if key in manifest["layers"] and layer_path.exists():
            loaded = artifacts.read_npz(layer_path)
            states_here = tuple(
                (int(a), int(b), int(c)) for a, b, c in loaded["states"].tolist()
            )
            v_next_states, v_next = states_here, loaded["v"]
            continue
        if layers_limit is not None and computed >= layers_limit:
            manifest["status"] = "partial"
            artifacts.write_json(manifest_path, manifest)
            return manifest
        layer_started = time.perf_counter()
        states_here = reachable[hand]
        sb, bb_amt = level_blinds(config, hand)
        layer = _solve_layer(
            tensors, config, states_here, hand, (sb, bb_amt), v_next_states, v_next
        )
        artifacts.write_npz(layer_path, layer)
        seconds = time.perf_counter() - layer_started
        manifest["layers"][key] = {
            "file": layer_path.name,
            "sha256": artifacts.sha256_file(layer_path),
            "seconds": round(seconds, 3),
            "n_states": len(states_here),
            "seconds_per_state": round(seconds / max(len(states_here), 1), 4),
            "fp_iters_median": float(statistics.median(layer["iters"].tolist())),
            "eps_internal_max": float(layer["eps"].max()),
        }
        artifacts.write_json(manifest_path, manifest)
        v_next_states, v_next = states_here, layer["v"]
        computed += 1
    manifest["status"] = "done"
    manifest["seconds_total_this_run"] = round(time.perf_counter() - started, 3)
    artifacts.write_json(manifest_path, manifest)
    return manifest


def load_layers(out_dir: Path) -> dict[int, dict[str, np.ndarray]]:
    layers: dict[int, dict[str, np.ndarray]] = {}
    for path in sorted(out_dir.glob("layer_*.npz")):
        hand = int(path.stem.split("_")[1])
        layers[hand] = artifacts.read_npz(path)
    return layers


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tensor", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--grid-step", type=int, default=5)
    parser.add_argument("--prizes", type=str, default="0.8,0.2,0.0")
    parser.add_argument("--fp-iters", type=int, default=24)
    parser.add_argument("--fp-check-every", type=int, default=8)
    parser.add_argument("--fp-tol", type=float, default=1e-3)
    parser.add_argument("--fp-restarts", type=int, default=2)
    parser.add_argument("--cfr-iters", type=int, default=128)
    parser.add_argument("--tail-cycles", type=int, default=3)
    parser.add_argument("--tail-tol", type=float, default=1e-3)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--layers-limit", type=int, default=None)
    args = parser.parse_args(argv)
    prizes = tuple(float(part) for part in args.prizes.split(","))
    if len(prizes) != 3:
        raise SystemExit("--prizes wymaga trzech wartości")
    config = GridConfig(
        prizes=(prizes[0], prizes[1], prizes[2]),
        grid_step=args.grid_step,
        fp_max_iters=args.fp_iters,
        fp_check_every=args.fp_check_every,
        fp_tol=args.fp_tol,
        fp_restarts=args.fp_restarts,
        cfr_iters=args.cfr_iters,
        tail_max_cycles=args.tail_cycles,
        tail_tol=args.tail_tol,
        jobs=args.jobs,
    )
    manifest = solve(config, args.tensor, args.out, layers_limit=args.layers_limit)
    print(json.dumps({"status": manifest["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

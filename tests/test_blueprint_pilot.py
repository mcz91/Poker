"""Testy pilota blueprintu (POKER-46/47/49/50): tensor rolloutu 3-way, solver siatki, ex-post.

Narzędzia żyją w tools/blueprint/ (zależności extras train) i są ładowane
przez importlib jak w testach reprodukcji treningu (test_mccfr, test_mlp).
Testy używają malutkich konfiguracji: podzbiór klas preflop, siatka 25
żetonów, 2 poziomy zegara i syntetyczny tensor — pełny pilot żyje poza bramką.
"""

import dataclasses
import importlib.util
import io
import itertools
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

import pytest

from poker.cards import Card, Rank, Suit
from poker.evaluation import evaluate_five
from poker.icm import icm_equities
from poker.preflop import ALL_CLASSES, CLASS_INDEX, PreflopClass
from poker.preflop_equity import equity as class_equity
from poker.preflop_equity_data import TRIALS_PER_PAIR
from poker.spin import blinds_for_hand

REPO = Path(__file__).resolve().parent.parent
BLUEPRINT = REPO / "tools" / "blueprint"

PRIZES = (0.8, 0.2, 0.0)


def _load(name: str) -> Any:
    """Ładuje moduł z tools/blueprint pod nazwą stem — jak testy reprodukcji."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _import_reader() -> Any:
    """Czytnik formatu blueprintu jako moduł — jedyny konsument formatu w pakiecie."""
    from poker import blueprint_reader

    return blueprint_reader


def _cls(name: str) -> int:
    """Indeks klasy preflop po nazwie w rodzaju 'AKs', 'QQ', '72o'."""
    symbols = {
        "A": Rank.ACE, "K": Rank.KING, "Q": Rank.QUEEN, "J": Rank.JACK, "T": Rank.TEN,
        "9": Rank.NINE, "8": Rank.EIGHT, "7": Rank.SEVEN, "6": Rank.SIX, "5": Rank.FIVE,
        "4": Rank.FOUR, "3": Rank.THREE, "2": Rank.TWO,
    }
    high, low = symbols[name[0]], symbols[name[1]]
    suited = len(name) == 3 and name[2] == "s"
    return CLASS_INDEX[PreflopClass(high=high, low=low, suited=suited)]


TEST_CLASSES = ("AA", "KK", "Q7s", "72o")

# Trójka o trzech różnych, mocno rozstrzelonych sile klasach: permutacje ról
# obejmują wtedy 3-cykle, na których widać złą orientację osi (transpozycje są
# inwolucjami, więc odwrócona tabela permutacji przechodzi je niezauważona).
AXIS_CLASSES = ("AA", "72o", "J8o")

# Klasy prawdziwego tensora kotwic: trójka osi plus KK, żeby próbka par
# w porównaniu z `poker.preflop_equity` miała dziesięć par, a nie trzy.
TENSOR_CLASSES = (*AXIS_CLASSES, "KK")

# Liście puli 2-way przy trzech żywych w stanie 50/50/50 na blindach 1/2:
# (liść, uczestnicy showdownu, wkłady per rola z `_contribs_3max`). Trzy liście
# pokrywają wszystkie trzy pary osi, więc kotwica przechodzi każdą tablicę
# `wt2_fold` — a nie tylko tę, którą akurat czyta pierwszy liść.
LEAVES_2WAY = (
    (5, (1, 2), (0, 50, 50)),  # U fold, T jam, B call
    (10, (0, 1), (50, 50, 2)),  # U open, T jam, B fold, U call
    (15, (0, 2), (50, 1, 50)),  # U jam, T fold, B call
)


def _toy_classes() -> tuple[int, ...]:
    return tuple(sorted(_cls(name) for name in TEST_CLASSES))


def _axis_classes() -> tuple[int, ...]:
    return tuple(sorted(_cls(name) for name in TENSOR_CLASSES))


def _pair_equity(rt: Any, row: Any) -> float:
    """Equity roli na pierwszej osi pary z wiersza (3,) tensora 2-way: wygrana + pół remisu."""
    total = float(row.sum())
    assert total > 0.0
    win = float(row[rt.OUTCOMES_2.index((0, 1))])
    tie = float(row[rt.OUTCOMES_2.index((0, 0))])
    return (win + 0.5 * tie) / total


def _mc_tolerance(effective_trials: float, sigmas: float = 4.0) -> float:
    """Próg zgodności equity wyprowadzony z liczby prób, nie dobrany do wyniku.

    Equity to średnia zmiennej z [0, 1], więc wariancja jednej próby ≤ 1/4.
    Porównujemy dwa pomiary Monte Carlo — tensor (`effective_trials` prób
    efektywnych) i macierz `poker.preflop_equity` (TRIALS_PER_PAIR prób na
    parę) — więc próg to `sigmas` odchyleń ich złożonego błędu.
    """
    return sigmas * math.hypot(
        0.5 / math.sqrt(effective_trials), 0.5 / math.sqrt(TRIALS_PER_PAIR)
    )


def _outright_by_axis(rt: Any, probs: Any) -> Any:
    """Prawdopodobieństwo wygranej bez remisu dla gracza na każdej z trzech osi."""
    np = rt.np
    return np.array(
        [
            sum(float(probs[out]) for out, ranks in enumerate(rt.OUTCOMES_3) if ranks[axis] == 0)
            for axis in range(3)
        ]
    )


def _to_base_axes(rt: Any, source: tuple[int, ...]) -> Any:
    """Mapa zdarzeń z osi permutowanych (oś a trzyma klasę bazową source[a]) na osie bazowe."""
    np = rt.np
    position = {ranks: index for index, ranks in enumerate(rt.OUTCOMES_3)}
    return np.array(
        [position[tuple(ranks[source.index(base)] for base in range(3))] for ranks in rt.OUTCOMES_3]
    )


def _synthetic_artifacts(tmp: Path, classes: tuple[int, ...], trials: int = 64) -> Path:
    """Syntetyczny artefakt tensora: rozkład deterministyczny od indeksów klas."""
    rt = _load("rollout_tensor")
    np = rt.np
    multisets = rt.multisets_for(classes)
    counts3 = np.zeros((len(multisets), 13), dtype=np.uint32)
    for row, triple in enumerate(multisets):
        remaining = trials
        for out in range(13):
            share = (row + out * 7 + triple[0]) % 11 + 1
            take = min(remaining, share)
            counts3[row, out] = take
            remaining -= take
        counts3[row, 0] += remaining
    pairs = rt.pairs_for(classes)
    counts2 = np.zeros((len(pairs), 3), dtype=np.uint32)
    for row, pair in enumerate(pairs):
        win = (row * 5 + pair[0]) % (trials - 2) + 1
        split = (row * 3) % (trials - win)
        counts2[row] = (win, split, trials - win - split)
    out_dir = tmp / "tensor"
    out_dir.mkdir(parents=True, exist_ok=True)
    rt.write_artifacts(
        out_dir,
        classes=classes,
        multisets=multisets,
        counts3=counts3,
        pairs=pairs,
        counts2=counts2,
        manifest_extra={
            "method": "synthetic-test", "master_seed": 0,
            "trials": trials, "hu_trials": trials, "backend": "synthetic",
        },
    )
    return out_dir


def _toy_config(sg: Any, **overrides: Any) -> Any:
    base: dict[str, Any] = {
        "prizes": PRIZES,
        "levels": ((1, 2), (2, 4)),
        "hands_per_level": 1,
        "total_chips": 150,
        "start_stacks": (50, 50, 50),
        "grid_step": 25,
        "classes": _toy_classes(),
        "fp_max_iters": 6,
        "fp_check_every": 3,
        "fp_tol": 0.0,
        "fp_restarts": 2,
        "cfr_iters": 8,
        "tail_max_cycles": 1,
        "tail_tol": 0.0,
        "jobs": 1,
    }
    base.update(overrides)
    return sg.GridConfig(**base)


@pytest.fixture(scope="module")
def axis_tensor(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Prawdziwy (nie syntetyczny) tensor trzech klas — kotwica orientacji osi."""
    rt = _load("rollout_tensor")
    out_dir = tmp_path_factory.mktemp("axes") / "tensor"
    rt.generate_artifacts(
        out_dir, trials=600, hu_trials=300, master_seed=23,
        classes=_axis_classes(), jobs=1, backend="direct",
    )
    return out_dir


@pytest.fixture(scope="module")
def curve_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Bieg toy z tolerancją, która kończy PI-FP przed sufitem — baza pomiaru krzywej.

    Trzy ręce na tych samych blindach, żeby w warstwach był więcej niż jeden
    stan `deep`; `fp_tol=1.0` jest osiągalne w pierwszym sprawdzeniu, więc bieg
    nigdy nie dochodzi do sufitu — dokładnie sytuacja, którą pomiar ma omijać.
    """
    sg = _load("solve_grid")
    ep = _load("expost")
    tmp = tmp_path_factory.mktemp("curve")
    tensor_dir = _synthetic_artifacts(tmp, _toy_classes())
    out_dir = tmp / "solve"
    config = _toy_config(
        sg, levels=((1, 2), (1, 2), (1, 2)), hands_per_level=1,
        fp_max_iters=6, fp_check_every=2, fp_tol=1.0,
    )
    sg.solve(config, tensor_dir, out_dir)
    ep.run_expost(out_dir)
    return {"sg": sg, "out_dir": out_dir, "config": config}


@pytest.fixture(scope="module")
def toy_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Jeden pełny bieg toy-solvera współdzielony przez testy raportów."""
    sg = _load("solve_grid")
    tmp = tmp_path_factory.mktemp("toy")
    tensor_dir = _synthetic_artifacts(tmp, _toy_classes())
    out_dir = tmp / "solve"
    config = _toy_config(sg)
    manifest = sg.solve(config, tensor_dir, out_dir)
    return {"sg": sg, "tensor_dir": tensor_dir, "out_dir": out_dir,
            "config": config, "manifest": manifest, "tmp": tmp}


def test_13_rozstrzygniec_to_wszystkie_slabe_porzadki() -> None:
    rt = _load("rollout_tensor")
    expected3 = set()
    for values in itertools.product(range(3), repeat=3):
        expected3.add(tuple(sum(1 for w in values if w > v) for v in values))
    assert set(rt.OUTCOMES_3) == expected3
    assert len(rt.OUTCOMES_3) == 13
    assert list(rt.OUTCOMES_3) == sorted(rt.OUTCOMES_3)
    expected2 = set()
    for values2 in itertools.product(range(2), repeat=2):
        expected2.add(tuple(sum(1 for w in values2 if w > v) for v in values2))
    assert set(rt.OUTCOMES_2) == expected2
    assert len(rt.OUTCOMES_2) == 3


def test_pack_value_zachowuje_porzadek_ewaluatora() -> None:
    rt = _load("rollout_tensor")
    deck = [Card(rank, suit) for rank in Rank for suit in Suit]
    rng = random.Random(9)
    hands = [tuple(rng.sample(deck, 5)) for _ in range(200)]
    values = [evaluate_five(hand) for hand in hands]
    packed = [rt.pack_value(value) for value in values]
    for (va, pa), (vb, pb) in itertools.combinations(zip(values, packed, strict=True), 2):
        assert (va < vb) == (pa < pb)
        assert (va == vb) == (pa == pb)


def test_symulacja_trojki_deterministyczna_i_zliczenia() -> None:
    rt = _load("rollout_tensor")
    np = rt.np
    triple = tuple(sorted((_cls("AA"), _cls("KK"), _cls("72o"))))
    trials = 400
    seed = rt.triple_seed(7, *triple)
    first = rt.simulate_triple(triple, trials, np.random.Generator(np.random.PCG64(seed)), None)
    second = rt.simulate_triple(triple, trials, np.random.Generator(np.random.PCG64(seed)), None)
    assert (first == second).all()
    assert int(first.sum()) == trials
    positions = {cls: pos for pos, cls in enumerate(triple)}
    aa_solo = sum(
        int(first[out]) for out, ranks in enumerate(rt.OUTCOMES_3)
        if ranks[positions[_cls("AA")]] == 0 and sorted(ranks) == [0, 1, 2]
    )
    junk_solo = sum(
        int(first[out]) for out, ranks in enumerate(rt.OUTCOMES_3)
        if ranks[positions[_cls("72o")]] == 0 and sorted(ranks) == [0, 1, 2]
    )
    assert aa_solo > junk_solo


def test_tensor_aa_wygrywa_na_swojej_osi_niezaleznie_od_kolejnosci() -> None:
    """Kotwica orientacji osi w tensorze: AA wygrywa tam, gdzie ją posadzono.

    Sześć kolejności tej samej trójki klas (w tym oba 3-cykle) musi dać po
    przeniesieniu na osie bazowe zgodne prawdopodobieństwa wygranej.
    """
    rt = _load("rollout_tensor")
    np = rt.np
    aa = _cls("AA")
    base_triple = tuple(_cls(name) for name in AXIS_CLASSES)
    trials = 600
    base_outright = None
    for source in itertools.permutations(range(3)):
        ordered = tuple(base_triple[source[axis]] for axis in range(3))
        seed = rt.triple_seed(23, *ordered)
        counts = rt.simulate_triple(
            ordered, trials, np.random.Generator(np.random.PCG64(seed)), None
        )
        assert int(counts.sum()) == trials
        outright = _outright_by_axis(rt, counts / counts.sum())
        aa_axis = ordered.index(aa)
        assert outright[aa_axis] > 0.55, (ordered, outright)
        for axis in range(3):
            if axis != aa_axis:
                assert outright[aa_axis] > 2.0 * outright[axis], (ordered, outright)
        in_base = np.zeros(3)
        for axis in range(3):
            in_base[source[axis]] = outright[axis]
        if base_outright is None:
            base_outright = in_base
        else:
            # Strumienie RNG różnią się kolejnością klas, więc porównanie jest
            # statystyczne: szum przy 600 próbach to ~0,03, pomyłka osi ~0,5.
            assert float(np.max(np.abs(in_base - base_outright))) < 0.15, (ordered, in_base)


def test_konsument_wt13_ma_te_sama_orientacje_osi_co_tensor(axis_tensor: Path) -> None:
    """Kotwica orientacji osi w `load_tensors`: wt13 indeksowane rolą, nie multizbiorem.

    Wszystkie sześć kolejności czyta ten sam wiersz multizbioru, więc zgodność
    po przeniesieniu na osie bazowe musi być dokładna, nie statystyczna.
    """
    sg = _load("solve_grid")
    rt = _load("rollout_tensor")
    np = sg.np
    classes = _axis_classes()
    tensors = sg.load_tensors(axis_tensor, classes)
    slot = {index: position for position, index in enumerate(classes)}
    aa = _cls("AA")
    base_triple = tuple(_cls(name) for name in AXIS_CLASSES)
    base_probs = None
    for source in itertools.permutations(range(3)):
        ordered = tuple(base_triple[source[axis]] for axis in range(3))
        flat = (slot[ordered[0]] * tensors.count + slot[ordered[1]]) * tensors.count + slot[
            ordered[2]
        ]
        weighted = tensors.wt13[flat]
        assert float(weighted.sum()) > 0.0
        probs = weighted / weighted.sum()
        outright = _outright_by_axis(rt, probs)
        aa_axis = ordered.index(aa)
        assert outright[aa_axis] > 0.55, (ordered, outright)
        for axis in range(3):
            if axis != aa_axis:
                assert outright[aa_axis] > 2.0 * outright[axis], (ordered, outright)
        in_base = np.zeros(len(rt.OUTCOMES_3), dtype=np.float64)
        in_base[_to_base_axes(rt, source)] = probs
        if base_probs is None:
            base_probs = in_base
        else:
            assert float(np.max(np.abs(in_base - base_probs))) < 1e-6, (ordered, in_base)
        assert abs(float(weighted.sum()) - float(tensors.deal3[flat])) < 1e-3


def test_konsument_wt2_endgame_nie_zamienia_rol_hu(axis_tensor: Path) -> None:
    """Ta sama kotwica dla endgame'u HU: rola trzymająca AA ma equity AA, nie 72o."""
    sg = _load("solve_grid")
    rt = _load("rollout_tensor")
    classes = _axis_classes()
    tensors = sg.load_tensors(axis_tensor, classes)
    slot = {index: position for position, index in enumerate(classes)}
    split = rt.OUTCOMES_2.index((0, 0))
    better_a = rt.OUTCOMES_2.index((0, 1))  # rola 0 lepsza: nikt nie jest od niej lepszy
    aa, junk = _cls("AA"), _cls("72o")
    for first, second, expected_high in ((aa, junk, True), (junk, aa, False)):
        weighted = tensors.wt2_endgame[slot[first] * tensors.count + slot[second]]
        total = float(weighted.sum())
        assert total > 0.0
        equity_first = (float(weighted[better_a]) + 0.5 * float(weighted[split])) / total
        assert (equity_first > 0.7) if expected_high else (equity_first < 0.3), equity_first


def test_kontrakcja_wyplat_sadza_aa_na_wlasciwej_roli(axis_tensor: Path) -> None:
    """Kotwica orientacji osi u konsumenta wypłat: tensor liścia showdownu 3-way.

    Przy równych stackach wypłaty są symetryczne względem ról, więc rola z AA
    ma najwyższe EV w każdej kolejności, a jej EV nie zależy od kolejności.
    """
    sg = _load("solve_grid")
    np = sg.np
    classes = _axis_classes()
    tensors = sg.load_tensors(axis_tensor, classes)
    config = _toy_config(sg, classes=classes)
    stacks = (50, 50, 50)

    def icm_lookup(state: tuple[int, int, int]) -> Any:
        return np.asarray(icm_equities(state, PRIZES), dtype=np.float64)

    problem, _, mode = sg.build_stage_problem(
        tensors, config, stacks, 0, 1, 2, icm_lookup
    )
    assert mode == "deep"
    leaf = 16  # U jam, T call, B call — jedyny liść z showdownem całej trójki
    assert problem.leaf_kind[leaf] == "sd"
    payload = problem.leaf_payload[leaf]
    slot = {index: position for position, index in enumerate(classes)}
    aa = _cls("AA")
    base_triple = tuple(_cls(name) for name in AXIS_CLASSES)
    aa_values: list[float] = []
    for source in itertools.permutations(range(3)):
        ordered = tuple(base_triple[source[axis]] for axis in range(3))
        flat = (slot[ordered[0]] * tensors.count + slot[ordered[1]]) * tensors.count + slot[
            ordered[2]
        ]
        weight = float(tensors.deal3[flat])
        assert weight > 0.0
        values = [float(payload[role][flat]) / weight for role in range(3)]
        aa_role = ordered.index(aa)
        assert values[aa_role] == max(values), (ordered, values)
        for role in range(3):
            if role != aa_role:
                assert values[aa_role] > values[role] + 1e-3, (ordered, values)
        aa_values.append(values[aa_role])
    assert max(aa_values) - min(aa_values) < 1e-5, aa_values


def _chips_problem(sg: Any, tensors: Any, classes: tuple[int, ...]) -> tuple[Any, tuple[int, ...]]:
    """Gra etapowa 50/50/50 na blindach 1/2 z kontynuacją „wartość = stacki po ręce".

    Kontynuacja podaje wprost wektor stacków, więc wypłata liścia jest oczekiwaną
    liczbą żetonów roli — wypłaty widać wprost, bez pośrednictwa ICM.
    """
    config = _toy_config(sg, classes=classes)
    problem, role_seats, mode = sg.build_stage_problem(
        tensors, config, (50, 50, 50), 0, 1, 2,
        lambda state: sg.np.asarray(state, dtype=float),
    )
    assert mode == "deep"
    return problem, role_seats


def _flat_index(tensors: Any, slot: dict[int, int], ordered: tuple[int, ...]) -> int:
    count = int(tensors.count)
    return (slot[ordered[0]] * count + slot[ordered[1]]) * count + slot[ordered[2]]


def test_kotwica_orientacji_osi_wt2_fold(axis_tensor: Path) -> None:
    """Kotwica orientacji osi puli 2-way przy trzech żywych — tensor i jego konsument.

    Kolaps trójki do pary jest inwolucją, więc odwrócenie osi nie zostawia śladu
    w niczym poza equity roli, a wybór złej pary osi nie zostawia śladu w ogóle.
    Kotwica przechodzi wszystkie trzy pary osi (`wt2_fold` wprost i trzy liście
    2-way, po jednym na parę) i wszystkie sześć kolejności klas: rola posadzona
    na AA ma equity AA niezależnie od klasy foldującego i od porządku argumentów.
    """
    sg = _load("solve_grid")
    rt = _load("rollout_tensor")
    classes = _axis_classes()
    tensors = sg.load_tensors(axis_tensor, classes)
    assert sorted(tensors.wt2_fold) == [(0, 1), (0, 2), (1, 2)]
    slot = {index: position for position, index in enumerate(classes)}
    aa = _cls("AA")
    base_triple = tuple(_cls(name) for name in AXIS_CLASSES)
    problem, _ = _chips_problem(sg, tensors, classes)
    seen: dict[tuple[int, int, int], list[float]] = {}
    for source in itertools.permutations(range(3)):
        ordered = tuple(base_triple[source[axis]] for axis in range(3))
        flat = _flat_index(tensors, slot, ordered)
        weight = float(tensors.deal3[flat])
        assert weight > 0.0
        for leaf, participants, contribs in LEAVES_2WAY:
            axis_a, axis_b = participants
            folder = 3 - axis_a - axis_b
            pot = sum(contribs)
            payload = problem.leaf_payload[leaf]
            assert problem.leaf_kind[leaf] == "sd"
            equities = (
                _pair_equity(rt, tensors.wt2_fold[(axis_a, axis_b)][flat]),
                (float(payload[axis_a][flat]) / weight
                 - (50 - contribs[axis_a])) / pot,
            )
            for equity in equities:
                if ordered[axis_a] == aa:
                    assert equity > 0.75, (leaf, ordered, equity)
                if ordered[axis_b] == aa:
                    assert equity < 0.25, (leaf, ordered, equity)
            # Ta sama para klas przy tym samym foldującym musi dać tę samą liczbę
            # z każdej pary osi i z obu porządków — inaczej osie się rozjeżdżają.
            assert abs(equities[0] - equities[1]) < 1e-3, (leaf, ordered, equities)
            seen.setdefault(
                (ordered[axis_a], ordered[axis_b], ordered[folder]), []
            ).append(equities[0])
    assert len(seen) == 6  # trzy klasy: trzy wybory foldującego × dwa kierunki pary
    for key, values in seen.items():
        assert len(values) == 3
        assert max(values) - min(values) < 1e-5, (key, values)
        mirrored = seen[(key[1], key[0], key[2])]
        assert abs(values[0] + mirrored[0] - 1.0) < 1e-5, (key, values, mirrored)


def test_kotwica_wyplat_lisca_2way(axis_tensor: Path) -> None:
    """Wypłaty liścia 2-way przy trzech żywych: pula do najsilniejszego, folder bez niej.

    Odpowiednik istniejącej kotwicy liścia 16 dla puli 2-way: suma żetonów jest
    stała, foldujący traci dokładnie swój wkład (zwrot nadpłaty i nic ponadto),
    a rola z AA przeciw 72o zabiera pulę.
    """
    sg = _load("solve_grid")
    classes = _axis_classes()
    tensors = sg.load_tensors(axis_tensor, classes)
    slot = {index: position for position, index in enumerate(classes)}
    aa, junk, dead = _cls("AA"), _cls("72o"), _cls("J8o")
    problem, _ = _chips_problem(sg, tensors, classes)
    for leaf, participants, contribs in LEAVES_2WAY:
        payload = problem.leaf_payload[leaf]
        folder = 3 - participants[0] - participants[1]
        pot = sum(contribs)
        ordered_list = [dead, dead, dead]
        ordered_list[participants[0]], ordered_list[participants[1]] = aa, junk
        ordered = (ordered_list[0], ordered_list[1], ordered_list[2])
        flat = _flat_index(tensors, slot, ordered)
        weight = float(tensors.deal3[flat])
        chips = [float(payload[role][flat]) / weight for role in range(3)]
        assert abs(sum(chips) - 150.0) < 1e-2, (leaf, chips)
        assert abs(chips[folder] - (50 - contribs[folder])) < 1e-2, (leaf, chips)
        won = [(chips[role] - (50 - contribs[role])) / pot for role in participants]
        assert won[0] > 0.85, (leaf, chips, won)
        assert won[1] < 0.15, (leaf, chips, won)
        assert abs(won[0] + won[1] - 1.0) < 1e-3, (leaf, won)


def test_equity_wt2_fold_zgadza_sie_z_macierza_preflop_equity(axis_tensor: Path) -> None:
    """Equity puli 2-way z tensora obok `poker.preflop_equity` — próg z liczby prób.

    Marginalizacja po klasie foldującego (wagami rozdania) daje equity pary klas
    liczone na innym modelu niż macierz produktu (trójki z card removal, board
    z 46 kart wobec par i 48 kart), więc wiąże je błąd Monte Carlo obu źródeł,
    a nie równość. Próg jest wyprowadzony z liczb prób obu artefaktów.
    """
    sg = _load("solve_grid")
    rt = _load("rollout_tensor")
    np = sg.np
    classes = _axis_classes()
    tensors = sg.load_tensors(axis_tensor, classes)
    trials = float(tensors.manifest["trials"])
    count = tensors.count
    pairs = 0
    worst = 0.0
    for first in range(count):
        for second in range(count):
            base = (first * count + second) * count
            rows = tensors.wt2_fold[(0, 1)][base:base + count]
            weights = np.asarray(
                [float(tensors.deal3[base + folder]) for folder in range(count)]
            )
            live = weights[weights > 0.0]
            assert live.size > 0
            equity = _pair_equity(rt, rows.sum(axis=0))
            expected = class_equity(ALL_CLASSES[classes[first]], ALL_CLASSES[classes[second]])
            # Próby efektywne marginalizacji: wagi rozdania nie są równe, więc
            # liczy się (Σw)²/Σw² wierszy, a nie ich liczba.
            n_eff = trials * float(live.sum() ** 2 / (live**2).sum())
            tolerance = _mc_tolerance(n_eff)
            assert tolerance < 0.1, tolerance  # próg luźniejszy nie odróżniałby klas
            assert abs(equity - expected) <= tolerance, (
                classes[first], classes[second], equity, expected, tolerance
            )
            pairs += 1
            worst = max(worst, abs(equity - expected))
    assert pairs == count * count and pairs >= 16
    # Próg musi odróżniać klasy, a nie tylko przepuszczać: podmiana partnera
    # w parze (72o na J8o przy AA) daje różnicę większą niż on.
    aa, junk, other = _cls("AA"), _cls("72o"), _cls("J8o")
    mismatch = abs(
        class_equity(ALL_CLASSES[aa], ALL_CLASSES[junk])
        - class_equity(ALL_CLASSES[aa], ALL_CLASSES[other])
    )
    assert worst < mismatch, (worst, mismatch)


def test_artefakt_tensora_reprodukcja_podzbioru(tmp_path: Path) -> None:
    rt = _load("rollout_tensor")
    np = rt.np
    classes = _toy_classes()
    dirs = (tmp_path / "a", tmp_path / "b")
    for out_dir in dirs:
        rt.generate_artifacts(
            out_dir, trials=40, hu_trials=30, master_seed=11,
            classes=classes, jobs=1, backend="direct",
        )
    assert (dirs[0] / "rollout3.npz").read_bytes() == (dirs[1] / "rollout3.npz").read_bytes()
    assert (dirs[0] / "rollout_hu.npz").read_bytes() == (dirs[1] / "rollout_hu.npz").read_bytes()
    manifest = json.loads((dirs[0] / "rollout_manifest.json").read_text())
    for key in ("method", "master_seed", "trials", "hu_trials", "classes", "backend"):
        assert key in manifest
    data = rt.read_artifacts(dirs[0])
    multisets = [tuple(int(x) for x in row) for row in data["multisets"]]
    row = multisets.index(tuple(sorted((_cls("AA"), _cls("KK"), _cls("72o")))))
    triple = multisets[row]
    seed = rt.triple_seed(11, *triple)
    redo = rt.simulate_triple(triple, 40, np.random.Generator(np.random.PCG64(seed)), None)
    assert (redo == data["counts3"][row]).all()
    for weight, counts_row, multiset in zip(
        data["weights3"], data["counts3"], multisets, strict=True
    ):
        if int(weight) > 0:
            assert int(counts_row.sum()) == 40, multiset
        else:
            assert int(counts_row.sum()) == 0, multiset
    aa = _cls("AA")
    infeasible = multisets.index((aa, aa, aa))
    assert int(data["weights3"][infeasible]) == 0  # trzy pary AA wymagają sześciu asów


def test_kwantyzacja_zachowuje_sume_zywych_i_wielokrotnosc() -> None:
    sg = _load("solve_grid")
    rng = random.Random(3)
    cases = [(1, 1, 148), (2, 3, 145), (0, 74, 76), (50, 50, 50), (0, 1, 149)]
    for _ in range(200):
        a = rng.randrange(0, 151)
        b = rng.randrange(0, 151 - a)
        cases.append((a, b, 150 - a - b))
    for stacks in cases:
        for step in (5, 10, 25):
            quantized = sg.quantize_stacks(stacks, step)
            assert sum(quantized) == sum(stacks)
            assert all(value % step == 0 for value in quantized)
            for before, after in zip(stacks, quantized, strict=True):
                assert (before > 0) == (after > 0)
            assert quantized == sg.quantize_stacks(stacks, step)
    assert sg.quantize_stacks((1, 1, 148), 5) == (5, 5, 140)


def test_domyslny_budzet_pi_fp_pochodzi_z_krzywej_i_jest_ten_sam_w_cli() -> None:
    """Budżet PI-FP zmierzony w POKER-47; CLI nie może się rozjechać z GridConfig.

    Sufit 384 i tolerancja 5e-5 pochodzą z krzywej ε-vs-iteracje (POKER-47):
    tolerancja 1e-3 pilota POKER-46 była progiem wiążącym — kończyła PI-FP
    zanim sufit cokolwiek znaczył, a jej dług sumował się przez 21 warstw DAG-u.
    """
    sg = _load("solve_grid")
    defaults = sg.GridConfig()
    assert (defaults.fp_max_iters, defaults.fp_tol) == (384, 5e-5)
    parsed = sg.build_parser().parse_args(["--tensor", "t", "--out", "o"])
    assert parsed.fp_iters == defaults.fp_max_iters
    assert parsed.fp_tol == defaults.fp_tol
    assert parsed.fp_restarts == defaults.fp_restarts
    assert parsed.fp_check_every == defaults.fp_check_every
    assert parsed.cfr_iters == defaults.cfr_iters
    assert parsed.grid_step == defaults.grid_step


def test_kryteria_stopu_solverow_maja_ten_sam_ksztalt_i_te_same_wartosci_w_cli() -> None:
    """Kryteria stopu mają ten sam kształt, a CLI nie rozjeżdża się z konfiguracją.

    Tolerancja CFR+ jest ta sama co PI-FP, bo dług obu solverów sumuje się
    w tym samym DAG-u i mierzy go ta sama metryka ex-post. Sufity pochodzą
    z krzywych POKER-49: horyzont 12 cykli przy tolerancji 5e−4 (delta ma
    podłogę ~2e−4, więc niżej zejść nie może), CFR+ 512 iteracji przy
    tolerancji 5e−5 (osiąga ją 128, sufit daje zapas).
    """
    sg = _load("solve_grid")
    defaults = sg.GridConfig()
    assert defaults.cfr_tol == defaults.fp_tol
    assert (defaults.tail_max_cycles, defaults.tail_tol) == (12, 5e-4)
    assert (defaults.cfr_iters, defaults.cfr_check_every) == (512, 32)
    assert defaults.boundary_perturb == 0.0
    parsed = sg.build_parser().parse_args(["--tensor", "t", "--out", "o"])
    assert parsed.tail_cycles == defaults.tail_max_cycles
    assert parsed.tail_tol == defaults.tail_tol
    assert parsed.cfr_iters == defaults.cfr_iters
    assert parsed.cfr_check_every == defaults.cfr_check_every
    assert parsed.cfr_tol == defaults.cfr_tol
    assert parsed.perturb == defaults.boundary_perturb
    assert parsed.perturb_kind == defaults.boundary_perturb_kind
    assert parsed.boundary_from is None


def test_horyzont_konczy_na_tolerancji_a_nie_na_sufcie(tmp_path: Path) -> None:
    """Punkt stały ostatniego poziomu zbiega do tolerancji; sufit tylko zabezpiecza.

    Bieg raportuje deltę każdego cyklu, więc „zbiegł" i „skończył się budżet" są
    rozróżnialne w artefakcie — pilot POKER-47 kończył na sufcie i nie było tego
    widać w żadnej liczbie poza prozą.
    """
    sg = _load("solve_grid")
    tensor_dir = _synthetic_artifacts(tmp_path, _toy_classes())
    loose = _toy_config(sg, tail_max_cycles=6, tail_tol=1.0)
    boundary = sg.solve(loose, tensor_dir, tmp_path / "loose", layers_limit=0)["boundary"]
    assert boundary["converged"] is True
    assert boundary["cycles"] < loose.tail_max_cycles
    assert boundary["delta"] <= loose.tail_tol
    assert boundary["deltas"] == pytest.approx([boundary["delta"]])
    assert boundary["source"]["kind"] == "computed"
    tight = _toy_config(sg, tail_max_cycles=2, tail_tol=0.0)
    strict = sg.solve(tight, tensor_dir, tmp_path / "tight", layers_limit=0)["boundary"]
    assert strict["converged"] is False
    assert strict["cycles"] == tight.tail_max_cycles == len(strict["deltas"])
    assert strict["delta"] > 0.0


def test_zaburzenie_brzegu_jest_zerosumowe_i_deterministyczne() -> None:
    """Zaburzony brzeg jest nadal legalnym brzegiem: suma nagród stała, wybici bez zmian."""
    sg = _load("solve_grid")
    np = sg.np
    states = sg.grid_states(150, 25)
    values = np.stack(
        [np.asarray(icm_equities(state, PRIZES), dtype=float) for state in states]
    )
    assert sg.perturb_boundary(values, states, 0.0, "tilt") is values
    for kind in sg.PERTURB_KINDS:
        shifted = sg.perturb_boundary(values, states, 0.002, kind)
        assert bool((shifted == sg.perturb_boundary(values, states, 0.002, kind)).all())
        assert float(np.max(np.abs(shifted.sum(axis=1) - values.sum(axis=1)))) < 1e-12
        assert float(np.max(np.abs(shifted - values))) == pytest.approx(0.002, rel=1e-9)
        for position, state in enumerate(states):
            for seat in range(3):
                if state[seat] == 0:
                    assert shifted[position, seat] == values[position, seat]
    tilt = sg.perturb_boundary(values, states, 0.002, "tilt")
    noise = sg.perturb_boundary(values, states, 0.002, "noise")
    assert float(np.max(np.abs(tilt - noise))) > 1e-4  # dwa różne błędy brzegu
    with pytest.raises(ValueError):
        sg.perturb_boundary(values, states, 0.002, "gaussian")


def test_wrazliwosc_na_brzeg_mierzy_zmiane_epsilon_i_strategii(tmp_path: Path) -> None:
    """Pomiar ślepoty metryki: zaburzony brzeg wchodzi do porównania, zerowy nie zmienia nic."""
    sg = _load("solve_grid")
    ep = _load("expost")
    bs = _load("boundary_sensitivity")
    tensor_dir = _synthetic_artifacts(tmp_path, _toy_classes())
    reference_dir = tmp_path / "ref"
    sg.solve(_toy_config(sg), tensor_dir, reference_dir)
    ep.run_expost(reference_dir)
    for amount, expect_change in ((0.0, False), (0.05, True)):
        target = tmp_path / f"perturbed{amount}"
        config = _toy_config(sg, boundary_perturb=amount, boundary_perturb_kind="tilt")
        manifest = sg.solve(config, tensor_dir, target, boundary_from=reference_dir)
        assert manifest["boundary"]["source"]["kind"] == "imported"
        assert manifest["boundary"]["perturb_max_abs"] == pytest.approx(amount)
        ep.run_expost(target)
        report = bs.compare(reference_dir, target)
        assert report["boundary"]["max_abs_delta"] == pytest.approx(amount)
        assert len(report["layers"]) == len(sg.load_layers(reference_dir))
        assert report["strategy"]["infosets"] > 0
        if expect_change:
            assert report["strategy"]["v_max_abs_delta"] > 0.0
            assert report["epsilon"]["start_state_perturbed"] >= 0.0
        else:
            assert report["strategy"]["v_max_abs_delta"] == 0.0
            assert report["strategy"]["sigma_max_abs_delta"] == 0.0
            assert report["strategy"]["action_changes"] == 0
            assert report["epsilon"]["start_state_delta"] == 0.0
    written = json.loads((tmp_path / "perturbed0.05" / "boundary_sensitivity.json").read_text())
    assert written["epsilon"]["perturbed_max"] >= 0.0


def test_cfr_plus_wazy_srednia_wlasnym_prawdopodobienstwem_dojscia(tmp_path: Path) -> None:
    """Średnia CFR+ jest ważona własnym reachem — na tej średniej stoi gwarancja zbieżności.

    W drzewie HU jedynym węzłem o nietrywialnym własnym reachu jest `H_N_VS_3BET`
    (bohater dochodzi tam wyłącznie przez własny open), więc wagą iteracji jest
    jego prawdopodobieństwo openu w tej iteracji. Test odtwarza średnią z samego
    ciągu profili i sprawdza, że średnia nieważona daje inny profil.
    """
    sg = _load("solve_grid")
    np = sg.np
    tensor_dir = _synthetic_artifacts(tmp_path, _toy_classes())
    config = _toy_config(sg, cfr_iters=12, cfr_check_every=32, cfr_tol=-1.0)
    tensors = sg.load_tensors(tensor_dir, config.classes)
    problem, _, mode = sg.build_stage_problem(
        tensors, config, (0, 75, 75), 0, 1, 2,
        lambda state: np.asarray(icm_equities(state, PRIZES), dtype=float),
    )
    assert mode == "hu-deep"
    node = sg.H_N_VS_3BET
    assert node in problem.nodes and len(problem.allowed[node]) > 1
    seen: list[dict[int, Any]] = []
    sigma, eps, iterations = sg._cfr_plus_solve(
        problem, config,
        observer=lambda step, current: seen.append(
            {key: value.copy() for key, value in current.items()}
        ),
    )
    assert iterations == config.cfr_iters == len(seen)
    assert eps >= 0.0
    reach = np.zeros(problem.count, dtype=float)
    weighted = np.zeros((problem.count, 3), dtype=float)
    flat = np.zeros((problem.count, 3), dtype=float)
    for step, current in enumerate(seen, start=1):
        own = step * current[sg.H_ROOT][:, sg.SLOT_MID].astype(float)
        reach += own
        weighted += own[:, None] * current[node].astype(float)
        flat += step * current[node].astype(float)
    live = reach > 0.0
    assert bool(live.any())
    expected = weighted[live] / reach[live][:, None]
    assert float(np.max(np.abs(sigma[node][live] - expected))) < 1e-5
    unweighted = flat[live] / sum(range(1, len(seen) + 1))
    assert float(np.max(np.abs(unweighted - expected))) > 1e-3  # średnie są różne
    for row in sigma[node]:
        assert abs(float(row.sum()) - 1.0) < 1e-5


def test_cfr_plus_konczy_na_tolerancji_przed_sufitem(tmp_path: Path) -> None:
    """Stop CFR+ jest na tolerancji, sufit zabezpiecza — jak w solverze 3-osobowym."""
    sg = _load("solve_grid")
    np = sg.np
    tensor_dir = _synthetic_artifacts(tmp_path, _toy_classes())
    config = _toy_config(sg, cfr_iters=256, cfr_check_every=4, cfr_tol=1e-3)
    tensors = sg.load_tensors(tensor_dir, config.classes)
    problem, _, mode = sg.build_stage_problem(
        tensors, config, (0, 75, 75), 0, 1, 2,
        lambda state: np.asarray(icm_equities(state, PRIZES), dtype=float),
    )
    assert mode == "hu-deep"
    _, eps, iterations = sg._cfr_plus_solve(problem, config)
    assert eps <= config.cfr_tol
    assert iterations < config.cfr_iters
    assert iterations % config.cfr_check_every == 0


def test_poziomy_blindow_zgodne_z_poker_spin() -> None:
    sg = _load("solve_grid")
    config = _toy_config(sg, levels=None, hands_per_level=3)
    for hand in range(24):
        sb, bb, _ = blinds_for_hand(hand)
        assert sg.level_blinds(config, hand) == (sb, bb)


def test_solver_bajt_w_bajt_po_wznowieniu(tmp_path: Path) -> None:
    sg = _load("solve_grid")
    tensor_dir = _synthetic_artifacts(tmp_path, _toy_classes())
    config = _toy_config(sg)
    full_dir = tmp_path / "full"
    sg.solve(config, tensor_dir, full_dir)
    resumed_dir = tmp_path / "resumed"
    sg.solve(config, tensor_dir, resumed_dir, layers_limit=1)
    sg.solve(config, tensor_dir, resumed_dir)
    full_files = sorted(path.name for path in full_dir.glob("*.npz"))
    resumed_files = sorted(path.name for path in resumed_dir.glob("*.npz"))
    assert full_files == resumed_files and full_files
    for name in full_files:
        assert (full_dir / name).read_bytes() == (resumed_dir / name).read_bytes(), name
    with pytest.raises(ValueError):
        sg.solve(_toy_config(sg, fp_max_iters=7), tensor_dir, resumed_dir)


def test_solver_niezalezny_od_liczby_procesow(tmp_path: Path) -> None:
    """Budżet iteracji nie może uczynić wyniku zależnym od podziału pracy na procesy."""
    sg = _load("solve_grid")
    tensor_dir = _synthetic_artifacts(tmp_path, _toy_classes())
    solo_dir = tmp_path / "solo"
    sg.solve(_toy_config(sg), tensor_dir, solo_dir)
    names = sorted(path.name for path in solo_dir.glob("*.npz"))
    assert names
    for jobs in (2, 4):
        forked_dir = tmp_path / f"forked{jobs}"
        sg.solve(_toy_config(sg, jobs=jobs), tensor_dir, forked_dir)
        for name in names:
            assert (solo_dir / name).read_bytes() == (forked_dir / name).read_bytes(), (
                name, jobs
            )


def test_v_pelnym_wektorem_sumuje_sie_do_puli(toy_run: dict[str, Any]) -> None:
    sg = toy_run["sg"]
    layers = sg.load_layers(toy_run["out_dir"])
    assert layers
    saw_hu = False
    pool = sum(PRIZES)
    for layer in layers.values():
        values = layer["v"]
        assert bool((values == values).all())  # brak NaN
        for row, state in zip(values, layer["states"], strict=True):
            assert abs(float(row.sum()) - pool) < 1e-6, state
            alive = sum(1 for stack in state if stack > 0)
            assert alive >= 2
            if alive == 2:
                saw_hu = True
    assert saw_hu


def test_wymuszony_call_i_jam_przy_allin_z_blinda() -> None:
    sg = _load("solve_grid")
    tensors = None
    tmp: Any = None
    import tempfile
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        tensor_dir = _synthetic_artifacts(tmp, _toy_classes())
        config = _toy_config(sg, levels=((8, 16),), hands_per_level=1)
        tensors = sg.load_tensors(tensor_dir, config.classes)
        result = sg.solve_single_state(
            config, tensors, stacks=(130, 50, 15), button=1, sb=8, bb_amt=16,
            v_next=None,
        )
        assert result.mode == "jamfold"
        for node in (sg.N_B_VS_U_JAM_T_FOLD, sg.N_B_VS_U_JAM_T_CALL):
            call = result.sigma[node, :, 1]
            assert bool((call == 1.0).all())
        forced_btn = sg.solve_single_state(
            config, tensors, stacks=(130, 5, 15), button=1, sb=8, bb_amt=16,
            v_next=None,
        )
        jam = forced_btn.sigma[sg.N_T_FI, :, 2]
        assert bool((jam == 1.0).all())


def test_expost_epsilon_nieujemny_i_raport(toy_run: dict[str, Any]) -> None:
    ep = _load("expost")
    report = ep.run_expost(toy_run["out_dir"])
    assert report["epsilon_max"] >= report["epsilon_median"] >= 0.0
    assert report["epsilon_min"] >= -1e-6
    assert report["states"] > 0
    written = json.loads((toy_run["out_dir"] / "expost_report.json").read_text())
    assert written["epsilon_max"] == report["epsilon_max"]


def test_obserwator_pi_fp_nie_zmienia_wyniku(toy_run: dict[str, Any]) -> None:
    """Hak pomiarowy PI-FP jest bierny: profil z obserwatorem i bez jest ten sam."""
    sg = toy_run["sg"]
    config = toy_run["config"]
    tensors = sg.load_tensors(toy_run["tensor_dir"], config.classes)
    problem, _, mode = sg.build_stage_problem(
        tensors, config, (50, 50, 50), 0, 1, 2,
        lambda state: sg.np.asarray(icm_equities(state, PRIZES), dtype=float),
    )
    assert mode == "deep"
    plain_sigma, plain_eps, plain_iters = sg._fp_solve(problem, config)
    seen: list[tuple[str, int]] = []
    watched_sigma, watched_eps, watched_iters = sg._fp_solve(
        problem, config, observer=lambda style, step, average, reply: seen.append((style, step))
    )
    assert seen and seen[0][1] == 1
    assert (plain_eps, plain_iters) == (watched_eps, watched_iters)
    for node_id in problem.nodes:
        assert bool((plain_sigma[node_id] == watched_sigma[node_id]).all()), node_id


def test_krzywa_epsilon_zgadza_sie_z_solverem_przy_tym_sufcie(curve_run: dict[str, Any]) -> None:
    """Punkt krzywej dla sufitu k to dokładnie ε profilu, który zwraca PI-FP z tym sufitem.

    Bez tego pomiar mierzyłby własną replikę fictitious play, nie solver pilota.
    """
    ec = _load("eps_curve")
    sg = curve_run["sg"]
    ladder = (2, 5)
    report = ec.eps_curve(curve_run["out_dir"], ladder=ladder, worst=1, extra=0, seed=47)
    assert [point["iters"] for point in report["points"]] == list(ladder)
    entry = report["per_state"][0]
    config = curve_run["config"]
    tensors = sg.load_tensors(Path(report["tensor_dir"]), config.classes)
    layers = sg.load_layers(curve_run["out_dir"])
    next_states = [tuple(int(x) for x in row) for row in layers[entry["hand"] + 1]["states"]]
    index = {state: position for position, state in enumerate(next_states)}
    values = layers[entry["hand"] + 1]["v"]
    sb, bb_amt = sg.level_blinds(config, entry["hand"])
    problem, _, _ = sg.build_stage_problem(
        tensors, config, tuple(entry["state"]), entry["hand"], sb, bb_amt,
        lambda state: values[index[sg.quantize_stacks(state, config.grid_step)]],
    )
    for position, cap in enumerate(ladder):
        capped = dataclasses.replace(
            config, fp_max_iters=cap, fp_check_every=cap, fp_tol=ec.NO_TOLERANCE
        )
        _, eps, iters = sg._fp_solve(problem, capped)
        assert iters == cap, (cap, iters)  # tolerancja biegu nie skraca pomiaru
        assert entry["eps"][position] == pytest.approx(eps, rel=1e-9, abs=1e-12), cap


def test_krzywa_trybu_hu_mierzy_cfr_plus_a_nie_pi_fp(curve_run: dict[str, Any]) -> None:
    """Drabinkę trybu mierzy ten solver, którym bieg ten tryb rozwiązuje.

    Bez tego budżet CFR+ w endgame'ach HU byłby dobrany z krzywej PI-FP, czyli
    z pomiaru innego algorytmu niż ten, który liczy te stany.
    """
    ec = _load("eps_curve")
    ep = _load("expost")
    sg = curve_run["sg"]
    ladder = (2, 8)
    report = ec.eps_curve(
        curve_run["out_dir"], ladder=ladder, worst=1, extra=0, seed=47,
        mode="hu-deep", report_name="eps_curve_hu.json",
    )
    entry = report["per_state"][0]
    assert entry["mode"] == "hu-deep"
    assert entry["run_lengths"] == {}  # CFR+ nie ma restartów ani runów best response
    config, tensors, layers, boundary_v = ep.load_run(curve_run["out_dir"])
    full_states = sg.grid_states(config.total_chips, config.grid_step)
    problem, _, mode = sg.build_stage_problem(
        tensors, config, tuple(entry["state"]), entry["hand"],
        *sg.level_blinds(config, entry["hand"]),
        ec._continuation(config, layers, boundary_v, full_states, entry["hand"]),
    )
    assert mode == "hu-deep" and problem.n_roles == 2
    for position, cap in enumerate(ladder):
        capped = dataclasses.replace(
            config, cfr_iters=cap, cfr_check_every=cap, cfr_tol=ec.NO_TOLERANCE
        )
        _, eps, iterations = sg._cfr_plus_solve(problem, capped)
        assert iterations == cap, (cap, iterations)
        assert entry["eps"][position] == pytest.approx(eps, rel=1e-9, abs=1e-12), cap


def test_koszt_punktu_krzywej_jest_kosztem_tego_sufitu(curve_run: dict[str, Any]) -> None:
    """Koszt punktu to k iteracji w każdym restarcie, nie cały bieg do najwyższego sufitu.

    Jeden bieg obsługuje całą drabinkę, więc zegar restartu musi startować od zera
    — inaczej najtańszy punkt raportuje prawie koszt najdroższego.
    """
    ec = _load("eps_curve")
    report = ec.eps_curve(curve_run["out_dir"], ladder=(1, 16), worst=1, extra=0, seed=47)
    cheap, dear = (point["core_seconds_per_state"] for point in report["points"])
    assert 0.0 < cheap < 0.3 * dear, (cheap, dear)


def test_odczyt_budzetu_z_krzywej_bierze_pierwszy_sufit_ponizej_progu() -> None:
    ec = _load("eps_curve")
    report = {
        "ladder": [4, 8, 16],
        "per_state": [
            {"budgets": [4, 8, 16], "eps": [1e-2, 1e-3, 1e-4], "core_seconds": [1.0, 2.0, 4.0]},
            {"budgets": [4, 8, 16], "eps": [1e-3, 1e-4, 1e-5], "core_seconds": [1.5, 3.0, 6.0]},
        ],
    }
    loose, tight = ec.budgets_for_targets(report, (1e-3, 1e-5))
    assert loose == {
        "epsilon": 1e-3, "n_reached": 2, "n_unreached": 0,
        "budget_median": 6.0, "budget_max": 8,
        "core_seconds_median": 1.75, "core_seconds_max": 2.0,
    }
    assert (tight["n_reached"], tight["n_unreached"], tight["budget_max"]) == (1, 1, 16)


def test_probka_krzywej_deterministyczna_i_tylko_deep(curve_run: dict[str, Any]) -> None:
    ec = _load("eps_curve")
    sg = curve_run["sg"]
    layers = sg.load_layers(curve_run["out_dir"])
    kwargs: dict[str, Any] = {"ladder": (1,), "worst": 1, "extra": 2}
    first = ec.eps_curve(curve_run["out_dir"], seed=11, **kwargs)
    again = ec.eps_curve(curve_run["out_dir"], seed=11, **kwargs)

    def names(report: dict[str, Any]) -> list[tuple[int, tuple[int, ...]]]:
        return [(row["hand"], tuple(row["state"])) for row in report["sample"]]

    assert names(first) == names(again)
    assert len(names(first)) == len(set(names(first)))
    for row in first["sample"]:
        layer = layers[row["hand"]]
        states = [tuple(int(x) for x in item) for item in layer["states"]]
        position = states.index(tuple(row["state"]))
        assert sg.MODE_NAMES[int(layer["mode"][position])] == "deep", row
    picked = [row["eps_dag"] for row in first["sample"] if row["source"] == "worst"]
    drawn = [row["eps_dag"] for row in first["sample"] if row["source"] == "random"]
    assert len(picked) == 1 and len(drawn) == 2
    assert first["sample"][0]["source"] == "worst"  # najgorsze idą przed losowaniem
    assert min(picked) >= max(drawn)


def test_koszt_trybu_mierzy_konfiguracje_biegu(curve_run: dict[str, Any]) -> None:
    """Koszt trybu liczony budżetem biegu (nie pomiaru) — z tego idzie ekstrapolacja."""
    ec = _load("eps_curve")
    report = ec.mode_costs(curve_run["out_dir"], per_mode=1)
    assert report["fp_max_iters"] == curve_run["config"].fp_max_iters
    assert report["fp_tol"] == curve_run["config"].fp_tol
    modes = {row["mode"]: row for row in report["modes"]}
    assert "deep" in modes
    for row in report["modes"]:
        assert row["n_states"] >= 1
        assert row["core_seconds_median"] > 0.0
        budget = (
            curve_run["config"].cfr_iters if row["mode"].startswith("hu-")
            else curve_run["config"].fp_max_iters
        )
        assert row["iterations_median"] <= budget, row


def test_dekompozycja_oddziela_epsilon_etapowe_od_odziedziczonego(
    curve_run: dict[str, Any],
) -> None:
    """ε ex-post po DAG-u nie jest mniejsze od etapowego, a ε etapowe to self-ε biegu.

    Ta równość jest sednem PUŁAPKI decyzji 17: self-ε solvera mierzy wyłącznie
    jedną warstwę, a ε ex-post dokłada do niej dług warstw późniejszych.
    """
    ec = _load("eps_curve")
    report = ec.decompose(curve_run["out_dir"], worst=2)
    assert report["states"]
    for row in report["states"]:
        assert row["eps_dag_max"] >= row["eps_stage_max"] - 1e-6, row
        assert row["eps_stage_max"] == pytest.approx(row["eps_stage_reported"], abs=1e-6), row
        assert 0.0 <= row["inherited_share"] <= 1.0 + 1e-9, row
    assert report["layers"][0]["hand"] == 0
    modes = {row["mode"]: row for row in report["modes"]}
    assert "deep" in modes
    assert sum(row["n_states"] for row in report["modes"]) == sum(
        row["n_states"] for row in report["layers"]
    )
    for row in report["modes"]:
        assert row["eps_stage_max"] >= row["eps_stage_median"] >= 0.0, row
        assert row["above_tolerance"] <= row["n_states"], row


# --- POKER-50: bieg produkcyjny — bezpiecznik kosztu, wycinek, łańcuch kontrolny ---

CONTROL_DIR = BLUEPRINT / "control"


@pytest.fixture(scope="module")
def value_table() -> Any:
    """Tablica wartości C(52,5) — backend `table` produkcji, budowana raz na moduł."""
    rt = _load("rollout_tensor")
    return rt.build_value_table()


def test_ekstrapolacja_bezpiecznika_kalibruje_priory_trybow() -> None:
    """Ekstrapolacja kosztu: tryb zmierzony liczy się własnym tempem, niezmierzony
    priorytetem POKER-49 przeskalowanym kalibracją tej maszyny, a narzut forka
    ilorazem kosztu ściennego do sumy czasów stanów."""
    sg = _load("solve_grid")
    assert set(sg.MODE_COST_PRIORS) == set(sg.MODE_NAMES)
    measured = {"jamfold": {"n_states": 10.0, "core_seconds": 30.0}}
    spent = 45.0  # narzut 1,5x nad zmierzonymi 30 s czasu stanów
    plan = [{"deep": 2, "jamfold": 4}]
    report = sg.extrapolate_cost(plan, measured, spent)
    calibration = 30.0 / (10.0 * sg.MODE_COST_PRIORS["jamfold"])
    assert report["calibration"] == pytest.approx(calibration)
    assert report["overhead"] == pytest.approx(1.5)
    rates = report["rates"]
    assert rates["jamfold"]["measured"] is True
    assert rates["jamfold"]["core_seconds_per_state"] == pytest.approx(3.0)
    assert rates["deep"]["measured"] is False
    assert rates["deep"]["core_seconds_per_state"] == pytest.approx(
        sg.MODE_COST_PRIORS["deep"] * calibration
    )
    remaining = 1.5 * (2 * sg.MODE_COST_PRIORS["deep"] * calibration + 4 * 3.0)
    assert report["remaining_core_hours"] == pytest.approx(remaining / 3600.0)
    assert report["extrapolated_core_hours"] == pytest.approx((45.0 + remaining) / 3600.0)
    assert report["spent_core_hours"] == pytest.approx(45.0 / 3600.0)


def test_bezpiecznik_kosztu_przerywa_po_trzech_warstwach_i_wznawia_bajt_w_bajt(
    tmp_path: Path,
) -> None:
    """Przekroczony limit przerywa bieg po trzeciej warstwie z raportem tempa;
    wznowienie z innym limitem (limit nie wchodzi do hasha konfiguracji) kończy
    bieg bajt w bajt identyczny z biegiem ciągłym."""
    sg = _load("solve_grid")
    tensor_dir = _synthetic_artifacts(tmp_path, _toy_classes())
    levels = ((1, 2), (1, 2), (1, 2), (1, 2))
    tight = _toy_config(sg, levels=levels, cost_limit_core_hours=1e-9)
    with pytest.raises(sg.CostFuseExceeded) as caught:
        sg.solve(tight, tensor_dir, tmp_path / "fused")
    report = caught.value.report
    assert report["verdict"] == "exceeded"
    assert report["limit_core_hours"] == tight.cost_limit_core_hours
    assert report["extrapolated_core_hours"] > tight.cost_limit_core_hours
    assert report["spent_core_hours"] > 0.0
    assert any(row["measured"] for row in report["rates"].values())
    manifest = json.loads((tmp_path / "fused" / "solve_manifest.json").read_text())
    assert manifest["status"] == "aborted-cost-fuse"
    assert len(manifest["layers"]) == 3
    assert manifest["cost_fuse"]["verdict"] == "exceeded"
    resumed = _toy_config(sg, levels=levels, cost_limit_core_hours=0.0)
    sg.solve(resumed, tensor_dir, tmp_path / "fused")
    sg.solve(_toy_config(sg, levels=levels), tensor_dir, tmp_path / "full")
    names = sorted(path.name for path in (tmp_path / "full").glob("*.npz"))
    assert names == sorted(path.name for path in (tmp_path / "fused").glob("*.npz"))
    for name in names:
        assert (tmp_path / "full" / name).read_bytes() == (
            tmp_path / "fused" / name
        ).read_bytes(), name


def test_bezpiecznik_domyslnie_140_w_cli_i_poza_hashem_konfiguracji() -> None:
    """Limit 140 rdzenio-h z kontraktu jest domyślny; nie wpływa na wynik, więc
    nie wchodzi do hasha konfiguracji (wznowienie może go zmienić)."""
    sg = _load("solve_grid")
    defaults = sg.GridConfig()
    assert defaults.cost_limit_core_hours == 140.0
    parsed = sg.build_parser().parse_args(["--tensor", "t", "--out", "o"])
    assert parsed.cost_limit == defaults.cost_limit_core_hours
    stub = {"sha256": {"rollout3.npz": "x", "rollout_hu.npz": "y"}}
    base = sg.config_hash(defaults, stub)
    assert sg.config_hash(
        dataclasses.replace(defaults, cost_limit_core_hours=1.0), stub
    ) == base
    assert sg.config_hash(dataclasses.replace(defaults, fp_tol=1.0), stub) != base


def test_wznowienie_bajt_w_bajt_na_wycinku_produkcyjnym(tmp_path: Path) -> None:
    """Wycinek konfiguracji produkcyjnej: siatka 2 żetony, prawdziwy tensor kontrolny,
    wszystkie cztery tryby solvera; przerwanie po warstwie i wznowienie daje pliki
    bajt w bajt, a manifest raportuje postęp per warstwa (czas, stany, tryby)."""
    sg = _load("solve_grid")
    cc = _load("control_chain")
    config = cc.control_config()
    assert config.grid_step == cc.PROD_GRID_STEP == 2
    tensor_dir = CONTROL_DIR / "tensor"
    full_dir = tmp_path / "full"
    sg.solve(config, tensor_dir, full_dir)
    resumed_dir = tmp_path / "resumed"
    sg.solve(config, tensor_dir, resumed_dir, layers_limit=1)
    sg.solve(config, tensor_dir, resumed_dir)
    names = sorted(path.name for path in full_dir.glob("*.npz"))
    assert names == sorted(path.name for path in resumed_dir.glob("*.npz")) and names
    for name in names:
        assert (full_dir / name).read_bytes() == (resumed_dir / name).read_bytes(), name
    manifest = json.loads((full_dir / "solve_manifest.json").read_text())
    seen_modes = set(manifest["boundary"]["modes"])
    for entry in manifest["layers"].values():
        assert entry["n_states"] >= 1
        assert entry["seconds"] >= 0.0
        assert entry["core_seconds_wall"] > 0.0
        assert entry["modes"]
        for stats in entry["modes"].values():
            assert stats["n_states"] >= 1 and stats["core_seconds"] >= 0.0
        seen_modes |= set(entry["modes"])
    assert seen_modes == set(sg.MODE_NAMES)  # wycinek pokrywa wszystkie tryby produkcji


def test_manifest_pochodzenia_kompletny(toy_run: dict[str, Any]) -> None:
    """Manifest biegu niesie pochodzenie: wersje, model CPU, seed i próby tensora."""
    manifest = toy_run["manifest"]
    provenance = manifest["provenance"]
    assert provenance["numpy"] and provenance["python"]
    assert provenance["cpu_model"]
    assert provenance["tensor"]["master_seed"] == 0  # syntetyczny artefakt testowy
    assert provenance["tensor"]["trials"] == 64
    assert provenance["tensor"]["hu_trials"] == 64
    assert manifest["config_hash"]


def test_lancuch_kontrolny_zgodny_z_artefaktem_w_repo(
    tmp_path: Path, value_table: Any
) -> None:
    """Dwustopniowy dowód odtwarzalności (decyzja 06): mały łańcuch kontrolny w bramce.

    Tensor kontrolny regenerowany z przybitych parametrów musi być identyczny
    z artefaktem w repo (tablice całkowite — porównanie dokładne), a łańcuch
    solver→ex-post na artefakcie z repo musi odtworzyć liczby z
    `chain_control.json` (tolerancja CONTROL_ABS_TOL na arytmetykę f32).
    Zmiana kodu, która przesuwa wynik, zapala tę bramkę zamiast po cichu
    unieważnić artefakt produkcyjny (PUŁAPKA regeneracji artefaktu).
    """
    cc = _load("control_chain")
    af = _load("artifacts")
    rt = _load("rollout_tensor")
    np = rt.np
    expected = json.loads((CONTROL_DIR / "chain_control.json").read_text())
    fresh = tmp_path / "tensor"
    cc.generate_control_tensor(fresh, table=value_table)
    for name in ("rollout3.npz", "rollout_hu.npz"):
        committed = af.read_npz(CONTROL_DIR / "tensor" / name)
        regenerated = af.read_npz(fresh / name)
        assert sorted(committed) == sorted(regenerated), name
        for key in committed:
            assert bool(np.array_equal(committed[key], regenerated[key])), (name, key)
    committed_manifest = json.loads((CONTROL_DIR / "tensor" / "rollout_manifest.json").read_text())
    assert committed_manifest["master_seed"] == cc.CONTROL_SEED
    assert committed_manifest["cpu_model"] and committed_manifest["python"]
    summary = cc.run_control_chain(CONTROL_DIR / "tensor", tmp_path / "solve", jobs=1)
    control = expected["control"]
    assert summary["config_hash"] == control["config_hash"]
    assert summary["boundary_cycles"] == control["boundary_cycles"]
    for key in ("boundary_delta", "epsilon_max", "epsilon_median"):
        assert summary[key] == pytest.approx(control[key], abs=cc.CONTROL_ABS_TOL), key
    assert summary["start_v"] == pytest.approx(control["start_v"], abs=cc.CONTROL_ABS_TOL)


def test_reprodukcja_podzbioru_tensora_produkcyjnego(value_table: Any) -> None:
    """Podzbiór tensora produkcyjnego (seed jawny, 15 000 / 60 000 prób) odtwarza się
    co do zliczenia, a equity pary HU zgadza się z macierzą produktu w progu
    wyprowadzonym z liczby prób obu artefaktów."""
    cc = _load("control_chain")
    rt = _load("rollout_tensor")
    np = rt.np
    assert cc.PROD_TRIALS == 15_000
    assert cc.PROD_HU_TRIALS == 60_000  # proporcjonalnie do pilota (x7,5 z 8 000)
    assert cc.PROD_HU_TRIALS >= 32_000  # podłoga kontraktu POKER-50
    assert cc.PROD_GRID_STEP == 2
    expected = json.loads((CONTROL_DIR / "chain_control.json").read_text())["production"]
    assert expected["trials"] == cc.PROD_TRIALS
    assert expected["hu_trials"] == cc.PROD_HU_TRIALS
    assert expected["master_seed"] == cc.PROD_SEED
    assert expected["grid_step"] == cc.PROD_GRID_STEP
    subset = cc.production_subset(value_table)
    assert subset["triple"] == expected["triple"]
    assert subset["pair"] == expected["pair"]
    pair = tuple(subset["pair"]["classes"])
    counts = subset["pair"]["counts"]
    assert sum(counts) == cc.PROD_HU_TRIALS
    aa_axis = pair.index(_cls("AA"))
    row = np.asarray(counts, dtype=float)
    # Zamiana osi pary permutuje zdarzenia (0,1)<->(1,0); remis (0,0) zostaje.
    equity = _pair_equity(rt, row if aa_axis == 0 else row[[0, 2, 1]])
    expected_equity = class_equity(ALL_CLASSES[_cls("AA")], ALL_CLASSES[_cls("72o")])
    assert abs(equity - expected_equity) <= _mc_tolerance(cc.PROD_HU_TRIALS)


def test_raport_expost_ma_kryteria_progow_i_rozklad_per_warstwa(
    toy_run: dict[str, Any],
) -> None:
    """Raport ex-post niesie kryterium blokujące 1e-3, punkt odniesienia 5e-4
    z werdyktem o opcji sufitu 1536 oraz rozkład ε per warstwa."""
    ep = _load("expost")
    assert ep.BLOCKING_EPS == 1e-3
    assert ep.REFERENCE_EPS == 5e-4
    report = ep.run_expost(toy_run["out_dir"])
    criteria = report["criteria"]
    assert criteria["blocking_max"] == ep.BLOCKING_EPS
    assert criteria["blocking_ok"] == (report["epsilon_max"] <= ep.BLOCKING_EPS)
    assert criteria["reference"] == ep.REFERENCE_EPS
    assert criteria["reference_exceeded"] == (report["epsilon_max"] > ep.REFERENCE_EPS)
    assert criteria["ceiling_1536_option_triggers"] == criteria["reference_exceeded"]
    layers = report["layers"]
    assert [row["hand"] for row in layers] == sorted(row["hand"] for row in layers)
    assert sum(row["n_states"] for row in layers) == report["states"]
    for row in layers:
        assert row["epsilon_max"] >= row["epsilon_median"]
    assert max(row["epsilon_max"] for row in layers) == pytest.approx(
        report["epsilon_max"]
    )
    written = json.loads((toy_run["out_dir"] / "expost_report.json").read_text())
    assert written["criteria"] == criteria


def test_raport_icm_struktura(toy_run: dict[str, Any]) -> None:
    ep = _load("expost")
    report = ep.icm_report(toy_run["out_dir"])
    assert report["layers"]
    for entry in report["layers"]:
        assert entry["max_abs_delta"] >= 0.0
        assert entry["mean_abs_delta"] >= 0.0
    assert "short_bb" in report
    state0 = tuple(toy_run["config"].start_stacks)
    icm0 = icm_equities(state0, PRIZES)
    assert abs(sum(icm0) - sum(PRIZES)) < 1e-9


# --- POKER-51: format binarny artefaktu i czytnik stdlib ---

# Krok kwantyzacji uint8: jeden poziom skali 255. Metoda największych reszt
# trzyma sumę dokładnie, więc błąd pojedynczego prawdopodobieństwa jest
# mniejszy od kroku — to granica round-tripu, nie próg dobrany do wyniku.
QUANT_STEP_U8 = 1.0 / 255.0

# Koszt kwantyzacji w ε na artefakcie kontrolnym z repo (POKER-51, pomiar
# w bramce). Kwantyzacja tego artefaktu nie kosztuje — ex-post ε maleje;
# liczby cytuje blok POKER-51 w docs/CURRENT_STATE.md.
CONTROL_QUANT_EPS_MAX = 0.003691128770597185
CONTROL_QUANT_EPS_MEDIAN = 0.00010865383906707993
CONTROL_QUANT_DELTA_SHARE = -0.0366

# Odczyt jednego stanu i jednej wartości V z artefaktu kontrolnego (190 stanów,
# 4 klasy, 8 328 B): sufity bajtów przeczytanych ze strumienia. Wyszukiwanie
# binarne to ceil(log2 n) kluczy po 6 B, blok stanu jest jeden i skompresowany.
# Zmierzone najgorsze przypadki na całym artefakcie: 116 B na stan, 56 B na V;
# sufity mają zapas na inną wersję zlib, a nie na inny sposób odczytu.
CONTROL_STATE_READ_MAX_BYTES = 160
CONTROL_VALUE_READ_MAX_BYTES = 72


class _CountingStream:
    """Strumień liczący przeczytane bajty — dowód, że odczyt stanu nie czyta całości."""

    def __init__(self, handle: Any) -> None:
        self._handle = handle
        self.read_bytes = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        return int(self._handle.seek(offset, whence))

    def read(self, size: int = -1) -> bytes:
        chunk: bytes = self._handle.read(size)
        self.read_bytes += len(chunk)
        return chunk


@pytest.fixture(scope="module")
def control_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Bieg solvera na artefakcie kontrolnym z repo — wejście testów formatu.

    Ten sam wycinek produkcyjny co test wznowienia: krok siatki 2, cztery tryby
    solvera, prawdziwy tensor kontrolny. Format testujemy na artefakcie, który
    repo umie odtworzyć, a nie na syntetycznej zabawce.
    """
    sg = _load("solve_grid")
    cc = _load("control_chain")
    out_dir = tmp_path_factory.mktemp("format") / "solve"
    manifest = sg.solve(cc.control_config(), CONTROL_DIR / "tensor", out_dir)
    return {"out_dir": out_dir, "manifest": manifest, "sg": sg}


def test_konwerter_daje_bajt_w_bajt_ten_sam_plik(control_run: dict[str, Any],
                                                 tmp_path: Path) -> None:
    """Ten sam artefakt wejściowy → ten sam plik. Bez znaczników czasu i nazw tymczasowych."""
    pk = _load("pack_blueprint")
    first, second = tmp_path / "a.bpk", tmp_path / "b.bpk"
    summary = pk.pack(control_run["out_dir"], first)
    pk.pack(control_run["out_dir"], second)
    assert first.read_bytes() == second.read_bytes()
    assert summary["bytes"] == first.stat().st_size
    assert summary["config_hash"] == control_run["manifest"]["config_hash"]
    assert not list(tmp_path.glob("*.tmp"))


def test_naglowek_i_metadane_niosa_hash_oraz_przepis_pochodzenia(
    control_run: dict[str, Any], tmp_path: Path
) -> None:
    """Nagłówek: magia, wersja, kwantyzacja, hash konfiguracji biegu w surowych bajtach.

    Przepis pochodzenia (kopia manifestu biegu z wersjami, modelem CPU i
    parametrami tensora) jedzie w bloku metadanych, a sha256 pakowanych plików
    liczy konwerter — manifest, który skłamał o zawartości, zapala błąd.
    """
    pk = _load("pack_blueprint")
    br = _import_reader()
    packed = tmp_path / "control.bpk"
    pk.pack(control_run["out_dir"], packed)
    head = packed.read_bytes()[: br.HEADER_SIZE]
    assert head[:8] == br.MAGIC
    manifest = control_run["manifest"]
    with packed.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        assert reader.format_version == br.FORMAT_VERSION == 1
        assert reader.quant_bits == pk.DEFAULT_QUANT_BITS == 8
        assert reader.config_hash == manifest["config_hash"]
        assert reader.n_classes == len(manifest["config"]["classes"])
        assert reader.file_length == packed.stat().st_size
        meta = json.loads(reader.meta_bytes())
    provenance = meta["run_manifest"]["provenance"]
    assert provenance["python"] and provenance["numpy"] and provenance["cpu_model"]
    assert provenance["tensor"]["master_seed"] == manifest["provenance"]["tensor"]["master_seed"]
    assert meta["run_manifest"]["tensor_sha256"] == manifest["tensor_sha256"]
    on_disk = json.loads((control_run["out_dir"] / "solve_manifest.json").read_text())
    assert meta["run_manifest"] == on_disk
    for key, entry in manifest["layers"].items():
        assert meta["source_sha256"][entry["file"]] == entry["sha256"], key
    assert meta["source_sha256"][manifest["boundary"]["file"]] == manifest["boundary"]["sha256"]
    assert meta["format"]["stored_slots"] == [0, 1] and meta["format"]["derived_slot"] == 2


def test_konwerter_odrzuca_artefakt_niezgodny_z_manifestem(control_run: dict[str, Any],
                                                           tmp_path: Path) -> None:
    """Sha256 w manifeście musi opisywać pakowane pliki — inaczej pochodzenie kłamie."""
    pk = _load("pack_blueprint")
    sg = control_run["sg"]
    tampered = tmp_path / "tampered"
    tampered.mkdir()
    for path in control_run["out_dir"].iterdir():
        if path.is_file():
            (tampered / path.name).write_bytes(path.read_bytes())
    layers = sg.load_layers(tampered)
    hand = max(layers)
    layers[hand]["eps"] = layers[hand]["eps"] + 1.0
    _load("artifacts").write_npz(tampered / f"layer_{hand:02d}.npz", layers[hand])
    with pytest.raises(ValueError, match="sha256"):
        pk.pack(tampered, tmp_path / "tampered.bpk")


def test_round_trip_rozkladow_miesci_sie_w_kroku_kwantyzacji(
    control_run: dict[str, Any], tmp_path: Path
) -> None:
    """Konwerter → czytnik: każdy rozkład wraca w granicach jednego kroku kwantyzacji.

    Sprawdzane są wszystkie węzły maski i wszystkie klasy, a nie próbka: przy
    czterech klasach artefaktu kontrolnego to pełne pokrycie. Trzeci slot jest
    dopełnieniem, więc suma wraca dokładnie równa jedności.
    """
    pk = _load("pack_blueprint")
    br = _import_reader()
    sg = control_run["sg"]
    packed = tmp_path / "control.bpk"
    pk.pack(control_run["out_dir"], packed)
    layers = sg.load_layers(control_run["out_dir"])
    worst = 0.0
    checked = 0
    with packed.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        for hand, layer in sorted(layers.items()):
            for position, row in enumerate(layer["states"].tolist()):
                stacks = (int(row[0]), int(row[1]), int(row[2]))
                block = reader.state(hand, stacks)
                for node in block.nodes():
                    for klass in range(reader.n_classes):
                        got = block.policy(node, klass)
                        expected = layer["sigma"][position, node, klass]
                        assert sum(got) == pytest.approx(1.0, abs=1e-12)
                        assert min(got) >= 0.0
                        for slot in range(3):
                            worst = max(worst, abs(got[slot] - float(expected[slot])))
                        checked += 1
    assert checked > 0
    assert worst <= QUANT_STEP_U8


def test_v_wraca_z_formatu_bajtowo_dokladnie(control_run: dict[str, Any],
                                             tmp_path: Path) -> None:
    """Tablica V jedzie w float64 bez straty — AIVAT i trener dostają pełną precyzję."""
    pk = _load("pack_blueprint")
    br = _import_reader()
    sg = control_run["sg"]
    af = _load("artifacts")
    packed = tmp_path / "control.bpk"
    pk.pack(control_run["out_dir"], packed)
    layers = sg.load_layers(control_run["out_dir"])
    boundary = af.read_npz(control_run["out_dir"] / "boundary.npz")
    horizon = max(layers) + 1
    with packed.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        for hand, arrays in list(layers.items()) + [(horizon, boundary)]:
            for position, row in enumerate(arrays["states"].tolist()):
                stacks = (int(row[0]), int(row[1]), int(row[2]))
                assert reader.value(hand, stacks) == tuple(arrays["v"][position].tolist())
                for seat in range(3):
                    assert reader.seat_value(hand, stacks, seat) == arrays["v"][position][seat]
        assert [info.has_policy for info in reader.layers] == [True] * len(layers) + [False]


def test_nieosiagalnosc_jest_jawna_a_nie_cichym_zerem(control_run: dict[str, Any],
                                                      tmp_path: Path) -> None:
    """Kontrakt fallbacku agenta (POKER-52): odczyt spoza maski podnosi rozróżnialny błąd.

    Maska osiągalności musi zgadzać się co do węzła z zerami w artefakcie
    solvera — inaczej czytnik zwracałby rozkład tam, gdzie solver nic nie
    policzył, albo odmawiał tam, gdzie policzył.
    """
    pk = _load("pack_blueprint")
    br = _import_reader()
    sg = control_run["sg"]
    packed = tmp_path / "control.bpk"
    pk.pack(control_run["out_dir"], packed)
    layers = sg.load_layers(control_run["out_dir"])
    hand = max(layers)
    layer = layers[hand]
    dead_seen = live_seen = 0
    with packed.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        for position, row in enumerate(layer["states"].tolist()):
            stacks = (int(row[0]), int(row[1]), int(row[2]))
            block = reader.state(hand, stacks)
            for node in range(reader.n_nodes):
                alive = bool(layer["sigma"][position, node].sum() > 0.0)
                assert block.has_node(node) == alive, (stacks, node)
                if alive:
                    live_seen += 1
                    continue
                dead_seen += 1
                with pytest.raises(br.NodeUnreachable):
                    block.policy(node, 0)
                with pytest.raises(br.NodeUnreachable):
                    block.policy_table(node)
        assert dead_seen > 0 and live_seen > 0
        with pytest.raises(br.StateNotFound):
            reader.value(hand, (1, 1, 32))
        with pytest.raises(br.LayerNotFound):
            reader.value(len(layers) + 5, (12, 10, 12))
        with pytest.raises(br.PolicyMissing):
            reader.state(max(layers) + 1, (0, 2, 32))
        assert not reader.has_state(hand, (1, 1, 32))
    for error in (br.StateNotFound, br.LayerNotFound, br.NodeUnreachable, br.PolicyMissing):
        assert issubclass(error, LookupError)


def test_czytnik_odrzuca_plik_ktory_nie_jest_tym_formatem(control_run: dict[str, Any],
                                                          tmp_path: Path) -> None:
    """Magia, wersja i długość nagłówka rozstrzygają się przy otwarciu, nie przy odczycie.

    Wersjonowanie ma sens tylko wtedy, gdy czytnik odmawia obcej wersji zamiast
    czytać ją po staremu — konsument POKER-52 dostaje błąd, nie śmieci.
    """
    pk = _load("pack_blueprint")
    br = _import_reader()
    packed = tmp_path / "control.bpk"
    pk.pack(control_run["out_dir"], packed)
    raw = packed.read_bytes()
    cases = {
        "magia": b"XXXXXXXX" + raw[8:],
        "wersja": raw[:8] + (br.FORMAT_VERSION + 1).to_bytes(2, "little") + raw[10:],
        "kwantyzacja": raw[:10] + (7).to_bytes(2, "little") + raw[12:],
        "obcięty nagłówek": raw[: br.HEADER_SIZE - 1],
    }
    for label, payload in cases.items():
        with pytest.raises(br.BlueprintFormatError):
            br.BlueprintReader(io.BytesIO(payload))
        assert issubclass(br.BlueprintFormatError, ValueError), label


def test_odczyt_stanu_nie_czyta_calego_pliku(control_run: dict[str, Any],
                                             tmp_path: Path) -> None:
    """Dostęp swobodny: jeden stan i jedna wartość V to kilkaset bajtów, nie cały plik."""
    pk = _load("pack_blueprint")
    br = _import_reader()
    packed = tmp_path / "control.bpk"
    summary = pk.pack(control_run["out_dir"], packed)
    with packed.open("rb") as handle:
        counting = _CountingStream(handle)
        reader = br.BlueprintReader(counting)
        horizon = max(info.hand for info in reader.layers)
        target = (0, 2, 32)
        counting.read_bytes = 0
        value = reader.seat_value(horizon, target, 0)
        value_bytes = counting.read_bytes
        counting.read_bytes = 0
        block = reader.state(0, tuple(control_run["manifest"]["config"]["start_stacks"]))
        state_bytes = counting.read_bytes
    assert isinstance(value, float)
    assert block.nodes()
    assert value_bytes <= CONTROL_VALUE_READ_MAX_BYTES
    assert state_bytes <= CONTROL_STATE_READ_MAX_BYTES
    assert state_bytes < summary["bytes"] // 4


def test_kwantyzacja_zachowuje_sume_i_nie_przenosi_masy_na_akcje_zerowa() -> None:
    """Największe reszty: suma dokładnie 255, zero zostaje zerem, błąd poniżej kroku.

    Zaokrąglanie slot po slocie potrafi dać sumę 254 albo 256 — wtedy trzeci
    slot z dopełnienia byłby fałszem. Akcja o prawdopodobieństwie zero nie może
    dostać reszty, bo w artefakcie oznacza akcję poza maską drzewa.
    """
    pk = _load("pack_blueprint")
    rng = random.Random(51)
    rows = [
        (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
        (0.5, 0.5, 0.0), (1 / 3, 1 / 3, 1 / 3), (0.996, 0.004, 0.0),
    ]
    rows += [(rng.random(), rng.random(), rng.random()) for _ in range(2000)]
    normalized = [(row[0] / sum(row), row[1] / sum(row), row[2] / sum(row)) for row in rows]
    sg = _load("solve_grid")
    sample = sg.np.asarray(normalized, dtype=sg.np.float32)
    quantized = pk.quantize_chunk(sample, 255)
    assert bool((quantized.sum(axis=-1) == 255).all())
    assert bool((quantized >= 0).all())
    zeros = sample == 0.0
    assert bool((quantized[zeros] == 0).all())
    error = abs(quantized / 255.0 - sample.astype(float))
    assert float(error.max()) < QUANT_STEP_U8
    with pytest.raises(ValueError, match="zerową sumę"):
        pk.quantize_chunk(sg.np.zeros((1, 3), dtype=sg.np.float32), 255)


def test_uint16_podnosi_precyzje_dziesieciokrotnie(control_run: dict[str, Any],
                                                   tmp_path: Path) -> None:
    """Ścieżka odwrotu kontraktu: gdyby koszt w ε przekroczył próg, precyzja rośnie.

    Ten sam konwerter i ten sam czytnik obsługują 16 bitów — podniesienie
    precyzji nie wymaga zmiany formatu, tylko flagi w nagłówku.
    """
    pk = _load("pack_blueprint")
    br = _import_reader()
    sg = control_run["sg"]
    packed = tmp_path / "control16.bpk"
    pk.pack(control_run["out_dir"], packed, quant_bits=16)
    layers = sg.load_layers(control_run["out_dir"])
    hand = max(layers)
    layer = layers[hand]
    worst = 0.0
    with packed.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        assert reader.quant_bits == 16
        for position, row in enumerate(layer["states"].tolist()):
            stacks = (int(row[0]), int(row[1]), int(row[2]))
            block = reader.state(hand, stacks)
            assert block.levels == 65535
            for node in block.nodes():
                for klass, got in enumerate(block.policy_table(node)):
                    expected = layer["sigma"][position, node, klass]
                    assert sum(got) == pytest.approx(1.0, abs=1e-12)
                    worst = max(worst, max(abs(got[s] - float(expected[s])) for s in range(3)))
    assert worst <= 1.0 / 65535.0
    assert worst < QUANT_STEP_U8 / 10.0


def test_koszt_kwantyzacji_w_epsilon_na_artefakcie_kontrolnym(
    control_run: dict[str, Any], tmp_path: Path
) -> None:
    """KRYTERIUM BLOKUJĄCE POKER-51 na artefakcie z repo: przyrost ε maks ≤ 10% surowego.

    Koszt mierzy TO SAMO narzędzie ex-post na dwóch kopiach biegu: surowej
    i przepuszczonej przez format czytnikiem stdlib. Nie z błędu
    prawdopodobieństw — to inna jednostka niż ε (KOREKTA JEDNOSTKOWA,
    2026-08-29). Pomiar na pilocie żyje poza bramką (blok POKER-51).
    """
    pk = _load("pack_blueprint")
    ep = _load("expost")
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    for path in control_run["out_dir"].iterdir():
        if path.is_file():
            (raw_dir / path.name).write_bytes(path.read_bytes())
    quant_dir = tmp_path / "quant"
    pk.requantize_run(control_run["out_dir"], quant_dir, tmp_path / "roundtrip.bpk")
    cost = pk.quantization_cost(ep.run_expost(raw_dir, jobs=1), ep.run_expost(quant_dir, jobs=1))
    assert pk.QUANT_EPS_LIMIT_SHARE == 0.10
    assert cost["ok"], cost
    assert cost["delta_share"] <= pk.QUANT_EPS_LIMIT_SHARE
    cc = _load("control_chain")
    expected = json.loads((CONTROL_DIR / "chain_control.json").read_text())["control"]
    assert cost["raw_epsilon_max"] == pytest.approx(expected["epsilon_max"],
                                                    abs=cc.CONTROL_ABS_TOL)
    assert cost["quant_epsilon_max"] == pytest.approx(CONTROL_QUANT_EPS_MAX,
                                                      abs=cc.CONTROL_ABS_TOL)
    assert cost["quant_epsilon_median"] == pytest.approx(CONTROL_QUANT_EPS_MEDIAN,
                                                         abs=cc.CONTROL_ABS_TOL)
    assert cost["delta_share"] == pytest.approx(CONTROL_QUANT_DELTA_SHARE, abs=0.01)

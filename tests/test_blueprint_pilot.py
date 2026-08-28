"""Testy pilota blueprintu (POKER-46): tensor rolloutu 3-way, solver siatki DAG-u, ex-post.

Narzędzia żyją w tools/blueprint/ (zależności extras train) i są ładowane
przez importlib jak w testach reprodukcji treningu (test_mccfr, test_mlp).
Testy używają malutkich konfiguracji: podzbiór klas preflop, siatka 25
żetonów, 2 poziomy zegara i syntetyczny tensor — pełny pilot żyje poza bramką.
"""

import importlib.util
import itertools
import json
import random
import sys
from pathlib import Path
from typing import Any

import pytest

from poker.cards import Card, Rank, Suit
from poker.evaluation import evaluate_five
from poker.icm import icm_equities
from poker.preflop import CLASS_INDEX, PreflopClass
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


def _toy_classes() -> tuple[int, ...]:
    return tuple(sorted(_cls(name) for name in TEST_CLASSES))


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
    sg = _load("solve_grid")
    tensor_dir = _synthetic_artifacts(tmp_path, _toy_classes())
    solo_dir = tmp_path / "solo"
    sg.solve(_toy_config(sg), tensor_dir, solo_dir)
    forked_dir = tmp_path / "forked"
    sg.solve(_toy_config(sg, jobs=2), tensor_dir, forked_dir)
    names = sorted(path.name for path in solo_dir.glob("*.npz"))
    assert names
    for name in names:
        assert (solo_dir / name).read_bytes() == (forked_dir / name).read_bytes(), name


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

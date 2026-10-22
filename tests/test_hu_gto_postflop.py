"""Testy klienta postflop tools/hu_gto/postflop/hupf_py i sterownika hupf.

Sterownik hupf (Rust, AGPL-3.0) jest opcjonalnym programem zewnętrznym budowanym przez
tools/hu_gto/postflop/hupf/build.sh; testy, które go uruchamiają, są pomijane z komunikatem,
gdy binarki nie ma. Indeksowanie kart, format zadania, próbki flopów i agregacja per klasa
nie potrzebują binarki i biegną zawsze.
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
HU = REPO / "tools" / "hu_gto"


def _load_hupf_py() -> Any:
    """hupf_py to pakiet w tools/hu_gto/postflop (nie w sys.path) — ładowany jak w integ/fp.py."""
    if "hupf_py" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "hupf_py",
            HU / "postflop" / "hupf_py" / "__init__.py",
            submodule_search_locations=[str(HU / "postflop" / "hupf_py")],
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["hupf_py"] = module
        spec.loader.exec_module(module)
    return sys.modules["hupf_py"]


def _load_preflop() -> Any:
    if "hu_preflop" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "hu_preflop", HU / "preflop" / "hu_preflop.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["hu_preflop"] = module
        spec.loader.exec_module(module)
    return sys.modules["hu_preflop"]


_load_hupf_py()
cards: Any = importlib.import_module("hupf_py.cards")
aggregate: Any = importlib.import_module("hupf_py.aggregate")
flops: Any = importlib.import_module("hupf_py.flops")
ranges: Any = importlib.import_module("hupf_py.ranges")
solver: Any = importlib.import_module("hupf_py.solver")
pipeline: Any = importlib.import_module("hupf_py.pipeline")

needs_hupf = pytest.mark.skipif(
    not solver.HUPF.is_file(),
    reason=f"brak sterownika hupf ({solver.HUPF}): opcjonalny program zewnętrzny AGPL-3.0, "
    "zbuduj go przez tools/hu_gto/postflop/hupf/build.sh",
)


def test_indeks_par_kart_jest_bijekcja_zgodna_z_b_inary() -> None:
    idx = {cards.pair_index(a, b) for a in range(52) for b in range(a + 1, 52)}
    assert idx == set(range(1326))
    assert cards.pair_index(0, 1) == 0 and cards.pair_index(50, 51) == 1325
    assert cards.card_str(cards.card_id("Ah")) == "Ah" and cards.card_id("2c") == 0


def test_klasy_postflop_w_kolejnosci_preflopu_i_pakietu_poker() -> None:
    cards.check_against_repo()
    assert cards.CLASS_NAMES == _load_preflop().CLASSES
    n = cards.CLASS_NCOMBOS
    names = cards.CLASS_NAMES
    assert {n[i] for i, c in enumerate(names) if len(c) == 2} == {6.0}
    assert {n[i] for i, c in enumerate(names) if c.endswith("s")} == {4.0}
    assert {n[i] for i, c in enumerate(names) if c.endswith("o")} == {12.0}


def test_maska_boardu_usuwa_kombinacje_z_kartami_boardu() -> None:
    m = cards.board_mask("Ks7d2c")
    assert m.sum() == 1326 - 3 * 51 + 3
    k = cards.card_id("Ks")
    assert not m[cards.pair_index(k, cards.card_id("Ah"))]


def test_zadanie_ma_min_bet_bb_i_pelne_zakresy() -> None:
    w = np.full(1326, 0.25)
    text = solver.job_text(
        board="Ks7d2c", pot_bb=2.0, stack_bb=14.0, range_oop=w, range_ip=w, tree="l1rf"
    )
    kv = dict(line.split(" ", 1) for line in text.strip().split("\n"))
    assert kv["pot"] == "200" and kv["stack"] == "1400" and kv["min_bet"] == "100"
    assert kv["flop_bet"] == "50%, a" and kv["flop_raise"] == "3x, a"
    assert kv["turn_raise"] == "a"
    assert len(kv["range_oop"].split()) == 1326 and set(kv["range_ip"].split()) == {"0.25"}


def test_wybor_drzewa_wedlug_spr() -> None:
    assert pipeline.auto_tree(3.25) == "low1rf"
    assert pipeline.auto_tree(4.5) == "low1rf"
    assert pipeline.auto_tree(7.0) == "l1rf"


def test_flopy_kanoniczne_i_herding_deterministyczny() -> None:
    fl, mult = flops.canonical_flops()
    assert len(fl) == 1755 and mult.sum() == 22100
    a, b = flops.herding_sample(30), flops.herding_sample(30)
    assert a == b
    assert abs(sum(w for _, w in a) - 1.0) < 1e-12
    canon = {flops.flop_str(f) for f in fl}
    assert {f for f, _ in a} <= canon


def test_agregacja_klasowa_i_estymator_ratio() -> None:
    def result(ev_chips: float) -> dict[str, Any]:
        p = {
            "nw": np.ones(1326),
            "ev": np.full(1326, ev_chips),
            "eq": np.full(1326, 0.5),
            "weight": np.ones(1326),
        }
        return {"players": [p, p]}

    agg = aggregate.aggregate(
        [result(100.0), result(300.0)], [0.25, 0.75], pot_bb=2.0, eq_exact=np.full((2, 169), 0.6)
    )
    assert np.allclose(agg["ev_bb"], 2.5)
    assert np.allclose(agg["eqr"], 2.5)
    assert np.allclose(agg["ev_bb_ratio"], 2.5 * 2.0 * 0.6)
    assert np.allclose(agg["mass"][0], cards.CLASS_NCOMBOS)


def test_brak_binarki_daje_komunikat_z_poleceniem_budowania(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(solver, "HUPF", tmp_path / "brak" / "hupf")
    w = np.ones(1326)
    with pytest.raises(FileNotFoundError, match=r"build\.sh"):
        solver.solve(board="Ks7d2c5h9c", pot_bb=2.0, stack_bb=14.0, range_oop=w, range_ip=w)


@needs_hupf
def test_lata_min_bet_podnosi_bet_ponizej_bb_do_bb(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(solver, "ROOT", tmp_path)
    sb = cards.class_to_combo(ranges.band(0.5, 1.0))
    bb = cards.class_to_combo(ranges.band(0.2, 1.0))
    tree = {"flop": ("", ""), "turn": ("", ""), "river": ("25%", "")}
    res = solver.solve(
        threads=1,
        board="Ks7d2c5h9c",
        pot_bb=2.0,
        stack_bb=14.0,
        range_oop=bb,
        range_ip=sb,
        tree=tree,
        target_pct=0.5,
        node_depth=1,
    )
    # 25% puli 2 bb to 0,5 bb; bez łatki upstream zbudowałby Bet(50).
    assert res["nodes"][0]["actions"] == ["Check", "Bet(100)"]
    assert res["expl_pct"] <= 0.5
    assert abs(sum(res["ev_avg"]) - 200.0) < 1e-2


@needs_hupf
def test_checkdown_w_potoku_daje_ev_rowne_equity_razy_pula(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(solver, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "CACHE", tmp_path / "cache")
    run = pipeline.run(
        "limp_check",
        15.0,
        tree="checkdown",
        n_flops=2,
        target=100.0,
        threads=1,
        eq_ref="none",
        max_iter=0,
        log=lambda *_: None,
    )
    agg = run["agg"]
    _, sb_range, bb_range, _, _ = ranges.PLACEHOLDERS["limp_check"]
    ok = agg["mass"] > 0
    assert np.array_equal(ok[0], bb_range() > 0) and np.array_equal(ok[1], sb_range() > 0)
    assert np.allclose(agg["ev_bb"][ok], 2.0 * agg["eq"][ok], atol=1e-4)
    assert len(list((tmp_path / "cache").glob("*.json"))) == 2


@needs_hupf
def test_serwer_odpowiada_jedna_linia_json_na_zadanie() -> None:
    w = cards.class_to_combo(ranges.band(0.0, 1.0))
    srv = solver.Server(threads=1)
    try:
        kw = dict(board="Ks7d2c5h9c", pot_bb=2.0, stack_bb=14.0, range_oop=w, range_ip=w)
        a, b = srv.query(**kw), srv.query(**kw)
    finally:
        srv.close()
    assert a["ok"] and b["ok"] and "wall_s" in a
    assert a["iters"] == b["iters"] and a["nodes"][0]["freq"] == b["nodes"][0]["freq"]

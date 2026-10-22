"""Testy narzędzia zapytań tools/hu_gto/tool/spin_gto.py i eksportu jego danych.

Dane narzędzia (book, liście, model liścia) to artefakt pętli integracji, nie część repo,
więc testy budują je same: szybki solve preflop z syntetycznym modelem liścia, zapis rundy
jak w run_fp.py i eksport skryptem integ/export_tool_data.py do katalogu tymczasowego.
Zapytania postflop uruchamiają sterownik hupf (AGPL, budowany osobno) — bez binarki są
pomijane z komunikatem.
"""

import importlib.util
import json
import pickle
import runpy
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
HU = REPO / "tools" / "hu_gto"


def _load(name: str, path: Path) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fp = _load("fp", HU / "integ" / "fp.py")
G = _load("spin_gto", HU / "tool" / "spin_gto.py")
H = fp.H
solver = fp.solver

needs_hupf = pytest.mark.skipif(
    not solver.HUPF.is_file(),
    reason=f"brak sterownika hupf ({solver.HUPF}): opcjonalny program zewnętrzny AGPL-3.0, "
    "zbuduj go przez tools/hu_gto/postflop/hupf/build.sh",
)


@pytest.fixture(scope="module")
def exported(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    root = tmp_path_factory.mktemp("hu_gto")
    rng = np.random.default_rng(11)
    a = {"limp-check@15": (rng.normal(0, 0.03, H.N), rng.normal(0, 0.03, H.N))}
    model = fp.IntegLeaf(a)
    res = {d: fp.preflop(d, model, target=1e-3) for d in (2.0, 15.0)}
    pkl = root / "round7.pkl"
    with open(pkl, "wb") as f:
        pickle.dump(dict(state={"rounds": [{"r": 7}]}, res=res, model=model), f)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fp, "HU", root)
        mp.setattr(sys, "argv", ["export_tool_data.py", str(pkl)])
        runpy.run_path(str(HU / "integ" / "export_tool_data.py"), run_name="__main__")
    yield dict(data=root / "tool" / "data", res=res, model=model)


@pytest.fixture
def tool(
    exported: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, Any]:
    monkeypatch.setattr(G, "DATA", exported["data"])
    monkeypatch.setattr(G, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(G, "_STATE", {"threads": 2})
    monkeypatch.setattr(solver, "ROOT", tmp_path)
    return exported


def test_eksport_zapisuje_book_liscie_i_model_rundy(exported: dict[str, Any]) -> None:
    data = exported["data"]
    meta = json.loads((data / "meta.json").read_text())
    assert meta["round"] == 7 and meta["depths"] == ["2", "15"]
    assert sorted(np.load(data / "leaf_model.npz").files) == [
        "limp-check@15|bb",
        "limp-check@15|sb",
    ]
    leaves = json.loads((data / "leaves_15.json").read_text())["leaves"]
    assert {lf["node"] for lf in leaves} == {"limp-check", "limp-iso-call", "r2-call", "r2.5-call"}
    book = H.Book(data / "book.npz")
    got = book.get(15.0, "root", "AKs")
    want = exported["res"][15.0].nodes["root"].strategy[H.INDEX["AKs"]]
    assert np.allclose(list(got.values()), want, atol=1e-6)


def test_zapytanie_preflop_zwraca_strategie_booka_i_ev_modelu(tool: dict[str, Any]) -> None:
    res, model = tool["res"][15.0], tool["model"]
    o = G.query(15.0, "", None, "AKs")
    assert o["street"] == "preflop" and o["node"] == "root" and o["actor"] == "SB"
    assert o["actions"] == res.nodes["root"].actions
    assert np.allclose(o["hand_strategy"], res.nodes["root"].strategy[H.INDEX["AKs"]], atol=1e-6)
    ev_sb, _ = fp.class_ev(res, model)
    assert abs(o["hand_ev"] - ev_sb[H.INDEX["AKs"]]) < 1e-4
    bb = G.query(15.0, "SB limp", None, "72o")
    assert bb["node"] == "limp" and bb["actor"] == "BB" and bb["actions"] == ["check", "iso", "jam"]
    assert 0 < bb["opp_reach"] <= 1


def test_zapytanie_bez_danych_mowi_jak_je_wygenerowac(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(G, "DATA", tmp_path / "data")
    monkeypatch.setattr(G, "_STATE", {})
    with pytest.raises(G.QueryError, match="brak danych narzędzia .*run_fp.py"):
        G.query(15.0, "SB limp", None, "AJo")


def test_parsowanie_reki_i_linii_preflop() -> None:
    assert G.norm_class("AhTd") == "ATo" and G.norm_class("Th9h") == "T9s"
    assert G.norm_class("kas") == "AKs" and G.norm_class("77") == "77"
    with pytest.raises(G.QueryError, match="podaj s/o"):
        G.norm_class("KQ")
    node = G.walk_preflop(15.0, ["SB limp", "BB iso"])
    assert node.id == "limp-iso" and node.actor == 0
    assert G.walk_preflop(15.0, ["SB raise 2.5"]).id == "r2.5"
    assert G.walk_preflop(15.0, ["SB call", "BB shove"]).id == "limp-jam"
    with pytest.raises(G.QueryError, match="teraz decyduje SB"):
        G.walk_preflop(15.0, ["BB fold"])
    with pytest.raises(G.QueryError, match="akcji 'r3' nie ma w węźle"):
        G.walk_preflop(15.0, ["SB raise 3"])
    with pytest.raises(G.QueryError, match="akcji 'r2.5' nie ma w węźle"):
        G.walk_preflop(10.0, ["SB raise 2.5"])


def test_akcja_postflop_mapowana_na_najblizszy_rozmiar_drzewa() -> None:
    acts = ["Check", "Bet(100)", "Bet(264)", "AllIn(1400)"]
    assert G.parse_post("BB bet 2.5") == ("BB", "bet", "2.5")
    assert G.parse_post("sb jam") == ("SB", "allin", None)
    assert G.match_action(acts, "bet", "1", 200) == 1
    assert G.match_action(acts, "bet", "150%", 200) == 2
    assert G.match_action(acts, "bet", "12", 200) == 3
    assert G.match_action(acts, "bet", None, 200) == 1
    assert G.match_action(acts, "check", None, 200) == 0
    with pytest.raises(G.QueryError, match="akcji 'fold' nie ma"):
        G.match_action(acts, "fold", None, 200)
    assert G.fmt_action("Bet(264)") == "bet 2.64" and G.fmt_action("Check") == "check"


@needs_hupf
def test_zapytanie_flop_i_turn_liczy_na_zywo_i_bierze_flop_z_cache(tool: dict[str, Any]) -> None:
    flop = G.query(2.0, "SB limp, BB check", "Ks7d2c", "Ah5d")
    assert flop["street"] == "flop" and flop["actor"] == "BB" and flop["tree"] == "low1rf"
    assert abs(sum(flop["hand_strategy"]) - 1) < 1e-4 and abs(sum(flop["range_freq"]) - 1) < 1e-4
    assert not flop["streets"][0]["cached"]
    # ręka, którą BB czasem checkuje na flopie (inaczej nie dochodzi do turnu tą linią)
    hand = next(
        h
        for h in ("Ah5d", "Qd6h", "9h8h", "Jd4c", "6d5h", "Tc3d", "8c8d")
        if G.query(2.0, "SB limp, BB check", "Ks7d2c", h)["hand_strategy"][0] > 0.2
    )
    turn = G.query(2.0, "SB limp, BB check; BB check, SB check", "Ks7d2c5h", hand)
    assert turn["street"] == "turn" and turn["actor"] == "BB"
    assert turn["streets"][0]["cached"] and not turn["streets"][1]["cached"]
    assert turn["streets"][1]["pot"] == 2.0
    with pytest.raises(G.QueryError, match="koliduje z boardem"):
        G.query(2.0, "SB limp, BB check", "Ks7d2c", "KsQd")

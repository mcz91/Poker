"""Testy solvera HU preflop narzędzia tools/hu_gto (spike HU Spin, nauka offline).

Moduły z tools/hu_gto/preflop nie są pakietem, więc ładuje je importlib — jak testy
blueprintu. Referencje push/fold: HRC (holdemresources.net/hune, gra jam/fold bez ante);
liczby open_jam: niezależny solver checkdown (fold/open 2x/jam) z wcześniejszego etapu badań,
poza repo.
"""

import hashlib
import importlib.util
import itertools
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
PREFLOP = REPO / "tools" / "hu_gto" / "preflop"

# sha256 macierzy wygenerowanej przez gen_equity.py (1e6 prób/parę, eval7 0.1.11, bez ziarna);
# zmiana pliku bez regeneracji pochodzenia w README ma czerwienić.
EQUITY_SHA256 = "33f8ed9d2f3e2520e546160138a892a47755fe127c620a2af56901bb80f3346a"

HRC = {6: (68.9, 54.4), 10: (58.4, 37.3), 15: (45.7, 28.8)}


def _load(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, PREFLOP / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


H = _load("hu_preflop")


def test_wagi_par_klas_zgadzaja_sie_z_przegladem_kombinacji() -> None:
    rng = np.random.default_rng(1)
    for i, j in rng.integers(0, H.N, (40, 2)):
        a, b = H._combos(H.CLASSES[i]), H._combos(H.CLASSES[j])
        n = sum(1 for x, y in itertools.product(a, b) if not set(x) & set(y))
        assert H.W[i, j] == n
    assert H.WTOT == 1326 * 1225


def test_klasy_w_kolejnosci_pakietu_poker() -> None:
    from poker.preflop import ALL_CLASSES

    def name(c: Any) -> str:
        ranks: str = H.RANKS
        hi, lo = ranks[14 - int(c.high)], ranks[14 - int(c.low)]
        return hi + lo if hi == lo else hi + lo + ("s" if c.suited else "o")

    assert [name(c) for c in ALL_CLASSES] == H.CLASSES


def test_macierz_equity_ma_zapisane_pochodzenie_i_jest_spojna() -> None:
    path = PREFLOP / "equity_eval7_1M.npy"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == EQUITY_SHA256
    E = H.load_equity("eval7")
    assert E.shape == (H.N, H.N)
    assert np.abs(E + E.T - 1).max() < 1e-12
    assert np.abs(np.diag(E) - 0.5).max() < 1e-12
    # Macierz repo (2048 prób/parę, SE ~1,1 pp) różni się od niej o szum MC, nie systematycznie.
    rms_pp = 100 * np.sqrt(((E - H.load_equity("repo")) ** 2).mean())
    assert 0.9 < rms_pp < 1.2


@pytest.mark.parametrize("equity", ["eval7", "repo"])
@pytest.mark.parametrize("S", sorted(HRC))
def test_drzewo_jamfold_odtwarza_hrc(S: int, equity: str) -> None:
    r = H.solve(S, tree=H.TreeConfig(mode="jamfold"), equity=equity, iters=3000, target_expl=1e-6)
    jam, call = 100 * r.nodes["root"].freq["jam"], 100 * r.nodes["jam"].freq["call"]
    assert abs(jam - HRC[S][0]) < 1.0 and abs(call - HRC[S][1]) < 1.0


@pytest.mark.parametrize(
    "S,expected",
    [
        (15, (45.3, 22.7, 32.0, 0.0, 67.8)),
        (20, (43.5, 33.3, 23.2, 0.0, 71.4)),
        (25, (38.0, 51.5, 10.5, 0.0, 76.0)),
    ],
)
def test_drzewo_open_jam_zgodne_z_solverem_checkdown(S: int, expected: tuple[float, ...]) -> None:
    r = H.solve(
        S,
        H.CheckdownLeaf(),
        tree=H.TreeConfig(mode="open_jam"),
        equity="repo",
        iters=5000,
        target_expl=1e-5,
    )
    f, b = r.nodes["root"].freq, r.nodes["r2"].freq
    got = (f["fold"], f["r2"], f["jam"], b["fold"], b["call"])
    assert np.allclose(np.array(got) * 100, expected, atol=0.2)


@pytest.mark.parametrize("S", [15, 20, 25])
def test_checkdown_odtwarza_patologie_bb_nie_pasuje_vs_minraise(S: int) -> None:
    r = H.solve(S, H.CheckdownLeaf(), iters=3000, target_expl=1e-4)
    assert r.nodes["r2"].freq["fold"] < 0.02


@pytest.mark.parametrize("leaf", [H.CheckdownLeaf(), H.ConstEQRLeaf()])
def test_suma_zerowa_i_zbieznosc(leaf: Any) -> None:
    r = H.solve(15, leaf, iters=3000, target_expl=1e-4)
    assert r.expl < 1e-4 and r.gap_sb >= -1e-9 and r.gap_bb >= -1e-9
    root = H.build_tree(15, H.TreeConfig(), H.load_equity(), leaf)
    sv = H._Solver(root)
    for n in sv.dec:
        n.S = r.nodes[n.id].strategy
    one = np.ones(H.N)
    ev_sb = sv._value(root, 0, one, False).sum()
    ev_bb = sv._value(root, 1, one, False).sum()
    assert abs(ev_sb + ev_bb) < 1e-6 * H.WTOT


def test_udzial_proporcjonalny_jest_suma_zerowa_i_checkdownem_przy_q1() -> None:
    E = H.load_equity()
    q = np.random.default_rng(0).uniform(0.6, 1.3, (2, H.N))
    R = H.proportional_share(E, q[0], q[1])
    RB = H.proportional_share(E, q[1], q[0])
    assert np.allclose(R + RB.T, 1.0)
    assert np.allclose(H.proportional_share(E, np.ones(H.N), np.ones(H.N)), E)


def test_dopasowanie_addytywne_odtwarza_model_par() -> None:
    E = H.load_equity()
    rng = np.random.default_rng(3)
    a, b = rng.normal(0, 0.05, H.N), rng.normal(0, 0.05, H.N)
    R_true = E + a[:, None] - b[None, :]
    r_sb, r_bb = rng.uniform(0, 1, H.N), rng.uniform(0, 1, H.N)
    s_sb, s_bb = H.shares_vs_range(R_true, r_sb, r_bb)
    fa, fb = H.fit_additive(E, s_sb, s_bb, r_sb, r_bb)
    R_fit = E + fa[:, None] - fb[None, :]
    f_sb, f_bb = H.shares_vs_range(R_fit, r_sb, r_bb)
    assert np.abs(f_sb - s_sb).max() < 1e-6 and np.abs(f_bb - s_bb).max() < 1e-6
    assert np.abs((R_fit - R_true) - (R_fit - R_true).mean()).max() < 1e-6


def test_punkt_staly_z_wyrocznia_zbiega_do_rownowagi_wyroczni() -> None:
    E = H.load_equity()
    truth = H.ConstEQRLeaf()

    def oracle(lf: dict[str, Any]) -> dict[str, Any]:
        line = H.Line(lf["line"], lf["node"], lf["depth"], lf["pot"], lf["aggressor"])
        s_sb, s_bb = H.shares_vs_range(
            truth.share(line, E), np.array(lf["range_sb"]), np.array(lf["range_bb"])
        )
        return dict(share_sb=s_sb, share_bb=s_bb)

    rounds = H.fixed_point(
        15, oracle, rounds=5, start=H.CheckdownLeaf(), iters=3000, target_expl=1e-4
    )
    expl = [H.evaluate_profile(r, truth)["expl"] for r in rounds]
    assert expl[-1] < 2e-3 and expl[-1] < expl[0] / 5


def test_book_lookup_jest_szybki(tmp_path: Path) -> None:
    res = [H.solve(S, H.ConstEQRLeaf(), iters=1000, target_expl=1e-3) for S in (14, 16)]
    H.save_book(res, tmp_path / "b.npz")
    book = H.Book(tmp_path / "b.npz")
    p = book.get(14, "root", "AKs")
    assert set(p) == set(res[0].nodes["root"].actions) and abs(sum(p.values()) - 1) < 1e-5
    t = time.perf_counter()
    for _ in range(10000):
        book.get(15, "limp", "72o")
    assert (time.perf_counter() - t) / 10000 < 1e-3


def test_cli_drukuje_wynik_i_chart_wezla() -> None:
    out = subprocess.run(
        [sys.executable, str(PREFLOP / "hu_preflop.py"), "10", "--leaf", "jamfold"]
        + ["--node", "root", "--action", "jam"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert out.startswith("S=10 bb  liść=checkdown")
    assert "--- węzeł root" in out and "% akcji 'jam'" in out
    assert "--- węzeł jam" not in out


def test_wiersz_tabeli_ma_kolumny_naglowka() -> None:
    run_table = _load("run_table")
    r = H.solve(15.0, H.ConstEQRLeaf(), iters=1000, target_expl=1e-3)
    assert len(run_table.row(r).split()) == len(run_table.header().split())


def test_generator_equity_eval7_zgadza_sie_z_zapisana_macierza() -> None:
    eval7 = pytest.importorskip(
        "eval7", reason="eval7 potrzebny tylko do regeneracji macierzy (README: pochodzenie)"
    )
    assert eval7 is not None
    gen = _load("gen_equity")
    assert gen.CLASSES == H.CLASSES
    i = H.INDEX["AKs"]
    _, row = gen.row((i, 4000))
    assert np.isnan(row[: i + 1]).all() and np.isfinite(row[i + 1 :]).all()
    # 4000 prób: SE ~0,8 pp, więc 3 pp to ok. 4 SE od macierzy 1e6.
    assert abs(row[H.INDEX["72o"]] - H.load_equity()[i, H.INDEX["72o"]]) < 0.03

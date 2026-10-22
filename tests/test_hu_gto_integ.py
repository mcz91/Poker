"""Testy pętli integracji preflop <-> postflop tools/hu_gto/integ (stan: spike, pętla NIEZBIEŻNA).

Pełna pętla (run_fp.py) liczy postflop sterownikiem hupf przez ok. 85 min, więc w bramce
sprawdzane są jej klocki bez solve'ów postflop: model liścia (dopasowanie, pożyczanie,
fallback), wygładzanie poprawki drzewa, miary zmiany między rundami, próbka flopów
i detektor naruszeń dominacji w chartach.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parent.parent
INTEG = REPO / "tools" / "hu_gto" / "integ"


def _load(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, INTEG / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fp = _load("fp")
H = fp.H
flopsample = _load("flopsample")
dom = _load("dom")
report = _load("report")


def _leaf(node: str, line: str, depth: float, pot: float, freq: float = 0.5) -> dict[str, Any]:
    rng = np.random.default_rng(len(node) + int(depth))
    return dict(
        node=node,
        line=line,
        depth=depth,
        pot=pot,
        spr=(depth - pot / 2) / pot,
        aggressor="none",
        range_sb=rng.uniform(0, 1, H.N).tolist(),
        range_bb=rng.uniform(0, 1, H.N).tolist(),
        freq_sb=freq,
        freq_bb=freq,
    )


def test_equity_wobec_zakresu_zgodna_z_udzialem_checkdownu() -> None:
    lf = _leaf("limp-check", "limp_check", 15.0, 2.0)
    sb, bb = fp.leaf_ranges(lf)
    eq = fp.eq_vs_range(sb, bb)
    s_sb, s_bb = H.shares_vs_range(fp.E7, sb, bb)
    assert np.allclose(eq[1], s_sb) and np.allclose(eq[0], s_bb)


def test_wygladzanie_poprawki_odtwarza_kwadrat_equity_i_pomija_nan() -> None:
    rng = np.random.default_rng(5)
    eq = rng.uniform(0.2, 0.8, (2, H.N))
    delta = 0.1 - 0.3 * eq + 0.2 * eq**2
    mass = rng.uniform(0.5, 2.0, (2, H.N))
    noisy = delta.copy()
    noisy[0, :5] = np.nan
    out = fp.smooth_delta(noisy, eq, mass)
    assert np.allclose(out, delta, atol=1e-10)


def test_model_liscia_dopasowany_pozyczony_i_fallback() -> None:
    solved_lf = _leaf("limp-check", "limp_check", 15.0, 2.0)
    near = _leaf("limp-check", "limp_check", 20.0, 2.0)
    other = _leaf("r2-call", "raise_call", 15.0, 4.0)
    sb, bb = fp.leaf_ranges(solved_lf)
    rng = np.random.default_rng(9)
    a_sb, a_bb = rng.normal(0, 0.05, H.N), rng.normal(0, 0.05, H.N)
    s_sb, s_bb = H.shares_vs_range(fp.E7 + a_sb[:, None] - a_bb[None, :], sb, bb)
    ev = np.stack([s_bb, s_sb]) * solved_lf["pot"]
    solved = {"limp-check@15": dict(lf=solved_lf, ev=ev)}
    model, info = fp.build_model(solved, [solved_lf, near, other], {})
    assert info == {
        "limp-check@15": "solved",
        "limp-check@20": "borrowed:limp-check@15",
        "r2-call@15": "fallback:ConstEQR",
    }
    line15 = H.Line("limp_check", "limp-check", 15.0, 2.0, "none")
    f_sb, f_bb = H.shares_vs_range(model.share(line15, fp.E7), sb, bb)
    assert np.abs(f_sb - s_sb).max() < 1e-6 and np.abs(f_bb - s_bb).max() < 1e-6
    line20 = H.Line("limp_check", "limp-check", 20.0, 2.0, "none")
    assert np.array_equal(model.share(line20, fp.E7), model.share(line15, fp.E7))
    line_r2 = H.Line("raise_call", "r2-call", 15.0, 4.0, "SB")
    assert np.array_equal(model.share(line_r2, fp.E7), H.ConstEQRLeaf().share(line_r2, fp.E7))


def test_poprawka_drzewa_wchodzi_do_modelu_tylko_z_use_delta() -> None:
    lf = _leaf("limp-check", "limp_check", 15.0, 2.0)
    sb, bb = fp.leaf_ranges(lf)
    s_sb, s_bb = H.shares_vs_range(fp.E7, sb, bb)
    ev = np.stack([s_bb, s_sb]) * lf["pot"]
    # poprawka sumy zerowej (BB traci, SB zyskuje 0,1 bb) jest w zasięgu modelu addytywnego
    deltas = {"limp-check@15": np.stack([np.full(H.N, -0.1), np.full(H.N, 0.1)])}
    solved = {"limp-check@15": dict(lf=lf, ev=ev)}
    with_d, info = fp.build_model(solved, [lf], deltas)
    without, _ = fp.build_model(solved, [lf], deltas, use_delta=False)
    assert info["limp-check@15"] == "solved+delta"
    line = H.Line("limp_check", "limp-check", 15.0, 2.0, "none")
    w_sb, w_bb = H.shares_vs_range(with_d.share(line, fp.E7), sb, bb)
    n_sb, n_bb = H.shares_vs_range(without.share(line, fp.E7), sb, bb)
    assert np.allclose(w_sb - n_sb, 0.1 / lf["pot"], atol=1e-6)
    assert np.allclose(w_bb - n_bb, -0.1 / lf["pot"], atol=1e-6)


def test_miara_zmiany_rund_zero_dla_tego_samego_profilu() -> None:
    model = H.ConstEQRLeaf()
    r = fp.preflop(15.0, model, target=1e-3)
    ch = fp.compare(r, r, model, model)
    assert ch["max_freq_pp"] == 0.0 and ch["ev_sb_max"] == 0.0 and ch["ev_bb_max"] == 0.0
    txt, stats = report.change(r, r, model, model)
    assert txt.startswith("max |Δ częstości|  0.00 pp") and stats["sb_max"] == 0.0
    assert fp.res_to_json(r)["nodes"]["root"]["actions"] == r.nodes["root"].actions


def test_probka_flopow_petli_ma_flopy_sparowane_ktorych_brak_w_oryginale() -> None:
    flops = sys.modules["hupf_py.flops"]
    sample = flopsample.herd(12)
    assert sample == flopsample.herd(12) and abs(sum(w for _, w in sample) - 1) < 1e-12

    def paired(s: list[tuple[str, float]]) -> float:
        return sum(w for f, w in s if len({f[0], f[2], f[4]}) < 3)

    assert paired(sample) > 0.1
    assert paired(flops.herding_sample(12)) == 0.0
    assert all(len({f[0], f[2], f[4]}) > 1 for f, _ in sample)


def test_detektor_dominacji_wskazuje_silniejsza_reke_ktora_pasuje() -> None:
    strategy = np.tile([0.0, 1.0], (H.N, 1))
    node = SimpleNamespace(actions=["fold", "call"], strategy=strategy)
    assert dom.violations(node) == []
    strategy[H.INDEX["Q7o"]] = [1.0, 0.0]
    viol = dom.violations(node)
    assert {"Q7o<Q6o", "Q7o<J7o", "Q7o<72o"} <= set(viol)
    assert not {"Q7o<K2o", "Q7o<Q8o", "Q7o<Q6s"} & set(viol)
    assert all(v.startswith("Q7o<") and v.endswith("o") for v in viol)

"""Testy fictitious play preflop <-> postflop (tools/hu_gto/integ/fpa.py, run_fpa.py).

Pełny bieg liczy postflop sterownikiem hupf godzinami, więc tu postflop zastępuje gra zabawkowa
albo syntetyczne wyniki per flop (system zewnętrzny), a sprawdzane jest zachowanie pętli,
modelu liścia, estymatorów i harmonogramu jobów.
"""

import importlib.util
import sys
import threading
import time
from pathlib import Path
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
fpa = _load("fpa")
flopsample = _load("flopsample")
run_fpa = _load("run_fpa")
BB_CHIPS = sys.modules["hupf_py.cards"].BB_CHIPS


def _toy_postflop(kappa: float = 0.6, f0: float = 0.5) -> Any:
    """Postflop zależny od zakresu: udział SB w puli r2-call spada, gdy SB otwiera szerzej
    (R = E + kappa (f0 - zasięg SB w liściu)) — jak adaptacja BB, której model addytywny
    nie widzi."""

    def P(avg: Any) -> dict[str, Any]:
        out = {}
        for lf in avg.leaves:
            sb, bb = fp.leaf_ranges(lf)
            s_sb, s_bb = H.shares_vs_range(fp.E7 + kappa * (f0 - lf["freq_sb"]), sb, bb)
            ev = np.stack([s_bb, s_sb]) * lf["pot"]
            out[fp.leaf_key(lf)] = fpa.LeafData(lf, ev, np.full((2, H.N), 1e-8))
        return out

    return P


def _run_toy(averaging: str, rounds: int) -> list[dict[str, Any]]:
    F = fpa.FictitiousPlay(15.0, H.TreeConfig(mode="open_jam"), averaging=averaging, target=1e-4)
    P = _toy_postflop()
    return [F.add_round(P(F.profile())) for _ in range(rounds)]


def test_iteracja_bez_usredniania_wpada_w_2_cykl_a_fp_zbiega() -> None:
    naive = _run_toy("last", 8)
    f = [rec["freq_iterate"]["root"]["r2"] for rec in naive]
    assert all(abs(f[k] - f[k - 1]) > 30 for k in range(4, 8))
    assert all(abs(f[k] - f[k - 2]) < 1 for k in range(5, 8))
    assert min(rec["gap_ho"]["expl"] for rec in naive[4:]) > 0.2

    avg = _run_toy("linear", 8)
    g = [rec["freq"]["root"]["r2"] for rec in avg]
    assert all(abs(g[k] - g[k - 1]) < 2 for k in range(5, 8))
    assert avg[-1]["gap_ho"]["expl"] < 2e-3
    assert avg[-1]["gap_ho"]["expl"] < max(rec["gap_ho"]["expl"] for rec in avg) / 5


def _round(lf: dict[str, Any], a_sb: np.ndarray, a_bb: np.ndarray) -> dict[str, Any]:
    sb, bb = fp.leaf_ranges(lf)
    s_sb, s_bb = H.shares_vs_range(fp.E7 + a_sb[:, None] - a_bb[None, :], sb, bb)
    ev = np.stack([s_bb, s_sb]) * lf["pot"]
    return {fp.leaf_key(lf): fpa.LeafData(lf, ev, np.full((2, H.N), 1e-4))}


def test_model_puli_to_srednia_liniowa_rund_i_suma_zerowa() -> None:
    F = fpa.FictitiousPlay(15.0, H.TreeConfig(mode="open_jam"), target=1e-3)
    lf = F.profile().leaves[0]
    rng = np.random.default_rng(4)
    a = [(rng.normal(0, 0.05, H.N), rng.normal(0, 0.05, H.N)) for _ in range(2)]
    F.rounds = [_round(lf, *a[0]), _round(lf, *a[1])]
    model, _ = F.pooled_model()
    k = fp.leaf_key(lf)
    m_sb, m_bb = model.a[k]
    want_sb, want_bb = (a[0][0] + 2 * a[1][0]) / 3, (a[0][1] + 2 * a[1][1]) / 3
    # a_sb i a_bb są wyznaczone z dokładnością do wspólnej stałej
    assert np.allclose(m_sb - want_sb, (m_sb - want_sb).mean(), atol=1e-6)
    assert np.allclose(m_bb - want_bb, (m_sb - want_sb).mean(), atol=1e-6)
    sb, bb = fp.leaf_ranges(lf)
    joint = H.W * sb[:, None] * bb[None, :]
    for smooth in (False, True):
        F.smooth = smooth
        ev = fpa.predicted_ev(F.pooled_model()[0], k, lf)
        total = joint.sum(1) @ ev[1] + joint.sum(0) @ ev[0]
        assert abs(total / joint.sum() - lf["pot"]) < 1e-9


def test_shrinkage_zmniejsza_blad_i_ma_poprawne_skrajnosci() -> None:
    X, w = fpa.FEATURES, H.NCOMBO.astype(float)
    ratios = []
    for seed in range(6):
        rng = np.random.default_rng(seed)
        truth = X @ rng.normal(0, 0.03, X.shape[1]) + rng.normal(0, 0.02, H.N)
        var = rng.uniform(0.5, 2.0, H.N) * 0.02**2
        obs = truth + rng.normal(0, np.sqrt(var))
        out, info = fpa.shrink(obs, var, w)
        err_out, err_obs = (float(w @ (x - truth) ** 2 / w.sum()) for x in (out, obs))
        assert err_out < 0.7 * err_obs
        ratios.append(np.sqrt(info["tau2"]) / 0.02)
    assert 0.6 < np.mean(ratios) < 1.2
    # klasa bez szumu zostaje przy obserwacji, klasa bez danych dostaje część gładką
    known = np.random.default_rng(9).permutation(H.N) < 120
    mixed, _ = fpa.shrink(obs, np.where(known, 0.0, np.inf), w)
    beta = np.linalg.lstsq(
        X[known] * np.sqrt(w[known])[:, None], obs[known] * np.sqrt(w[known]), rcond=None
    )[0]
    assert np.allclose(mixed[known], obs[known], atol=1e-9)
    assert np.allclose(mixed[~known], X[~known] @ beta, atol=1e-6)


def test_jackknife_sredniej_rowny_klasycznemu_bledowi() -> None:
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, (10, 2, H.N))
    cs = np.stack([np.ones_like(x), x, np.ones_like(x)], 1)  # (K, 3, 2, 169)
    full, var, loo = fpa.jackknife(cs, np.full(10, 0.1), lambda S: S[1] / S[0])
    assert np.allclose(full, x.mean(0)) and loo.shape == (10, 2, H.N)
    assert np.allclose(var, x.var(0, ddof=1) / 10)


def _flop_result(eq: np.ndarray, ev_share: np.ndarray, pot: float) -> dict[str, Any]:
    """Wynik sterownika dla jednego flopu (system zewnętrzny): nw, ev (żetony), eq per
    kombinacja."""
    return {
        "players": [
            dict(
                nw=np.ones(1326).tolist(),
                ev=(ev_share[p] * pot * BB_CHIPS).tolist(),
                eq=eq[p].tolist(),
                weight=np.ones(1326).tolist(),
            )
            for p in (0, 1)
        ]
    }


def test_estymator_ratio_i_poprawka_drzewa_na_syntetycznych_flopach() -> None:
    rng = np.random.default_rng(1)
    pot = 2.0
    lf: dict[str, Any] = dict(
        node="limp-check", depth=15.0, pot=pot, range_sb=np.ones(H.N), range_bb=np.ones(H.N)
    )
    eqs = [rng.uniform(0.2, 0.8, (2, 1326)) for _ in range(5)]
    lo = [_flop_result(e, e, pot) for e in eqs]  # EQR = 1 na każdym flopie
    ev, var, _ = fpa.leaf_ev(lf, lo, [0.2] * 5)
    sb, bb = fp.leaf_ranges(lf)
    assert np.allclose(ev, pot * fp.eq_vs_range(sb, bb)) and np.allclose(var, 0, atol=1e-20)
    hi = [_flop_result(e, e + 0.05, pot) for e in eqs]
    d, dvar = fpa.tree_correction(hi, lo, [0.2] * 5)
    assert np.allclose(d, 0.05 * pot) and np.allclose(dvar, 0, atol=1e-20)


def test_bloki_flopow_rozlaczne_zbalansowane_i_stabilne() -> None:
    blocks = flopsample.herd_blocks([8, 6, 6])
    names = [f for b in blocks for f, _ in b]
    assert len(names) == len(set(names)) == 20
    assert all(abs(sum(w for _, w in b) - 1) < 1e-12 for b in blocks)
    assert flopsample.herd_blocks([8, 6]) == blocks[:2]
    for b in blocks:
        paired = sum(w for f, w in b if len({f[0], f[2], f[4]}) < 3)
        assert 0.1 < paired < 0.35  # populacja: 17,2% flopów sparowanych


def test_harmonogram_jobow_trzyma_budzet_pamieci_i_liczy_wszystko(monkeypatch: Any) -> None:
    active = {"mem": 0.0, "max": 0.0}
    lock = threading.Lock()

    def fake_run_one(kw: dict[str, Any], threads: int) -> tuple[dict[str, Any], bool]:
        m = run_fpa.mem_gb(kw)
        with lock:
            active["mem"] += m
            active["max"] = max(active["max"], active["mem"])
        time.sleep(0.01)
        with lock:
            active["mem"] -= m
        return {"board": kw["board"], "tree": kw["tree"]}, True

    monkeypatch.setattr(fp, "run_one", fake_run_one)
    monkeypatch.setattr(fp, "log", lambda *a: None)
    boards = ["Kd4h3s", "Jh8h7s", "Qs6s5s", "Td9h2s", "9h5h3s", "As8s6s"]
    jobs = [
        ((f"limp-check@{d}", b, kind), dict(board=b, tree=tree, stack_bb=d - 1, pot_bb=2))
        for b in boards
        for d in (15, 20)
        for kind, tree in (("hi", "l1rf"), ("lo", "flopsmall"))
    ]
    out = run_fpa.run_all(jobs, 4, "t")
    assert set(out) == {lab for lab, _ in jobs}
    assert all(out[lab]["tree"] == kw["tree"] for lab, kw in jobs)
    assert 0 < active["max"] <= run_fpa.MEM_BUDGET_GB
    # tęczowy l1rf przy 20 bb liczony ostrożniej niż monokolorowy przy 15 bb (pomiar spike'u)
    rainbow20 = run_fpa.mem_gb(dict(board="Kd4h3s", tree="l1rf", stack_bb=19, pot_bb=2))
    mono15 = run_fpa.mem_gb(dict(board="Qs6s5s", tree="l1rf", stack_bb=14, pot_bb=2))
    assert rainbow20 > 5.8 and 1.4 < mono15 < 2.0


def test_kategorie_referencji_sumuja_rozmiary() -> None:
    root = {"fold": 5.0, "limp": 60.0, "r2": 20.0, "r2.5": 10.0, "jam": 5.0}
    assert run_fpa.categories("root", root) == dict(fold=5.0, limp=60.0, raise_=30.0, jam=5.0)
    limp = {"check": 60.0, "iso3": 15.0, "iso5": 13.0, "jam": 12.0}
    cats = run_fpa.categories("limp", limp)
    assert cats == dict(check=60.0, iso_small=15.0, iso_big=13.0, jam=12.0)
    cmp = run_fpa.ref_compare(15.0, {"root": root, "limp": limp})
    assert [c["ref"] for c in cmp] == ["GW-AI 16", "GW-AI 16"]
    assert cmp[0]["diff"]["raise_"] == 5.0 and cmp[1]["max_abs"] == 1.7


def test_raport_rund_pokazuje_2_cykl_iteratow_i_wynik_held_out() -> None:
    report = _load("report_fpa")
    gap = dict(expl=0.05, gap_sb=0.04, gap_bb=0.06)
    a = {"root": {"limp": 70.0, "r2": 30.0}}
    b = {"root": {"limp": 40.0, "r2": 60.0}}
    rounds: list[dict[str, Any]] = [
        dict(
            depths={
                "15": dict(
                    r=r,
                    gap_ho=gap,
                    gap_in=gap,
                    change=None if r == 0 else (1.5, "root:r2"),
                    freq_iterate=a if r % 2 == 0 else b,
                    mass={"root": 1.0},
                    refs=[],
                    dominance={"r2": 3, "root": 1},
                    agree_in_oos={"root": 0.9},
                )
            }
        )
        for r in range(3)
    ]
    final = dict(
        gaps={"held-out": gap},
        agree_in_oos={"root": 0.95},
        dominance={"r2": 0},
        bias={"r2-call@15": {"SB": dict(bias=0.01, se=0.02), "BB": dict(bias=-0.01, se=0.02)}},
        refs=[dict(ref="GW-AI 16", node="root", ours={"limp": 60.0}, diff={"limp": -7.8})],
    )
    txt = report.rounds_table(dict(rounds=rounds, final={"15": final}))
    row = txt.splitlines()[4]
    assert row.startswith("2  0.0500 (0.040/0.060)") and " 30.0 /   0.0 " in row and " 4 " in row
    assert "held-out końcowy: held-out 0.0500" in txt and "IN/OOS 95 (root)" in txt
    assert "bias r2-call@15: SB +0.010±0.020" in txt and "Δ {'limp': -7.8}" in txt


def test_porownanie_wygladzania_przy_znikomym_szumie_daje_model_surowy() -> None:
    cmp = _load("compare_smooth")
    F = fpa.FictitiousPlay(15.0, H.TreeConfig(mode="open_jam"), target=1e-4)
    P = _toy_postflop()
    for _ in range(3):
        F.add_round(P(F.profile()))
    ho = F.raw_model(P(F.profile()))
    rep = cmp.compare(F, ho, [1.0])
    assert set(rep) == {"surowy", "EB x1"} and not F.smooth
    raw, eb = rep["surowy"], rep["EB x1"]
    assert abs(raw["gap_ho"]["expl"] - eb["gap_ho"]["expl"]) < 1e-4
    assert raw["root"] == eb["root"] and set(raw["agree"]) == {"root", "r2"}

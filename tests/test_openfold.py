"""Open 2.2x tree: first-in is the product. 3bet in this tree is not shipped."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from poker import jamfold
from poker.cards import Rank
from poker.openfold import (
    BB_VS_JAM,
    BB_VS_OJ,
    BB_VS_OPEN,
    BTN_VS_JAM,
    BTN_VS_OPEN,
    DECISIONS,
    N_HANDS,
    N_NODES,
    UTG_DEF,
    UTG_JAM,
    UTG_OPEN,
    _eq_vs,
    _sd,
    _top_slice,
    action_values,
    best_response,
    br_gain,
    solve,
    solve_curve,
    terminals,
    threebet,
    threebet_vs_range,
)
from poker.preflop import ALL_CLASSES, CLASS_INDEX, PreflopClass
from poker.spin import PAYOUTS, terminal_equities

REPO = Path(__file__).resolve().parent.parent

JUNK_72O = next(
    i
    for i, cls in enumerate(ALL_CLASSES)
    if cls.high.name == "SEVEN" and cls.low.name == "TWO" and not cls.suited
)
K2O = CLASS_INDEX[PreflopClass(Rank.KING, Rank.TWO, suited=False)]
J2O = CLASS_INDEX[PreflopClass(Rank.JACK, Rank.TWO, suited=False)]
AA = CLASS_INDEX[PreflopClass(Rank.ACE, Rank.ACE, suited=False)]
ANY = [1.0] * N_HANDS
TOP_10 = _top_slice(ANY, 0.10)
TOP_30 = _top_slice(ANY, 0.30)


def _profile(ranges: dict[int, list[float]]) -> list[list[float]]:
    sigma = [[0.0] * N_HANDS for _ in range(N_NODES)]
    for node, freq in ranges.items():
        sigma[node] = list(freq)
    return sigma


def _values(
    node: int, stacks: tuple[int, int, int], pay: str, sigma: list[list[float]]
) -> list[tuple[float, ...]]:
    """Wyceny akcji (fold, *węzły) punktu decyzji z węzłem `node`, per klasa ręki."""
    decision = next(d for d, nodes in enumerate(DECISIONS) if node in nodes)
    terms = terminals(stacks, PAYOUTS[pay].prizes, button=1, sb=1, bb_amt=2)
    return list(action_values(terms, sigma)[decision])


def _strictly_increasing(values: list[float], equity: list[float]) -> list[tuple[int, int]]:
    """Pary klas łamiące ścisły wzrost wartości z equity (pusta lista = wzrost ścisły)."""
    return [
        (lo, hi)
        for lo in range(N_HANDS)
        for hi in range(N_HANDS)
        if equity[lo] < equity[hi] and not values[lo] < values[hi]
    ]


def test_utg_otwiera_nie_shoveuje_na_25bb() -> None:
    """Test dymny przy jawnym N = 12: wynik uciętego FP zależy od N, więc test
    pilnuje kształtu (open w korytarzu, jam rzadki, AA gra, 72o pasuje), który
    krzywa POKER-73 potwierdza na każdym punkcie kontrolnym 8–1024."""
    hit = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=12)
    assert 12.0 <= hit.utg_open_pct <= 45.0
    assert hit.utg_jam_pct < hit.utg_open_pct * 0.25
    # Częstości z rozkładu strategii i próg testu, nie werdykt produkcyjny.
    assert hit.utg_open[0] + hit.utg_jam[0] > 0.85
    assert hit.utg_open[JUNK_72O] + hit.utg_jam[JUNK_72O] < 0.25


def test_10x_nie_wybucha_open() -> None:
    """Test dymny przy jawnym N = 10: open 10x nie szerszy niż open 3x (8,7%
    wobec 22,5%) i w korytarzu openu 3x.

    Relację „open 10x ≤ open 3x" krzywa POKER-73 potwierdza przy N eksportu
    512 (32,7% ≤ 33,9%) i w punktach 256 i 1024; łamie się przy 128
    (30,4% > 28,9%). Korytarz ≤ 45% trzyma się na każdym punkcie kontrolnym
    8–1024 (11,9–33,2%); mutant ze starym terminalem callu BB_VS_OJ daje przy
    N = 10 open 10x 98,2%.
    """
    wta = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=10)
    icm = solve((50, 50, 50), PAYOUTS["10x"].prizes, button=1, iterations=10)
    assert icm.utg_open_pct <= wta.utg_open_pct
    assert icm.utg_open_pct <= 45.0


def test_threebet_ciasny_nie_artefakt() -> None:
    """Test dymny przy jawnych N = 12 (3x) i N = 10 (10x); korytarz i relacja
    10x ≤ 3x trzymają się też na krzywej POKER-73 w punktach 64–1024."""
    hit = threebet((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=12)
    assert 6.0 <= hit.btn_vs_open_pct <= 18.0
    assert hit.btn_vs_open[0] > 0.85
    assert hit.btn_vs_open[JUNK_72O] < 0.25
    tight = threebet((50, 50, 50), PAYOUTS["10x"].prizes, button=1, iterations=10)
    assert tight.btn_vs_open_pct <= hit.btn_vs_open_pct


def test_showdown_spasowany_bb_nie_odzyskuje_blinda() -> None:
    """UTG i BTN all-in (BTN z samym SB 1), BB pasuje blind 2, wygrywa BTN.

    Pula główna 3 dla BTN, drugi żeton blinda BB w side pocie, o który gra
    tylko UTG (finding B3 audytu 09-26). Ranga przegranego dla spasowanego
    dzieliła ten side pot: (49, 3, 49).
    """
    assert _sd((50, 1, 50), [50, 1, 2], (0, 1), 1) == (50, 3, 48)


def test_koniec_turnieju_nie_zalezy_od_numeracji_miejsc() -> None:
    """BTN all-in z samego SB odpada razem z przegranym all-in UTG–BB.

    Te same role i stacki (UTG, BTN, BB) = (89, 1, 60) pod dwiema numeracjami
    miejsc dają tę samą strategię, bo drugie miejsce bierze większy stack
    wejściowy, nie niższy indeks miejsca. Przed POKER-70 (finding I-21 audytu
    09-26) BB 3-betował tu szeroki open w 8,7% przy guziku 1 i w 39,7% przy
    guziku 2.
    """
    prizes = PAYOUTS["10x"].prizes
    first = solve((89, 1, 60), prizes, button=1, iterations=4)
    assert first == solve((60, 89, 1), prizes, button=2, iterations=4)
    wide = [1.0] * N_HANDS
    assert threebet_vs_range(wide, (89, 1, 60), prizes, button=1) == threebet_vs_range(
        wide, (60, 89, 1), prizes, button=2
    )


def test_bb_odpadajacy_razem_z_btn_bierze_drugie_miejsce() -> None:
    """(UTG, BTN, BB) = (89, 1, 60): BTN ma tylko SB, więc gdy BB przegra all-in
    z pokrywającym go UTG, obaj kończą rękę bez żetonów (150, 0, 0), a drugie
    miejsce (2,0) bierze większy stack wejściowy — BB, nie podział (1,0).

    3-bet BB przeciw otwarciu 100% z kontynuacją 100%: fold daje ICM
    (92, 0, 58) = 4,32, wygrana ICM (29, 0, 121) = 6,84, więc próg equity to
    (4,32 − 2) / (6,84 − 2) ≈ 0,479; przy podziale byłby ≈ 0,568. K2o (equity
    0,504 wobec dowolnych dwóch) jamuje, J2o (0,445) folduje. W pełnym drzewie
    (N = 4) BB 3-betuje open w 48,48% (przy podziale 14,62%, przy ICM z indeksem
    sprzed POKER-70 5,67%); do POKER-73, gdy overcall BB wyceniał showdown bez
    udziału BB, 47,63%.
    """
    prizes = PAYOUTS["10x"].prizes
    against_any = threebet_vs_range(
        [1.0] * N_HANDS, (89, 1, 60), prizes, button=1, continue_frac=1.0
    )
    assert against_any.bb_vs_open[K2O] == 1.0
    assert against_any.bb_vs_open[J2O] == 0.0
    tree = solve((89, 1, 60), prizes, button=1, iterations=4)
    assert tree.bb_vs_open_pct == pytest.approx(48.477, abs=1e-3)


@pytest.mark.parametrize("pay", ["3x", "10x"])
def test_overcall_bb_rosnie_z_equity_wobec_jamu_btn(pay: str) -> None:
    """Call BB po jamie BTN nad openem UTG: showdown BTN–BB z martwym openem.

    Finding B6 audytu 09-26: call wyceniany był showdownem UTG–BTN, w którym
    BB ma tylko blind — na 10x Δ = +0,696 dla każdej ręki (overcall 100%),
    na 3x |Δ| ~1e−16 (decyzję rozstrzygał szum floatów).
    """
    sigma = _profile({BTN_VS_OPEN: TOP_10})
    delta = [call - fold for fold, call in _values(BB_VS_OJ, (50, 50, 50), pay, sigma)]
    equity = [_eq_vs(h, TOP_10) for h in range(N_HANDS)]
    assert _strictly_increasing(delta, equity) == []
    tol = 1e-3 * sum(PAYOUTS[pay].prizes)
    assert delta[AA] >= tol
    assert delta[JUNK_72O] <= -tol


@pytest.mark.parametrize("pay", ["3x", "10x"])
def test_jam_btn_przy_pewnym_overcallu_rosnie_z_equity_wobec_bb(pay: str) -> None:
    """p_oj = 1: jam BTN nad openem gra zawsze showdown z BB, więc jego wartość
    rośnie z equity ręki BTN wobec zakresu overcallu (nie showdown UTG–BB)."""
    sigma = _profile({BB_VS_OJ: ANY})
    jam = [q[1] for q in _values(BTN_VS_OPEN, (50, 50, 50), pay, sigma)]
    equity = [_eq_vs(h, ANY) for h in range(N_HANDS)]
    assert _strictly_increasing(jam, equity) == []


def test_fold_utg_po_jamie_i_overcallu_to_showdown_btn_bb_z_martwym_openem() -> None:
    """UTG pasujący po jamie BTN i overcallu BB zostaje z 46 żetonami, a zwycięzca
    showdownu BTN–BB bierze 104 (oba stacki i martwy open 4) — ICM dwóch żywych.

    Przy BTN jamującym i BB overcallującym zawsze open UTG = max(call, fold);
    72o pasuje, więc open ma wartość foldu. Wcześniej fold wyceniał stan, w którym
    BTN bierze pulę bez calla BB: (46, 56, 48).
    """
    prizes = PAYOUTS["10x"].prizes
    sigma = _profile({BTN_VS_OPEN: ANY, BB_VS_OJ: ANY})
    open_72o = _values(UTG_OPEN, (50, 50, 50), "10x", sigma)[JUNK_72O][1]
    assert open_72o == pytest.approx(terminal_equities((50, 50, 50), (46, 104, 0), prizes)[0])


@pytest.mark.parametrize("node", [BTN_VS_OPEN, BTN_VS_JAM], ids=["BTN_VS_OPEN", "BTN_VS_JAM"])
def test_fold_btn_nie_zalezy_od_reki_spasowanego(node: int) -> None:
    """Po foldzie BTN o puli grają UTG i BB; przy nierównych stackach i ICM ich
    wynik zmienia $EV BTN, ale jego prawdopodobieństwo nie zależy od ręki BTN."""
    sigma = _profile(
        {
            UTG_OPEN: TOP_30,
            UTG_JAM: TOP_10,
            UTG_DEF: TOP_10,
            BB_VS_OPEN: TOP_10,
            BB_VS_JAM: TOP_30,
        }
    )
    folds = {q[0] for q in _values(node, (30, 50, 70), "10x", sigma)}
    assert len(folds) == 1


@pytest.mark.parametrize("pay", ["3x", "10x"])
def test_bb_overcalluje_jam_btn_reka_nie_szumem(pay: str) -> None:
    """Test dymny przy jawnym N = 16 (liczba iteracji eksportu sprzed POKER-73):
    AA woła jam BTN nad openem, 72o pasuje. Przed POKER-73: 3x AA 0,00; 10x 72o 1,00."""
    hit = solve((50, 50, 50), PAYOUTS[pay].prizes, button=1, iterations=16)
    assert hit.bb_vs_oj[AA] >= 0.85
    assert hit.bb_vs_oj[JUNK_72O] <= 0.15


def test_miara_zbieznosci_nieujemna_z_konstrukcji() -> None:
    """Zysk z best response ≥ 0 w każdym punkcie decyzji — dla profili FP
    i dla profilu mieszanego spoza FP; miara to maksimum tych zysków."""
    terms = terminals((30, 50, 70), PAYOUTS["10x"].prizes, button=1, sb=1, bb_amt=2)
    mixed = [[0.3] * N_HANDS for _ in range(N_NODES)]
    for sigma in (mixed, _profile({})):
        assert min(br_gain(terms, sigma)) >= 0.0
    for hit in solve_curve((50, 50, 50), PAYOUTS["3x"].prizes, (1, 2, 5), sb=2, bb_amt=4):
        assert len(hit.br_gain) == len(DECISIONS)
        assert min(hit.br_gain) >= 0.0
        assert hit.convergence == max(hit.br_gain)


def test_miara_zero_dla_profilu_bedacego_wlasnym_best_response() -> None:
    """(50, 50, 50), 3x, 10/20: trzy kroki czystej dynamiki best response od
    profilu zerowego dają profil, który jest własnym best response (UTG otwiera
    64%, BTN po foldzie UTG jamuje 81%) — jego miara to dokładnie 0; miara
    profilu zerowego w tym samym spocie jest dodatnia w każdym punkcie."""
    terms = terminals((50, 50, 50), PAYOUTS["3x"].prizes, button=1, sb=10, bb_amt=20)
    sigma = _profile({})
    for _ in range(3):
        sigma = best_response(action_values(terms, sigma))
    assert best_response(action_values(terms, sigma)) == sigma
    assert br_gain(terms, sigma) == (0.0,) * len(DECISIONS)
    assert min(br_gain(terms, _profile({}))) > 0.0


def test_miara_maleje_z_iteracjami_fp() -> None:
    """3x, 3/6: miara po 64 iteracjach FP poniżej miary po 8 (3,4e−4 wobec 3,6e−3).

    Jawny wyjątek od N ≤ 24 testów bramki (rozstrzygnięcie architekta, POKER-73):
    po przyspieszeniu wyceny, bitowo zgodnym z bazą, bieg do N = 64 kosztuje ok. 1,5 s.
    """
    early, late = solve_curve((50, 50, 50), PAYOUTS["3x"].prizes, (8, 64), sb=3, bb_amt=6)
    assert late.convergence < early.convergence


def test_krzywa_zwraca_to_co_solve_w_punktach_kontrolnych() -> None:
    """Punkt kontrolny krzywej nie zaburza biegu FP: wpis dla N = wynik solve(N)."""
    prizes = PAYOUTS["10x"].prizes
    curve = solve_curve((30, 50, 70), prizes, (7, 3))
    assert curve == (
        solve((30, 50, 70), prizes, iterations=7),
        solve((30, 50, 70), prizes, iterations=3),
    )


def _tool(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_n_z_krzywej_to_punkt_od_ktorego_miara_zostaje_w_tolerancji() -> None:
    """Miary z krzywej POKER-73 (3x 1/2 i 3x 2/4, punkty 64–1024): 3x 2/4 schodzi
    do 8,75e−5 przy 128 i wraca do 1,26e−3 przy 256, więc N z krzywej to 512 —
    punkt, od którego oba poziomy zostają w tolerancji do końca krzywej — a nie
    najmniejszy punkt w tolerancji (128). Gdy tolerancji nie spełnia ostatni
    punkt, takiego N nie ma."""
    export = _tool("export_open_nash")
    wta_1_2 = {64: 1.23e-3, 128: 8.46e-4, 256: 5.63e-4, 512: 4.80e-4, 1024: 2.90e-4}
    wta_2_4 = {64: 3.47e-4, 128: 8.75e-5, 256: 1.26e-3, 512: 3.41e-4, 1024: 8.53e-5}
    assert export.stable_checkpoint([wta_1_2, wta_2_4]) == 512
    assert export.stable_checkpoint([wta_1_2]) == 128
    assert export.stable_checkpoint([wta_2_4, {**wta_1_2, 1024: 1.01e-3}]) is None


def test_ksiazki_areny_biora_openfold_i_jamfold_z_osobnych_parametrow() -> None:
    """Open, overjam i 3bet książek areny z openfold przy własnej liczbie
    iteracji, call jamu z jamfold przy swojej (POKER-73; jamfold — sprint B)."""
    arena = _tool("run_arena")
    prizes = PAYOUTS["3x"].prizes
    hero = arena.hero_book("3x", jamfold_iterations=2, openfold_iterations=4)
    deep = solve((50, 50, 50), prizes, iterations=4)
    assert hero.open == list(deep.utg_open)
    assert hero.overjam == list(deep.utg_jam)
    assert hero.vs_jam == list(jamfold.solve((50, 50, 50), prizes, 1, 2).btn_call)
    expl = arena.exploit_book("3x", jamfold_iterations=2, openfold_iterations=4)
    assert expl.open == hero.open


def test_opcja_openfold_iters_areny() -> None:
    arena = _tool("run_arena")
    assert arena.openfold_option("compare", ["320", "3x"]) == (["320", "3x"], 512)
    assert arena.openfold_option("sd", ["--openfold-iters", "64", "320"]) == (["320"], 64)
    with pytest.raises(SystemExit, match="compare i sd"):
        arena.openfold_option("seats", ["--openfold-iters", "64"])
    with pytest.raises(SystemExit, match="wymaga liczby"):
        arena.openfold_option("compare", ["320", "--openfold-iters"])

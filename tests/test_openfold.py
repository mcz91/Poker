"""Open 2.2x tree: first-in is the product. 3bet in this tree is not shipped."""

from __future__ import annotations

import pytest

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
    solve,
    terminals,
    threebet,
    threebet_vs_range,
)
from poker.preflop import ALL_CLASSES, CLASS_INDEX, PreflopClass
from poker.spin import PAYOUTS, terminal_equities

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
    hit = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=12)
    assert 12.0 <= hit.utg_open_pct <= 45.0
    assert hit.utg_jam_pct < hit.utg_open_pct * 0.25
    # Częstości z rozkładu strategii i próg testu, nie werdykt produkcyjny.
    assert hit.utg_open[0] + hit.utg_jam[0] > 0.85
    assert hit.utg_open[JUNK_72O] + hit.utg_jam[JUNK_72O] < 0.25


def test_10x_nie_wybucha_open() -> None:
    wta = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=10)
    icm = solve((50, 50, 50), PAYOUTS["10x"].prizes, button=1, iterations=10)
    assert icm.utg_open_pct <= wta.utg_open_pct


def test_threebet_ciasny_nie_artefakt() -> None:
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

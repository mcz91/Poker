"""3-max jam/fold: próg calla i fictitious play na 25 bb."""

from __future__ import annotations

import ast
import functools
import hashlib
import random
from pathlib import Path

import pytest

from poker.icm import icm_equities, wta_equities
from poker.jamfold import (
    N_HANDS,
    N_NODES,
    ROLE_NODES,
    JamFoldSolution,
    _allin_two,
    _best_response,
    _eval_values,
    _exploitability,
    _hand_utility,
    _payoffs,
    _terminal_states,
    _three_way,
    _three_way_ev,
    call_beats_fold,
    exploitability,
    jam_vs_depth,
    one_step_values,
    solve,
)
from poker.preflop import ALL_CLASSES
from poker.spin import DEPTHS, LEVELS, PAYOUTS, roles, terminal_equities

# Porządki rąk 3-way (miejsca od najlepszej ręki) w kolejności terminali 3-way.
ORDERS = ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0))


def test_call_beats_fold_wta_25bb() -> None:
    # BB fold vs UTG jam: 48/150 * 3 = 0.96; win 101/150*3; lose 0.
    fold_ev = 48 / 150 * 3
    win_ev = 101 / 150 * 3
    assert call_beats_fold(0.50, fold_ev, win_ev, 0.0)
    assert not call_beats_fold(0.40, fold_ev, win_ev, 0.0)


def test_call_beats_fold_odrzuca_equity_poza_zakresem() -> None:
    with pytest.raises(ValueError, match="equity"):
        call_beats_fold(1.1, 1.0, 2.0, 0.0)


def test_wta_25bb_aa_jamuje_72o_folduje() -> None:
    result = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=20)
    junk = next(
        i
        for i, cls in enumerate(ALL_CLASSES)
        if cls.high.name == "SEVEN" and cls.low.name == "TWO" and not cls.suited
    )
    assert result.aa_jams is True
    assert result.junk_folds is True
    assert result.utg_jam[0] > 0.85
    assert result.utg_jam[junk] < 0.25


def test_wta_25bb_zakresy_w_pasie_nash() -> None:
    result = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=20)
    assert 10.0 <= result.utg_jam_pct <= 22.0
    assert 4.0 <= result.btn_call_pct <= 14.0
    assert 5.0 <= result.bb_call_pct <= 16.0
    assert result.btn_call_pct < result.utg_jam_pct
    assert result.bb_call_pct < result.utg_jam_pct


def test_icm_10x_zaciska_call_wzgledem_wta() -> None:
    wta = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=20)
    icm = solve((50, 50, 50), PAYOUTS["10x"].prizes, button=1, iterations=20)
    assert icm.btn_call_pct < wta.btn_call_pct
    assert icm.bb_call_pct < wta.bb_call_pct


def test_solve_jest_deterministyczny() -> None:
    a = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=8)
    b = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=8)
    assert a.utg_jam == b.utg_jam
    assert a.btn_call == b.btn_call


def test_jamfold_importuje_tylko_icm_spin_preflop() -> None:
    path = Path(__file__).resolve().parent.parent / "src" / "poker" / "jamfold.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
    poker = {name for name in names if name.startswith("poker")}
    assert poker <= {
        "poker.icm",
        "poker.preflop",
        "poker.preflop_equity",
        "poker.spin",
    }
    assert "poker.betting" not in poker
    assert "poker.table" not in poker
    assert "poker.strategy_table" not in poker


def test_wta_one_step_rowne_cash_out() -> None:
    stacks = (70, 50, 30)
    prizes = PAYOUTS["3x"].prizes
    result = solve(stacks, prizes, button=1, iterations=16)
    assert result.values == pytest.approx(wta_equities(stacks, 3.0), abs=0.05)
    assert result.values == pytest.approx(result.icm, abs=0.05)


def test_icm_10x_one_step_rozjezdza_sie_przy_nierownych() -> None:
    stacks = (16, 50, 84)
    prizes = PAYOUTS["10x"].prizes
    values = one_step_values(stacks, prizes, button=1, iterations=16)
    cash = icm_equities(stacks, prizes)
    assert max(abs(values[i] - cash[i]) for i in range(3)) > 0.01


def test_kazdy_stan_terminalny_solve_zachowuje_sume_zetonow() -> None:
    """Niezmiennik sumy żetonów zamiast tożsamości sum(values)==sum(prizes),
    która zachodzi z konstrukcji wektorów ICM i niczego nie chroni."""
    for stacks in ((50, 50, 50), (16, 50, 84), (12, 12, 12), (70, 50, 30)):
        for sb, bb in ((1, 2), (4, 8)):
            for state in _terminal_states(stacks, 1, sb, bb):
                assert sum(state) == sum(stacks), (stacks, sb, bb, state)
                assert all(s >= 0 for s in state)


def test_terminal_shove_utg_call_btn_spasowany_bb_traci_blind() -> None:
    """Terminal „UTG shove, call BTN, wygrywa BTN" przy BTN all-in z samego SB.

    BB pasuje blind 2: pula główna 3 dla BTN, a drugi żeton blinda należy do
    UTG, jedynego uprawnionego do side potu (finding B3 audytu 09-26).
    """
    states = _terminal_states((50, 1, 50), 1, 1, 2)
    assert states[6] == (50, 3, 48)


# sha256 repr() listy terminali poniższej siatki w układzie sprzed POKER-84
# (9 terminali bez 3-way i stan 3-way dla zwycięzcy 0, 1, 2 — pierwszy porządek
# z tym zwycięzcą), policzony na bazie POKER-71 (de0f9cb, rangi przegranego także
# dla spasowanych).
EQUAL_STACK_TERMINALS_SHA256 = "c503e5766458e24147ff762796cac65f867c1a6235a0ce04b2cadc9c51ba2185"


def test_terminale_przy_rownych_stackach_bez_zmian() -> None:
    """Rangi spasowanych i drugie miejsce 3-way nie ruszają terminali przy równych stackach.

    Przy równych stackach spasowany wkłada najwyżej blind, a zwycięzca all-in
    cały stack, więc zwycięzca jest uprawniony do każdej warstwy puli i ranga
    spasowanego niczego nie rozstrzyga; w 3-way wszyscy wkładają tyle samo, więc
    oba porządki drugiego miejsca dają ten sam stan. Siatka DEPTHS × LEVELS ×
    guzik obejmuje stany narzędzi eksportu (50/50/50 na całym zegarze)
    i `jam_vs_depth`.
    """
    grid = []
    for _, stacks in DEPTHS:
        for sb, bb in LEVELS:
            for button in range(3):
                states = _terminal_states(stacks, button, sb, bb)
                for winner in range(3):
                    assert states[9 + 2 * winner] == states[10 + 2 * winner]
                grid.append(states[:9] + (states[9], states[11], states[13]))
    assert len(grid) == 84
    digest = hashlib.sha256(repr(grid).encode()).hexdigest()
    assert digest == EQUAL_STACK_TERMINALS_SHA256


# sha256 repr() strategii (utg_jam, btn_call, bb_call, btn_open, bb_vs_btn) i repr()
# values solve((50, 50, 50), guzik 1, 8 iteracji), policzone na bazie POKER-84
# (124d903, 3-way bez drugiego miejsca).
EQUAL_STACK_SOLVE_SHA256 = (
    (
        "3x",
        1,
        2,
        "ee205db2ddaf0207d20e00ce48acbef1d0b22f8f5ccf609a38316a4ca28d7217",
        "c594ad8cc385b54edb8b1ce70e17d0989e22815ed7823ebe5aed8b55ad6a0ed7",
    ),
    (
        "10x",
        4,
        8,
        "4c5379b77d53279c6c4e8632e3bff539e97a53dac184d178e0439015c4d31817",
        "105c0ee2642b13deb2e1744db9e8806bd9df2efac9d9db76f83472ea74ac93a0",
    ),
)


def test_strategie_i_values_przy_rownych_stackach_bez_zmian() -> None:
    """Drugie miejsce 3-way niczego nie rozstrzyga przy równych stackach (jedna pula),
    więc strategie i values solve zostają tam bitowo te same — pin na stanach
    książek areny (3x 1/2 i 10x 4/8, 50/50/50)."""
    for pay_id, sb, bb, strategies_sha, values_sha in EQUAL_STACK_SOLVE_SHA256:
        result = solve(
            (50, 50, 50), PAYOUTS[pay_id].prizes, button=1, iterations=8, sb=sb, bb_amt=bb
        )
        strategies = (
            result.utg_jam,
            result.btn_call,
            result.bb_call,
            result.btn_open,
            result.bb_vs_btn,
        )
        assert hashlib.sha256(repr(strategies).encode()).hexdigest() == strategies_sha
        assert hashlib.sha256(repr(result.values).encode()).hexdigest() == values_sha


def test_allin_dwoch_pelne_stacki_sprzed_blindow() -> None:
    """BTN vs BB all-in po foldzie UTG: blindy nie znikają z rozliczenia."""
    assert _allin_two((50, 50, 50), 1, 2, 2) == (50, 0, 100)
    assert _allin_two((50, 50, 50), 1, 2, 1) == (50, 100, 0)
    assert _allin_two((16, 50, 84), 1, 2, 1) == (16, 100, 34)
    assert _allin_two((16, 50, 84), 1, 2, 2) == (16, 0, 134)


def test_three_way_wolajacy_wklada_min_stack_shove() -> None:
    """Shove UTG=16: wołający wkładają 16, nie całe stacki."""
    assert _three_way((16, 50, 84), 0, (2, 0, 1)) == (0, 34, 116)
    assert _three_way((16, 50, 84), 0, (1, 0, 2)) == (0, 82, 68)
    assert _three_way((16, 50, 84), 0, (0, 1, 2)) == (48, 34, 68)


def test_three_way_side_pot_wygrywa_lepsza_reka_sposrod_uprawnionych() -> None:
    """Rangi z pełnego porządku rąk: side pot bierze lepsza z uprawnionych rąk.

    Rangi {zwycięzca, reszta} (przed POKER-84) dzieliły side pot po równo między
    przegranych puli głównej: (100, 15, 35) z wygraną miejsca 1 dawało (85, 45, 20),
    stan niebędący wynikiem żadnego rozdania (finding B3 audytu 09-26).
    """
    short = (100, 15, 35)
    assert [_three_way(short, 0, order) for order in ORDERS] == [
        (150, 0, 0),
        (150, 0, 0),
        (105, 45, 0),
        (65, 45, 40),
        (65, 0, 85),
        (65, 0, 85),
    ]
    assert _three_way((70, 50, 30), 0, (2, 0, 1)) == (60, 0, 90)
    assert _three_way((70, 50, 30), 0, (2, 1, 0)) == (20, 40, 90)
    assert _three_way((16, 50, 84), 2, (0, 1, 2)) == (48, 68, 34)
    assert _three_way((16, 50, 84), 2, (0, 2, 1)) == (48, 0, 102)
    states = _terminal_states(short, 1, 1, 2)
    assert len(states) == 15
    assert list(states[9:]) == [_three_way(short, 0, order) for order in ORDERS]


def test_three_way_konczacy_turniej_placi_miejsca_z_terminal_equities() -> None:
    """Wektory $EV porządków 3-way: koniec turnieju regułą miejsc `terminal_equities`.

    UTG (miejsce 0) wygrywa wszystko: wybici w jednej ręce, BB wszedł z 35 > 15,
    więc bierze drugie miejsce niezależnie od porządku ich rąk.
    """
    stacks = (100, 15, 35)
    prizes = PAYOUTS["10x"].prizes
    pay = _payoffs(stacks, prizes, 1, 1, 2)
    assert (pay.utg, pay.btn, pay.bb) == (0, 1, 2)
    expected = (
        (8.0, 0.0, 2.0),
        (8.0, 0.0, 2.0),
        (6.2, 3.8, 0.0),
        icm_equities((65, 45, 40), prizes),
        (4.6, 0.0, 5.4),
        (4.6, 0.0, 5.4),
    )
    assert len(pay.tw) == len(expected)
    for got, want in zip(pay.tw, expected, strict=True):
        assert got == pytest.approx(want, abs=1e-12)


def test_three_way_ev_drugie_miejsce_z_equity_pary_pozostalych() -> None:
    """$EV 3-way = Σ po porządkach P(porządek)·$EV stanu porządku.

    P(x pierwsze) — iloczyn equity par znormalizowany; P(y drugie | x pierwsze) =
    P(y wygrywa z z). Przy P(U>B) = 0,6, P(U>C) = 0,7, P(B>C) = 0,55 porządki mają
    (0,231; 0,189; 0,154; 0,066; 0,081; 0,054) / 0,775.
    """
    stacks = (100, 15, 35)
    prizes = PAYOUTS["10x"].prizes
    pay = _payoffs(stacks, prizes, 1, 1, 2)
    got = _three_way_ev(pay.tw, (0, 1, 2), 0.6, 0.7, 0.55)
    weights = (0.231, 0.189, 0.154, 0.066, 0.081, 0.054)
    expected = [0.0, 0.0, 0.0]
    for order, weight in zip(ORDERS, weights, strict=True):
        state = terminal_equities(stacks, _three_way(stacks, 0, order), prizes)
        for seat in range(3):
            expected[seat] += weight / 0.775 * state[seat]
    assert got == pytest.approx(expected, abs=1e-12)
    assert got == pytest.approx((6.722470, 1.017139, 2.260391), abs=1e-6)


@functools.cache
def _side_pot_solution(sb: int, bb: int) -> JamFoldSolution:
    """(20, 50, 80), 3x, guzik 0, 16 iteracji: UTG 80, BTN 20, BB 50 — 3-way z side
    potem UTG–BB. Jeden solve na blindy dla kilku testów (solve jest deterministyczny)."""
    return solve((20, 50, 80), PAYOUTS["3x"].prizes, button=0, iterations=16, sb=sb, bb_amt=bb)


def test_drugie_miejsce_3way_dziala_w_solve() -> None:
    """(20, 50, 80), guzik 0, 8/16: 3-way z side potem UTG–BB.

    Side pot dzielony po równo między przegranych puli głównej (przed POKER-84)
    dawał BTN call 85,2%; lepsza ręka spośród uprawnionych — 92,3%.
    """
    assert _side_pot_solution(8, 16).btn_call_pct >= 90.0


def test_three_way_10x_z_rownych_stackow_dzieli_drugie_i_trzecie_miejsce() -> None:
    """3-way all-in z 50/50/50 kończy turniej: dwaj przegrani mieli równe stacki
    wejściowe, więc dzielą nagrody 2. i 3. miejsca — przed POKER-70 ICM dawał
    drugie miejsce niższemu indeksowi (finding I-21 audytu 09-26)."""
    stacks = (50, 50, 50)
    pay = _payoffs(stacks, PAYOUTS["10x"].prizes, 1, 1, 2)
    ends = [_three_way(stacks, pay.utg, order) for order in ORDERS]
    assert ends == [(150, 0, 0)] * 2 + [(0, 150, 0)] * 2 + [(0, 0, 150)] * 2
    assert pay.tw == ((8.0, 1.0, 1.0),) * 2 + ((1.0, 8.0, 1.0),) * 2 + ((1.0, 1.0, 8.0),) * 2


def test_three_way_10x_drugie_miejsce_bierze_wiekszy_stack_wejsciowy() -> None:
    """UTG 70 pokrywa obu wołających i wygrywa 3-way: BB wszedł w rękę z 50,
    BTN z 30, więc drugie miejsce bierze BB, choć ma wyższy indeks miejsca.
    Podział jak przy równych stackach dałby (8, 1, 1), ICM z indeksem sprzed
    POKER-70 — (8, 2, 0)."""
    stacks = (70, 30, 50)
    pay = _payoffs(stacks, PAYOUTS["10x"].prizes, 1, 1, 2)
    assert (pay.utg, pay.btn, pay.bb) == (0, 1, 2)
    for order in ORDERS[:2]:
        assert _three_way(stacks, pay.utg, order) == (150, 0, 0)
    assert pay.tw[:2] == ((8.0, 0.0, 2.0),) * 2


def test_stany_terminalne_zachowuja_sume_zetonow() -> None:
    for stacks in ((16, 50, 84), (50, 50, 50), (12, 12, 12), (100, 15, 35)):
        total = sum(stacks)
        for shover in range(3):
            for order in ORDERS:
                state = _three_way(stacks, shover, order)
                assert sum(state) == total, (stacks, shover, order, state)
                assert all(s >= 0 for s in state)
        for winner in (1, 2):
            assert sum(_allin_two(stacks, 1, 2, winner)) == total


def test_jam_vs_depth_rosnie() -> None:
    rows = jam_vs_depth(PAYOUTS["3x"].prizes, button=1, iterations=12)
    assert [row[0] for row in rows] == [25, 15, 10, 6]
    assert rows[-1][1] > rows[0][1] + 5.0


def test_wyzszy_blind_szerzej_jamuje() -> None:
    deep = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=12)
    mid = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=12, sb=2, bb_amt=4)
    assert mid.utg_jam_pct > deep.utg_jam_pct + 4.0


def test_wyzszy_blind_szerzej_jamuje_caly_zegar() -> None:
    """Monotoniczność przez pełny zegar 1/2 → 10/20 przy stackach 50.

    Odwrócenie na 8/16 i 10/20 raportowane w audycie 2026-08-28
    (30.3 → 23.8 → 20.1) odtwarza się tylko na kodzie sprzed naprawy
    _allin_two — było artefaktem gubienia blindów, nie własnością modelu.
    """
    pcts = [
        solve(
            (50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=8, sb=sb, bb_amt=bb
        ).utg_jam_pct
        for sb, bb in LEVELS
    ]
    assert pcts == sorted(pcts)
    assert pcts[-1] > pcts[0] + 20.0


def test_10x_zaciska_wzgledem_wta_na_starcie() -> None:
    wta = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=12)
    icm = solve((50, 50, 50), PAYOUTS["10x"].prizes, button=1, iterations=12)
    assert icm.btn_call_pct < wta.btn_call_pct


def test_wiecej_iteracji_sciska_exploitability() -> None:
    loose = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=2)
    tight = solve((50, 50, 50), PAYOUTS["3x"].prizes, button=1, iterations=16)
    assert tight.exploitability < loose.exploitability
    assert tight.exploitability < 0.01
    assert min(tight.epsilon) >= -1e-6


def _profile(result: JamFoldSolution) -> list[list[float]]:
    """Profil końcowy fictitious play w kolejności węzłów modułu."""
    rows = (
        result.utg_jam,
        result.btn_call,
        result.bb_call,
        result.bb_vs_both,
        result.btn_open,
        result.bb_vs_btn,
    )
    return [list(row) for row in rows]


def _replace_nodes(
    sigma: list[list[float]], nodes: tuple[int, ...], rows: list[list[float]]
) -> list[list[float]]:
    out = [list(row) for row in sigma]
    for node in nodes:
        out[node] = list(rows[node])
    return out


def test_funkcja_per_reka_liniowa_we_wlasnej_strategii_a_br_jej_argmaxem() -> None:
    """u_i^ręka jest liniowa we własnej strategii miejsca i, a best response jest jej
    argmaxem — dlatego ε liczone tą funkcją jest nieujemne.

    Profil losowy (Random(0), węzły 0…5 × ręce 0…168). Łączna wycena zakres–zakres,
    którą ε liczono przed POKER-84, ma tu defekt liniowości 4,7e−4 i 3,4e−5, więc
    best response nie był argmaxem mierzonej wartości (finding I-27).
    """
    rng = random.Random(0)
    sigma = [[rng.random() for _ in range(N_HANDS)] for _ in range(N_NODES)]
    for stacks, button, sb, bb in (((50, 50, 50), 1, 1, 2), ((20, 50, 80), 0, 8, 16)):
        pay = _payoffs(stacks, PAYOUTS["3x"].prizes, button, sb, bb)
        reply = _best_response(sigma, pay)
        half = [
            [0.5 * own + 0.5 * best for own, best in zip(sigma[node], reply[node], strict=True)]
            for node in range(N_NODES)
        ]
        value = _hand_utility(sigma, pay)
        for seat, nodes in zip(roles(button), ROLE_NODES, strict=True):
            deviated = _hand_utility(_replace_nodes(sigma, nodes, reply), pay)[seat]
            mixed = _hand_utility(_replace_nodes(sigma, nodes, half), pay)[seat]
            assert abs(mixed - 0.5 * value[seat] - 0.5 * deviated) <= 1e-12, (stacks, seat)
            assert deviated - value[seat] >= 0.0, (stacks, seat)


def test_epsilon_i_values_solve_z_funkcji_modulu() -> None:
    """ε z solve = zysk best response w funkcji per ręka (≥ 0), values = łączna wycena
    zakres–zakres, a te wyceny się różnią — ε nie jest różnicą values.

    (20, 50, 80), guzik 0: przed POKER-84 ε liczone różnicą czterech wycen
    zakres–zakres było ujemne — min −5,9e−5 (8/16) i −5,1e−5 (10/20).
    """
    result = _side_pot_solution(8, 16)
    pay = _payoffs((20, 50, 80), PAYOUTS["3x"].prizes, 0, 8, 16)
    final = _profile(result)
    assert result.values == pytest.approx(_eval_values(final, pay), abs=1e-12)
    value = _hand_utility(final, pay)
    reply = _best_response(final, pay)
    for seat, nodes in zip(roles(0), ROLE_NODES, strict=True):
        deviated = _hand_utility(_replace_nodes(final, nodes, reply), pay)[seat]
        assert result.epsilon[seat] == pytest.approx(deviated - value[seat], abs=1e-12)
    assert max(abs(value[seat] - result.values[seat]) for seat in range(3)) >= 1e-3
    assert min(result.epsilon) >= -1e-12
    assert min(_side_pot_solution(10, 20).epsilon) >= -1e-12


def test_exploitability_publiczne_api() -> None:
    hit = exploitability((50, 50, 50), PAYOUTS["3x"].prizes, iterations=12)
    assert hit.max_gain < 0.02
    assert hit.iterations == 12


def test_epsilon_odroznia_smieci_od_nasha() -> None:
    """ε≈0 nic nie znaczy bez mianownika. Always-jam wycieka ~0.147 BI."""
    stacks = (50, 50, 50)
    prizes = PAYOUTS["3x"].prizes
    pay = _payoffs(stacks, prizes, 1, 1, 2)
    junk = [[1.0] * N_HANDS for _ in range(N_NODES)]
    nash = solve(stacks, prizes, button=1, iterations=16)
    junk_eps = max(_exploitability(junk, pay))
    assert junk_eps > 0.1
    assert nash.exploitability * 20 < junk_eps

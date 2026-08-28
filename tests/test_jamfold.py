"""3-max jam/fold: próg calla i fictitious play na 25 bb."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from poker.icm import icm_equities, wta_equities
from poker.jamfold import (
    _allin_two,
    _terminal_states,
    _three_way,
    call_beats_fold,
    exploitability,
    jam_vs_depth,
    one_step_values,
    solve,
)
from poker.preflop import ALL_CLASSES
from poker.spin import LEVELS, PAYOUTS


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


def test_allin_dwoch_pelne_stacki_sprzed_blindow() -> None:
    """BTN vs BB all-in po foldzie UTG: blindy nie znikają z rozliczenia."""
    assert _allin_two((50, 50, 50), 1, 2, 2) == (50, 0, 100)
    assert _allin_two((50, 50, 50), 1, 2, 1) == (50, 100, 0)
    assert _allin_two((16, 50, 84), 1, 2, 1) == (16, 100, 34)
    assert _allin_two((16, 50, 84), 1, 2, 2) == (16, 0, 134)


def test_three_way_wolajacy_wklada_min_stack_shove() -> None:
    """Shove UTG=16: wołający wkładają 16, nie całe stacki."""
    assert _three_way((16, 50, 84), 0, 2) == (0, 34, 116)
    assert _three_way((16, 50, 84), 0, 1) == (0, 82, 68)
    assert _three_way((16, 50, 84), 0, 0) == (48, 34, 68)


def test_stany_terminalne_zachowuja_sume_zetonow() -> None:
    for stacks in ((16, 50, 84), (50, 50, 50), (12, 12, 12)):
        total = sum(stacks)
        for winner in range(3):
            assert sum(_three_way(stacks, 0, winner)) == total
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


def test_exploitability_publiczne_api() -> None:
    hit = exploitability((50, 50, 50), PAYOUTS["3x"].prizes, iterations=12)
    assert hit.max_gain < 0.02
    assert hit.iterations == 12


def test_epsilon_odroznia_smieci_od_nasha() -> None:
    """ε≈0 nic nie znaczy bez mianownika. Always-jam wycieka ~0.18 BI."""
    from poker.icm import icm_equities
    from poker.jamfold import (
        N_HANDS,
        N_NODES,
        _exploitability,
        _Payoffs,
        _take,
    )
    from poker.spin import post_blinds, roles, utg_shove_both_fold, utg_shove_called

    stacks = (50, 50, 50)
    prizes = PAYOUTS["3x"].prizes
    utg, btn, bb = roles(1)
    behind, pot = post_blinds(stacks, 1, 1, 2)
    blinds = utg_shove_both_fold(stacks, 1, 1, 2)

    def money(state: tuple[int, int, int]) -> tuple[float, ...]:
        return icm_equities(state, prizes)

    pay = _Payoffs(
        utg=utg,
        btn=btn,
        bb=bb,
        utg_b=money(blinds),
        btn_b=money(_take(behind, btn, pot)),
        bb_b=money(_take(behind, bb, pot)),
        hu_utg_bb=(
            money(utg_shove_called(stacks, 1, bb, utg, 1, 2)),
            money(utg_shove_called(stacks, 1, bb, bb, 1, 2)),
        ),
        hu_utg_btn=(
            money(utg_shove_called(stacks, 1, btn, utg, 1, 2)),
            money(utg_shove_called(stacks, 1, btn, btn, 1, 2)),
        ),
        hu_btn_bb=(
            money(_allin_two(stacks, btn, bb, btn)),
            money(_allin_two(stacks, btn, bb, bb)),
        ),
        tw=tuple(money(_three_way(stacks, utg, w)) for w in range(3)),
    )
    junk = [[1.0] * N_HANDS for _ in range(N_NODES)]
    nash = solve(stacks, prizes, button=1, iterations=16)
    junk_eps = max(_exploitability(junk, pay))
    assert junk_eps > 0.1
    assert nash.exploitability * 20 < junk_eps

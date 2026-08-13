"""3-max jam/fold: fictitious play na jednym stanie stacków.

Wewnętrzna gra Ganzfried & Sandholm, AAMAS 2008. Equity HU z macierzy
preflop (POKER-12). 3-way: para znormalizowana. Bez blockerów.
"""

from __future__ import annotations

from poker.icm import icm_equities
from poker.preflop import ALL_CLASSES, CLASS_INDEX
from poker.preflop_equity import equity as class_equity
from poker.spin import (
    BIG_BLIND,
    DEPTHS,
    SMALL_BLIND,
    award_allin,
    post_blinds,
    roles,
    utg_shove_both_fold,
    utg_shove_called,
)

N_HANDS = len(ALL_CLASSES)
UTG_OPEN, BTN_VS_UTG, BB_VS_UTG, BB_VS_BOTH, BTN_OPEN, BB_VS_BTN = range(6)
N_NODES = 6

WEIGHTS: tuple[int, ...] = tuple(
    6 if cls.high == cls.low else (4 if cls.suited else 12) for cls in ALL_CLASSES
)


def _hu(i: int, j: int) -> float:
    return class_equity(ALL_CLASSES[i], ALL_CLASSES[j])


def _mass(sigma: list[float]) -> float:
    num = sum(WEIGHTS[i] * sigma[i] for i in range(N_HANDS))
    den = sum(WEIGHTS)
    return num / den


def _eq_vs(h: int, sigma: list[float]) -> float:
    num = 0.0
    den = 0.0
    for i in range(N_HANDS):
        w = WEIGHTS[i] * sigma[i]
        if w == 0:
            continue
        num += w * _hu(h, i)
        den += w
    return 0.5 if den == 0 else num / den


def _eq_ranges(a: list[float], b: list[float]) -> float:
    num = 0.0
    den = 0.0
    for i in range(N_HANDS):
        wa = WEIGHTS[i] * a[i]
        if wa == 0:
            continue
        for j in range(N_HANDS):
            wb = WEIGHTS[j] * b[j]
            if wb == 0:
                continue
            num += wa * wb * _hu(i, j)
            den += wa * wb
    return 0.5 if den == 0 else num / den


def _norm3(a: float, b: float, c: float) -> tuple[float, float, float]:
    total = a + b + c
    if total <= 0:
        return (1 / 3, 1 / 3, 1 / 3)
    return (a / total, b / total, c / total)


def _mix(e: float, win: float, lose: float) -> float:
    return e * win + (1.0 - e) * lose


def _take(behind: tuple[int, int, int], seat: int, pot: int) -> tuple[int, int, int]:
    out = list(behind)
    out[seat] += pot
    return (out[0], out[1], out[2])


def _allin_two(
    behind: tuple[int, int, int], a: int, b: int, winner: int
) -> tuple[int, int, int]:
    contrib = [0, 0, 0]
    contrib[a] = behind[a]
    contrib[b] = behind[b]
    ranks = [2, 2, 2]
    ranks[winner] = 0
    awarded = award_allin((contrib[0], contrib[1], contrib[2]), (ranks[0], ranks[1], ranks[2]))
    return (
        behind[0] - contrib[0] + awarded[0],
        behind[1] - contrib[1] + awarded[1],
        behind[2] - contrib[2] + awarded[2],
    )


def _three_way(stacks: tuple[int, int, int], winner: int) -> tuple[int, int, int]:
    ranks = [1, 1, 1]
    ranks[winner] = 0
    awarded = award_allin(stacks, (ranks[0], ranks[1], ranks[2]))
    return (awarded[0], awarded[1], awarded[2])


def call_beats_fold(equity: float, fold_ev: float, win_ev: float, lose_ev: float) -> bool:
    """Wołający: e·win + (1−e)·lose > fold. e to equity wołającego, nie shovera."""
    if not 0.0 <= equity <= 1.0:
        raise ValueError(f"equity poza [0, 1]: {equity}")
    return equity * win_ev + (1.0 - equity) * lose_ev > fold_ev


def solve(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int = 1,
    iterations: int = 80,
    sb: int = SMALL_BLIND,
    bb_amt: int = BIG_BLIND,
) -> dict[str, object]:
    """Zwraca średnie strategie fictitious play (jam/call ∈ [0, 1] per klasa)."""
    if iterations < 1:
        raise ValueError("iteracje muszą być dodatnie")
    utg, btn, bb = roles(button)
    behind, pot = post_blinds(stacks, button, sb, bb_amt)
    blinds = utg_shove_both_fold(stacks, button, sb, bb_amt)
    btn_blinds = _take(behind, btn, pot)
    bb_blinds = _take(behind, bb, pot)

    def money(state: tuple[int, int, int]) -> tuple[float, ...]:
        return icm_equities(state, prizes)

    utg_b = money(blinds)
    btn_b = money(btn_blinds)
    bb_b = money(bb_blinds)
    hu_utg_bb = (
        money(utg_shove_called(stacks, button, bb, utg, sb, bb_amt)),
        money(utg_shove_called(stacks, button, bb, bb, sb, bb_amt)),
    )
    hu_utg_btn = (
        money(utg_shove_called(stacks, button, btn, utg, sb, bb_amt)),
        money(utg_shove_called(stacks, button, btn, btn, sb, bb_amt)),
    )
    hu_btn_bb = (
        money(_allin_two(behind, btn, bb, btn)),
        money(_allin_two(behind, btn, bb, bb)),
    )
    tw = tuple(money(_three_way(stacks, w)) for w in range(3))

    pay = {
        "utg": utg,
        "btn": btn,
        "bb": bb,
        "utg_b": utg_b,
        "btn_b": btn_b,
        "bb_b": bb_b,
        "hu_utg_bb": hu_utg_bb,
        "hu_utg_btn": hu_utg_btn,
        "hu_btn_bb": hu_btn_bb,
        "tw": tw,
    }

    cum = [[0.0] * N_HANDS for _ in range(N_NODES)]
    weight_sum = 0.0

    def avg(_done: int) -> list[list[float]]:
        if weight_sum == 0:
            return [[0.5] * N_HANDS for _ in range(N_NODES)]
        return [[cum[n][i] / weight_sum for i in range(N_HANDS)] for n in range(N_NODES)]

    for done in range(iterations):
        reply = _best_response(avg(done), pay)
        weight = float(done + 1)
        for node in range(N_NODES):
            for i in range(N_HANDS):
                cum[node][i] += weight * reply[node][i]
        weight_sum += weight

    final = avg(iterations)
    values = _eval_values(final, pay)
    cash = icm_equities(stacks, prizes)
    expl = _exploitability(final, pay)

    def pct(sigma: list[float]) -> float:
        return 100.0 * _mass(sigma)

    aa = CLASS_INDEX[ALL_CLASSES[0]]
    junk = next(
        i
        for i, cls in enumerate(ALL_CLASSES)
        if cls.high.name == "SEVEN" and cls.low.name == "TWO" and not cls.suited
    )
    return {
        "iterations": iterations,
        "utg_jam": final[UTG_OPEN],
        "btn_call": final[BTN_VS_UTG],
        "bb_call": final[BB_VS_UTG],
        "btn_open": final[BTN_OPEN],
        "bb_vs_btn": final[BB_VS_BTN],
        "utg_jam_pct": pct(final[UTG_OPEN]),
        "btn_call_pct": pct(final[BTN_VS_UTG]),
        "bb_call_pct": pct(final[BB_VS_UTG]),
        "aa_jams": final[UTG_OPEN][aa] > 0.85,
        "junk_folds": final[UTG_OPEN][junk] < 0.25,
        "values": values,
        "icm": cash,
        "epsilon": expl["epsilon"],
        "exploitability": expl["max"],
    }


def one_step_values(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int = 1,
    iterations: int = 20,
) -> tuple[float, float, float]:
    """Pierwszy backup zewnętrzny: E[ICM(s′)] przy Nash jam/fold."""
    result = solve(stacks, prizes, button, iterations)
    values = result["values"]
    assert isinstance(values, tuple)
    return values


def _eval_values(sigma: list[list[float]], pay: dict[str, object]) -> tuple[float, float, float]:
    utg = int(pay["utg"])  # type: ignore[arg-type]
    btn = int(pay["btn"])  # type: ignore[arg-type]
    bb = int(pay["bb"])  # type: ignore[arg-type]
    utg_r, btn_c, bb_utg, bb_both, btn_o, bb_btn = sigma
    p_jam = _mass(utg_r)
    p_btn_c = _mass(btn_c)
    p_bb_utg = _mass(bb_utg)
    p_bb_both = _mass(bb_both)
    p_btn_o = _mass(btn_o)
    p_bb_btn = _mass(bb_btn)
    e_utg_bb = _eq_ranges(utg_r, bb_utg)
    e_utg_btn = _eq_ranges(utg_r, btn_c)
    e_utg_both = _eq_ranges(utg_r, bb_both)
    e_call_both = _eq_ranges(btn_c, bb_both)
    e_btn_bb = _eq_ranges(btn_o, bb_btn)
    p3_u, p3_b, p3_c = _norm3(
        e_utg_btn * e_utg_both,
        (1 - e_utg_btn) * e_call_both,
        (1 - e_utg_both) * (1 - e_call_both),
    )
    utg_b = pay["utg_b"]
    btn_b = pay["btn_b"]
    bb_b = pay["bb_b"]
    hu_utg_bb = pay["hu_utg_bb"]
    hu_utg_btn = pay["hu_utg_btn"]
    hu_btn_bb = pay["hu_btn_bb"]
    tw = pay["tw"]
    assert isinstance(utg_b, tuple) and isinstance(btn_b, tuple) and isinstance(bb_b, tuple)
    assert isinstance(hu_utg_bb, tuple) and isinstance(hu_utg_btn, tuple)
    assert isinstance(hu_btn_bb, tuple) and isinstance(tw, tuple)

    acc = [0.0, 0.0, 0.0]

    def add(weight: float, vec: tuple[float, ...]) -> None:
        for i in range(3):
            acc[i] += weight * vec[i]

    def mix_vec(equity: float, win: tuple[float, ...], lose: tuple[float, ...]) -> tuple[float, ...]:
        return (
            equity * win[0] + (1 - equity) * lose[0],
            equity * win[1] + (1 - equity) * lose[1],
            equity * win[2] + (1 - equity) * lose[2],
        )

    add((1 - p_jam) * (1 - p_btn_o), bb_b)
    add((1 - p_jam) * p_btn_o * (1 - p_bb_btn), btn_b)
    add((1 - p_jam) * p_btn_o * p_bb_btn, mix_vec(e_btn_bb, hu_btn_bb[0], hu_btn_bb[1]))
    add(p_jam * (1 - p_btn_c) * (1 - p_bb_utg), utg_b)
    add(p_jam * (1 - p_btn_c) * p_bb_utg, mix_vec(e_utg_bb, hu_utg_bb[0], hu_utg_bb[1]))
    add(p_jam * p_btn_c * (1 - p_bb_both), mix_vec(e_utg_btn, hu_utg_btn[0], hu_utg_btn[1]))
    tw_mix = tuple(
        p3_u * tw[utg][i] + p3_b * tw[btn][i] + p3_c * tw[bb][i] for i in range(3)
    )
    add(p_jam * p_btn_c * p_bb_both, tw_mix)
    return (acc[0], acc[1], acc[2])


def _best_response(sigma: list[list[float]], pay: dict[str, object]) -> list[list[float]]:
    utg = int(pay["utg"])  # type: ignore[arg-type]
    btn = int(pay["btn"])  # type: ignore[arg-type]
    bb = int(pay["bb"])  # type: ignore[arg-type]
    utg_b = pay["utg_b"]
    btn_b = pay["btn_b"]
    bb_b = pay["bb_b"]
    hu_utg_bb = pay["hu_utg_bb"]
    hu_utg_btn = pay["hu_utg_btn"]
    hu_btn_bb = pay["hu_btn_bb"]
    tw = pay["tw"]
    assert isinstance(utg_b, tuple) and isinstance(btn_b, tuple) and isinstance(bb_b, tuple)
    assert isinstance(hu_utg_bb, tuple) and isinstance(hu_utg_btn, tuple)
    assert isinstance(hu_btn_bb, tuple) and isinstance(tw, tuple)
    utg_r, btn_c, bb_utg, bb_both, btn_o, bb_btn = sigma
    p_btn_c, p_bb_utg, p_bb_both = _mass(btn_c), _mass(bb_utg), _mass(bb_both)
    p_btn_o, p_bb_btn = _mass(btn_o), _mass(bb_btn)
    e_utg_bb = _eq_ranges(utg_r, bb_utg)
    e_utg_btn = _eq_ranges(utg_r, btn_c)
    e_call_both = _eq_ranges(btn_c, bb_both)
    e_utg_both = _eq_ranges(utg_r, bb_both)
    e_btn_bb = _eq_ranges(btn_o, bb_btn)
    fold_utg = (
        (1 - p_btn_o) * bb_b[utg]
        + p_btn_o * (1 - p_bb_btn) * btn_b[utg]
        + p_btn_o * p_bb_btn * _mix(e_btn_bb, hu_btn_bb[0][utg], hu_btn_bb[1][utg])
    )
    out = [[0.0] * N_HANDS for _ in range(N_NODES)]
    for h in range(N_HANDS):
        e_h_bb = _eq_vs(h, bb_utg)
        e_h_btn = _eq_vs(h, btn_c)
        e_h_both = _eq_vs(h, bb_both)
        p_h, p_btn, p_bb = _norm3(
            e_h_btn * e_h_both,
            (1 - e_h_btn) * e_call_both,
            (1 - e_h_both) * (1 - e_call_both),
        )
        jam_utg = (
            (1 - p_btn_c) * (1 - p_bb_utg) * utg_b[utg]
            + (1 - p_btn_c) * p_bb_utg * _mix(e_h_bb, hu_utg_bb[0][utg], hu_utg_bb[1][utg])
            + p_btn_c * (1 - p_bb_both) * _mix(e_h_btn, hu_utg_btn[0][utg], hu_utg_btn[1][utg])
            + p_btn_c * p_bb_both * (p_h * tw[utg][utg] + p_btn * tw[btn][utg] + p_bb * tw[bb][utg])
        )
        out[UTG_OPEN][h] = 1.0 if jam_utg > fold_utg else 0.0
        e_vs_utg = _eq_vs(h, utg_r)
        fold_btn = (1 - p_bb_utg) * utg_b[btn] + p_bb_utg * _mix(
            e_utg_bb, hu_utg_bb[0][btn], hu_utg_bb[1][btn]
        )
        q_h, q_utg, q_bb = _norm3(
            e_vs_utg * e_h_both,
            (1 - e_vs_utg) * e_utg_both,
            (1 - e_h_both) * (1 - e_utg_both),
        )
        call_btn = (1 - p_bb_both) * _mix(
            e_vs_utg, hu_utg_btn[1][btn], hu_utg_btn[0][btn]
        ) + p_bb_both * (q_h * tw[btn][btn] + q_utg * tw[utg][btn] + q_bb * tw[bb][btn])
        out[BTN_VS_UTG][h] = 1.0 if call_btn > fold_btn else 0.0
        out[BB_VS_UTG][h] = (
            1.0 if _mix(e_vs_utg, hu_utg_bb[1][bb], hu_utg_bb[0][bb]) > utg_b[bb] else 0.0
        )
        fold_both = _mix(e_utg_btn, hu_utg_btn[0][bb], hu_utg_btn[1][bb])
        r_h, r_utg, r_btn = _norm3(
            e_vs_utg * e_h_btn,
            (1 - e_vs_utg) * e_utg_btn,
            (1 - e_h_btn) * (1 - e_utg_btn),
        )
        call_both = r_h * tw[bb][bb] + r_utg * tw[utg][bb] + r_btn * tw[btn][bb]
        out[BB_VS_BOTH][h] = 1.0 if call_both > fold_both else 0.0
        e_vs_bb = _eq_vs(h, bb_btn)
        jam_btn = (1 - p_bb_btn) * btn_b[btn] + p_bb_btn * _mix(
            e_vs_bb, hu_btn_bb[0][btn], hu_btn_bb[1][btn]
        )
        out[BTN_OPEN][h] = 1.0 if jam_btn > bb_b[btn] else 0.0
        e_vs_btn = _eq_vs(h, btn_o)
        out[BB_VS_BTN][h] = (
            1.0 if _mix(e_vs_btn, hu_btn_bb[1][bb], hu_btn_bb[0][bb]) > btn_b[bb] else 0.0
        )
    return out


def _exploitability(sigma: list[list[float]], pay: dict[str, object]) -> dict[str, object]:
    utg = int(pay["utg"])  # type: ignore[arg-type]
    btn = int(pay["btn"])  # type: ignore[arg-type]
    bb = int(pay["bb"])  # type: ignore[arg-type]
    ev = _eval_values(sigma, pay)
    reply = _best_response(sigma, pay)

    def swap(nodes: tuple[int, ...]) -> list[list[float]]:
        out = [list(row) for row in sigma]
        for node in nodes:
            out[node] = reply[node]
        return out

    ev_utg = _eval_values(swap((UTG_OPEN,)), pay)
    ev_btn = _eval_values(swap((BTN_VS_UTG, BTN_OPEN)), pay)
    ev_bb = _eval_values(swap((BB_VS_UTG, BB_VS_BOTH, BB_VS_BTN)), pay)
    seats = [0.0, 0.0, 0.0]
    seats[utg] = ev_utg[utg] - ev[utg]
    seats[btn] = ev_btn[btn] - ev[btn]
    seats[bb] = ev_bb[bb] - ev[bb]
    return {
        "epsilon": (seats[0], seats[1], seats[2]),
        "max": max(seats),
        "sum": sum(seats),
    }


def exploitability(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int = 1,
    iterations: int = 24,
    sb: int = SMALL_BLIND,
    bb_amt: int = BIG_BLIND,
) -> dict[str, object]:
    """Max zysk z odchylenia do BR. Metryka Spina (decyzja 15), w buy-inach."""
    result = solve(stacks, prizes, button, iterations, sb, bb_amt)
    return {
        "epsilon": result["epsilon"],
        "max": result["exploitability"],
        "values": result["values"],
        "iterations": iterations,
    }


def jam_vs_depth(
    prizes: tuple[float, float, float],
    button: int = 1,
    iterations: int = 16,
) -> tuple[tuple[int, float, float, float], ...]:
    """UTG jam % i call % na klasycznym zegarze 25/15/10/6 bb."""
    rows: list[tuple[int, float, float, float]] = []
    for bb, stacks in DEPTHS:
        result = solve(stacks, prizes, button, iterations)
        utg = result["utg_jam_pct"]
        btn = result["btn_call_pct"]
        bb_c = result["bb_call_pct"]
        assert isinstance(utg, float) and isinstance(btn, float) and isinstance(bb_c, float)
        rows.append((bb, utg, btn, bb_c))
    return tuple(rows)

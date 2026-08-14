"""3-max fold / open 2.2x / jam. No flats. Fictitious play, real preflop matrix.

Used above JAM_FOLD_BB. Jam/fold remains the endgame (decyzja 19).
"""

from __future__ import annotations

from poker.icm import icm_equities
from poker.preflop import ALL_CLASSES, CLASS_INDEX
from poker.preflop_equity import equity as class_equity
from poker.spin import (
    BIG_BLIND,
    SMALL_BLIND,
    award_allin,
    open_amount,
    roles,
)

N_HANDS = len(ALL_CLASSES)
# First-in: two exclusive freqs (open, jam); rest fold.
# Facing: one freq (jam or call).
UTG_OPEN, UTG_JAM, BTN_VS_OPEN, BTN_VS_JAM, BB_VS_OPEN, BB_VS_JAM = range(6)
UTG_DEF, BB_VS_OJ, BTN_OPEN, BTN_JAM, BB_VS_BTN_OPEN, BB_VS_BTN_JAM, BTN_DEF = range(6, 13)
N_NODES = 13

WEIGHTS: tuple[int, ...] = tuple(
    6 if cls.high == cls.low else (4 if cls.suited else 12) for cls in ALL_CLASSES
)


def _hu(i: int, j: int) -> float:
    return class_equity(ALL_CLASSES[i], ALL_CLASSES[j])


def _mass(sigma: list[float]) -> float:
    return sum(WEIGHTS[i] * sigma[i] for i in range(N_HANDS)) / sum(WEIGHTS)


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


def _mix(e: float, win: float, lose: float) -> float:
    return e * win + (1.0 - e) * lose


def _blinds(stacks: tuple[int, int, int], button: int, sb: int, bb: int) -> list[int]:
    contrib = [0, 0, 0]
    _, btn, bb_seat = roles(button)
    contrib[btn] = min(stacks[btn], sb)
    contrib[bb_seat] = min(stacks[bb_seat], bb)
    return contrib


def _put(stacks: tuple[int, int, int], contrib: list[int], seat: int, want: int) -> list[int]:
    out = list(contrib)
    out[seat] = min(stacks[seat], max(out[seat], want))
    return out


def _take(stacks: tuple[int, int, int], contrib: list[int], winner: int) -> tuple[int, int, int]:
    pot = contrib[0] + contrib[1] + contrib[2]
    out = [stacks[i] - contrib[i] for i in range(3)]
    out[winner] += pot
    return (out[0], out[1], out[2])


def _sd(stacks: tuple[int, int, int], contrib: list[int], winner: int) -> tuple[int, int, int]:
    ranks = [1, 1, 1]
    ranks[winner] = 0
    awarded = award_allin(
        (contrib[0], contrib[1], contrib[2]), (ranks[0], ranks[1], ranks[2])
    )
    return (
        stacks[0] - contrib[0] + awarded[0],
        stacks[1] - contrib[1] + awarded[1],
        stacks[2] - contrib[2] + awarded[2],
    )


def solve(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int = 1,
    iterations: int = 24,
    sb: int = SMALL_BLIND,
    bb_amt: int = BIG_BLIND,
) -> dict[str, object]:
    if iterations < 1:
        raise ValueError("iteracje muszą być dodatnie")
    utg, btn, bb = roles(button)
    size = open_amount(bb_amt)
    blinds = _blinds(stacks, button, sb, bb_amt)
    opened_utg = _put(stacks, blinds, utg, size)
    opened_btn = _put(stacks, blinds, btn, size)

    def money(state: tuple[int, int, int]) -> tuple[float, ...]:
        return icm_equities(state, prizes)

    fold_both = money(_take(stacks, blinds, bb))
    steal_utg = money(_take(stacks, opened_utg, utg))
    steal_btn = money(_take(stacks, opened_btn, btn))
    jam_utg_fold = money(_take(stacks, _put(stacks, blinds, utg, stacks[utg]), utg))
    jam_btn_fold = money(_take(stacks, _put(stacks, blinds, btn, stacks[btn]), btn))

    def hu(a: int, b: int, base: list[int], w: int) -> tuple[float, ...]:
        c = _put(stacks, _put(stacks, base, a, stacks[a]), b, stacks[b])
        return money(_sd(stacks, c, w))

    hu_uj_b = (hu(utg, btn, blinds, utg), hu(utg, btn, blinds, btn))
    hu_uj_c = (hu(utg, bb, blinds, utg), hu(utg, bb, blinds, bb))
    hu_bj = (hu(btn, bb, blinds, btn), hu(btn, bb, blinds, bb))
    hu_uo_b = (hu(utg, btn, opened_utg, utg), hu(utg, btn, opened_utg, btn))
    hu_uo_c = (hu(utg, bb, opened_utg, utg), hu(utg, bb, opened_utg, bb))
    hu_bo = (hu(btn, bb, opened_btn, btn), hu(btn, bb, opened_btn, bb))

    cum = [[0.0] * N_HANDS for _ in range(N_NODES)]
    weight_sum = 0.0

    def avg() -> list[list[float]]:
        if weight_sum == 0:
            out = [[0.0] * N_HANDS for _ in range(N_NODES)]
            for h in range(N_HANDS):
                out[UTG_OPEN][h] = 0.25
                out[BTN_OPEN][h] = 0.30
            return out
        return [[cum[n][i] / weight_sum for i in range(N_HANDS)] for n in range(N_NODES)]

    def br(sigma: list[list[float]]) -> list[list[float]]:
        p_bvo, p_bvj = _mass(sigma[BTN_VS_OPEN]), _mass(sigma[BTN_VS_JAM])
        p_cvo, p_cvj = _mass(sigma[BB_VS_OPEN]), _mass(sigma[BB_VS_JAM])
        p_oj, p_def = _mass(sigma[BB_VS_OJ]), _mass(sigma[UTG_DEF])
        p_bto, p_btj = _mass(sigma[BTN_OPEN]), _mass(sigma[BTN_JAM])
        p_cbo, p_cbj = _mass(sigma[BB_VS_BTN_OPEN]), _mass(sigma[BB_VS_BTN_JAM])
        p_bdef = _mass(sigma[BTN_DEF])

        # After UTG folds: BTN first-in, then BB.
        ev_utg_fold = (
            (1 - p_bto - p_btj) * fold_both[utg]
            + p_btj * (1 - p_cbj) * jam_btn_fold[utg]
            + p_btj * p_cbj * _mix(0.5, hu_bj[0][utg], hu_bj[1][utg])
            + p_bto * (1 - p_cbo) * steal_btn[utg]
            + p_bto * p_cbo * (1 - p_bdef) * money(_take(stacks, _put(stacks, opened_btn, bb, stacks[bb]), bb))[utg]
            + p_bto * p_cbo * p_bdef * _mix(0.5, hu_bo[0][utg], hu_bo[1][utg])
        )
        ev_btn_after_utg_fold_fold = fold_both[btn]
        ev_bb_after_utg_fold_if_btn_folds = fold_both[bb]

        out = [[0.0] * N_HANDS for _ in range(N_NODES)]
        for h in range(N_HANDS):
            e_bvo = _eq_vs(h, sigma[BTN_VS_OPEN])
            e_cvo = _eq_vs(h, sigma[BB_VS_OPEN])
            e_bvj = _eq_vs(h, sigma[BTN_VS_JAM])
            e_cvj = _eq_vs(h, sigma[BB_VS_JAM])
            e_oj = _eq_vs(h, sigma[BB_VS_OJ])
            e_cbo = _eq_vs(h, sigma[BB_VS_BTN_OPEN])
            e_cbj = _eq_vs(h, sigma[BB_VS_BTN_JAM])

            jam_utg = (
                (1 - p_bvj) * (1 - p_cvj) * jam_utg_fold[utg]
                + (1 - p_bvj) * p_cvj * _mix(e_cvj, hu_uj_c[0][utg], hu_uj_c[1][utg])
                + p_bvj * (1 - p_cvj) * _mix(e_bvj, hu_uj_b[0][utg], hu_uj_b[1][utg])
                + p_bvj * p_cvj * _mix(e_bvj * e_cvj, hu_uj_b[0][utg], hu_uj_c[1][utg])
            )
            def_vs_btn = _mix(e_bvo, hu_uo_b[0][utg], hu_uo_b[1][utg])
            def_vs_bb = _mix(e_cvo, hu_uo_c[0][utg], hu_uo_c[1][utg])
            fold_vs_btn = money(_take(stacks, _put(stacks, opened_utg, btn, stacks[btn]), btn))[utg]
            fold_vs_bb = money(_take(stacks, _put(stacks, opened_utg, bb, stacks[bb]), bb))[utg]
            open_utg = (
                (1 - p_bvo) * (1 - p_cvo) * steal_utg[utg]
                + (1 - p_bvo) * p_cvo * max(def_vs_bb, fold_vs_bb)
                + p_bvo * (1 - p_oj) * max(def_vs_btn, fold_vs_btn)
                + p_bvo * p_oj * max(_mix(e_oj, hu_uo_c[0][utg], hu_uo_c[1][utg]), fold_vs_btn)
            )
            if jam_utg >= open_utg and jam_utg > ev_utg_fold:
                out[UTG_JAM][h] = 1.0
            elif open_utg > ev_utg_fold:
                out[UTG_OPEN][h] = 1.0

            e_vs_utg_o = _eq_vs(h, sigma[UTG_OPEN])
            e_vs_utg_j = _eq_vs(h, sigma[UTG_JAM])
            utg_pot_btn = money(_take(stacks, _put(stacks, opened_utg, btn, stacks[btn]), btn))
            bb_pot_vs_utg = money(_take(stacks, _put(stacks, opened_utg, bb, stacks[bb]), bb))
            fold_btn_vo = (1 - p_cvo) * steal_utg[btn] + p_cvo * (
                (1 - p_def) * bb_pot_vs_utg[btn]
                + p_def * _mix(_eq_vs(h, sigma[UTG_DEF]), hu_uo_c[0][btn], hu_uo_c[1][btn])
            )
            p_cont = max(p_def, 0.45)
            jam_btn_vo = (1 - p_cont) * utg_pot_btn[btn] + p_cont * _mix(
                _eq_vs(h, sigma[UTG_DEF]), hu_uo_b[1][btn], hu_uo_b[0][btn]
            )
            # BB may also call the jam; cheap mix.
            jam_btn_vo = (1 - p_oj) * jam_btn_vo + p_oj * _mix(
                e_oj, hu_uo_c[1][btn], hu_uo_c[0][btn]
            )
            out[BTN_VS_OPEN][h] = 1.0 if jam_btn_vo > fold_btn_vo else 0.0

            fold_btn_vj = (1 - p_cvj) * jam_utg_fold[btn] + p_cvj * _mix(
                e_cvj, hu_uj_c[0][btn], hu_uj_c[1][btn]
            )
            call_btn_vj = _mix(e_vs_utg_j, hu_uj_b[1][btn], hu_uj_b[0][btn])
            out[BTN_VS_JAM][h] = 1.0 if call_btn_vj > fold_btn_vj else 0.0

            jam_bb_vo = (1 - p_cont) * bb_pot_vs_utg[bb] + p_cont * _mix(
                e_vs_utg_o, hu_uo_c[1][bb], hu_uo_c[0][bb]
            )
            out[BB_VS_OPEN][h] = 1.0 if jam_bb_vo > steal_utg[bb] else 0.0
            out[BB_VS_JAM][h] = (
                1.0
                if _mix(e_vs_utg_j, hu_uj_c[1][bb], hu_uj_c[0][bb]) > jam_utg_fold[bb]
                else 0.0
            )
            out[BB_VS_OJ][h] = (
                1.0
                if _mix(_eq_vs(h, sigma[BTN_VS_OPEN]), hu_uo_b[1][bb], hu_uo_b[0][bb])
                > utg_pot_btn[bb]
                else 0.0
            )
            out[UTG_DEF][h] = 1.0 if def_vs_btn > fold_vs_btn else 0.0

            jam_btn = (1 - p_cbj) * jam_btn_fold[btn] + p_cbj * _mix(
                e_cbj, hu_bj[0][btn], hu_bj[1][btn]
            )
            bb_pot_vs_btn = money(_take(stacks, _put(stacks, opened_btn, bb, stacks[bb]), bb))
            open_btn = (1 - p_cbo) * steal_btn[btn] + p_cbo * max(
                _mix(e_cbo, hu_bo[0][btn], hu_bo[1][btn]),
                bb_pot_vs_btn[btn],
            )
            if jam_btn >= open_btn and jam_btn > ev_btn_after_utg_fold_fold:
                out[BTN_JAM][h] = 1.0
            elif open_btn > ev_btn_after_utg_fold_fold:
                out[BTN_OPEN][h] = 1.0

            e_vs_btn_o = _eq_vs(h, sigma[BTN_OPEN])
            e_vs_btn_j = _eq_vs(h, sigma[BTN_JAM])
            jam_bb_bo = (1 - p_bdef) * bb_pot_vs_btn[bb] + p_bdef * _mix(
                e_vs_btn_o, hu_bo[1][bb], hu_bo[0][bb]
            )
            out[BB_VS_BTN_OPEN][h] = 1.0 if jam_bb_bo > steal_btn[bb] else 0.0
            out[BB_VS_BTN_JAM][h] = (
                1.0
                if _mix(e_vs_btn_j, hu_bj[1][bb], hu_bj[0][bb]) > jam_btn_fold[bb]
                else 0.0
            )
            out[BTN_DEF][h] = (
                1.0 if _mix(e_cbo, hu_bo[0][btn], hu_bo[1][btn]) > bb_pot_vs_btn[btn] else 0.0
            )
            _ = ev_bb_after_utg_fold_if_btn_folds
        return out

    for done in range(iterations):
        reply = br(avg())
        weight = float(done + 1)
        for node in range(N_NODES):
            for i in range(N_HANDS):
                cum[node][i] += weight * reply[node][i]
        weight_sum += weight

    final = avg()

    def pct(node: int) -> float:
        return 100.0 * _mass(final[node])

    aa = 0
    junk = next(
        i
        for i, cls in enumerate(ALL_CLASSES)
        if cls.high.name == "SEVEN" and cls.low.name == "TWO" and not cls.suited
    )
    _ = CLASS_INDEX
    return {
        "iterations": iterations,
        "utg_open": final[UTG_OPEN],
        "utg_jam": final[UTG_JAM],
        "btn_vs_open": final[BTN_VS_OPEN],
        "btn_vs_jam": final[BTN_VS_JAM],
        "bb_vs_open": final[BB_VS_OPEN],
        "utg_def": final[UTG_DEF],
        "btn_open": final[BTN_OPEN],
        "btn_jam": final[BTN_JAM],
        "bb_vs_btn_open": final[BB_VS_BTN_OPEN],
        "utg_open_pct": pct(UTG_OPEN),
        "utg_jam_pct": pct(UTG_JAM),
        "btn_vs_open_pct": pct(BTN_VS_OPEN),
        "bb_vs_open_pct": pct(BB_VS_OPEN),
        "btn_open_pct": pct(BTN_OPEN),
        "utg_def_pct": pct(UTG_DEF),
        "aa_plays": final[UTG_OPEN][aa] + final[UTG_JAM][aa] > 0.85,
        "junk_folds": final[UTG_OPEN][junk] + final[UTG_JAM][junk] < 0.25,
    }

"""3-max fold / open 2.2x / jam. No flats. Fictitious play, real preflop matrix.

Used above JAM_FOLD_BB. Jam/fold remains the endgame (decyzja 19).
Wynik to średnia FP po N iteracjach — przybliżenie punktu stałego modelu, nie
Nash pełnej gry; jak bliskie, mówi miara zbieżności: zysk z best response
(`br_gain`) liczony tą samą wyceną co best response.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from poker.preflop import ALL_CLASSES
from poker.preflop_equity import equity as class_equity
from poker.spin import (
    BIG_BLIND,
    SMALL_BLIND,
    award_allin,
    model_ranks,
    open_amount,
    roles,
    terminal_equities,
)

N_HANDS = len(ALL_CLASSES)
# First-in: two exclusive freqs (open, jam); rest fold.
# Facing: one freq (jam or call).
UTG_OPEN, UTG_JAM, BTN_VS_OPEN, BTN_VS_JAM, BB_VS_OPEN, BB_VS_JAM = range(6)
UTG_DEF, BB_VS_OJ, BTN_OPEN, BTN_JAM, BB_VS_BTN_OPEN, BB_VS_BTN_JAM, BTN_DEF = range(6, 13)
N_NODES = 13
# Punkty decyzji: węzły strategii, między którymi (i foldem) wybiera jedna ręka.
DECISIONS: tuple[tuple[int, ...], ...] = (
    (UTG_OPEN, UTG_JAM),
    (BTN_VS_OPEN,),
    (BTN_VS_JAM,),
    (BB_VS_OPEN,),
    (BB_VS_JAM,),
    (UTG_DEF,),
    (BB_VS_OJ,),
    (BTN_OPEN, BTN_JAM),
    (BB_VS_BTN_OPEN,),
    (BB_VS_BTN_JAM,),
    (BTN_DEF,),
)
# Rola decydująca i sytuacja każdego punktu DECISIONS — klucze miary zbieżności.
DECISION_LABELS: tuple[str, ...] = (
    "UTG first-in",
    "BTN vs open",
    "BTN vs jam UTG",
    "BB vs open",
    "BB vs jam UTG",
    "UTG vs jam BTN po openie",
    "BB vs open i jam BTN",
    "BTN first-in",
    "BB vs open BTN",
    "BB vs jam BTN",
    "BTN vs jam BB po openie",
)
# Tolerancja miary zbieżności w ułamku sumy nagród (decyzja architekta, POKER-73).
CONVERGENCE_TOL = 1e-3
CURVE_CHECKPOINTS: tuple[int, ...] = (8, 16, 32, 64, 128, 256, 512, 1024)
# Najmniejszy punkt kontrolny, na którym miara ≤ CONVERGENCE_TOL na wszystkich
# poziomach eksportu (`python tools/export_open_nash.py --curve`): liczba
# iteracji eksportu i książek openfold areny. Ucięte FP zależy od N, więc
# liczba bez krzywej nie mówi nic o zbieżności.
CURVE_ITERATIONS = 128

WEIGHTS: tuple[int, ...] = tuple(
    6 if cls.high == cls.low else (4 if cls.suited else 12) for cls in ALL_CLASSES
)

Equities = tuple[float, ...]
HuPair = tuple[Equities, Equities]
# values[d][h] — $EV akcji (fold, *DECISIONS[d]) ręki h w punkcie decyzji d.
ActionValues = tuple[tuple[Equities, ...], ...]


@dataclass(frozen=True, slots=True)
class OpenFoldSolution:
    iterations: int
    utg_open: tuple[float, ...]
    utg_jam: tuple[float, ...]
    btn_vs_open: tuple[float, ...]
    btn_vs_jam: tuple[float, ...]
    bb_vs_open: tuple[float, ...]
    bb_vs_oj: tuple[float, ...]
    utg_def: tuple[float, ...]
    btn_open: tuple[float, ...]
    btn_jam: tuple[float, ...]
    bb_vs_btn_open: tuple[float, ...]
    utg_open_pct: float
    utg_jam_pct: float
    btn_vs_open_pct: float
    bb_vs_open_pct: float
    btn_open_pct: float
    utg_def_pct: float
    aa_plays: bool
    junk_folds: bool
    # Zysk z best response per punkt DECISIONS (etykiety DECISION_LABELS)
    # w ułamku sumy nagród; `convergence` to jego maksimum — miara zbieżności.
    br_gain: tuple[float, ...]
    convergence: float


@dataclass(frozen=True, slots=True)
class ThreeBetSolution:
    continue_frac: float
    btn_vs_open: tuple[float, ...]
    bb_vs_open: tuple[float, ...]
    btn_vs_open_pct: float
    bb_vs_open_pct: float
    aa_jams: bool
    junk_folds: bool
    utg_open_pct: float


@dataclass(frozen=True, slots=True)
class Terminals:
    """$EV stanów terminalnych drzewa jednego stanu stacków — stałe przez cały FP.

    Pary `hu_*` to (wygrywa pierwszy, wygrywa drugi) showdownu all-in: u = UTG,
    b = BTN, c = BB; `j` — jam z samych blindów, `o` — po openie 2.2x UTG albo
    BTN. `hu_uo_bc` to showdown BTN–BB, w którym open UTG leży martwy w puli.
    """

    utg: int
    btn: int
    bb: int
    fold_both: Equities
    steal_utg: Equities
    steal_btn: Equities
    jam_utg_fold: Equities
    jam_btn_fold: Equities
    utg_pot_btn: Equities
    bb_pot_vs_utg: Equities
    bb_pot_vs_btn: Equities
    hu_uj_b: HuPair
    hu_uj_c: HuPair
    hu_bj: HuPair
    hu_uo_b: HuPair
    hu_uo_c: HuPair
    hu_bo: HuPair
    hu_uo_bc: HuPair
    prize_sum: float


def _hu(i: int, j: int) -> float:
    return class_equity(ALL_CLASSES[i], ALL_CLASSES[j])


_EQUITY: tuple[tuple[float, ...], ...] = tuple(
    tuple(_hu(i, j) for j in range(N_HANDS)) for i in range(N_HANDS)
)


def _mass(sigma: Sequence[float]) -> float:
    return sum(WEIGHTS[i] * sigma[i] for i in range(N_HANDS)) / sum(WEIGHTS)


def _eq_vs(h: int, sigma: Sequence[float]) -> float:
    row = _EQUITY[h]
    num = 0.0
    den = 0.0
    for i in range(N_HANDS):
        w = WEIGHTS[i] * sigma[i]
        if w == 0:
            continue
        num += w * row[i]
        den += w
    return 0.5 if den == 0 else num / den


def _eq_all(sigma: Sequence[float]) -> list[float]:
    """`_eq_vs` każdej ręki wobec jednego zakresu — ta sama kolejność sumowania."""
    live = [(i, WEIGHTS[i] * sigma[i]) for i in range(N_HANDS) if WEIGHTS[i] * sigma[i] != 0]
    den = 0.0
    for _, w in live:
        den += w
    if den == 0:
        return [0.5] * N_HANDS
    out = []
    for h in range(N_HANDS):
        row = _EQUITY[h]
        num = 0.0
        for i, w in live:
            num += w * row[i]
        out.append(num / den)
    return out


def _eq_ranges(a: Sequence[float], b: Sequence[float]) -> float:
    """Equity zakresu `a` wobec zakresu `b` — nie zależy od ręki trzeciego gracza."""
    num = 0.0
    den = 0.0
    for i in range(N_HANDS):
        wa = WEIGHTS[i] * a[i]
        if wa == 0:
            continue
        row = _EQUITY[i]
        for j in range(N_HANDS):
            wb = WEIGHTS[j] * b[j]
            if wb == 0:
                continue
            num += wa * wb * row[j]
            den += wa * wb
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


def _sd(
    stacks: tuple[int, int, int], contrib: list[int], showdown: tuple[int, int], winner: int
) -> tuple[int, int, int]:
    paid = (contrib[0], contrib[1], contrib[2])
    awarded = award_allin(paid, model_ranks(stacks, paid, showdown, winner))
    return (
        stacks[0] - contrib[0] + awarded[0],
        stacks[1] - contrib[1] + awarded[1],
        stacks[2] - contrib[2] + awarded[2],
    )


def terminals(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int = 1,
    sb: int = SMALL_BLIND,
    bb_amt: int = BIG_BLIND,
) -> Terminals:
    utg, btn, bb = roles(button)
    size = open_amount(bb_amt)
    blinds = _blinds(stacks, button, sb, bb_amt)
    opened_utg = _put(stacks, blinds, utg, size)
    opened_btn = _put(stacks, blinds, btn, size)

    def money(state: tuple[int, int, int]) -> Equities:
        return terminal_equities(stacks, state, prizes)

    def hu(a: int, b: int, base: list[int], w: int) -> Equities:
        c = _put(stacks, _put(stacks, base, a, stacks[a]), b, stacks[b])
        return money(_sd(stacks, c, (a, b), w))

    return Terminals(
        utg=utg,
        btn=btn,
        bb=bb,
        fold_both=money(_take(stacks, blinds, bb)),
        steal_utg=money(_take(stacks, opened_utg, utg)),
        steal_btn=money(_take(stacks, opened_btn, btn)),
        jam_utg_fold=money(_take(stacks, _put(stacks, blinds, utg, stacks[utg]), utg)),
        jam_btn_fold=money(_take(stacks, _put(stacks, blinds, btn, stacks[btn]), btn)),
        utg_pot_btn=money(_take(stacks, _put(stacks, opened_utg, btn, stacks[btn]), btn)),
        bb_pot_vs_utg=money(_take(stacks, _put(stacks, opened_utg, bb, stacks[bb]), bb)),
        bb_pot_vs_btn=money(_take(stacks, _put(stacks, opened_btn, bb, stacks[bb]), bb)),
        hu_uj_b=(hu(utg, btn, blinds, utg), hu(utg, btn, blinds, btn)),
        hu_uj_c=(hu(utg, bb, blinds, utg), hu(utg, bb, blinds, bb)),
        hu_bj=(hu(btn, bb, blinds, btn), hu(btn, bb, blinds, bb)),
        hu_uo_b=(hu(utg, btn, opened_utg, utg), hu(utg, btn, opened_utg, btn)),
        hu_uo_c=(hu(utg, bb, opened_utg, utg), hu(utg, bb, opened_utg, bb)),
        hu_bo=(hu(btn, bb, opened_btn, btn), hu(btn, bb, opened_btn, bb)),
        hu_uo_bc=(hu(btn, bb, opened_utg, btn), hu(btn, bb, opened_utg, bb)),
        prize_sum=sum(prizes),
    )


def action_values(t: Terminals, sigma: Sequence[Sequence[float]]) -> ActionValues:
    """$EV każdej akcji w każdym punkcie decyzji przy profilu `sigma`, per klasa ręki.

    Akcja, po której gracz gra showdown, jest wyceniana showdownem z jego
    udziałem; fold — prawdopodobieństwem wyniku niezależnym od ręki spasowanego
    (equity zakres–zakres albo jawna stała 0.5). Wycena openu liczy własny dalszy
    ciąg ręki jako best response (max z call i fold), więc UTG wobec jamu BB nad
    openem i wobec jamu z overcallem nie ma węzła strategii.

    Przybliżenia modelu, nazwane wprost (pełny terminal 3-way z side potami jest
    poza modelem):

    - fold BB po jamie BTN nad openem UTG pomija call UTG: BTN bierze pulę;
    - call BB po jamie BTN nad openem oraz call UTG po jamie i overcallu
      pomijają 3-way z side potami: BB gra showdown z BTN przy martwym openie
      UTG, a UTG — showdown z samym BB (BTN wnosi tylko blind);
    - jam UTG sprawdzony przez obu: UTG wycenia go iloczynem equity dwóch par,
      a call BTN i call BB — showdownem z samym UTG;
    - częstość cudzego ciągu po openie to masa węzła UTG_DEF albo BTN_DEF po
      wszystkich klasach (bez warunku na zakres openu), w wycenie jamu BTN i BB
      nad openem UTG nie niższa niż 0.45; showdown z kontynuującym UTG liczony
      jest wobec zakresu UTG_DEF (jam BTN) albo zakresu openu (jam BB),
      z kontynuującym BTN — wobec zakresu openu BTN; UTG_DEF stoi też za
      odpowiedzią UTG na jam BB w wycenie foldu BTN;
    - showdowny BTN–BB po foldzie UTG wyceniane dla UTG z equity 0.5;
    - blind all-in z samego blinda nie gra showdownu, gdy pozostali pasują:
      pulę bierze agresor albo BB (terminale `_take`).
    """
    utg, btn, bb = t.utg, t.btn, t.bb
    p_bvo, p_bvj = _mass(sigma[BTN_VS_OPEN]), _mass(sigma[BTN_VS_JAM])
    p_cvo, p_cvj = _mass(sigma[BB_VS_OPEN]), _mass(sigma[BB_VS_JAM])
    p_oj, p_def = _mass(sigma[BB_VS_OJ]), _mass(sigma[UTG_DEF])
    p_bto, p_btj = _mass(sigma[BTN_OPEN]), _mass(sigma[BTN_JAM])
    p_cbo, p_cbj = _mass(sigma[BB_VS_BTN_OPEN]), _mass(sigma[BB_VS_BTN_JAM])
    p_bdef = _mass(sigma[BTN_DEF])
    p_cont = max(p_def, 0.45)

    # After UTG folds: BTN first-in, then BB.
    ev_utg_fold = (
        (1 - p_bto - p_btj) * t.fold_both[utg]
        + p_btj * (1 - p_cbj) * t.jam_btn_fold[utg]
        + p_btj * p_cbj * _mix(0.5, t.hu_bj[0][utg], t.hu_bj[1][utg])
        + p_bto * (1 - p_cbo) * t.steal_btn[utg]
        + p_bto * p_cbo * (1 - p_bdef) * t.bb_pot_vs_btn[utg]
        + p_bto * p_cbo * p_bdef * _mix(0.5, t.hu_bo[0][utg], t.hu_bo[1][utg])
    )
    ev_btn_after_utg_fold_fold = t.fold_both[btn]
    fold_vs_btn = t.utg_pot_btn[utg]
    fold_vs_bb = t.bb_pot_vs_utg[utg]
    fold_vs_oj = _mix(
        _eq_ranges(sigma[BTN_VS_OPEN], sigma[BB_VS_OJ]), t.hu_uo_bc[0][utg], t.hu_uo_bc[1][utg]
    )
    fold_btn_vo = (1 - p_cvo) * t.steal_utg[btn] + p_cvo * (
        (1 - p_def) * t.bb_pot_vs_utg[btn]
        + p_def
        * _mix(
            _eq_ranges(sigma[UTG_DEF], sigma[BB_VS_OPEN]), t.hu_uo_c[0][btn], t.hu_uo_c[1][btn]
        )
    )
    fold_btn_vj = (1 - p_cvj) * t.jam_utg_fold[btn] + p_cvj * _mix(
        _eq_ranges(sigma[UTG_JAM], sigma[BB_VS_JAM]), t.hu_uj_c[0][btn], t.hu_uj_c[1][btn]
    )

    e_bvo_all = _eq_all(sigma[BTN_VS_OPEN])
    e_cvo_all = _eq_all(sigma[BB_VS_OPEN])
    e_bvj_all = _eq_all(sigma[BTN_VS_JAM])
    e_cvj_all = _eq_all(sigma[BB_VS_JAM])
    e_oj_all = _eq_all(sigma[BB_VS_OJ])
    e_cbo_all = _eq_all(sigma[BB_VS_BTN_OPEN])
    e_cbj_all = _eq_all(sigma[BB_VS_BTN_JAM])
    e_def_all = _eq_all(sigma[UTG_DEF])
    e_uo_all = _eq_all(sigma[UTG_OPEN])
    e_uj_all = _eq_all(sigma[UTG_JAM])
    e_bo_all = _eq_all(sigma[BTN_OPEN])
    e_bj_all = _eq_all(sigma[BTN_JAM])

    rows: dict[int, list[Equities]] = {nodes[0]: [] for nodes in DECISIONS}
    for h in range(N_HANDS):
        e_bvo = e_bvo_all[h]
        e_cvo = e_cvo_all[h]
        e_bvj = e_bvj_all[h]
        e_cvj = e_cvj_all[h]
        e_oj = e_oj_all[h]
        e_cbo = e_cbo_all[h]
        e_cbj = e_cbj_all[h]

        jam_utg = (
            (1 - p_bvj) * (1 - p_cvj) * t.jam_utg_fold[utg]
            + (1 - p_bvj) * p_cvj * _mix(e_cvj, t.hu_uj_c[0][utg], t.hu_uj_c[1][utg])
            + p_bvj * (1 - p_cvj) * _mix(e_bvj, t.hu_uj_b[0][utg], t.hu_uj_b[1][utg])
            + p_bvj * p_cvj * _mix(e_bvj * e_cvj, t.hu_uj_b[0][utg], t.hu_uj_c[1][utg])
        )
        def_vs_btn = _mix(e_bvo, t.hu_uo_b[0][utg], t.hu_uo_b[1][utg])
        def_vs_bb = _mix(e_cvo, t.hu_uo_c[0][utg], t.hu_uo_c[1][utg])
        open_utg = (
            (1 - p_bvo) * (1 - p_cvo) * t.steal_utg[utg]
            + (1 - p_bvo) * p_cvo * max(def_vs_bb, fold_vs_bb)
            + p_bvo * (1 - p_oj) * max(def_vs_btn, fold_vs_btn)
            + p_bvo * p_oj * max(_mix(e_oj, t.hu_uo_c[0][utg], t.hu_uo_c[1][utg]), fold_vs_oj)
        )
        rows[UTG_OPEN].append((ev_utg_fold, open_utg, jam_utg))

        e_vs_utg_o = e_uo_all[h]
        e_vs_utg_j = e_uj_all[h]
        jam_btn_vo = (1 - p_cont) * t.utg_pot_btn[btn] + p_cont * _mix(
            e_def_all[h], t.hu_uo_b[1][btn], t.hu_uo_b[0][btn]
        )
        jam_btn_vo = (1 - p_oj) * jam_btn_vo + p_oj * _mix(
            e_oj, t.hu_uo_bc[0][btn], t.hu_uo_bc[1][btn]
        )
        rows[BTN_VS_OPEN].append((fold_btn_vo, jam_btn_vo))

        call_btn_vj = _mix(e_vs_utg_j, t.hu_uj_b[1][btn], t.hu_uj_b[0][btn])
        rows[BTN_VS_JAM].append((fold_btn_vj, call_btn_vj))

        jam_bb_vo = (1 - p_cont) * t.bb_pot_vs_utg[bb] + p_cont * _mix(
            e_vs_utg_o, t.hu_uo_c[1][bb], t.hu_uo_c[0][bb]
        )
        rows[BB_VS_OPEN].append((t.steal_utg[bb], jam_bb_vo))
        rows[BB_VS_JAM].append(
            (t.jam_utg_fold[bb], _mix(e_vs_utg_j, t.hu_uj_c[1][bb], t.hu_uj_c[0][bb]))
        )
        rows[UTG_DEF].append((fold_vs_btn, def_vs_btn))
        rows[BB_VS_OJ].append(
            (t.utg_pot_btn[bb], _mix(e_bvo, t.hu_uo_bc[1][bb], t.hu_uo_bc[0][bb]))
        )

        jam_btn = (1 - p_cbj) * t.jam_btn_fold[btn] + p_cbj * _mix(
            e_cbj, t.hu_bj[0][btn], t.hu_bj[1][btn]
        )
        open_btn = (1 - p_cbo) * t.steal_btn[btn] + p_cbo * max(
            _mix(e_cbo, t.hu_bo[0][btn], t.hu_bo[1][btn]),
            t.bb_pot_vs_btn[btn],
        )
        rows[BTN_OPEN].append((ev_btn_after_utg_fold_fold, open_btn, jam_btn))

        e_vs_btn_o = e_bo_all[h]
        e_vs_btn_j = e_bj_all[h]
        jam_bb_bo = (1 - p_bdef) * t.bb_pot_vs_btn[bb] + p_bdef * _mix(
            e_vs_btn_o, t.hu_bo[1][bb], t.hu_bo[0][bb]
        )
        rows[BB_VS_BTN_OPEN].append((t.steal_btn[bb], jam_bb_bo))
        rows[BB_VS_BTN_JAM].append(
            (t.jam_btn_fold[bb], _mix(e_vs_btn_j, t.hu_bj[1][bb], t.hu_bj[0][bb]))
        )
        rows[BTN_DEF].append(
            (t.bb_pot_vs_btn[btn], _mix(e_cbo, t.hu_bo[0][btn], t.hu_bo[1][btn]))
        )
    return tuple(tuple(rows[nodes[0]]) for nodes in DECISIONS)


def best_response(values: ActionValues) -> list[list[float]]:
    """Czysta odpowiedź na wyceny: remis rozstrzyga fold, a jam przed openem."""
    out = [[0.0] * N_HANDS for _ in range(N_NODES)]
    for nodes, row in zip(DECISIONS, values, strict=True):
        for h, q in enumerate(row):
            if len(nodes) == 1:
                out[nodes[0]][h] = 1.0 if q[1] > q[0] else 0.0
            elif q[2] >= q[1] and q[2] > q[0]:
                out[nodes[1]][h] = 1.0
            elif q[1] > q[0]:
                out[nodes[0]][h] = 1.0
    return out


def br_gain(t: Terminals, sigma: Sequence[Sequence[float]]) -> tuple[float, ...]:
    """Zysk z best response w każdym punkcie `DECISIONS`, w ułamku sumy nagród.

    Ta sama wycena co best response FP (`action_values`): w punkcie decyzji
    ręka h zyskuje max_a Q(h, a) − Σ_a σ(h, a)·Q(h, a), średnio po klasach
    ważonych kombinacjami (bez warunku na dojście do węzła). Każdy składnik to
    częstość razy nieujemna strata akcji, więc zysk ≥ 0 z konstrukcji i równy
    zeru dokładnie wtedy, gdy profil jest własnym best response.
    """
    total = float(sum(WEIGHTS))
    out = []
    for nodes, row in zip(DECISIONS, action_values(t, sigma), strict=True):
        gain = 0.0
        for h, q in enumerate(row):
            best = max(q)
            played = [sigma[node][h] for node in nodes]
            loss = max(0.0, 1.0 - sum(played)) * (best - q[0])
            for freq, value in zip(played, q[1:], strict=True):
                loss += freq * (best - value)
            gain += WEIGHTS[h] * loss
        out.append(gain / total / t.prize_sum)
    return tuple(out)


def solve(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int = 1,
    iterations: int = 24,
    sb: int = SMALL_BLIND,
    bb_amt: int = BIG_BLIND,
) -> OpenFoldSolution:
    return solve_curve(stacks, prizes, (iterations,), button, sb, bb_amt)[0]


def solve_curve(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    checkpoints: Sequence[int],
    button: int = 1,
    sb: int = SMALL_BLIND,
    bb_amt: int = BIG_BLIND,
) -> tuple[OpenFoldSolution, ...]:
    """Jeden bieg FP do max(checkpoints); wynik po każdym punkcie kontrolnym.

    Średnia FP po N iteracjach nie zależy od tego, ile iteracji przyjdzie po
    niej, więc wpis dla N jest tym, co zwraca `solve(..., iterations=N)`.
    """
    if not checkpoints or min(checkpoints) < 1:
        raise ValueError("iteracje muszą być dodatnie")
    t = terminals(stacks, prizes, button, sb, bb_amt)

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

    marks: dict[int, OpenFoldSolution] = {}
    for done in range(max(checkpoints)):
        reply = best_response(action_values(t, avg()))
        weight = float(done + 1)
        for node in range(N_NODES):
            for i in range(N_HANDS):
                cum[node][i] += weight * reply[node][i]
        weight_sum += weight
        if done + 1 in checkpoints:
            marks[done + 1] = _solution(t, avg(), done + 1)
    return tuple(marks[n] for n in checkpoints)


def _solution(t: Terminals, final: list[list[float]], iterations: int) -> OpenFoldSolution:
    def pct(node: int) -> float:
        return 100.0 * _mass(final[node])

    aa = 0
    junk = next(
        i
        for i, cls in enumerate(ALL_CLASSES)
        if cls.high.name == "SEVEN" and cls.low.name == "TWO" and not cls.suited
    )
    gain = br_gain(t, final)
    return OpenFoldSolution(
        iterations=iterations,
        utg_open=tuple(final[UTG_OPEN]),
        utg_jam=tuple(final[UTG_JAM]),
        btn_vs_open=tuple(final[BTN_VS_OPEN]),
        btn_vs_jam=tuple(final[BTN_VS_JAM]),
        bb_vs_open=tuple(final[BB_VS_OPEN]),
        bb_vs_oj=tuple(final[BB_VS_OJ]),
        utg_def=tuple(final[UTG_DEF]),
        btn_open=tuple(final[BTN_OPEN]),
        btn_jam=tuple(final[BTN_JAM]),
        bb_vs_btn_open=tuple(final[BB_VS_BTN_OPEN]),
        utg_open_pct=pct(UTG_OPEN),
        utg_jam_pct=pct(UTG_JAM),
        btn_vs_open_pct=pct(BTN_VS_OPEN),
        bb_vs_open_pct=pct(BB_VS_OPEN),
        btn_open_pct=pct(BTN_OPEN),
        utg_def_pct=pct(UTG_DEF),
        aa_plays=final[UTG_OPEN][aa] + final[UTG_JAM][aa] > 0.85,
        junk_folds=final[UTG_OPEN][junk] + final[UTG_JAM][junk] < 0.25,
        br_gain=gain,
        convergence=max(gain),
    )


def _top_slice(sigma: Sequence[float], frac: float) -> list[float]:
    """Strongest `frac` of a range (by equity vs that range)."""
    if frac <= 0:
        return [0.0] * N_HANDS
    if frac >= 1:
        return list(sigma)
    ranked = sorted(range(N_HANDS), key=lambda i: -_eq_vs(i, sigma))
    target = frac * _mass(sigma)
    out = [0.0] * N_HANDS
    acc = 0.0
    denom = float(sum(WEIGHTS))
    for i in ranked:
        if sigma[i] <= 0:
            continue
        out[i] = sigma[i]
        acc += WEIGHTS[i] * sigma[i] / denom
        if acc >= target:
            break
    return out


def threebet(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int = 1,
    iterations: int = 16,
    sb: int = SMALL_BLIND,
    bb_amt: int = BIG_BLIND,
    continue_frac: float = 0.55,
) -> ThreeBetSolution:
    """BTN/BB jam-or-fold vs a frozen UTG open. Continue = top of that open.

    Not a Nash of the full tree — the no-flat 3bet explodes. This is the
    policy we actually ship (decyzja 20).
    """
    if not 0.0 < continue_frac <= 1.0:
        raise ValueError("continue_frac")
    first = solve(stacks, prizes, button, iterations, sb, bb_amt)
    return _threebet_from_open(
        first.utg_open, first.utg_open_pct, stacks, prizes, button, sb, bb_amt, continue_frac
    )


def _threebet_from_open(
    utg_open: Sequence[float],
    utg_open_pct: float,
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int,
    sb: int,
    bb_amt: int,
    continue_frac: float,
) -> ThreeBetSolution:
    cont = _top_slice(utg_open, continue_frac)
    utg, btn, bb = roles(button)
    size = open_amount(bb_amt)
    blinds = _blinds(stacks, button, sb, bb_amt)
    opened = _put(stacks, blinds, utg, size)

    def money(state: tuple[int, int, int]) -> tuple[float, ...]:
        return terminal_equities(stacks, state, prizes)

    steal = money(_take(stacks, opened, utg))
    btn_wins = money(_take(stacks, _put(stacks, opened, btn, stacks[btn]), btn))
    bb_wins = money(_take(stacks, _put(stacks, opened, bb, stacks[bb]), bb))

    def hu(a: int, b: int, w: int) -> tuple[float, ...]:
        c = _put(stacks, _put(stacks, opened, a, stacks[a]), b, stacks[b])
        return money(_sd(stacks, c, (a, b), w))

    hu_btn = (hu(utg, btn, utg), hu(utg, btn, btn))
    hu_bb = (hu(utg, bb, utg), hu(utg, bb, bb))
    p_cont = continue_frac
    btn_j = [0.0] * N_HANDS
    bb_j = [0.0] * N_HANDS
    for h in range(N_HANDS):
        e = _eq_vs(h, cont)
        jam_btn = (1 - p_cont) * btn_wins[btn] + p_cont * _mix(e, hu_btn[1][btn], hu_btn[0][btn])
        jam_bb = (1 - p_cont) * bb_wins[bb] + p_cont * _mix(e, hu_bb[1][bb], hu_bb[0][bb])
        btn_j[h] = 1.0 if jam_btn > steal[btn] else 0.0
        bb_j[h] = 1.0 if jam_bb > steal[bb] else 0.0
    aa = 0
    junk = next(
        i
        for i, cls in enumerate(ALL_CLASSES)
        if cls.high.name == "SEVEN" and cls.low.name == "TWO" and not cls.suited
    )
    return ThreeBetSolution(
        continue_frac=continue_frac,
        btn_vs_open=tuple(btn_j),
        bb_vs_open=tuple(bb_j),
        btn_vs_open_pct=100.0 * _mass(btn_j),
        bb_vs_open_pct=100.0 * _mass(bb_j),
        aa_jams=btn_j[aa] > 0.85,
        junk_folds=btn_j[junk] < 0.25,
        utg_open_pct=utg_open_pct,
    )


def threebet_vs_range(
    open_sigma: Sequence[float],
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int = 1,
    sb: int = SMALL_BLIND,
    bb_amt: int = BIG_BLIND,
    continue_frac: float = 0.35,
) -> ThreeBetSolution:
    """3bet-jam vs a known open range. Lower continue = they fold too much."""
    if not 0.0 < continue_frac <= 1.0:
        raise ValueError("continue_frac")
    return _threebet_from_open(
        open_sigma,
        100.0 * _mass(open_sigma),
        stacks,
        prizes,
        button,
        sb,
        bb_amt,
        continue_frac,
    )

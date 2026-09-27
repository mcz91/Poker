"""3-max jam/fold: fictitious play na jednym stanie stacków.

Wewnętrzna gra Ganzfried & Sandholm, AAMAS 2008. Equity HU z macierzy
preflop (POKER-12). Bez blockerów. 3-way all-in: zwycięzca z iloczynu
equity par znormalizowanego, drugie miejsce z equity pary pozostałych
dwóch; stan żetonowy każdego porządku rąk rozlicza `award_allin`, więc
side pot wygrywa lepsza ręka spośród uprawnionych.

Best response i ε liczy funkcja wartości per ręka decydenta (ręka wobec
zakresów rywali, `_hand_values`), a `values` (V¹ decyzji 12) — łączna wycena
zakres–zakres (`_eval_values`). Normalizacja iloczynu par nie jest liniowa
w zakresie, więc u_i w ε ≠ values_i.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    terminal_equities,
    utg_shove_both_fold,
    utg_shove_called,
)

N_HANDS = len(ALL_CLASSES)
UTG_OPEN, BTN_VS_UTG, BB_VS_UTG, BB_VS_BOTH, BTN_OPEN, BB_VS_BTN = range(6)
N_NODES = 6
# Węzły decyzji ról w kolejności `roles`: UTG, BTN, BB.
ROLE_NODES: tuple[tuple[int, ...], ...] = (
    (UTG_OPEN,),
    (BTN_VS_UTG, BTN_OPEN),
    (BB_VS_UTG, BB_VS_BOTH, BB_VS_BTN),
)

WEIGHTS: tuple[int, ...] = tuple(
    6 if cls.high == cls.low else (4 if cls.suited else 12) for cls in ALL_CLASSES
)

Equities3 = tuple[float, ...]
HuPair = tuple[Equities3, Equities3]
Order3 = tuple[int, int, int]

# Porządki rąk 3-way all-in (miejsca od najlepszej ręki) — kolejność terminali
# 3-way w `_terminal_states` i wektorów `_Payoffs.tw`.
THREE_WAY_ORDERS: tuple[Order3, ...] = (
    (0, 1, 2),
    (0, 2, 1),
    (1, 0, 2),
    (1, 2, 0),
    (2, 0, 1),
    (2, 1, 0),
)
_ORDER_INDEX = {order: k for k, order in enumerate(THREE_WAY_ORDERS)}


@dataclass(frozen=True, slots=True)
class _Payoffs:
    """Wektory stanów terminalnych drzewa jam/fold: $EV (`_payoffs`, stałe przez cały
    fictitious play) albo stany żetonowe (`_payoffs_of` — test V¹ − V⁰ pod WTA)."""

    utg: int
    btn: int
    bb: int
    utg_b: Equities3
    btn_b: Equities3
    bb_b: Equities3
    hu_utg_bb: HuPair
    hu_utg_btn: HuPair
    hu_btn_bb: HuPair
    tw: tuple[Equities3, ...]


@dataclass(frozen=True, slots=True)
class JamFoldSolution:
    iterations: int
    utg_jam: tuple[float, ...]
    btn_call: tuple[float, ...]
    bb_call: tuple[float, ...]
    bb_vs_both: tuple[float, ...]
    btn_open: tuple[float, ...]
    bb_vs_btn: tuple[float, ...]
    utg_jam_pct: float
    btn_call_pct: float
    bb_call_pct: float
    aa_jams: bool
    junk_folds: bool
    values: tuple[float, float, float]
    icm: tuple[float, ...]
    epsilon: tuple[float, float, float]
    exploitability: float


@dataclass(frozen=True, slots=True)
class ExploitabilityReport:
    epsilon: tuple[float, float, float]
    max_gain: float
    values: tuple[float, float, float]
    iterations: int


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
    stacks: tuple[int, int, int], a: int, b: int, winner: int
) -> tuple[int, int, int]:
    """All-in dwóch miejsc: wkłady od pełnych stacków sprzed blindów.

    Blindy siedzą w pełnych wkładach; nadpłatę większego stacka zwraca
    `award_allin` — suma żetonów przy stole jest stała.
    """
    contrib = [0, 0, 0]
    contrib[a] = stacks[a]
    contrib[b] = stacks[b]
    ranks = [2, 2, 2]
    ranks[winner] = 0
    awarded = award_allin((contrib[0], contrib[1], contrib[2]), (ranks[0], ranks[1], ranks[2]))
    return (
        stacks[0] - contrib[0] + awarded[0],
        stacks[1] - contrib[1] + awarded[1],
        stacks[2] - contrib[2] + awarded[2],
    )


def _three_way(
    stacks: tuple[int, int, int], shover: int, order: Order3
) -> tuple[int, int, int]:
    """3-way all-in za shove shovera: wołający wkłada min(stack, shove).

    `order` to miejsca od najlepszej ręki; ranga `award_allin` = pozycja
    w porządku, więc każdą warstwę puli bierze najlepsza z uprawnionych rąk.
    """
    shove = stacks[shover]
    contrib = [min(stacks[i], shove) for i in range(3)]
    ranks = [0, 0, 0]
    for place, seat in enumerate(order):
        ranks[seat] = place
    awarded = award_allin((contrib[0], contrib[1], contrib[2]), (ranks[0], ranks[1], ranks[2]))
    return (
        stacks[0] - contrib[0] + awarded[0],
        stacks[1] - contrib[1] + awarded[1],
        stacks[2] - contrib[2] + awarded[2],
    )


def _terminal_states(
    stacks: tuple[int, int, int],
    button: int,
    sb: int,
    bb_amt: int,
) -> tuple[tuple[int, int, int], ...]:
    """Stany żetonowe wszystkich terminali drzewa jam/fold, w stałej kolejności.

    (blindy do UTG, blindy do BTN, blindy do BB, HU UTG–BB ×2, HU UTG–BTN ×2,
    HU BTN–BB ×2, 3-way ×6 w kolejności `THREE_WAY_ORDERS`). Jedno źródło dla
    wypłat `solve` i testu niezmiennika sumy żetonów.
    """
    utg, btn, bb = roles(button)
    behind, pot = post_blinds(stacks, button, sb, bb_amt)
    return (
        utg_shove_both_fold(stacks, button, sb, bb_amt),
        _take(behind, btn, pot),
        _take(behind, bb, pot),
        utg_shove_called(stacks, button, bb, utg, sb, bb_amt),
        utg_shove_called(stacks, button, bb, bb, sb, bb_amt),
        utg_shove_called(stacks, button, btn, utg, sb, bb_amt),
        utg_shove_called(stacks, button, btn, btn, sb, bb_amt),
        _allin_two(stacks, btn, bb, btn),
        _allin_two(stacks, btn, bb, bb),
        *(_three_way(stacks, utg, order) for order in THREE_WAY_ORDERS),
    )


def _payoffs(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int,
    sb: int,
    bb_amt: int,
) -> _Payoffs:
    """$EV terminali: ICM, gdy grają dalej co najmniej dwaj, a przy końcu
    turnieju reguła miejsc ze stackami wejściowymi ręki (`terminal_equities`)."""
    return _payoffs_of(
        button,
        tuple(
            terminal_equities(stacks, state, prizes)
            for state in _terminal_states(stacks, button, sb, bb_amt)
        ),
    )


def _payoffs_of(button: int, vectors: tuple[Equities3, ...]) -> _Payoffs:
    """Wektory terminali w kolejności `_terminal_states` rozłożone na pola `_Payoffs`.

    Wektorem może być też stan żetonowy terminala: wycena `_eval_values` daje
    wtedy E[żetonów po ręce] pod profilem.
    """
    utg, btn, bb = roles(button)
    return _Payoffs(
        utg=utg,
        btn=btn,
        bb=bb,
        utg_b=vectors[0],
        btn_b=vectors[1],
        bb_b=vectors[2],
        hu_utg_bb=(vectors[3], vectors[4]),
        hu_utg_btn=(vectors[5], vectors[6]),
        hu_btn_bb=(vectors[7], vectors[8]),
        tw=vectors[9:],
    )


def _second(
    tw: tuple[Equities3, ...], first: int, second: int, third: int, p_second: float
) -> Equities3:
    """$EV po wygranej `first`: `second` przed `third` z prawdopodobieństwem p_second.

    Postać y + p·(x − y), nie p·x + (1 − p)·y: gdy drugie miejsce niczego nie
    rozstrzyga (x = y — równe stacki), wynik jest bitowo y i łańcuch liczb
    solve zostaje bitowo ten sam co w modelu bez drugiego miejsca.
    """
    ahead = tw[_ORDER_INDEX[(first, second, third)]]
    behind = tw[_ORDER_INDEX[(first, third, second)]]
    return (
        behind[0] + p_second * (ahead[0] - behind[0]),
        behind[1] + p_second * (ahead[1] - behind[1]),
        behind[2] + p_second * (ahead[2] - behind[2]),
    )


def _three_way_ev(
    tw: tuple[Equities3, ...],
    seats: Order3,
    p_ab: float,
    p_ac: float,
    p_bc: float,
) -> Equities3:
    """$EV 3-way all-in miejsc `seats` = (a, b, c); p_xy = P(ręka x wygrywa z ręką y).

    Zwycięzca: iloczyn equity par znormalizowany (decyzja 11 pkt 3). Drugie
    miejsce po zwycięzcy x: lepsza z pozostałych rąk y, z z equity tej pary,
    P(y drugie | x pierwsze) = P(y wygrywa z z). Kolejność miejsc w `seats`
    zmienia tylko kolejność działań zmiennoprzecinkowych: węzeł best response
    podaje decydenta pierwszego, jak liczył go model bez drugiego miejsca, więc
    przy równych stackach strategie zostają bitowo te same.
    """
    a, b, c = seats
    p_a, p_b, p_c = _norm3(p_ab * p_ac, (1 - p_ab) * p_bc, (1 - p_ac) * (1 - p_bc))
    after_a = _second(tw, a, b, c, p_bc)
    after_b = _second(tw, b, a, c, p_ac)
    after_c = _second(tw, c, a, b, p_ab)
    return (
        p_a * after_a[0] + p_b * after_b[0] + p_c * after_c[0],
        p_a * after_a[1] + p_b * after_b[1] + p_c * after_c[1],
        p_a * after_a[2] + p_b * after_b[2] + p_c * after_c[2],
    )


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
) -> JamFoldSolution:
    """Zwraca średnie strategie fictitious play (jam/call ∈ [0, 1] per klasa)."""
    if iterations < 1:
        raise ValueError("iteracje muszą być dodatnie")
    pay = _payoffs(stacks, prizes, button, sb, bb_amt)

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
    epsilon = _exploitability(final, pay)

    def pct(sigma: list[float]) -> float:
        return 100.0 * _mass(sigma)

    aa = CLASS_INDEX[ALL_CLASSES[0]]
    junk = next(
        i
        for i, cls in enumerate(ALL_CLASSES)
        if cls.high.name == "SEVEN" and cls.low.name == "TWO" and not cls.suited
    )
    return JamFoldSolution(
        iterations=iterations,
        utg_jam=tuple(final[UTG_OPEN]),
        btn_call=tuple(final[BTN_VS_UTG]),
        bb_call=tuple(final[BB_VS_UTG]),
        bb_vs_both=tuple(final[BB_VS_BOTH]),
        btn_open=tuple(final[BTN_OPEN]),
        bb_vs_btn=tuple(final[BB_VS_BTN]),
        utg_jam_pct=pct(final[UTG_OPEN]),
        btn_call_pct=pct(final[BTN_VS_UTG]),
        bb_call_pct=pct(final[BB_VS_UTG]),
        aa_jams=final[UTG_OPEN][aa] > 0.85,
        junk_folds=final[UTG_OPEN][junk] < 0.25,
        values=values,
        icm=cash,
        epsilon=epsilon,
        exploitability=max(epsilon),
    )


def one_step_values(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int = 1,
    iterations: int = 20,
) -> tuple[float, float, float]:
    """Pierwszy backup zewnętrzny: E[ICM(s′)] przy Nash jam/fold."""
    return solve(stacks, prizes, button, iterations).values


def _eval_values(sigma: list[list[float]], pay: _Payoffs) -> tuple[float, float, float]:
    """Łączna wycena zakres–zakres: E[$EV terminala] pod profilem σ — `values` solve.

    Wagi gałęzi sumują się do 1, więc sum(values) == sum(nagród) z konstrukcji.
    """
    utg, btn, bb = pay.utg, pay.btn, pay.bb
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
    utg_b = pay.utg_b
    btn_b = pay.btn_b
    bb_b = pay.bb_b
    hu_utg_bb = pay.hu_utg_bb
    hu_utg_btn = pay.hu_utg_btn
    hu_btn_bb = pay.hu_btn_bb
    tw = pay.tw

    acc = [0.0, 0.0, 0.0]

    def add(weight: float, vec: tuple[float, ...]) -> None:
        for i in range(3):
            acc[i] += weight * vec[i]

    def mix_vec(
        equity: float, win: tuple[float, ...], lose: tuple[float, ...]
    ) -> tuple[float, ...]:
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
    add(
        p_jam * p_btn_c * p_bb_both,
        _three_way_ev(tw, (utg, btn, bb), e_utg_btn, e_utg_both, e_call_both),
    )
    return (acc[0], acc[1], acc[2])


def _hand_values(
    sigma: list[list[float]], pay: _Payoffs
) -> tuple[list[float], list[list[float]]]:
    """Wartości decyzji w aproksymacji ręki decydenta: (pas per węzeł, akcja per węzeł i ręka).

    Para z decydentem gra ręka–zakres, para bez niego — zakres–zakres; pas nie
    zależy od ręki, bo pasujący nie gra showdownu. Wartości zależą wyłącznie od
    strategii rywali właściciela węzła, więc best response jest ich argmaxem
    per ręka, a u^ręka i ε liczą się z nich bez nowej wyceny.
    """
    utg, btn, bb = pay.utg, pay.btn, pay.bb
    utg_b = pay.utg_b
    btn_b = pay.btn_b
    bb_b = pay.bb_b
    hu_utg_bb = pay.hu_utg_bb
    hu_utg_btn = pay.hu_utg_btn
    hu_btn_bb = pay.hu_btn_bb
    tw = pay.tw
    utg_r, btn_c, bb_utg, bb_both, btn_o, bb_btn = sigma
    p_btn_c, p_bb_utg, p_bb_both = _mass(btn_c), _mass(bb_utg), _mass(bb_both)
    p_btn_o, p_bb_btn = _mass(btn_o), _mass(bb_btn)
    e_utg_bb = _eq_ranges(utg_r, bb_utg)
    e_utg_btn = _eq_ranges(utg_r, btn_c)
    e_call_both = _eq_ranges(btn_c, bb_both)
    e_utg_both = _eq_ranges(utg_r, bb_both)
    e_btn_bb = _eq_ranges(btn_o, bb_btn)
    fold = [0.0] * N_NODES
    fold[UTG_OPEN] = (
        (1 - p_btn_o) * bb_b[utg]
        + p_btn_o * (1 - p_bb_btn) * btn_b[utg]
        + p_btn_o * p_bb_btn * _mix(e_btn_bb, hu_btn_bb[0][utg], hu_btn_bb[1][utg])
    )
    fold[BTN_VS_UTG] = (1 - p_bb_utg) * utg_b[btn] + p_bb_utg * _mix(
        e_utg_bb, hu_utg_bb[0][btn], hu_utg_bb[1][btn]
    )
    fold[BB_VS_UTG] = utg_b[bb]
    fold[BB_VS_BOTH] = _mix(e_utg_btn, hu_utg_btn[0][bb], hu_utg_btn[1][bb])
    fold[BTN_OPEN] = bb_b[btn]
    fold[BB_VS_BTN] = btn_b[bb]
    act = [[0.0] * N_HANDS for _ in range(N_NODES)]
    for h in range(N_HANDS):
        e_h_bb = _eq_vs(h, bb_utg)
        e_h_btn = _eq_vs(h, btn_c)
        e_h_both = _eq_vs(h, bb_both)
        act[UTG_OPEN][h] = (
            (1 - p_btn_c) * (1 - p_bb_utg) * utg_b[utg]
            + (1 - p_btn_c) * p_bb_utg * _mix(e_h_bb, hu_utg_bb[0][utg], hu_utg_bb[1][utg])
            + p_btn_c * (1 - p_bb_both) * _mix(e_h_btn, hu_utg_btn[0][utg], hu_utg_btn[1][utg])
            + p_btn_c
            * p_bb_both
            * _three_way_ev(tw, (utg, btn, bb), e_h_btn, e_h_both, e_call_both)[utg]
        )
        e_vs_utg = _eq_vs(h, utg_r)
        act[BTN_VS_UTG][h] = (1 - p_bb_both) * _mix(
            e_vs_utg, hu_utg_btn[1][btn], hu_utg_btn[0][btn]
        ) + p_bb_both * _three_way_ev(tw, (btn, utg, bb), e_vs_utg, e_h_both, e_utg_both)[btn]
        act[BB_VS_UTG][h] = _mix(e_vs_utg, hu_utg_bb[1][bb], hu_utg_bb[0][bb])
        act[BB_VS_BOTH][h] = _three_way_ev(tw, (bb, utg, btn), e_vs_utg, e_h_btn, e_utg_btn)[bb]
        e_vs_bb = _eq_vs(h, bb_btn)
        act[BTN_OPEN][h] = (1 - p_bb_btn) * btn_b[btn] + p_bb_btn * _mix(
            e_vs_bb, hu_btn_bb[0][btn], hu_btn_bb[1][btn]
        )
        e_vs_btn = _eq_vs(h, btn_o)
        act[BB_VS_BTN][h] = _mix(e_vs_btn, hu_btn_bb[1][bb], hu_btn_bb[0][bb])
    return fold, act


def _best_response(sigma: list[list[float]], pay: _Payoffs) -> list[list[float]]:
    """Argmax `_hand_values` per ręka; remis — pas."""
    fold, act = _hand_values(sigma, pay)
    return [[1.0 if value > fold[node] else 0.0 for value in act[node]] for node in range(N_NODES)]


def _reach(sigma: list[list[float]]) -> tuple[list[float], float]:
    """(zasięg węzłów, gałąź bez decyzji BB: UTG i BTN pasują).

    Zasięg węzła to masa zakresów rywali jego właściciela — strategia właściciela
    go nie zmienia, więc u^ręka jest liniowa we własnej strategii miejsca.
    """
    p_jam = _mass(sigma[UTG_OPEN])
    p_btn_c = _mass(sigma[BTN_VS_UTG])
    p_btn_o = _mass(sigma[BTN_OPEN])
    reach = [0.0] * N_NODES
    reach[UTG_OPEN] = 1.0
    reach[BTN_VS_UTG] = p_jam
    reach[BTN_OPEN] = 1 - p_jam
    reach[BB_VS_UTG] = p_jam * (1 - p_btn_c)
    reach[BB_VS_BOTH] = p_jam * p_btn_c
    reach[BB_VS_BTN] = (1 - p_jam) * p_btn_o
    return reach, (1 - p_jam) * (1 - p_btn_o)


def _hand_accounts(
    sigma: list[list[float]], pay: _Payoffs
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """(u^ręka(σ), ε) per miejsce jednym przejściem `_hand_values`.

    W węźle ręka h ma σ_h·akcja_h + (1 − σ_h)·pas_h, a best response max(akcja_h,
    pas_h); średnie po rękach mają wagi kombinacji, węzły waży `_reach`. Obie
    liczby pochodzą z tych samych wartości, z których `_best_response` bierze
    argmax, więc ε_i = u_i^ręka(BR_i, σ−i) − u_i^ręka(σ) ≥ 0 z konstrukcji.
    """
    fold, act = _hand_values(sigma, pay)
    reach, walk = _reach(sigma)
    value = [0.0, 0.0, 0.0]
    gain = [0.0, 0.0, 0.0]
    for seat, nodes in zip((pay.utg, pay.btn, pay.bb), ROLE_NODES, strict=True):
        for node in nodes:
            row = sigma[node]
            node_value = 0.0
            node_gain = 0.0
            for h in range(N_HANDS):
                mixed = row[h] * act[node][h] + (1 - row[h]) * fold[node]
                node_value += WEIGHTS[h] * mixed
                node_gain += WEIGHTS[h] * (max(act[node][h], fold[node]) - mixed)
            value[seat] += reach[node] * node_value / sum(WEIGHTS)
            gain[seat] += reach[node] * node_gain / sum(WEIGHTS)
    value[pay.bb] += walk * pay.bb_b[pay.bb]
    return (value[0], value[1], value[2]), (gain[0], gain[1], gain[2])


def _hand_utility(sigma: list[list[float]], pay: _Payoffs) -> tuple[float, float, float]:
    """u^ręka(σ): wartość oczekiwana miejsc w aproksymacji ręki decydenta.

    Funkcja, której argmaxem jest best response i z której liczy się ε; ≠ `values`
    (łączna wycena zakres–zakres), bo normalizacja iloczynu par 3-way nie jest
    liniowa w zakresie.
    """
    return _hand_accounts(sigma, pay)[0]


def _exploitability(sigma: list[list[float]], pay: _Payoffs) -> tuple[float, float, float]:
    """ε per miejsce: zysk z jednostronnego odchylenia do best response.

    Liczony funkcją per ręka `_hand_accounts`, tą samą co best response, bez
    wyceny profili z podmienionymi węzłami; u_i w ε to nie `values`, więc ε nie
    wolno liczyć różnicą values.
    """
    return _hand_accounts(sigma, pay)[1]


def exploitability(
    stacks: tuple[int, int, int],
    prizes: tuple[float, float, float],
    button: int = 1,
    iterations: int = 24,
    sb: int = SMALL_BLIND,
    bb_amt: int = BIG_BLIND,
) -> ExploitabilityReport:
    """Max zysk z odchylenia do BR. Metryka Spina (decyzja 15), w buy-inach."""
    result = solve(stacks, prizes, button, iterations, sb, bb_amt)
    return ExploitabilityReport(
        epsilon=result.epsilon,
        max_gain=result.exploitability,
        values=result.values,
        iterations=iterations,
    )


def jam_vs_depth(
    prizes: tuple[float, float, float],
    button: int = 1,
    iterations: int = 16,
) -> tuple[tuple[int, float, float, float], ...]:
    """UTG jam % i call % na klasycznym zegarze 25/15/10/6 bb."""
    rows: list[tuple[int, float, float, float]] = []
    for bb, stacks in DEPTHS:
        result = solve(stacks, prizes, button, iterations)
        rows.append((bb, result.utg_jam_pct, result.btn_call_pct, result.bb_call_pct))
    return tuple(rows)

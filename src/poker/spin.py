"""Spin & Go: wypłaty 3-max, tabela tierów, role blindów, rozliczenie all-in, EV shove UTG.

Dwie różne rzeczy nazywają się tu „wypłatami" i mylenie ich jest kosztowne:

- `PAYOUTS` niesie wektor NIEZNORMALIZOWANY (3x to (3, 0, 0)) i służy
  punktacji areny, gdzie ROI liczy się w buy-inach, więc multiplikator ma być
  w liczbach;
- `TIERS` niesie kształt ZNORMALIZOWANY (suma 1) do konfiguracji przebiegu
  solvera. Multiplikator żyje w tabeli tierów, NIGDY w wektorze wypłat
  solvera: ex-post ε jest w jednostkach sumy wektora wypłat
  (`tools/blueprint/expost.py` dzieli przez `sum(prizes)`), więc przebieg
  puszczony z `PAYOUTS["3x"].prizes` po cichu podzieliłby ε przez 3
  i zamienił próg blokujący 1e-3 w 3e-3. `GridConfig` odrzuca taki wektor.
"""

from __future__ import annotations

from dataclasses import dataclass

from poker.icm import icm_equities

STARTING_CHIPS = 50
SMALL_BLIND = 1
BIG_BLIND = 2
HANDS_PER_LEVEL = 3
JAM_FOLD_BB = 7
LEVELS: tuple[tuple[int, int], ...] = (
    (1, 2),
    (2, 4),
    (3, 6),
    (4, 8),
    (5, 10),
    (8, 16),
    (10, 20),
)


@dataclass(frozen=True, slots=True)
class SpinPayout:
    name: str
    multiplier: int
    prizes: tuple[float, float, float]
    winner_take_all: bool


PAYOUTS: dict[str, SpinPayout] = {
    "2x": SpinPayout("2x WTA", 2, (2.0, 0.0, 0.0), True),
    "3x": SpinPayout("3x WTA", 3, (3.0, 0.0, 0.0), True),
    "10x": SpinPayout("10x 80/20", 10, (8.0, 2.0, 0.0), False),
}

Stacks3 = tuple[int, int, int]

# Suma wektora wypłat jest jednostką ε, więc odchyłka musi być poniżej progu,
# przy którym ε zmieniłoby się w ostatniej znaczącej cyfrze raportu (1e-9).
PRIZE_SUM_TOLERANCE = 1e-9


class UnconfirmedTierError(ValueError):
    """Tier bez potwierdzenia operatora użyty do konfiguracji przebiegu."""


@dataclass(frozen=True, slots=True)
class SpinTier:
    """Wiersz tabeli tierów: co multiplikator ustala w KONFIGURACJI PRZEBIEGU.

    `prizes` jest znormalizowany (suma 1) — to wektor dla solvera. Sam
    multiplikator zostaje tu, w tabeli, i wchodzi dopiero do przeliczenia
    wyniku (ROI [pp] = ε × multiplikator × 100).
    """

    key: str
    multipliers: tuple[int, ...]
    start_stack: int
    hands_per_level: int
    prizes: tuple[float, float, float]
    volume_share: float
    confirmed: bool

    def __post_init__(self) -> None:
        total = sum(self.prizes)
        if abs(total - 1.0) > PRIZE_SUM_TOLERANCE:
            raise ValueError(
                f"tier {self.key}: kształt wypłat {self.prizes} sumuje się do {total}, nie do 1 "
                "— multiplikator należy do tabeli tierów, nie do wektora wypłat solvera"
            )

    @property
    def total_chips(self) -> int:
        """Suma żetonów przy stole — to jest wymiar siatki stanów solvera."""
        return 3 * self.start_stack


# Tabela tierów — WEJŚCIE OPERATORSKIE, status: NIEPOTWIERDZONA.
# Źródło: decyzja 29 pkt 1 i 3A (`docs/decisions/29-tier-first-fundament-gto-mapa-po-researchu.md`,
# 2026-09-05), streszczająca research ze źródeł WTÓRNYCH (rozkład multiplikatorów
# i stacków startowych Spin & Go). Format był raz restrukturyzowany (fuzja Flash
# 2025), więc żaden wiersz nie wchodzi do przebiegu bez potwierdzenia wobec
# żywego lobby — `tier_for_run` wymaga wtedy jawnej flagi.
# `hands_per_level` NIE pochodzi z researchu: to dzisiejszy zegar produktu
# (`HANDS_PER_LEVEL`), a krzywa wrażliwości {3, 6} rąk na poziom jest osobnym
# kontraktem (decyzja 29, P-8). Udziały wolumenu nie sumują się do 1, bo tiery
# 25x+ są odroczone (decyzja 29 pkt 3A).
TIERS: dict[str, SpinTier] = {
    "T-MODAL": SpinTier("T-MODAL", (2, 3), 30, HANDS_PER_LEVEL, (1.0, 0.0, 0.0), 0.87, False),
    "T-MID": SpinTier("T-MID", (4,), 40, HANDS_PER_LEVEL, (1.0, 0.0, 0.0), 0.09, False),
    "T-DEEP": SpinTier("T-DEEP", (10,), 50, HANDS_PER_LEVEL, (0.8, 0.2, 0.0), 0.01, False),
}


def tier_for_multiplier(multiplier: int) -> SpinTier:
    """Tier ujawnionego multiplikatora — wybór artefaktu jest lookupem, nie liczeniem."""
    for tier in TIERS.values():
        if multiplier in tier.multipliers:
            return tier
    raise LookupError(f"multiplikator {multiplier} spoza tabeli tierów (25x+ odroczone)")


def tier_for_run(key: str, *, allow_unconfirmed: bool = False) -> SpinTier:
    """Tier do konfiguracji przebiegu solvera.

    Niepotwierdzony wiersz przechodzi wyłącznie z jawną flagą: przebieg tierowy
    kosztuje rdzenio-godziny, a tabela pochodzi ze źródeł wtórnych, więc cicha
    zgoda na niepotwierdzone liczby jest tu droższa niż zatrzymanie.
    """
    tier = TIERS[key]
    if not tier.confirmed and not allow_unconfirmed:
        raise UnconfirmedTierError(
            f"tier {key} nie jest potwierdzony wobec żywego lobby (wejście operatorskie, "
            "decyzja 29 pkt 6) — przebieg wymaga jawnego allow_unconfirmed=True"
        )
    return tier


SOLVER_MODES: tuple[str, ...] = ("deep", "jamfold", "hu-deep", "hu-jamfold")

# Equal-stack depths (bb=2). Classic Spin clock, chips scale.
DEPTHS: tuple[tuple[int, Stacks3], ...] = (
    (25, (50, 50, 50)),
    (15, (30, 30, 30)),
    (10, (20, 20, 20)),
    (6, (12, 12, 12)),
)


def roles(button: int) -> tuple[int, int, int]:
    """(utg, btn_sb, bb). Button posts SB; left of button is BB; other acts first."""
    if button not in (0, 1, 2):
        raise ValueError(f"button poza 3 miejscami: {button}")
    btn = button
    bb = (button + 1) % 3
    utg = (button + 2) % 3
    return utg, btn, bb


def blinds_for_hand(hand: int) -> tuple[int, int, int]:
    """(sb, bb, level). Level 0 = 1/2. Escalates every HANDS_PER_LEVEL hands."""
    if hand < 0:
        raise ValueError("numer ręki nie może być ujemny")
    level = min(hand // HANDS_PER_LEVEL, len(LEVELS) - 1)
    sb, bb = LEVELS[level]
    return sb, bb, level


def open_amount(bb: int) -> int:
    return max(bb * 2, int(round(bb * 2.2)))


def effective_bb(stacks: Stacks3, bb: int) -> float:
    if bb <= 0:
        raise ValueError(f"big blind musi być dodatni: {bb}")
    live = [s for s in stacks if s > 0]
    if not live:
        raise ValueError("brak żywych stacków przy stole")
    return min(live) / bb


def is_jam_fold_depth(stacks: Stacks3, bb: int) -> bool:
    return effective_bb(stacks, bb) <= JAM_FOLD_BB


def solver_mode(stacks: Stacks3, bb: int) -> str:
    """Tryb solvera stanu: liczba żywych × próg jam/fold — bez rozwiązywania stanu.

    Jedno źródło dla trzech rachunków, które muszą się zgadzać: mieszanka trybów
    w manifeście biegu, wycena kosztu per tryb i udział decyzyjny trybów
    w arenie. Rozjazd którejkolwiek z tych reguł byłby niewidoczny w wyniku.
    """
    alive = sum(1 for value in stacks if value > 0)
    jamfold = is_jam_fold_depth(stacks, bb)
    if alive == 3:
        return "jamfold" if jamfold else "deep"
    return "hu-jamfold" if jamfold else "hu-deep"


def post_blinds(
    stacks: Stacks3,
    button: int,
    sb: int = SMALL_BLIND,
    bb: int = BIG_BLIND,
) -> tuple[Stacks3, int]:
    _, btn, bb_seat = roles(button)
    behind = list(stacks)
    posted_sb = min(stacks[btn], sb)
    posted_bb = min(stacks[bb_seat], bb)
    behind[btn] -= posted_sb
    behind[bb_seat] -= posted_bb
    return (behind[0], behind[1], behind[2]), posted_sb + posted_bb


def award_allin(contributions: tuple[int, ...], ranks: tuple[int, ...]) -> tuple[int, ...]:
    """Niższy rank wygrywa. Nadpłata wraca. Side poty po poziomach wpłaty.

    Remis rang dzieli pulę (każdy side pot osobno) równo między zwycięzców;
    niepodzielna reszta żetonów trafia do zwycięzcy o najniższym indeksie
    miejsca — deterministycznie, żaden żeton nie ginie.
    """
    if len(contributions) != len(ranks):
        raise ValueError("wkłady i rangi muszą mieć tę samą długość")
    if any(amount < 0 for amount in contributions):
        raise ValueError("wkład nie może być ujemny")
    n = len(contributions)
    payouts = [0] * n
    contrib = list(contributions)
    ordered = sorted(contrib)
    uncalled = ordered[-1] - ordered[-2] if n >= 2 else (ordered[0] if ordered else 0)
    if uncalled:
        big = max(range(n), key=lambda i: contrib[i])
        payouts[big] += uncalled
        contrib[big] -= uncalled
    levels = sorted({amount for amount in contrib if amount > 0})
    prev = 0
    eligible = [i for i, amount in enumerate(contrib) if amount > 0]
    for level in levels:
        pot = (level - prev) * len(eligible)
        if pot:
            best = min(ranks[i] for i in eligible)
            winners = [i for i in eligible if ranks[i] == best]
            share, rem = divmod(pot, len(winners))
            for winner in winners:
                payouts[winner] += share
            if rem:
                payouts[min(winners)] += rem
        eligible = [i for i in eligible if contrib[i] > level]
        prev = level
    return tuple(payouts)


def utg_shove_both_fold(
    stacks: Stacks3,
    button: int,
    sb: int = SMALL_BLIND,
    bb: int = BIG_BLIND,
) -> Stacks3:
    behind, pot = post_blinds(stacks, button, sb, bb)
    utg, _, _ = roles(button)
    out = list(behind)
    out[utg] += pot
    return (out[0], out[1], out[2])


def utg_shove_called(
    stacks: Stacks3,
    button: int,
    caller: int,
    winner: int,
    sb: int = SMALL_BLIND,
    bb: int = BIG_BLIND,
) -> Stacks3:
    utg, btn, bb_seat = roles(button)
    if caller == utg:
        raise ValueError("caller nie może być UTG")
    contrib = [0, 0, 0]
    contrib[btn] += min(stacks[btn], sb)
    contrib[bb_seat] += min(stacks[bb_seat], bb)
    contrib[utg] = stacks[utg]
    already = contrib[caller]
    target = contrib[utg]
    add = max(0, min(stacks[caller] - already, target - already))
    contrib[caller] = already + add
    ranks = [1, 1, 1]
    ranks[winner] = 0
    awarded = award_allin((contrib[0], contrib[1], contrib[2]), (ranks[0], ranks[1], ranks[2]))
    return (
        stacks[0] - contrib[0] + awarded[0],
        stacks[1] - contrib[1] + awarded[1],
        stacks[2] - contrib[2] + awarded[2],
    )


def utg_shove_ev(
    stacks: Stacks3,
    button: int,
    prizes: tuple[float, float, float],
    caller: int,
    equity: float,
) -> tuple[float, float, float]:
    """$EV UTG: fold / jam obie fold / jam caller woła z danym equity.

    Gałąź fold zamyka rozdanie po stronie BTN/BB najprostszym legalnym
    rozstrzygnięciem: BTN też folduje i BB zgarnia pulę blindów — pełna
    księgowość żetonów (pod WTA fold to dokładnie udział żetonowy UTG).
    """
    if not 0.0 <= equity <= 1.0:
        raise ValueError(f"equity poza [0, 1]: {equity}")
    utg, _, bb_seat = roles(button)
    behind, pot = post_blinds(stacks, button)
    folded = list(behind)
    folded[bb_seat] += pot
    fold = icm_equities((folded[0], folded[1], folded[2]), prizes)[utg]
    shove_fold = icm_equities(utg_shove_both_fold(stacks, button), prizes)[utg]
    win = icm_equities(utg_shove_called(stacks, button, caller, utg), prizes)[utg]
    lose = icm_equities(utg_shove_called(stacks, button, caller, caller), prizes)[utg]
    return fold, shove_fold, equity * win + (1.0 - equity) * lose

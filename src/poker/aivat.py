"""AIVAT w przestrzeni nagród (POKER-53, decyzje 26 i 29 P-5).

Jednostka statystyczna = blok rotacji. Funkcja wartości zamrożona
i zhashowana przed danymi. V z profilu DBR nie zasila estymatora.
Zakaz Jensena: żadna ścieżka nie uśrednia żetonów przed mapowaniem
przez nagrody / ICM.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from poker.blueprint_reader import (
    PROFILE_BLUEPRINT,
    PROFILE_DBR,
    check_fingerprint,
    run_fingerprint,
)
from poker.icm import icm_equities

IDENTICAL_TENX_ROI = 10.0 / 3.0 - 1.0  # +233,(3)% przy puli 10 i buy-inie 1
GATE2_K = 3.0


class AivatError(ValueError):
    """Estymator odrzucił wejście, które złamałoby nieobciążoność."""


class JensenViolation(AivatError):
    """Próba redukcji wariancji w przestrzeni żetonów przed ICM/nagrodami."""


class FrozenValue:
    """Funkcja wartości zamknięta odciskiem zanim spadną dane ewaluacyjne."""

    def __init__(
        self,
        fingerprint: Mapping[str, object],
        value: Callable[[int, tuple[int, int, int]], tuple[float, float, float]],
    ) -> None:
        fp = dict(fingerprint)
        if fp.get("profile") == PROFILE_DBR:
            raise AivatError("V z profilu DBR nie zasila AIVAT (decyzja 29 pkt 3B)")
        fp.setdefault("profile", PROFILE_BLUEPRINT)
        check_fingerprint(fp, {"profile": PROFILE_BLUEPRINT})
        self.fingerprint = fp
        self._value = value
        payload = json.dumps(self.fingerprint, sort_keys=True, ensure_ascii=False)
        self.digest = hashlib.sha256(payload.encode()).hexdigest()

    def at(self, hand: int, stacks: tuple[int, int, int]) -> tuple[float, float, float]:
        prizes = self._value(hand, stacks)
        if len(prizes) != 3:
            raise AivatError("V musi zwracać trzy nagrody")
        return (float(prizes[0]), float(prizes[1]), float(prizes[2]))


def icm_value_fn(prizes: tuple[float, float, float]) -> FrozenValue:
    """Heurystyka V = ICM(stacków) w przestrzeni nagród — zamrożona przed danymi."""

    def value(_hand: int, stacks: tuple[int, int, int]) -> tuple[float, float, float]:
        raw = icm_equities(stacks, prizes)
        return (float(raw[0]), float(raw[1]), float(raw[2]))

    return FrozenValue(
        run_fingerprint(
            prizes=prizes,
            total_chips=1,
            levels=((0, 0),),
            hands_per_level=1,
            grid_step=1,
            source="icm",
        ),
        value,
    )


def map_stacks_to_prizes(
    stacks: tuple[int, int, int], prizes: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Terminal: miejsce wg stacków → nagroda. Bez uśredniania żetonów."""
    order = sorted(range(3), key=lambda seat: (-stacks[seat], seat))
    money = [0.0, 0.0, 0.0]
    for place, seat in enumerate(order):
        money[seat] = prizes[place]
    return (money[0], money[1], money[2])


def refuse_chip_expectation(chip_average: tuple[float, float, float]) -> None:
    """Strażnik zakazu Jensena: ułamkowy stack nie jest stanem turnieju."""
    if any(part != int(part) for part in chip_average):
        raise JensenViolation(
            "E[ICM(stack)] ≠ ICM(E[stack]) — nie wolno uśredniać żetonów przed nagrodami"
        )


@dataclass(frozen=True)
class Correction:
    """Jedna poprawka w przestrzeni nagród (szansa albo akcja hero)."""

    kind: str
    expected: float
    realized: float

    @property
    def amount(self) -> float:
        return self.expected - self.realized


def estimate(
    payoff: float,
    corrections: Sequence[Correction],
) -> float:
    """Nieobciążony estymator: wypłata + suma (E[V] − V zrealizowane)."""
    total = float(payoff)
    for item in corrections:
        if item.kind not in {"chance", "action"}:
            raise AivatError(f"nieznany rodzaj poprawki: {item.kind}")
        total += item.amount
    return total


def block_mean(values: Sequence[float]) -> float:
    if not values:
        raise AivatError("blok bez obserwacji")
    return sum(values) / len(values)


def sd_reduction(raw: Sequence[float], adjusted: Sequence[float]) -> float:
    """1 − sd(AIVAT)/sd(surowe); jednostka = blok, nie ręka."""
    if len(raw) != len(adjusted) or len(raw) < 2:
        raise AivatError("redukcja SD wymaga pary serii tej samej długości ≥ 2")
    return 1.0 - _sd(adjusted) / _sd(raw)


def gate2_holds(raw: Sequence[float], adjusted: Sequence[float], k: float = GATE2_K) -> bool:
    """|średnia AIVAT − surowa| < k · SE surowej."""
    if len(raw) != len(adjusted) or len(raw) < 2:
        raise AivatError("bramka 2 wymaga pary serii")
    diff = abs(block_mean(adjusted) - block_mean(raw))
    return diff < k * (_sd(raw) / len(raw) ** 0.5)


def _sd(xs: Sequence[float]) -> float:
    mean = block_mean(xs)
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    if var <= 0.0:
        return 0.0
    return var**0.5

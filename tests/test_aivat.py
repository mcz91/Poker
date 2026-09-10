"""AIVAT w przestrzeni nagród (POKER-53 plaster 1: estymator i bramki)."""

from __future__ import annotations

import random

import pytest

from poker.aivat import (
    GATE2_K,
    IDENTICAL_TENX_ROI,
    AivatError,
    Correction,
    FrozenValue,
    JensenViolation,
    estimate,
    gate2_holds,
    icm_value_fn,
    map_stacks_to_prizes,
    refuse_chip_expectation,
    sd_reduction,
)
from poker.blueprint_reader import PROFILE_BLUEPRINT, PROFILE_DBR, run_fingerprint
from poker.spin import PAYOUTS
from poker.spin_arena import always_jam, run_spin


def test_roi_trzech_identycznych_przy_10x_jest_dokladne() -> None:
    assert IDENTICAL_TENX_ROI == pytest.approx(7.0 / 3.0)
    assert IDENTICAL_TENX_ROI == pytest.approx(2.333333, abs=1e-6)


def test_dbr_nie_zasila_funkcji_wartosci() -> None:
    fp = run_fingerprint(
        prizes=(0.8, 0.2, 0.0),
        total_chips=150,
        levels=((1, 2),),
        hands_per_level=3,
        grid_step=2,
        profile=PROFILE_DBR,
    )
    with pytest.raises(AivatError, match="DBR"):
        FrozenValue(fp, lambda hand, stacks: (0.8, 0.2, 0.0))


def test_fingerprint_zamraza_v_przed_danymi() -> None:
    fp = run_fingerprint(
        prizes=(8.0, 2.0, 0.0),
        total_chips=150,
        levels=((1, 2),),
        hands_per_level=3,
        grid_step=2,
        profile=PROFILE_BLUEPRINT,
    )
    frozen = FrozenValue(fp, lambda hand, stacks: (8.0, 2.0, 0.0))
    again = FrozenValue(fp, lambda hand, stacks: (8.0, 2.0, 0.0))
    assert frozen.digest == again.digest
    assert frozen.digest != FrozenValue(
        run_fingerprint(
            prizes=(1.0, 0.0, 0.0),
            total_chips=150,
            levels=((1, 2),),
            hands_per_level=3,
            grid_step=2,
        ),
        lambda hand, stacks: (1.0, 0.0, 0.0),
    ).digest


def test_zakaz_jensena_odrzuca_sredni_stack() -> None:
    with pytest.raises(JensenViolation):
        refuse_chip_expectation((50.5, 49.5, 50.0))
    refuse_chip_expectation((50.0, 50.0, 50.0))


def test_terminal_mapuje_miejsca_nie_srednie_zetony() -> None:
    prizes = PAYOUTS["10x"].prizes
    assert map_stacks_to_prizes((100, 50, 0), prizes) == (8.0, 2.0, 0.0)


def test_dokladne_v_zeruje_wariancje_szansy() -> None:
    """Szansa 50/50, V dokładne → AIVAT = EV na każdej realizacji."""
    ev = 5.0
    raw: list[float] = []
    adj: list[float] = []
    rng = random.Random(3)
    for _ in range(40):
        realized = 8.0 if rng.random() < 0.5 else 2.0
        raw.append(realized)
        adj.append(estimate(realized, (Correction("chance", ev, realized),)))
    assert all(value == pytest.approx(ev) for value in adj)
    assert sd_reduction(raw, adj) == pytest.approx(1.0)
    assert gate2_holds(raw, adj, GATE2_K)
    assert sum(adj) / len(adj) == pytest.approx(ev)


def test_poprawka_akcji_nie_obciaza_przy_dokladnym_v() -> None:
    policy_ev = 4.0
    raw = [8.0, 0.0, 8.0, 0.0]
    adj = [estimate(pay, (Correction("action", policy_ev, pay),)) for pay in raw]
    assert all(value == pytest.approx(policy_ev) for value in adj)
    assert gate2_holds(raw, adj)


def test_arena_oddaje_granice_rozdan() -> None:
    seen: list[tuple[int, tuple[int, int, int], tuple[int, int, int]]] = []

    def collect(
        hand: int,
        before: tuple[int, int, int],
        after: tuple[int, int, int],
    ) -> None:
        seen.append((hand, before, after))

    stacks, _ = run_spin((always_jam(), always_jam(), always_jam()), 11, on_hand_end=collect)
    assert seen
    assert seen[0][1] == (50, 50, 50)
    assert seen[-1][2] == stacks
    assert icm_value_fn(PAYOUTS["10x"].prizes).at(0, (50, 50, 50))[0] == pytest.approx(
        10.0 / 3.0
    )

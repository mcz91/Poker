"""ROI arena: buy-in, not BB/100."""

from __future__ import annotations

from poker.arena import always_fold, always_jam, call_vs_random, play_spin, sample
from poker.openfold import _mass
from poker.spin import PAYOUTS


def test_trzech_jammerow_okolo_jednego_bi() -> None:
    jam = always_jam()
    hit = sample(jam, jam, PAYOUTS["3x"].prizes, n=80, seed=7)
    assert 0.6 < hit["mean_bi"] < 1.4


def test_foldbot_przegrywa_z_jammerem() -> None:
    hit = sample(always_fold(), always_jam(), PAYOUTS["3x"].prizes, n=60, seed=3)
    assert hit["mean_bi"] < 0.85


def test_spin_konczy_sie_wyplata() -> None:
    money = play_spin((always_jam(), always_jam(), always_jam()), PAYOUTS["3x"].prizes, 11)
    assert sum(money) == 3.0
    assert max(money) == 3.0


def test_call_vs_random_to_nie_jest_gto() -> None:
    mass = 100.0 * _mass(call_vs_random(0.50))
    assert 40.0 < mass < 58.0


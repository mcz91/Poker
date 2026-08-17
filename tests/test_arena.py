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


def test_dollar_fish_otwiera_za_szeroko() -> None:
    from poker.arena import dollar_fish
    from poker.openfold import threebet_vs_range

    fish = dollar_fish()
    assert 45.0 < 100.0 * _mass(fish.open) < 65.0
    assert 100.0 * _mass(fish.vs_open) < 100.0 * _mass(fish.open)
    hit = threebet_vs_range(
        fish.open, (50, 50, 50), PAYOUTS["3x"].prizes, continue_frac=0.45
    )
    assert 12.0 <= float(hit["btn_vs_open_pct"]) <= 40.0
    assert hit["aa_jams"]
    assert hit["junk_folds"]


def test_field_exploit_kradnie_szerzej() -> None:
    from poker.arena import field_exploit

    book = field_exploit()
    assert 40.0 < 100.0 * _mass(book.open) < 60.0
    assert 25.0 < 100.0 * _mass(book.vs_open) < 50.0
    assert 100.0 * _mass(book.vs_jam) > 35.0



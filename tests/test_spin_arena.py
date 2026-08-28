"""ROI arena: buy-in, not BB/100; determinizm INV-P1; ręka HU po wybiciu."""

from __future__ import annotations

import os
import random
import subprocess
import sys

from poker.openfold import _mass, threebet_vs_range
from poker.spin import PAYOUTS, STARTING_CHIPS
from poker.spin_arena import (
    _play_hand,
    always_fold,
    always_jam,
    call_vs_random,
    dollar_fish,
    field_exploit,
    play_spin,
    run_spin,
    sample,
)


def test_trzech_jammerow_okolo_jednego_bi() -> None:
    jam = always_jam()
    hit = sample(jam, jam, PAYOUTS["3x"].prizes, n=80, seed=7)
    assert 0.6 < hit["mean_bi"] < 1.4


def test_foldbot_przegrywa_z_jammerem() -> None:
    hit = sample(always_fold(), always_jam(), PAYOUTS["3x"].prizes, n=60, seed=3)
    assert hit["mean_bi"] < 0.85


def test_spin_konczy_sie_bustem_bez_utraty_zetonow() -> None:
    """Powód końca i suma żetonów — nie suma nagród, która jest tożsamością wypłat."""
    books = (always_jam(), always_jam(), always_jam())
    stacks, reason = run_spin(books, 11)
    assert reason == "bust"
    assert sum(stacks) == 3 * STARTING_CHIPS
    assert sorted(stacks) == [0, 0, 3 * STARTING_CHIPS]
    money = play_spin(books, PAYOUTS["3x"].prizes, 11)
    assert money[stacks.index(3 * STARTING_CHIPS)] == 3.0


def test_kazda_reka_areny_zachowuje_sume_zetonow() -> None:
    books = (field_exploit(), dollar_fish(), always_jam())
    for seed in range(20):
        rng = random.Random(seed)
        for stacks in ([50, 50, 50], [16, 50, 84], [3, 1, 146], [0, 60, 90]):
            for button in range(3):
                if stacks[button] <= 0:
                    continue
                out = _play_hand(list(stacks), button, 2, 4, books, rng)
                assert sum(out) == sum(stacks), (seed, stacks, button, out)
                assert all(s >= 0 for s in out)


def test_call_vs_random_to_nie_jest_gto() -> None:
    mass = 100.0 * _mass(call_vs_random(0.50))
    assert 40.0 < mass < 58.0


def test_dollar_fish_otwiera_za_szeroko() -> None:
    fish = dollar_fish()
    assert 45.0 < 100.0 * _mass(fish.open) < 65.0
    assert 100.0 * _mass(fish.vs_open) < 100.0 * _mass(fish.open)
    hit = threebet_vs_range(
        fish.open, (50, 50, 50), PAYOUTS["3x"].prizes, continue_frac=0.45
    )
    assert 12.0 <= hit.btn_vs_open_pct <= 40.0
    assert hit.aa_jams
    assert hit.junk_folds


def test_field_exploit_kradnie_szerzej() -> None:
    book = field_exploit()
    assert 40.0 < 100.0 * _mass(book.open) < 60.0
    assert 25.0 < 100.0 * _mass(book.vs_open) < 50.0
    assert 100.0 * _mass(book.vs_jam) > 35.0


def test_ten_sam_seed_daje_ten_sam_wynik_przy_roznym_hash_seed() -> None:
    """INV-P1: wynik spina zależy wyłącznie od seeda, nie od PYTHONHASHSEED procesu."""
    script = (
        "from poker.spin import PAYOUTS\n"
        "from poker.spin_arena import always_jam, play_spin\n"
        "books = (always_jam(), always_jam(), always_jam())\n"
        "print([play_spin(books, PAYOUTS['3x'].prizes, seed) for seed in range(5)])\n"
    )
    runs = [
        subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for hash_seed in ("1", "2")
    ]
    assert runs[0] == runs[1]


def test_reka_hu_po_wybiciu_bb_obaj_zywi_jamuja_dla_kazdego_buttona() -> None:
    """Wybite miejsce na nominalnym BB nie może gubić żywego gracza: pot się rozstrzyga."""
    books = (always_jam(), always_jam(), always_jam())
    for button in range(3):
        busted = (button + 1) % 3
        stacks = [10, 10, 10]
        stacks[busted] = 0
        # Seed 0: rozdania rozstrzygające (bez split potu) dla każdej pozycji buttona.
        out = _play_hand(stacks, button, 1, 2, books, random.Random(0))
        assert sorted(out) == [0, 0, 20], (button, out)
        assert out[busted] == 0


def test_reka_hu_po_wybiciu_bb_blindy_pobierane_z_zywych_miejsc() -> None:
    """Button płaci SB, drugi żywy gracz BB; fold buttona oddaje SB przeciwnikowi."""
    books = (always_fold(), always_fold(), always_fold())
    for button in range(3):
        busted = (button + 1) % 3
        other = (button + 2) % 3
        stacks = [10, 10, 10]
        stacks[busted] = 0
        out = _play_hand(stacks, button, 1, 2, books, random.Random(4))
        assert out[button] == 9, (button, out)
        assert out[other] == 11, (button, out)
        assert out[busted] == 0

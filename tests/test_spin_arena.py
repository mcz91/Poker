"""ROI arena: blok rotacji, wspólne seedy, bootstrap; determinizm INV-P1; ręka HU."""

from __future__ import annotations

import os
import random
import subprocess
import sys

import pytest

from poker.cards import Card
from poker.dealing import shuffled_deck
from poker.openfold import _mass, threebet_vs_range
from poker.spin import PAYOUTS, STARTING_CHIPS
from poker.spin_arena import (
    _play_hand,
    always_fold,
    always_jam,
    bootstrap_ci,
    call_vs_random,
    compare_blocks,
    dollar_fish,
    field_exploit,
    play_block,
    play_spin,
    run_spin,
    sample_blocks,
    sample_seat,
)


def test_trzech_jammerow_okolo_jednego_bi() -> None:
    jam = always_jam()
    hit = sample_blocks(jam, jam, PAYOUTS["3x"].prizes, n=30, seed=7)
    assert 0.6 < hit["mean_bi"] < 1.4


def test_foldbot_przegrywa_z_jammerem() -> None:
    hit = sample_blocks(always_fold(), always_jam(), PAYOUTS["3x"].prizes, n=20, seed=3)
    assert hit["mean_bi"] < 0.85


def test_rotacje_bloku_graja_te_same_karty() -> None:
    """Ten sam seed w trzech rotacjach: talia ręki i zależy tylko od (seed, i).

    Książki są asymetryczne, więc przebieg licytacji różni się między
    rotacjami — talie wspólnych rąk muszą mimo to być identyczne.
    """
    hero, villain = field_exploit(), dollar_fish()
    seat_books = (
        (hero, villain, villain),
        (villain, hero, villain),
        (villain, villain, hero),
    )
    decks: list[dict[int, tuple[Card, ...]]] = []
    for books in seat_books:
        seen: dict[int, tuple[Card, ...]] = {}
        run_spin(books, 5, on_deck=seen.__setitem__)
        decks.append(seen)
    common = min(len(seen) for seen in decks)
    assert common >= 2
    for hand_i in range(common):
        assert decks[0][hand_i] == decks[1][hand_i] == decks[2][hand_i], hand_i


def test_blok_to_srednia_hero_po_trzech_rotacjach() -> None:
    hero, villain = field_exploit(), always_jam()
    prizes = PAYOUTS["3x"].prizes
    rotations = [
        play_spin((hero, villain, villain), prizes, 9)[0],
        play_spin((villain, hero, villain), prizes, 9)[1],
        play_spin((villain, villain, hero), prizes, 9)[2],
    ]
    assert play_block(hero, villain, prizes, 9) == sum(rotations) / 3.0
    assert play_block(hero, villain, prizes, 9) == play_block(hero, villain, prizes, 9)


def test_sample_blocks_deterministyczne_z_bootstrapem() -> None:
    hit = sample_blocks(field_exploit(), always_jam(), PAYOUTS["3x"].prizes, n=12, seed=5)
    again = sample_blocks(field_exploit(), always_jam(), PAYOUTS["3x"].prizes, n=12, seed=5)
    assert hit == again
    assert hit["n"] == 12.0
    assert hit["ci_lo"] <= hit["roi"] <= hit["ci_hi"]
    assert hit["boot_lo"] <= hit["roi"] <= hit["boot_hi"]
    other = sample_blocks(
        field_exploit(), always_jam(), PAYOUTS["3x"].prizes, n=12, seed=5, bootstrap_seed=1
    )
    assert other["roi"] == hit["roi"]
    assert other["se"] == hit["se"]


def test_bootstrap_ci_deterministyczny_i_obejmuje_srednia_stalej_proby() -> None:
    xs = [0.0, 3.0, 0.0, 0.0, 3.0, 0.0, 3.0, 3.0, 0.0, 0.0]
    assert bootstrap_ci(xs, replications=500, seed=2) == bootstrap_ci(xs, replications=500, seed=2)
    lo, hi = bootstrap_ci(xs, replications=500, seed=2)
    assert lo <= sum(xs) / len(xs) <= hi
    assert bootstrap_ci([1.0, 1.0, 1.0, 1.0], replications=100, seed=0) == (1.0, 1.0)
    with pytest.raises(ValueError):
        bootstrap_ci([1.0], replications=100, seed=0)
    with pytest.raises(ValueError):
        bootstrap_ci(xs, replications=0, seed=0)


def test_compare_blocks_wspolne_seedy_znosza_identyczne_ramiona_do_zera() -> None:
    a = (field_exploit(), always_jam())
    hit = compare_blocks(a, a, PAYOUTS["3x"].prizes, n=8, seed=13)
    assert hit["diff"] == 0.0
    assert hit["se"] == 0.0
    assert (hit["ci_lo"], hit["ci_hi"]) == (0.0, 0.0)
    assert (hit["boot_lo"], hit["boot_hi"]) == (0.0, 0.0)


def test_compare_blocks_deterministyczne_i_spojne_z_ramionami() -> None:
    a = (field_exploit(), always_jam())
    b = (dollar_fish(), always_jam())
    hit = compare_blocks(a, b, PAYOUTS["3x"].prizes, n=10, seed=17)
    again = compare_blocks(a, b, PAYOUTS["3x"].prizes, n=10, seed=17)
    assert hit == again
    assert hit["diff"] == pytest.approx(hit["roi_a"] - hit["roi_b"])
    assert hit["ci_lo"] <= hit["diff"] <= hit["ci_hi"]


def test_sample_seat_mierzy_jedno_miejsce() -> None:
    prizes = PAYOUTS["3x"].prizes
    foldbot = sample_seat(always_fold(), always_jam(), prizes, n=20, seed=3, hero_seat=1)
    assert foldbot["mean_bi"] < 0.85
    assert foldbot["hero_seat"] == 1.0
    per_seat = [
        sample_seat(field_exploit(), always_jam(), prizes, n=20, seed=3, hero_seat=seat)
        for seat in range(3)
    ]
    for seat, hit in enumerate(per_seat):
        again = sample_seat(
            field_exploit(), always_jam(), prizes, n=20, seed=3, hero_seat=seat
        )
        assert hit == again
    # Te same seedy, inne miejsce: inne karty i pozycje, więc inny wynik.
    assert len({hit["mean_bi"] for hit in per_seat}) > 1


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
        deck = shuffled_deck(rng)
        for stacks in ([50, 50, 50], [16, 50, 84], [3, 1, 146], [0, 60, 90]):
            for button in range(3):
                if stacks[button] <= 0:
                    continue
                out = _play_hand(list(stacks), button, 2, 4, books, deck, rng)
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
    """INV-P1: wynik bloku zależy wyłącznie od seeda, nie od PYTHONHASHSEED procesu."""
    script = (
        "from poker.spin import PAYOUTS\n"
        "from poker.spin_arena import always_jam, field_exploit, play_block, play_spin\n"
        "books = (always_jam(), always_jam(), always_jam())\n"
        "print([play_spin(books, PAYOUTS['3x'].prizes, seed) for seed in range(5)])\n"
        "print([play_block(field_exploit(), always_jam(), PAYOUTS['3x'].prizes, seed)"
        " for seed in range(5)])\n"
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
        deck = shuffled_deck(random.Random(0))
        out = _play_hand(stacks, button, 1, 2, books, deck, random.Random(0))
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
        deck = shuffled_deck(random.Random(4))
        out = _play_hand(stacks, button, 1, 2, books, deck, random.Random(4))
        assert out[button] == 9, (button, out)
        assert out[other] == 11, (button, out)
        assert out[busted] == 0

"""Testy equity preflop (POKER-12): spójność macierzy, wartości odniesienia, reprodukcja."""

import random

from poker.cards import Rank
from poker.preflop import ALL_CLASSES, CLASS_INDEX, PreflopClass, class_combos
from poker.preflop_equity import equity
from poker.preflop_equity_data import (
    HALF_POT_UNITS,
    METHOD,
    SEED,
    TRIALS_PER_PAIR,
)
from poker.preflop_sim import pair_seed, simulate_pair_units

AA = PreflopClass(high=Rank.ACE, low=Rank.ACE, suited=False)
KK = PreflopClass(high=Rank.KING, low=Rank.KING, suited=False)
AKS = PreflopClass(high=Rank.ACE, low=Rank.KING, suited=True)
QQ = PreflopClass(high=Rank.QUEEN, low=Rank.QUEEN, suited=False)


def srednia_przeciw_polu(cls: PreflopClass) -> float:
    total = sum(len(class_combos(other)) * equity(cls, other) for other in ALL_CLASSES)
    return total / 1326


def test_metadane_metody_w_module_danych() -> None:
    assert METHOD == "monte-carlo"
    assert isinstance(SEED, int)
    assert TRIALS_PER_PAIR >= 1000
    assert len(HALF_POT_UNITS) == 169 * 169
    assert all(0 <= units <= 2 * TRIALS_PER_PAIR for units in HALF_POT_UNITS)


def test_suma_equity_obu_stron_rowna_dokladnie_1() -> None:
    for class_a in ALL_CLASSES:
        for class_b in ALL_CLASSES:
            assert equity(class_a, class_b) + equity(class_b, class_a) == 1.0


def test_equity_klasy_przeciw_samej_sobie_wynosi_dokladnie_pol() -> None:
    for cls in ALL_CLASSES:
        assert equity(cls, cls) == 0.5


def test_aa_ma_najwyzsza_srednia_equity_przeciw_polu() -> None:
    najlepsza = max(ALL_CLASSES, key=srednia_przeciw_polu)
    assert najlepsza == AA
    assert 0.83 <= srednia_przeciw_polu(AA) <= 0.87


def test_aa_przeciw_kk_w_przedziale_odniesienia() -> None:
    assert 0.79 <= equity(AA, KK) <= 0.84


def test_reprodukcja_podzbioru_z_tym_samym_seedem() -> None:
    for class_a, class_b in ((AA, KK), (AKS, QQ)):
        index_a, index_b = CLASS_INDEX[class_a], CLASS_INDEX[class_b]
        rng = random.Random(pair_seed(SEED, index_a, index_b))
        units = simulate_pair_units(class_a, class_b, rng=rng, trials=TRIALS_PER_PAIR)
        assert units == HALF_POT_UNITS[index_a * 169 + index_b]

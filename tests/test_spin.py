"""Spin 3-max: role, side pot all-in, EV shove UTG."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from poker.icm import wta_equities
from poker.spin import (
    BIG_BLIND,
    HANDS_PER_LEVEL,
    JAM_FOLD_BB,
    LEVELS,
    PAYOUTS,
    SMALL_BLIND,
    SOLVER_MODES,
    STARTING_CHIPS,
    TIERS,
    SpinTier,
    UnconfirmedTierError,
    award_allin,
    blinds_for_hand,
    effective_bb,
    is_jam_fold_depth,
    open_amount,
    post_blinds,
    roles,
    solver_mode,
    tier_for_multiplier,
    tier_for_run,
    utg_shove_both_fold,
    utg_shove_called,
    utg_shove_ev,
)


def test_role_button_jeden() -> None:
    utg, btn, bb = roles(1)
    assert (utg, btn, bb) == (0, 1, 2)


def test_post_blinds_25bb() -> None:
    behind, pot = post_blinds((STARTING_CHIPS,) * 3, 1)
    assert pot == SMALL_BLIND + BIG_BLIND
    assert behind == (50, 49, 48)


def test_zegar_eskaluje_co_trzy_rece() -> None:
    assert HANDS_PER_LEVEL == 3
    assert LEVELS == ((1, 2), (2, 4), (3, 6), (4, 8), (5, 10), (8, 16), (10, 20))
    assert blinds_for_hand(0) == (1, 2, 0)
    assert blinds_for_hand(2) == (1, 2, 0)
    assert blinds_for_hand(3) == (2, 4, 1)
    assert blinds_for_hand(18) == (10, 20, 6)
    assert blinds_for_hand(20) == (10, 20, 6)
    with pytest.raises(ValueError, match="ujemny"):
        blinds_for_hand(-1)


def test_push_fold_dopiero_przy_siedmiu_bb() -> None:
    assert JAM_FOLD_BB == 7
    assert open_amount(2) == 4
    assert not is_jam_fold_depth((50, 50, 50), 2)
    assert not is_jam_fold_depth((50, 50, 50), 6)
    assert is_jam_fold_depth((50, 50, 50), 8)
    assert is_jam_fold_depth((14, 50, 50), 2)
    assert effective_bb((50, 50, 50), 2) == 25.0
    assert effective_bb((50, 50, 50), 8) == 6.25


def test_effective_bb_odrzuca_zly_blind_i_pusty_stol() -> None:
    with pytest.raises(ValueError, match="dodatni"):
        effective_bb((50, 50, 50), 0)
    with pytest.raises(ValueError, match="dodatni"):
        effective_bb((50, 50, 50), -2)
    with pytest.raises(ValueError, match="żywych"):
        effective_bb((0, 0, 0), 2)


def test_post_blinds_poziom_dwa() -> None:
    behind, pot = post_blinds((50, 50, 50), 1, 2, 4)
    assert pot == 6
    assert behind == (50, 48, 46)


def test_award_rowny_trzy_way() -> None:
    assert award_allin((10, 10, 10), (0, 1, 2)) == (30, 0, 0)


def test_award_side_pot_krotki_wygrywa() -> None:
    assert award_allin((5, 10, 10), (0, 1, 2)) == (15, 10, 0)


def test_award_side_pot_krotki_przegrywa() -> None:
    assert award_allin((5, 10, 10), (2, 0, 1)) == (0, 25, 0)


def test_award_zwrot_nadplaty() -> None:
    assert award_allin((20, 10, 0), (0, 1, 2)) == (30, 0, 0)


def test_award_remis_pula_parzysta() -> None:
    assert award_allin((10, 10, 10), (0, 0, 1)) == (15, 15, 0)


def test_award_remis_pula_nieparzysta_reszta_do_najnizszego_miejsca() -> None:
    # Pula 15, dwóch zwycięzców: 7 + 7, niepodzielna reszta 1 do miejsca 0.
    assert award_allin((5, 5, 5), (0, 0, 1)) == (8, 7, 0)
    # Reszta idzie do najniższego indeksu wśród zwycięzców, nie przy stole.
    assert award_allin((5, 5, 5), (1, 0, 0)) == (0, 8, 7)


def test_utg_shove_obie_fold_zabiera_blindy() -> None:
    assert utg_shove_both_fold((50, 50, 50), 1) == (53, 49, 48)


def test_utg_shove_bb_wola_rowne_stacki() -> None:
    win = utg_shove_called((50, 50, 50), 1, caller=2, winner=0)
    lose = utg_shove_called((50, 50, 50), 1, caller=2, winner=2)
    assert win == (101, 49, 0)
    assert lose == (0, 49, 101)


def test_wta_fold_rowna_sie_dokladnie_udzialowi_zetonowemu() -> None:
    """Gałąź fold nie gubi żetonów blindów: pod WTA fold == udział żetonowy."""
    for stacks in ((50, 50, 50), (16, 50, 84)):
        fold, _, _ = utg_shove_ev(stacks, 1, PAYOUTS["3x"].prizes, caller=2, equity=0.5)
        utg = roles(1)[0]
        assert fold == pytest.approx(wta_equities(stacks, 3.0)[utg], abs=1e-12)


def test_wta_shove_fold_jest_dodatnie() -> None:
    fold, shove_fold, _ = utg_shove_ev(
        (50, 50, 50),
        1,
        PAYOUTS["3x"].prizes,
        caller=2,
        equity=0.5,
    )
    assert shove_fold > fold


def test_icm_10x_zmienia_ev_wzgledem_wta() -> None:
    stacks = (70, 20, 10)
    wta = utg_shove_ev(stacks, 1, PAYOUTS["3x"].prizes, caller=2, equity=0.5)
    icm = utg_shove_ev(stacks, 1, PAYOUTS["10x"].prizes, caller=2, equity=0.5)
    assert wta != icm


def test_spin_importuje_wylacznie_icm() -> None:
    path = Path(__file__).resolve().parent.parent / "src" / "poker" / "spin.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
    poker = {name for name in names if name.startswith("poker")}
    assert poker <= {"poker.icm"}


def test_tabela_tierow_niesie_ksztalt_znormalizowany_a_multiplikator_osobno() -> None:
    """Wektor wypłat tieru sumuje się do 1; multiplikator zostaje w tabeli.

    To jest cała pułapka normalizacji z decyzji 29 pkt 3A: ε jest w jednostkach
    sumy wektora wypłat, więc multiplikator wpuszczony do wektora dzieli ε i próg
    blokujący przez siebie. `PAYOUTS` (punktacja areny, ROI w buy-inach) niesie
    go świadomie i dlatego NIE jest wektorem dla solvera.
    """
    for key, tier in TIERS.items():
        assert abs(sum(tier.prizes) - 1.0) < 1e-12, key
        assert tier.total_chips == 3 * tier.start_stack
    assert {sum(PAYOUTS[key].prizes) for key in PAYOUTS} == {2.0, 3.0, 10.0}


def test_wiersz_tieru_odrzuca_wektor_nieznormalizowany() -> None:
    with pytest.raises(ValueError, match="nie do 1"):
        SpinTier("T-ZLY", (3,), 30, HANDS_PER_LEVEL, PAYOUTS["3x"].prizes, 0.5, False)


def test_tabela_tierow_zgadza_sie_z_decyzja_29() -> None:
    """Liczby wiersz po wierszu (decyzja 29 pkt 1 i 3A) — dokument ma tu niezmiennik."""
    modal, mid, deep = TIERS["T-MODAL"], TIERS["T-MID"], TIERS["T-DEEP"]
    assert (modal.multipliers, modal.total_chips, modal.prizes) == ((2, 3), 90, (1.0, 0.0, 0.0))
    assert (mid.multipliers, mid.total_chips, mid.prizes) == ((4,), 120, (1.0, 0.0, 0.0))
    assert (deep.multipliers, deep.total_chips, deep.prizes) == ((10,), 150, (0.8, 0.2, 0.0))
    assert (modal.volume_share, mid.volume_share, deep.volume_share) == (0.87, 0.09, 0.01)
    # T-DEEP to dzisiejszy artefakt produkcyjny: żetony i zegar mają się zgadzać
    # z tym, co bieg naprawdę policzył, inaczej tabela opisywałaby inną grę.
    assert deep.start_stack == STARTING_CHIPS and deep.hands_per_level == HANDS_PER_LEVEL
    assert tier_for_multiplier(2) is modal and tier_for_multiplier(3) is modal
    assert tier_for_multiplier(4) is mid and tier_for_multiplier(10) is deep
    with pytest.raises(LookupError):
        tier_for_multiplier(25)


def test_przebieg_z_niepotwierdzonej_tabeli_wymaga_jawnej_flagi() -> None:
    """Tabela jest wejściem operatorskim — dopóki nie potwierdzi, zgoda jest jawna."""
    assert not any(tier.confirmed for tier in TIERS.values())
    for key in TIERS:
        with pytest.raises(UnconfirmedTierError, match="allow_unconfirmed"):
            tier_for_run(key)
        assert tier_for_run(key, allow_unconfirmed=True) is TIERS[key]


def test_tryb_solvera_rozdziela_liczbe_zywych_i_prog_jamfold() -> None:
    """Reguła trybu jest jedna dla wyceny, manifestu i licznika areny."""
    assert set(SOLVER_MODES) == {"deep", "jamfold", "hu-deep", "hu-jamfold"}
    assert solver_mode((50, 50, 50), 2) == "deep"
    assert solver_mode((50, 50, 50), 10) == "jamfold"
    assert solver_mode((0, 75, 75), 2) == "hu-deep"
    assert solver_mode((0, 75, 75), 20) == "hu-jamfold"
    # Próg 7 bb liczy się z NAJKRÓTSZEGO żywego stacku, nie ze średniej.
    assert solver_mode((14, 68, 68), 2) == "jamfold"
    assert solver_mode((16, 67, 67), 2) == "deep"

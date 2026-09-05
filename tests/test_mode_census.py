"""Wycena przebiegu per tryb solvera (POKER-56): fixture rozstrzyga koszt deterministycznie.

Wycena mnożnikiem liczby stanów myliła panel projektowy w obie strony, bo koszt
stanu różni się między trybami o trzy rzędy wielkości. Każda liczba, która
z tego fixture'a trafiła do `docs/CURRENT_STATE.md`, ma tu asercję — inaczej
dokument mówiłby coś, czego następny bieg nie musi spełnić.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BLUEPRINT = REPO_ROOT / "tools" / "blueprint"


def _load(name: str) -> Any:
    """Moduł narzędzia po ścieżce — `tools` nie jest pakietem (jak w testach pilota)."""
    module = sys.modules.get(name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def census_table() -> dict[str, Any]:
    """Cała tabela wyceny liczona RAZ — to jest ta sama droga co komenda z dokumentu."""
    return dict(_load("mode_census").table())


def test_formula_stanow_siatki_zgadza_sie_z_decyzja_29() -> None:
    """(u+1)(u+2)/2 − 3 na trzech siatkach: 2 923 / 11 473 / 1 078 (decyzja 29 pkt 1)."""
    sg = _load("solve_grid")
    for total, step, expected in ((150, 2, 2923), (150, 1, 11473), (90, 2, 1078)):
        units = total // step
        assert len(sg.grid_states(total, step)) == (units + 1) * (units + 2) // 2 - 3
        assert len(sg.grid_states(total, step)) == expected


def test_populacje_trybow_odtwarzaja_bieg_produkcyjny(census_table: dict[str, Any]) -> None:
    """Zmierzona mieszanka trybów biegu produkcyjnego (blok POKER-50) wychodzi z fixture'a.

    To jest jedyny wiersz tabeli, dla którego istnieje POMIAR, więc jedyny, który
    sprawdza sam fixture: zgadzają się i rozmiary warstw przyciętych osiągalnością,
    i populacje czterech trybów, i mieszanka horyzontu.
    """
    row = census_table["rows"]["prod-10x"]
    assert row["states_per_layer"] == [1, 18, 147, 691, 2143, 2920] + [2923] * 15
    assert sum(row["states_per_layer"]) == 49765
    assert row["layer_modes"] == {
        "deep": 1198,
        "jamfold": 44550,
        "hu-deep": 932,
        "hu-jamfold": 3085,
    }
    # Horyzont: sześć cykli po trzy warstwy pełnej siatki przy blindach 10/20 —
    # przy 150 żetonach żaden stan nie jest głęboki, więc dwa tryby są zerami.
    assert row["boundary_modes"] == {
        "deep": 0,
        "jamfold": 48618,
        "hu-deep": 0,
        "hu-jamfold": 3996,
    }


def test_wycena_zgadza_sie_ze_zmierzonym_kosztem_biegu(census_table: dict[str, Any]) -> None:
    """Kalibracja na jedynym biegu, który naprawdę zapłacono (POKER-50 pkt 4a).

    Zmierzono: warstwy 40,2 rdzenio-h, horyzont 25,2, solver razem 65,4, całość
    z tensorem 76,6. Tempa per stan nie niosą narzutu forka (1,018), więc wycena
    ma być tuż PONIŻEJ pomiaru — kilka procent, nie kilkadziesiąt.
    """
    row = census_table["rows"]["prod-10x"]
    for predicted, measured in (
        (row["layers_core_hours"], 40.2),
        (row["boundary_core_hours"], 25.2),
        (row["solver_core_hours"], 65.4),
        (row["with_tensor_core_hours"], 76.6),
    ):
        assert predicted < measured, (predicted, measured)
        assert predicted > 0.95 * measured, (predicted, measured)


def test_tempa_sa_zmierzone_w_biegu_produkcyjnym(census_table: dict[str, Any]) -> None:
    """Tempa to pomiar POKER-50 pkt 3, nie priory pilota z bezpiecznika kosztu."""
    sg = _load("solve_grid")
    rates = census_table["rates_core_seconds_per_state"]
    assert rates == {"deep": 50.8, "jamfold": 1.83, "hu-deep": 0.054, "hu-jamfold": 0.018}
    assert rates != sg.MODE_COST_PRIORS
    assert rates["deep"] / rates["hu-jamfold"] > 1000.0


def test_populacje_pelnej_siatki_zgadzaja_sie_z_liczbami_decyzji_29() -> None:
    """T-MODAL, pełna siatka 90/2: 253/693/90/42 przy bb=2 i 1 deep / 945 jamfold przy bb=4."""
    mc = _load("mode_census")
    config = mc.tier_config("T-MODAL")
    assert mc.full_grid_census(config, 0) == {
        "deep": 253,
        "jamfold": 693,
        "hu-deep": 90,
        "hu-jamfold": 42,
    }
    at_bb4 = mc.full_grid_census(config, 3)
    assert (at_bb4["deep"], at_bb4["jamfold"]) == (1, 945)
    assert sum(at_bb4.values()) == 1078


def test_wycena_tierow_i_kroku_jeden_wchodzi_do_dokumentu(census_table: dict[str, Any]) -> None:
    """Liczby wierszy tabeli wyceny — te same, które niesie blok POKER-56."""
    rows = census_table["rows"]
    expected = {
        "T-MODAL": (9.2, 8.7, 17.8),
        "T-MID": (20.8, 15.7, 36.4),
        "WTA@25bb": (39.6, 24.7, 64.3),
        "krok-1": (151.2, 100.9, 252.1),
    }
    for name, (layers, boundary, solver) in expected.items():
        row = rows[name]
        assert row["layers_core_hours"] == pytest.approx(layers, abs=0.05), name
        assert row["boundary_core_hours"] == pytest.approx(boundary, abs=0.05), name
        assert row["solver_core_hours"] == pytest.approx(solver, abs=0.05), name
    assert rows["krok-1"]["with_tensor_core_hours"] == pytest.approx(263.3, abs=0.05)
    # Kolumny „stany-warstwy" i „deep" tej samej tabeli w dokumencie.
    populations = {
        "prod-10x": (49765, 1198),
        "WTA@25bb": (49765, 1198),
        "T-MODAL": (19129, 49),
        "T-MID": (32792, 421),
        "krok-1": (191028, 4268),
    }
    for name, (states, deep) in populations.items():
        modes = rows[name]["layer_modes"]
        assert sum(modes.values()) == states == sum(rows[name]["states_per_layer"]), name
        assert modes["deep"] == deep, name
    # DBR seat-restricted to trzy przebiegi hero na TYM SAMYM tensorze.
    assert rows["DBR-T-MODAL"]["solver_core_hours"] == pytest.approx(53.5, abs=0.05)
    assert rows["DBR-T-MODAL"]["with_tensor_core_hours"] == pytest.approx(64.7, abs=0.05)


def test_domkniecie_warstw_1_5_jest_glebokie_a_nie_proporcjonalne(
    census_table: dict[str, Any],
) -> None:
    """+8 696 stanów-warstw to +17,5% liczby stanów, ale +47,9 rdzenio-h, nie +13,4.

    Brakujące stany wczesnych warstw są w większości głębokie (3 212 z 8 696),
    a stan `deep` kosztuje 28× stan `jamfold` — dlatego mnożnik liczby stanów
    (0,175 × 76,6 = 13,4) mylił się tu ponad trzykrotnie.
    """
    row = census_table["rows"]["warstwy-1-5-do-pelnej-siatki"]
    assert row["gap_states"] == 8696
    assert row["gap_modes"] == {"deep": 3212, "jamfold": 5061, "hu-deep": 328, "hu-jamfold": 95}
    assert row["core_hours"] == pytest.approx(47.9, abs=0.05)
    assert row["core_hours"] > 3.0 * 0.175 * 76.6


def test_mnoznik_liczby_stanow_myli_sie_w_obie_strony(census_table: dict[str, Any]) -> None:
    """Dowód wprost, że wycena musi iść per tryb, a nie przez liczbę stanów.

    T-MODAL ma 0,38 stanów-warstw biegu produkcyjnego, a kosztuje 0,23 jego
    warstw (mnożnik zawyża); domknięcie warstw 1–5 ma 0,175 stanów, a kosztuje
    1,2 warstw biegu (mnożnik zaniża).
    """
    rows = census_table["rows"]
    prod, modal = rows["prod-10x"], rows["T-MODAL"]
    states_ratio = sum(modal["states_per_layer"]) / sum(prod["states_per_layer"])
    cost_ratio = modal["layers_core_hours"] / prod["layers_core_hours"]
    assert states_ratio == pytest.approx(0.384, abs=0.005)
    assert cost_ratio == pytest.approx(0.232, abs=0.005)
    gap = rows["warstwy-1-5-do-pelnej-siatki"]
    assert gap["gap_states"] / sum(prod["states_per_layer"]) == pytest.approx(0.175, abs=0.001)
    assert gap["core_hours"] / prod["layers_core_hours"] == pytest.approx(1.21, abs=0.01)


def test_ab_wyplat_jest_neutralne_kosztowo(census_table: dict[str, Any]) -> None:
    """Przejścia siatki nie zależą od wypłat, więc WTA@25bb kosztuje tyle co 80/20.

    To rozstrzyga wycenę P-7 (jednozmienny A/B wypłat) bez przebiegu: cena
    eksperymentu to cena drugiego biegu tej samej siatki, ani grosza więcej.
    """
    rows = census_table["rows"]
    assert rows["WTA@25bb"]["layer_modes"] == rows["prod-10x"]["layer_modes"]
    assert rows["WTA@25bb"]["boundary_modes"] == rows["prod-10x"]["boundary_modes"]
    assert rows["WTA@25bb"]["prizes"] == [1.0, 0.0, 0.0]
    assert rows["prod-10x"]["prizes"] == [0.8, 0.2, 0.0]


def test_wycena_buduje_konfiguracje_tieru_przez_jawna_flage() -> None:
    """Wycena tieru przechodzi tą samą bramką co przebieg — tabela jest niepotwierdzona."""
    mc = _load("mode_census")
    from poker.spin import UnconfirmedTierError

    config = mc.tier_config("T-MODAL")
    assert (config.total_chips, config.start_stacks, config.prizes) == (
        90,
        (30, 30, 30),
        (1.0, 0.0, 0.0),
    )
    with pytest.raises(UnconfirmedTierError):
        mc.tier_for_run("T-MODAL")

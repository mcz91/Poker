"""Testy CLI (POKER-9): punkt wejścia w procesie testów, wynik, eksport, błędy."""

from pathlib import Path

import pytest

from poker.adapters.cli import main
from poker.adapters.export import deserialize_match_history
from poker.projection import project


def test_mecz_z_domyslnymi_wartosciami_argumentow(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--seed", "7", "--hands", "5"]) == 0
    out = capsys.readouterr().out
    assert "rozdania: " in out
    assert "powód zakończenia: " in out
    assert "stacki końcowe: " in out


def test_eksport_do_pliku_z_round_tripem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "mecz.json"
    assert main(["--seed", "7", "--hands", "3", "--export", str(target)]) == 0
    histories = deserialize_match_history(target.read_text(encoding="utf-8"))
    assert len(histories) >= 1
    for history in histories:
        assert project(history).pot == 0


def test_eksport_bajt_w_bajt_dla_tych_samych_argumentow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    assert main(["--seed", "11", "--hands", "4", "--export", str(first)]) == 0
    assert main(["--seed", "11", "--hands", "4", "--export", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()


def test_wybor_agenta_wariantem_progow_zmienia_przebieg(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    default, aggressive = tmp_path / "rule.json", tmp_path / "aggressive.json"
    assert main(["--seed", "7", "--hands", "20", "--export", str(default)]) == 0
    assert (
        main(
            [
                "--seed",
                "7",
                "--hands",
                "20",
                "--agent1",
                "rule-aggressive",
                "--export",
                str(aggressive),
            ]
        )
        == 0
    )
    assert default.read_bytes() != aggressive.read_bytes()


def test_bledne_argumenty_daja_niezerowy_kod_i_komunikat(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--hands", "0"]) == 2
    assert "błąd" in capsys.readouterr().err
    assert main(["--agent0", "nieznany"]) == 2
    assert "błąd" in capsys.readouterr().err
    assert main(["--big-blind", "-2"]) == 2
    assert "błąd" in capsys.readouterr().err

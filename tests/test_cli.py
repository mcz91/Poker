"""Testy CLI (POKER-9, POKER-69): punkt wejścia w procesie testów, wynik, eksport, błędy,
domyślny seed."""

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


@pytest.mark.parametrize(
    "tryb",
    [
        ["--hands", "5", "--export", "{wyjscie}/mecz.json"],
        ["--series", "2", "--hands", "5"],
        ["--corpus", "{wyjscie}/korpus", "--matches", "2", "--hands", "5"],
    ],
    ids=["mecz-z-eksportem", "seria", "korpus"],
)
def test_bez_czlowieka_domyslny_seed_to_zero_bajt_w_bajt(
    tryb: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    przebiegi = []
    for nazwa, jawny_seed in (("domyslny", []), ("zero", ["--seed", "0"])):
        wyjscie = tmp_path / nazwa
        wyjscie.mkdir()
        argv = [argument.format(wyjscie=wyjscie) for argument in tryb]
        assert main([*argv, *jawny_seed]) == 0
        pliki = {
            str(plik.relative_to(wyjscie)): plik.read_bytes()
            for plik in sorted(wyjscie.rglob("*"))
            if plik.is_file()
        }
        przebiegi.append((capsys.readouterr().out.replace(str(wyjscie), "<wyjscie>"), pliki))
    assert przebiegi[0] == przebiegi[1]
    assert "seed meczu" not in przebiegi[0][0]


def test_bledne_argumenty_daja_niezerowy_kod_i_komunikat(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--hands", "0"]) == 2
    assert "błąd" in capsys.readouterr().err
    assert main(["--agent0", "nieznany"]) == 2
    assert "błąd" in capsys.readouterr().err
    assert main(["--big-blind", "-2"]) == 2
    assert "błąd" in capsys.readouterr().err

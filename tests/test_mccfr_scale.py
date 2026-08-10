"""Testy skali treningu MCCFR (POKER-24): wznowienia i zgodność z biegiem ciągłym."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
MALY_BIEG = ["--seed", "5", "--stack", "12", "12"]


def narzedzie(sciezka: Path | None = None) -> Any:
    spec = importlib.util.spec_from_file_location(
        "train_mccfr_scale", sciezka or REPO / "tools" / "train_mccfr.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wznowienie_daje_artefakt_identyczny_z_biegiem_ciaglym(tmp_path: Path) -> None:
    tool = narzedzie()
    ciagly = tmp_path / "ciagly.py"
    assert tool.main([*MALY_BIEG, "--iterations", "6", "--output", str(ciagly)]) == 0

    checkpoint = tmp_path / "stan.json"
    czesc = tmp_path / "czesc.py"
    assert tool.main([
        *MALY_BIEG, "--iterations", "2", "--checkpoint", str(checkpoint),
        "--checkpoint-every", "1", "--output", str(czesc),
    ]) == 0
    assert tool.read_checkpoint(checkpoint).done == 2

    wznowiony = tmp_path / "wznowiony.py"
    assert tool.main([
        *MALY_BIEG, "--iterations", "6", "--checkpoint", str(checkpoint),
        "--checkpoint-every", "1", "--resume", "--output", str(wznowiony),
    ]) == 0
    assert tool.read_checkpoint(checkpoint).done == 6
    assert wznowiony.read_bytes() == ciagly.read_bytes()
    assert czesc.read_bytes() != ciagly.read_bytes()


def test_wznowienie_w_wielu_krokach_jest_rownowazne(tmp_path: Path) -> None:
    tool = narzedzie()
    ciagly = tmp_path / "ciagly.py"
    assert tool.main([*MALY_BIEG, "--iterations", "6", "--output", str(ciagly)]) == 0

    checkpoint = tmp_path / "stan.json"
    wynik = tmp_path / "krokowy.py"
    for granica in (1, 3, 4, 6):
        argv = [
            *MALY_BIEG, "--iterations", str(granica), "--checkpoint", str(checkpoint),
            "--checkpoint-every", "1", "--output", str(wynik),
        ]
        if granica > 1:
            argv.append("--resume")
        assert tool.main(argv) == 0
    assert wynik.read_bytes() == ciagly.read_bytes()


def test_resume_bez_checkpointu_jest_bledem(tmp_path: Path) -> None:
    tool = narzedzie()
    with pytest.raises(SystemExit):
        tool.main([*MALY_BIEG, "--iterations", "2", "--resume",
                   "--output", str(tmp_path / "x.py")])
    with pytest.raises(SystemExit):
        tool.main([*MALY_BIEG, "--iterations", "2", "--resume",
                   "--checkpoint", str(tmp_path / "nie-ma.json"),
                   "--output", str(tmp_path / "x.py")])


def test_checkpoint_odrzuca_nieznana_wersje(tmp_path: Path) -> None:
    tool = narzedzie()
    checkpoint = tmp_path / "stan.json"
    checkpoint.write_text('{"checkpoint_version": 999, "done": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="wersj"):
        tool.read_checkpoint(checkpoint)


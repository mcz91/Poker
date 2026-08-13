"""Testy liniowego uśredniania MCCFR (POKER-29)."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
MALY_BIEG = ["--seed", "5", "--stack", "12", "12", "--iterations", "6"]


def narzedzie() -> Any:
    spec = importlib.util.spec_from_file_location(
        "train_mccfr_linear", REPO / "tools" / "train_mccfr.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_liniowe_rozni_sie_od_jednostajnego(tmp_path: Path) -> None:
    tool = narzedzie()
    lin = tmp_path / "lin.py"
    uni = tmp_path / "uni.py"
    assert tool.main([*MALY_BIEG, "--averaging", "linear", "--output", str(lin)]) == 0
    assert tool.main([*MALY_BIEG, "--averaging", "uniform", "--output", str(uni)]) == 0
    assert lin.read_bytes() != uni.read_bytes()
    assert "AVERAGING = 'linear'" in lin.read_text(encoding="utf-8")
    assert "AVERAGING = 'uniform'" in uni.read_text(encoding="utf-8")


def test_liniowe_wznowienie_identyczne_z_ciaglym(tmp_path: Path) -> None:
    tool = narzedzie()
    ciagly = tmp_path / "ciagly.py"
    assert tool.main([*MALY_BIEG, "--averaging", "linear", "--output", str(ciagly)]) == 0

    checkpoint = tmp_path / "stan.json"
    assert tool.main([
        *MALY_BIEG, "--iterations", "2", "--averaging", "linear",
        "--checkpoint", str(checkpoint), "--checkpoint-every", "1",
        "--output", str(tmp_path / "czesc.py"),
    ]) == 0
    wznowiony = tmp_path / "wznowiony.py"
    assert tool.main([
        *MALY_BIEG, "--averaging", "linear",
        "--checkpoint", str(checkpoint), "--checkpoint-every", "1",
        "--resume", "--output", str(wznowiony),
    ]) == 0
    assert wznowiony.read_bytes() == ciagly.read_bytes()


def test_resume_odrzuca_rozne_usrednianie(tmp_path: Path) -> None:
    tool = narzedzie()
    checkpoint = tmp_path / "stan.json"
    assert tool.main([
        "--seed", "5", "--stack", "12", "12", "--iterations", "2",
        "--averaging", "linear", "--checkpoint", str(checkpoint),
        "--output", str(tmp_path / "a.py"),
    ]) == 0
    with pytest.raises(ValueError, match="uśredniania"):
        tool.main([
            "--seed", "5", "--stack", "12", "12", "--iterations", "4",
            "--averaging", "uniform", "--checkpoint", str(checkpoint),
            "--resume", "--output", str(tmp_path / "b.py"),
        ])


def test_stary_checkpoint_v1_odrzucany(tmp_path: Path) -> None:
    tool = narzedzie()
    checkpoint = tmp_path / "stan.json"
    checkpoint.write_text(
        '{"checkpoint_version": 1, "done": 1, "regrets": {}, "average": {}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="wersj"):
        tool.read_checkpoint(checkpoint)

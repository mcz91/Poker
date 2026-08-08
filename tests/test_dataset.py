"""Testy pliku zbioru przykładów (POKER-15): round-trip, determinizm, błędy wejścia, CLI."""

import json
from pathlib import Path

import pytest

from poker.adapters.cli import main
from poker.adapters.corpus import MANIFEST_NAME, generate_corpus, read_corpus
from poker.adapters.dataset import extract_dataset, read_dataset
from poker.encoding import DATASET_VERSION, encode_hand
from poker.table import MatchConfig

CONFIG = MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=5)


def korpus(directory: Path, matches: int = 2) -> Path:
    generate_corpus(
        directory,
        config=CONFIG,
        agent_names=("rule", "rule-aggressive"),
        matches=matches,
        seed=5,
    )
    return directory


def test_ekstrakcja_z_korpusu_i_round_trip(tmp_path: Path) -> None:
    katalog = korpus(tmp_path / "korpus")
    plik = tmp_path / "zbior.json"
    report = extract_dataset(katalog, plik)
    examples = read_dataset(plik)
    assert report.examples == len(examples) > 0
    _, matches = read_corpus(katalog)
    expected = tuple(
        example
        for histories in matches
        for history in histories
        for example in encode_hand(history)
    )
    assert examples == expected
    assert report.matches == len(matches)
    assert report.hands == sum(len(histories) for histories in matches)
    doc = json.loads(plik.read_text(encoding="utf-8"))
    assert doc["dataset_version"] == DATASET_VERSION


def test_ten_sam_korpus_daje_plik_identyczny_bajt_w_bajt(tmp_path: Path) -> None:
    katalog = korpus(tmp_path / "korpus")
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    extract_dataset(katalog, first)
    extract_dataset(katalog, second)
    assert first.read_bytes() == second.read_bytes()


def test_istniejacy_plik_wyjsciowy_jest_bledem(tmp_path: Path) -> None:
    katalog = korpus(tmp_path / "korpus")
    plik = tmp_path / "zbior.json"
    plik.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="istnieje"):
        extract_dataset(katalog, plik)


def test_brak_lub_zla_wersja_manifestu_jest_bledem(tmp_path: Path) -> None:
    pusty = tmp_path / "pusty"
    pusty.mkdir()
    with pytest.raises(ValueError, match="manifest"):
        extract_dataset(pusty, tmp_path / "a.json")
    zly = korpus(tmp_path / "zly")
    manifest = json.loads((zly / MANIFEST_NAME).read_text(encoding="utf-8"))
    manifest["manifest_version"] = 999
    (zly / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="wersj"):
        extract_dataset(zly, tmp_path / "b.json")


def test_odczyt_odrzuca_zla_wersje_zbioru(tmp_path: Path) -> None:
    plik = tmp_path / "zbior.json"
    plik.write_text(
        json.dumps({"dataset_version": 999, "feature_names": [], "examples": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="wersj"):
        read_dataset(plik)


def test_zbior_przez_cli_z_raportem(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    katalog = korpus(tmp_path / "korpus")
    plik = tmp_path / "zbior.json"
    assert main(["--dataset", str(plik), "--from-corpus", str(katalog)]) == 0
    out = capsys.readouterr().out
    assert "przykładów: " in out
    assert "rozdań: " in out
    assert "meczów: 2" in out
    assert str(plik) in out
    assert len(read_dataset(plik)) > 0


def test_zbior_przez_cli_odrzuca_bledy_i_niespojne_flagi(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    katalog = korpus(tmp_path / "korpus")
    plik = tmp_path / "zbior.json"
    assert main(["--dataset", str(plik)]) == 2
    assert "from-corpus" in capsys.readouterr().err
    assert main(["--dataset", str(plik), "--from-corpus", str(tmp_path / "nie-ma")]) == 2
    assert "manifest" in capsys.readouterr().err
    for flaga in (["--human", "0"], ["--series", "2"], ["--corpus", str(tmp_path / "k")],
                  ["--export", str(tmp_path / "e.json")]):
        assert main(["--dataset", str(plik), "--from-corpus", str(katalog), *flaga]) == 2
        assert capsys.readouterr().err.strip()

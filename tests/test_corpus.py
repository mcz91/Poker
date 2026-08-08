"""Testy korpusu self-play (POKER-14): round-trip, determinizm, niezależność od procesów."""

import json
from pathlib import Path

import pytest

from poker.adapters.cli import main
from poker.adapters.corpus import (
    MANIFEST_NAME,
    MANIFEST_VERSION,
    corpus_match_seeds,
    generate_corpus,
    read_corpus,
)
from poker.adapters.registry import agent_registry
from poker.table import MatchConfig, play_match

CONFIG = MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=10)
AGENCI = ("rule", "rule-aggressive")


def wygeneruj(directory: Path, seed: int = 5, matches: int = 3, jobs: int = 1) -> None:
    generate_corpus(
        directory, config=CONFIG, agent_names=AGENCI, matches=matches, seed=seed, jobs=jobs
    )


def zawartosc(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


def test_round_trip_korpusu_odtwarza_wygenerowane_historie(tmp_path: Path) -> None:
    katalog = tmp_path / "korpus"
    wygeneruj(katalog)
    manifest, matches = read_corpus(katalog)
    assert manifest.match_config == CONFIG
    assert manifest.agents == AGENCI
    assert manifest.seed == 5
    assert manifest.matches == 3
    assert len(manifest.files) == 3
    registry = agent_registry()
    agents = (registry[AGENCI[0]], registry[AGENCI[1]])
    for seed, histories in zip(corpus_match_seeds(5, 3), matches, strict=True):
        assert histories == play_match(CONFIG, seed=seed, agents=agents).histories


def test_manifest_ma_wlasna_wersje_i_wylacznie_dane_niewyprowadzalne(tmp_path: Path) -> None:
    katalog = tmp_path / "korpus"
    wygeneruj(katalog)
    doc = json.loads((katalog / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert doc["manifest_version"] == MANIFEST_VERSION == 1
    assert set(doc) == {
        "manifest_version", "match_config", "agents", "seed", "matches", "files",
    }
    for name in doc["files"]:
        assert (katalog / name).is_file()


def test_ten_sam_seed_daje_korpus_identyczny_bajt_w_bajt(tmp_path: Path) -> None:
    pierwszy, drugi, inny = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    wygeneruj(pierwszy, seed=5)
    wygeneruj(drugi, seed=5)
    wygeneruj(inny, seed=6)
    assert zawartosc(pierwszy) == zawartosc(drugi)
    assert zawartosc(pierwszy) != zawartosc(inny)


def test_zawartosc_korpusu_niezalezna_od_liczby_procesow(tmp_path: Path) -> None:
    sekwencyjny, rownolegly = tmp_path / "seq", tmp_path / "par"
    wygeneruj(sekwencyjny, jobs=1, matches=4)
    wygeneruj(rownolegly, jobs=2, matches=4)
    assert zawartosc(sekwencyjny) == zawartosc(rownolegly)


def test_niepusty_katalog_docelowy_jest_bledem(tmp_path: Path) -> None:
    katalog = tmp_path / "korpus"
    katalog.mkdir()
    (katalog / "obcy.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="niepusty"):
        wygeneruj(katalog)


def test_nieznana_nazwa_agenta_jest_bledem(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="agent"):
        generate_corpus(
            tmp_path / "korpus",
            config=CONFIG,
            agent_names=("rule", "nie-ma"),
            matches=2,
            seed=5,
        )


def test_korpus_przez_cli_z_raportem(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    katalog = tmp_path / "korpus"
    argv = ["--corpus", str(katalog), "--matches", "2", "--seed", "5", "--hands", "10"]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "meczów: 2" in out
    assert "rozdań: " in out
    assert str(katalog) in out
    manifest, matches = read_corpus(katalog)
    assert manifest.matches == len(matches) == 2


def test_korpus_przez_cli_odrzuca_bledy_i_niespojne_flagi(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    katalog = tmp_path / "korpus"
    katalog.mkdir()
    (katalog / "obcy.txt").write_text("x", encoding="utf-8")
    assert main(["--corpus", str(katalog), "--matches", "2"]) == 2
    assert "niepusty" in capsys.readouterr().err
    assert main(["--corpus", str(tmp_path / "k1"), "--matches", "0"]) == 2
    assert "mecz" in capsys.readouterr().err
    assert main(["--corpus", str(tmp_path / "k2"), "--human", "0"]) == 2
    assert "human" in capsys.readouterr().err
    assert main(["--corpus", str(tmp_path / "k3"), "--series", "2"]) == 2
    assert "series" in capsys.readouterr().err
    assert main(["--corpus", str(tmp_path / "k4"), "--export", str(tmp_path / "e.json")]) == 2
    assert "export" in capsys.readouterr().err
    assert main(["--corpus", str(tmp_path / "k5"), "--big-blind", "0"]) == 2
    assert "blind" in capsys.readouterr().err
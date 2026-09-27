"""Testy granicy konfiguracji (POKER-78): każda ścieżka wejścia odrzuca small blind większy
od big blinda przez HandConfig.

Asercje wyłącznie na kod wyjścia, prefiks „błąd: ”, nazwy pól, brak plików i typ wiadomości:
brzmienie komunikatów, stdout i obsługę połączenia po błędzie zmieniają POKER-76 i POKER-77.
"""

import json
import socket
from pathlib import Path

import pytest

from poker.adapters.cli import main
from poker.adapters.corpus import MANIFEST_NAME, generate_corpus
from poker.adapters.lan_server import TableServer
from poker.adapters.protocol import PROTOCOL_VERSION
from poker.table import MatchConfig

KATALOG = "<katalog>"
ODWROCONE_BLINDY = ["--small-blind", "10", "--big-blind", "5"]


def blad_nazywa_oba_blindy(stderr: str) -> None:
    assert stderr.startswith("błąd: ")
    assert "small_blind" in stderr
    assert "big_blind" in stderr


@pytest.mark.parametrize(
    "tryb",
    [
        pytest.param(("--hands", "3"), id="mecz"),
        pytest.param(("--series", "2"), id="seria"),
        pytest.param(("--corpus", KATALOG, "--matches", "1"), id="korpus"),
    ],
)
def test_cli_odrzuca_small_blind_wiekszy_od_big_blinda(
    tryb: tuple[str, ...], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    katalog = tmp_path / "k"
    argv = [*ODWROCONE_BLINDY, *(str(katalog) if arg == KATALOG else arg for arg in tryb)]
    assert main(argv) == 2
    blad_nazywa_oba_blindy(capsys.readouterr().err)
    assert not katalog.exists() or not any(katalog.iterdir())


@pytest.mark.parametrize(
    ("plik", "klucze"),
    [
        pytest.param("match-000000.json", ("hands", 0, 0, "config"), id="plik-meczu"),
        pytest.param(MANIFEST_NAME, ("match_config",), id="manifest"),
    ],
)
def test_zbior_z_korpusu_z_odwroconymi_blindami_jest_bledem(
    plik: str,
    klucze: tuple[str | int, ...],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    korpus = tmp_path / "korpus"
    generate_corpus(
        korpus,
        config=MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=2),
        agent_names=("rule", "rule"),
        matches=1,
        seed=0,
    )
    sciezka = korpus / plik
    document = json.loads(sciezka.read_text(encoding="utf-8"))
    config = document
    for klucz in klucze:
        config = config[klucz]
    config["small_blind"], config["big_blind"] = 10, 5
    sciezka.write_text(json.dumps(document), encoding="utf-8")
    zbior = tmp_path / "zbior.json"
    assert main(["--dataset", str(zbior), "--from-corpus", str(korpus)]) == 2
    blad_nazywa_oba_blindy(capsys.readouterr().err)
    assert not zbior.exists()


def test_serwer_lan_odrzuca_create_z_small_blindem_wiekszym_od_big_blinda() -> None:
    server = TableServer()
    host, port = server.start()
    try:
        with (
            socket.create_connection((host, port), timeout=5) as connection,
            connection.makefile("rwb") as stream,
        ):
            request = {
                "v": PROTOCOL_VERSION,
                "type": "create",
                "small_blind": 10,
                "big_blind": 5,
                "stacks": [100, 100],
                "button": 0,
                "hand_limit": 1,
                "opponent": "rule",
            }
            stream.write(json.dumps(request).encode("utf-8") + b"\n")
            stream.flush()
            response = json.loads(stream.readline())
    finally:
        server.close()
    assert response["type"] == "error"
    assert "small_blind" in response["message"]
    assert "big_blind" in response["message"]

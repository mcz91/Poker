"""Testy LAN (POKER-21): stoły heads-up przez sieć, przeciek bajtów, izolacja stołów."""

import io
import json
import socket
import threading
from pathlib import Path

import pytest

from poker.adapters.cli import main
from poker.adapters.export import deserialize_match_history
from poker.adapters.human import card_token
from poker.adapters.lan_server import TableServer
from poker.adapters.protocol import PROTOCOL_VERSION
from poker.events import ActionTaken, ActionType, DeckSeeded, HoleCardsDealt
from poker.projection import project


class Stub:
    """Surowy klient protokołu; rejestruje pełny strumień bajtów od serwera."""

    def __init__(self, port: int) -> None:
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.file = self.sock.makefile("rwb")
        self.raw = b""

    def send(self, message: dict[str, object]) -> None:
        self.file.write(json.dumps(message).encode("utf-8") + b"\n")
        self.file.flush()

    def recv(self) -> dict[str, object]:
        line = self.file.readline()
        if not line:
            raise ConnectionError("serwer zamknął połączenie")
        self.raw += line
        parsed: dict[str, object] = json.loads(line)
        return parsed

    def close(self) -> None:
        # makefile duplikuje deskryptor — bez zamknięcia pliku FIN nie wychodzi
        self.file.close()
        self.sock.close()


def create_message(**overrides: object) -> dict[str, object]:
    message: dict[str, object] = {
        "v": PROTOCOL_VERSION,
        "type": "create",
        "small_blind": 1,
        "big_blind": 2,
        "stacks": [100, 100],
        "button": 0,
        "hand_limit": 1,
        "seed": 1,
        "opponent": "rule",
    }
    message.update(overrides)
    return message


def play_until_end(stub: Stub, script: list[str]) -> dict[str, object]:
    """Odpowiada na prompty kolejnymi liniami skryptu aż do końca meczu."""
    position = 0
    while True:
        message = stub.recv()
        match message["type"]:
            case "prompt":
                stub.send({"v": PROTOCOL_VERSION, "type": "input", "text": script[position]})
                position += 1
            case "match_end" | "opponent_left" | "error":
                return message
            case _:
                continue


def graj_odpornie(stub: Stub) -> dict[str, object]:
    """Call, a po komunikacie o nielegalnym wejściu check — deterministycznie do końca."""
    poprawka = False
    while True:
        message = stub.recv()
        match message["type"]:
            case "text":
                text = message["text"]
                assert isinstance(text, str)
                if "nieprawidłowe" in text:
                    poprawka = True
            case "prompt":
                stub.send({
                    "v": PROTOCOL_VERSION, "type": "input",
                    "text": "check" if poprawka else "call",
                })
                if poprawka:
                    poprawka = False
            case "match_end" | "opponent_left" | "error":
                return message
            case _:
                continue


def test_stol_czlowiek_vs_agent_z_przybitym_wynikiem() -> None:
    server = TableServer()
    try:
        _, port = server.start()
        stub = Stub(port)
        stub.send(create_message())
        created = stub.recv()
        assert created["type"] == "table_created"
        koniec = play_until_end(stub, ["call", "call", "call", "call"])
        assert koniec == {
            "v": PROTOCOL_VERSION, "type": "match_end",
            "stacks": [92, 108], "hands": 1, "reason": "hand_limit",
        }
        stub.close()
    finally:
        server.close()


def test_dwa_stoly_rownolegle_bez_pomieszania() -> None:
    server = TableServer()
    wyniki: dict[str, object] = {}
    try:
        _, port = server.start()

        def zagraj(nazwa: str, seed: int) -> None:
            stub = Stub(port)
            stub.send(create_message(seed=seed))
            assert stub.recv()["type"] == "table_created"
            wyniki[nazwa] = play_until_end(stub, ["call"] * 8)
            stub.close()

        pierwszy = threading.Thread(target=zagraj, args=("a", 1))
        drugi = threading.Thread(target=zagraj, args=("b", 5))
        pierwszy.start()
        drugi.start()
        pierwszy.join(timeout=15)
        drugi.join(timeout=15)
        koniec_a, koniec_b = wyniki["a"], wyniki["b"]
        assert isinstance(koniec_a, dict) and koniec_a["type"] == "match_end"
        assert isinstance(koniec_b, dict) and koniec_b["type"] == "match_end"
        assert koniec_a["stacks"] == [92, 108]  # seed 1, jak w teście pojedynczego stołu
        assert koniec_a["stacks"] != koniec_b["stacks"] or koniec_a == koniec_b
    finally:
        server.close()


def test_przeciek_bajtow_do_klienta_a(tmp_path: Path) -> None:
    server = TableServer(export_directory=tmp_path)
    try:
        _, port = server.start()
        stub_a = Stub(port)
        stub_a.send(create_message(opponent="human", seed=3))
        created = stub_a.recv()
        code = created["code"]
        stub_b = Stub(port)
        stub_b.send({"v": PROTOCOL_VERSION, "type": "join", "code": code})
        wyniki: dict[str, object] = {}

        watek_a = threading.Thread(target=lambda: wyniki.update(a=graj_odpornie(stub_a)))
        watek_b = threading.Thread(target=lambda: wyniki.update(b=graj_odpornie(stub_b)))
        watek_a.start()
        watek_b.start()
        watek_a.join(timeout=15)
        watek_b.join(timeout=15)
        koniec_a = wyniki["a"]
        assert isinstance(koniec_a, dict) and koniec_a["type"] == "match_end"

        eksporty = list(tmp_path.glob("*.json"))
        assert len(eksporty) == 1
        histories = deserialize_match_history(eksporty[0].read_text(encoding="utf-8"))
        for history in histories:
            assert project(history).pot == 0  # round-trip istniejącym parserem
        karty_b = {
            card_token(card)
            for history in histories
            for event in history
            if isinstance(event, HoleCardsDealt) and event.seat == 1
            for card in event.cards
        }
        seedy = {
            str(event.seed)
            for history in histories
            for event in history
            if isinstance(event, DeckSeeded)
        }
        tekst_a = stub_a.raw.decode("utf-8")
        for seed_text in seedy:
            assert seed_text not in tekst_a
        marker = tekst_a.find("koniec rozdania")
        assert marker != -1
        przed_showdownem = tekst_a[:marker]
        for token in karty_b:
            assert token not in przed_showdownem
            assert token in tekst_a[marker:]  # po CardsRevealed karty jawne widoczne
        stub_a.close()
        stub_b.close()
    finally:
        server.close()


def test_nielegalne_wejscie_bez_sladu_i_rozlaczenie_nie_klade_serwera(
    tmp_path: Path,
) -> None:
    server = TableServer(export_directory=tmp_path)
    try:
        _, port = server.start()
        stub = Stub(port)
        stub.send(create_message(seed=3))
        assert stub.recv()["type"] == "table_created"
        koniec = play_until_end(stub, ["xyzzy", "fold"])
        assert isinstance(koniec, dict) and koniec["type"] == "match_end"
        assert "nieprawidłowe wejście" in stub.raw.decode("utf-8")
        eksport = next(iter(tmp_path.glob("*.json")))
        history = deserialize_match_history(eksport.read_text(encoding="utf-8"))[0]
        akcje_czlowieka = [
            event for event in history
            if isinstance(event, ActionTaken) and event.seat == 0
        ]
        assert akcje_czlowieka == [ActionTaken(seat=0, action=ActionType.FOLD, amount=0)]
        stub.close()

        # rozłączenie w trakcie rozdania: przeciwnik dostaje komunikat, serwer żyje
        stub_a = Stub(port)
        stub_a.send(create_message(opponent="human", seed=3, hand_limit=10))
        code = stub_a.recv()["code"]
        stub_b = Stub(port)
        stub_b.send({"v": PROTOCOL_VERSION, "type": "join", "code": code})
        assert stub_a.recv()["type"] == "started"
        stub_b.close()
        komunikat = play_until_end(stub_a, ["call"] * 20)
        assert komunikat["type"] == "opponent_left"
        stub_a.close()

        kolejny = Stub(port)
        kolejny.send(create_message(seed=1))
        assert kolejny.recv()["type"] == "table_created"
        assert play_until_end(kolejny, ["call"] * 4)["type"] == "match_end"
        kolejny.close()
    finally:
        server.close()


def test_nieznana_wersja_protokolu_odrzucana_po_obu_stronach() -> None:
    server = TableServer()
    try:
        _, port = server.start()
        stub = Stub(port)
        stub.send(create_message(v=999))
        odpowiedz = stub.recv()
        assert odpowiedz["type"] == "error"
        message = odpowiedz["message"]
        assert isinstance(message, str) and "wersj" in message
        stub.close()
    finally:
        server.close()

    # strona kliencka: sfałszowany serwer wysyła nieznaną wersję
    listener = socket.create_server(("127.0.0.1", 0))
    _, fake_port = listener.getsockname()

    def fake_server() -> None:
        connection, _ = listener.accept()
        with connection, connection.makefile("rwb") as file:
            file.readline()
            file.write(json.dumps({"v": 999, "type": "table_created", "code": "X"}).encode()
                       + b"\n")
            file.flush()

    watek = threading.Thread(target=fake_server)
    watek.start()
    wynik = main(
        ["--connect", f"127.0.0.1:{fake_port}", "--opponent", "rule"],
        stdin=io.StringIO(""),
    )
    watek.join(timeout=10)
    listener.close()
    assert wynik != 0


def test_cli_connect_tworzy_stol_i_zwraca_wynik(capsys: pytest.CaptureFixture[str]) -> None:
    server = TableServer()
    try:
        _, port = server.start()
        wynik = main(
            ["--connect", f"127.0.0.1:{port}", "--opponent", "rule",
             "--hands", "1", "--seed", "1"],
            stdin=io.StringIO("call\ncall\ncall\ncall\n"),
        )
        out = capsys.readouterr().out
        assert wynik == 0
        assert "92" in out and "108" in out
        assert "hand_limit" in out
    finally:
        server.close()

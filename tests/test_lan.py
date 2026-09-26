"""Testy LAN (POKER-21, POKER-69): stoły heads-up przez sieć, przeciek bajtów, izolacja stołów,
seed meczu losowany przez serwer."""

import io
import json
import random
import re
import socket
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from poker.adapters import cli
from poker.adapters.cli import main
from poker.adapters.export import deserialize_match_history, serialize_match_history
from poker.adapters.human import HumanAgent, card_token
from poker.adapters.lan_server import TableServer
from poker.adapters.protocol import PROTOCOL_VERSION
from poker.adapters.registry import agent_registry
from poker.events import ActionTaken, ActionType, DeckSeeded, HoleCardsDealt
from poker.projection import project
from poker.table import MatchConfig, MatchResult, play_match


class Stub:
    """Surowy klient protokołu; rejestruje pełny strumień bajtów i wiadomości od serwera."""

    def __init__(self, port: int) -> None:
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.file = self.sock.makefile("rwb")
        self.raw = b""
        self.messages: list[dict[str, object]] = []

    def send(self, message: dict[str, object]) -> None:
        self.file.write(json.dumps(message).encode("utf-8") + b"\n")
        self.file.flush()

    def next_message(self) -> dict[str, object] | None:
        """Kolejna wiadomość albo None, gdy serwer zamknął połączenie."""
        line = self.file.readline()
        if not line:
            return None
        self.raw += line
        parsed: dict[str, object] = json.loads(line)
        self.messages.append(parsed)
        return parsed

    def recv(self) -> dict[str, object]:
        message = self.next_message()
        if message is None:
            raise ConnectionError("serwer zamknął połączenie")
        return message

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


def do_zamkniecia(stub: Stub) -> list[dict[str, object]]:
    """Czyta aż serwer zamknie połączenie; zwraca pełny strumień wiadomości."""
    while stub.next_message() is not None:
        pass
    return stub.messages


def graj_odpornie(stub: Stub) -> list[dict[str, object]]:
    """Call, a po komunikacie o nielegalnym wejściu check — deterministycznie, aż serwer
    zamknie połączenie; zwraca pełny strumień wiadomości."""
    poprawka = False
    while (message := stub.next_message()) is not None:
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
                poprawka = False
            case _:
                continue
    return stub.messages


def koniec_meczu(messages: list[dict[str, object]]) -> dict[str, object]:
    (koniec,) = [message for message in messages if message["type"] == "match_end"]
    return koniec


def mecz_silnika(seed: int, hand_limit: int, wejscie: str) -> MatchResult:
    """Ten sam mecz lokalnie: człowiek ze skryptu na miejscu 0, agent rule na miejscu 1."""
    return play_match(
        MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0,
                    hand_limit=hand_limit),
        seed=seed,
        agents=(
            HumanAgent(input_stream=io.StringIO(wejscie), output_stream=io.StringIO()),
            agent_registry()["rule"],
        ),
    )


def karty_z_eksportu(path: Path) -> list[tuple[int, tuple[str, ...]]]:
    return [
        (event.seat, tuple(card_token(card) for card in event.cards))
        for history in deserialize_match_history(path.read_text(encoding="utf-8"))
        for event in history
        if isinstance(event, HoleCardsDealt)
    ]


def test_stol_czlowiek_vs_agent_z_przybitym_wynikiem() -> None:
    server = TableServer(match_rng=random.Random(1))
    try:
        _, port = server.start()
        stub = Stub(port)
        stub.send(create_message())
        created = stub.recv()
        assert created["type"] == "table_created"
        koniec = koniec_meczu(graj_odpornie(stub))
        assert koniec == {
            "v": PROTOCOL_VERSION, "type": "match_end",
            "stacks": [92, 108], "hands": 1, "reason": "hand_limit",
        }
        stub.close()
    finally:
        server.close()


def test_kolejne_stoly_dostaja_kolejne_seedy_wstrzyknietego_generatora(tmp_path: Path) -> None:
    server = TableServer(export_directory=tmp_path, match_rng=random.Random(2026))
    kody: list[object] = []
    try:
        _, port = server.start()
        for _ in range(3):
            stub = Stub(port)
            stub.send(create_message(hand_limit=2))
            kody.append(stub.recv()["code"])
            play_until_end(stub, ["fold", "fold"])
            do_zamkniecia(stub)
            stub.close()
    finally:
        server.close()
    wzorzec = random.Random(2026)
    for kod in kody:
        oczekiwany = mecz_silnika(wzorzec.getrandbits(64), hand_limit=2, wejscie="fold\n" * 2)
        eksport = (tmp_path / f"{kod}.json").read_text(encoding="utf-8")
        assert eksport == serialize_match_history(oczekiwany.histories)


def test_domyslny_generator_meczow_to_64_bity_csprng_systemu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Entropia systemu to system zewnętrzny: podstawiamy ją, żeby zobaczyć, czy i ile z niej
    # serwer bierze.
    wartosc = 0xC0DE_5EED_1234_5678
    pobrania: list[int] = []

    def entropia(self: random.SystemRandom, k: int) -> int:
        pobrania.append(k)
        return wartosc

    monkeypatch.setattr(random.SystemRandom, "getrandbits", entropia)
    server = TableServer(export_directory=tmp_path)
    try:
        _, port = server.start()
        stub = Stub(port)
        stub.send(create_message(hand_limit=2))
        kod = stub.recv()["code"]
        play_until_end(stub, ["fold", "fold"])
        do_zamkniecia(stub)
        stub.close()
    finally:
        server.close()
    assert pobrania == [64]
    oczekiwany = mecz_silnika(wartosc, hand_limit=2, wejscie="fold\n" * 2)
    eksport = (tmp_path / f"{kod}.json").read_text(encoding="utf-8")
    assert eksport == serialize_match_history(oczekiwany.histories)


def test_identyczny_create_rozdaje_rozne_karty_a_seed_serwera_przybija_tylko_kody(
    tmp_path: Path,
) -> None:
    server = TableServer(seed=123, export_directory=tmp_path)
    kody: list[object] = []
    try:
        _, port = server.start()
        for _ in range(2):
            stub = Stub(port)
            stub.send(create_message(hand_limit=3))
            kody.append(stub.recv()["code"])
            play_until_end(stub, ["fold"] * 3)
            do_zamkniecia(stub)
            stub.close()
    finally:
        server.close()
    assert kody == ["BJC3QJD5", "76BPUUMM"]
    karty = [karty_z_eksportu(tmp_path / f"{kod}.json") for kod in kody]
    assert karty[0] != karty[1]


def test_serve_seed_w_cli_przybija_kody_nie_talie(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    przebiegi: list[tuple[object, Path]] = []

    class SesjaOperatora:
        """W miejscu czekania serwera CLI na Ctrl+C: jeden stół na nasłuchu, potem koniec."""

        def wait(self) -> None:
            adres = re.search(r":(\d+) ", capsys.readouterr().out)
            assert adres is not None
            stub = Stub(int(adres.group(1)))
            stub.send(create_message(hand_limit=3))
            kod = stub.recv()["code"]
            play_until_end(stub, ["fold"] * 3)
            do_zamkniecia(stub)
            stub.close()
            przebiegi.append((kod, tmp_path / str(len(przebiegi)) / f"{kod}.json"))

    monkeypatch.setattr(cli, "threading", SimpleNamespace(Event=SesjaOperatora))
    for numer in range(2):
        assert main([
            "--serve", "0", "--serve-host", "127.0.0.1", "--serve-seed", "123",
            "--export-dir", str(tmp_path / str(numer)),
        ]) == 0
    (kod_a, eksport_a), (kod_b, eksport_b) = przebiegi
    assert kod_a == kod_b == "BJC3QJD5"
    assert karty_z_eksportu(eksport_a) != karty_z_eksportu(eksport_b)


def test_dwa_stoly_rownolegle_bez_pomieszania() -> None:
    def bez_kodu(messages: list[dict[str, object]]) -> list[dict[str, object]]:
        return [{k: v for k, v in message.items() if k != "code"} for message in messages]

    # Referencja: ten sam generator meczów i ta sama kolejność create, stoły po kolei.
    server = TableServer(match_rng=random.Random(4))
    referencja = []
    try:
        _, port = server.start()
        for _ in range(2):
            stub = Stub(port)
            stub.send(create_message(hand_limit=3))
            referencja.append(bez_kodu(graj_odpornie(stub)))
            stub.close()
    finally:
        server.close()

    server = TableServer(match_rng=random.Random(4))
    strumienie: dict[int, list[dict[str, object]]] = {}
    try:
        _, port = server.start()
        stuby = []
        for _ in range(2):
            stub = Stub(port)
            stub.send(create_message(hand_limit=3))
            assert stub.recv()["type"] == "table_created"
            stuby.append(stub)

        def zagraj(numer: int) -> None:
            strumienie[numer] = graj_odpornie(stuby[numer])

        watki = [threading.Thread(target=zagraj, args=(numer,)) for numer in range(2)]
        for watek in watki:
            watek.start()
        for watek in watki:
            watek.join(timeout=15)
        for stub in stuby:
            stub.close()
    finally:
        server.close()
    assert [bez_kodu(strumienie[0]), bez_kodu(strumienie[1])] == referencja
    wynik_a, wynik_b = (koniec_meczu(strumien)["stacks"] for strumien in referencja)
    assert wynik_a != wynik_b


def test_przeciek_bajtow_do_obu_klientow_stolu_ludzi(tmp_path: Path) -> None:
    server = TableServer(export_directory=tmp_path, match_rng=random.Random(3))
    try:
        _, port = server.start()
        stub_a = Stub(port)
        stub_a.send(create_message(opponent="human"))
        created = stub_a.recv()
        code = created["code"]
        stub_b = Stub(port)
        stub_b.send({"v": PROTOCOL_VERSION, "type": "join", "code": code})
        strumienie: dict[str, list[dict[str, object]]] = {}

        watek_a = threading.Thread(target=lambda: strumienie.update(a=graj_odpornie(stub_a)))
        watek_b = threading.Thread(target=lambda: strumienie.update(b=graj_odpornie(stub_b)))
        watek_a.start()
        watek_b.start()
        watek_a.join(timeout=15)
        watek_b.join(timeout=15)
        # pełne strumienie: oba wątki doczytały do zamknięcia połączenia przez serwer
        assert koniec_meczu(strumienie["a"]) == koniec_meczu(strumienie["b"])

        eksporty = list(tmp_path.glob("*.json"))
        assert len(eksporty) == 1
        histories = deserialize_match_history(eksporty[0].read_text(encoding="utf-8"))
        for history in histories:
            assert project(history).pot == 0  # round-trip istniejącym parserem
        seedy = {str(random.Random(3).getrandbits(64))} | {
            str(event.seed)
            for history in histories
            for event in history
            if isinstance(event, DeckSeeded)
        }
        for stub, rywal in ((stub_a, 1), (stub_b, 0)):
            karty_rywala = {
                card_token(card)
                for history in histories
                for event in history
                if isinstance(event, HoleCardsDealt) and event.seat == rywal
                for card in event.cards
            }
            tekst = stub.raw.decode("utf-8")
            for seed_text in seedy:
                assert seed_text not in tekst
            marker = tekst.find("koniec rozdania")
            assert marker != -1
            przed_showdownem = tekst[:marker]
            for token in karty_rywala:
                assert token not in przed_showdownem
                assert token in tekst[marker:]  # po CardsRevealed karty jawne widoczne
        stub_a.close()
        stub_b.close()
    finally:
        server.close()


def test_nielegalne_wejscie_bez_sladu_i_rozlaczenie_nie_klade_serwera(
    tmp_path: Path,
) -> None:
    server = TableServer(export_directory=tmp_path, match_rng=random.Random(3))
    try:
        _, port = server.start()
        stub = Stub(port)
        stub.send(create_message())
        assert stub.recv()["type"] == "table_created"
        koniec = play_until_end(stub, ["xyzzy", "fold"])
        assert isinstance(koniec, dict) and koniec["type"] == "match_end"
        do_zamkniecia(stub)
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
        stub_a.send(create_message(opponent="human", hand_limit=10))
        code = stub_a.recv()["code"]
        stub_b = Stub(port)
        stub_b.send({"v": PROTOCOL_VERSION, "type": "join", "code": code})
        assert stub_a.recv()["type"] == "started"
        stub_b.close()
        komunikat = play_until_end(stub_a, ["call"] * 20)
        assert komunikat["type"] == "opponent_left"
        stub_a.close()

        kolejny = Stub(port)
        kolejny.send(create_message())
        assert kolejny.recv()["type"] == "table_created"
        assert koniec_meczu(graj_odpornie(kolejny))["type"] == "match_end"
        kolejny.close()
    finally:
        server.close()


@pytest.mark.parametrize("obca_wersja", [1, 999])
def test_obca_wersja_protokolu_odrzucana_po_obu_stronach(
    obca_wersja: int, capsys: pytest.CaptureFixture[str]
) -> None:
    # strona serwera: klient obcej wersji z create z polem seed (tak mówił klient v1)
    server = TableServer()
    try:
        _, port = server.start()
        stub = Stub(port)
        stub.send(create_message(v=obca_wersja, seed=1))
        odpowiedz = stub.recv()
        assert odpowiedz["type"] == "error"
        message = odpowiedz["message"]
        assert isinstance(message, str) and "wersj" in message
        stub.close()
    finally:
        server.close()

    # strona kliencka: sfałszowany serwer obcej wersji
    listener = socket.create_server(("127.0.0.1", 0))
    _, fake_port = listener.getsockname()

    def fake_server() -> None:
        connection, _ = listener.accept()
        with connection, connection.makefile("rwb") as file:
            file.readline()
            file.write(
                json.dumps({"v": obca_wersja, "type": "table_created", "code": "X"}).encode()
                + b"\n"
            )
            file.flush()

    watek = threading.Thread(target=fake_server)
    watek.start()
    wynik = main(
        ["--connect", f"127.0.0.1:{fake_port}", "--opponent", "rule"],
        stdin=io.StringIO(""),
    )
    watek.join(timeout=10)
    listener.close()
    assert wynik == 2
    assert "wersj" in capsys.readouterr().out


def test_create_z_polem_seed_odrzucany() -> None:
    server = TableServer()
    try:
        _, port = server.start()
        stub = Stub(port)
        stub.send(create_message(seed=1))
        odpowiedz = stub.recv()
        assert odpowiedz["type"] == "error"
        message = odpowiedz["message"]
        assert isinstance(message, str) and "seed" in message
        stub.close()
    finally:
        server.close()


def test_cli_connect_wysyla_create_bez_seeda(capsys: pytest.CaptureFixture[str]) -> None:
    listener = socket.create_server(("127.0.0.1", 0))
    _, fake_port = listener.getsockname()
    zadania: list[dict[str, object]] = []

    def fake_server() -> None:
        connection, _ = listener.accept()
        with connection, connection.makefile("rwb") as file:
            zadania.append(json.loads(file.readline()))

    watek = threading.Thread(target=fake_server)
    watek.start()
    main(
        ["--connect", f"127.0.0.1:{fake_port}", "--opponent", "rule", "--hands", "3"],
        stdin=io.StringIO(""),
    )
    watek.join(timeout=10)
    listener.close()
    assert zadania == [{
        "v": PROTOCOL_VERSION, "type": "create", "small_blind": 1, "big_blind": 2,
        "stacks": [100, 100], "button": 0, "hand_limit": 3, "opponent": "rule",
    }]


@pytest.mark.parametrize("dolaczenie", [[], ["--join", "ABCDEFGH"]])
def test_cli_connect_z_jawnym_seedem_konczy_sie_bledem(
    dolaczenie: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    # Port bez nasłuchu: próba połączenia wywróciłaby main wyjątkiem, więc błąd musi paść
    # przed nią.
    zwolniony = socket.create_server(("127.0.0.1", 0))
    _, port = zwolniony.getsockname()
    zwolniony.close()
    wynik = main(
        ["--connect", f"127.0.0.1:{port}", "--seed", "0", *dolaczenie],
        stdin=io.StringIO(""),
    )
    err = capsys.readouterr().err
    assert wynik == 2
    assert "--seed" in err and "serwer" in err


def test_cli_connect_tworzy_stol_i_zwraca_wynik(capsys: pytest.CaptureFixture[str]) -> None:
    wejscie = "call\ncheck\n" * 10
    server = TableServer(match_rng=random.Random(1))
    try:
        _, port = server.start()
        wynik = main(
            ["--connect", f"127.0.0.1:{port}", "--opponent", "rule", "--hands", "1"],
            stdin=io.StringIO(wejscie),
        )
        out = capsys.readouterr().out
        assert wynik == 0
        oczekiwany = mecz_silnika(random.Random(1).getrandbits(64), hand_limit=1, wejscie=wejscie)
        assert f"koniec meczu: stacki {list(oczekiwany.stacks)}, rozdań 1" in out
        assert "hand_limit" in out
    finally:
        server.close()

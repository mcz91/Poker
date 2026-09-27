"""Testy odporności serwera LAN (POKER-76): wadliwy klient, agent, gniazdo ani eksport nie
wyłączają serwera — awaria kończy wyłącznie dotknięty stół komunikatem do jego graczy
i zamknięciem ich połączeń, a wejście klienta ma jawne granice."""

import io
import json
import random
import socket
import threading
import time
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest

from poker.adapters import lan_server, protocol
from poker.adapters.lan_server import TableServer
from poker.adapters.protocol import PROTOCOL_VERSION, MessageStream, read_message
from poker.adapters.registry import agent_registry
from poker.agent import Agent, Decision
from poker.events import HandEvent
from poker.views import PlayerView

# Granica przybita literalnie w teście *_przybity; tu literał, żeby strażnik granicy mówił
# prawdę także o kodzie sprzed stałej, a czerwień na nim wskazywała zachowanie.
LIMIT_LINII = 65_536


class Klient:
    """Surowy klient protokołu z timeoutem gniazda; zapisuje pełny strumień bajtów od serwera."""

    def __init__(self, port: int, timeout: float = 5.0) -> None:
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.file = self.sock.makefile("rwb")
        self.raw = b""

    def wyslij_bajty(self, dane: bytes) -> None:
        self.file.write(dane)
        self.file.flush()

    def wyslij(self, message: dict[str, object]) -> None:
        self.wyslij_bajty(json.dumps(message).encode("utf-8") + b"\n")

    def nastepna(self) -> dict[str, object] | None:
        """Kolejna wiadomość albo None na końcu strumienia (b'' albo RST); gdy nie ma ani
        jednego, ani drugiego przed timeoutem gniazda, test pada na TimeoutError."""
        try:
            line = self.file.readline()
        except ConnectionResetError:
            return None
        self.raw += line
        if not line:
            return None
        parsed: dict[str, object] = json.loads(line)
        return parsed

    def odbierz(self) -> dict[str, object]:
        message = self.nastepna()
        assert message is not None, "koniec strumienia zamiast wiadomości"
        return message

    def do_konca(self) -> list[dict[str, object]]:
        wiadomosci = []
        while (message := self.nastepna()) is not None:
            wiadomosci.append(message)
        return wiadomosci

    def close(self) -> None:
        self.file.close()
        self.sock.close()


@contextmanager
def nasluch(server: TableServer) -> Iterator[int]:
    _, port = server.start()
    try:
        yield port
    finally:
        server.close()


def create(**overrides: object) -> dict[str, object]:
    message: dict[str, object] = {
        "v": PROTOCOL_VERSION, "type": "create", "small_blind": 1, "big_blind": 2,
        "stacks": [100, 100], "button": 0, "hand_limit": 1, "opponent": "rule",
    }
    message.update(overrides)
    return message


def dopelniona(message: dict[str, object], dlugosc: int, koniec: bytes = b"\n") -> bytes:
    """Wiadomość dopełniona spacjami do dokładnie `dlugosc` bajtów łącznie z końcem linii."""
    tresc = json.dumps(message).encode("utf-8")
    wynik = tresc + b" " * (dlugosc - len(tresc) - len(koniec)) + koniec
    assert len(wynik) == dlugosc
    return wynik


def utworz(port: int, **overrides: object) -> tuple[Klient, str]:
    klient = Klient(port)
    klient.wyslij(create(**overrides))
    created = klient.odbierz()
    assert created["type"] == "table_created", created
    code = created["code"]
    assert isinstance(code, str)
    return klient, code


# --- N-01: limit linii czytanej przez serwer ------------------------------------------------


def test_limit_linii_serwera_przybity() -> None:
    assert protocol.MAX_LINE_BYTES == LIMIT_LINII == 65_536


def test_create_dokladnie_na_limicie_linii_tworzy_stol() -> None:
    with nasluch(TableServer()) as port:
        klient = Klient(port)
        klient.wyslij_bajty(dopelniona(create(), LIMIT_LINII))
        assert klient.odbierz()["type"] == "table_created"
        klient.close()


def test_linia_o_bajt_dluzsza_niz_limit_dostaje_error_z_limitem() -> None:
    with nasluch(TableServer()) as port:
        klient = Klient(port)
        klient.wyslij_bajty(dopelniona(create(), LIMIT_LINII + 1))
        odpowiedz = klient.odbierz()
        assert odpowiedz["type"] == "error", odpowiedz
        assert str(LIMIT_LINII) in str(odpowiedz["message"])
        assert klient.nastepna() is None
        klient.close()


def test_linia_ponad_limit_bez_konca_linii_odrzucona_bez_czekania_a_inni_obsluzeni() -> None:
    with nasluch(TableServer()) as port:
        klient = Klient(port)
        klient.wyslij_bajty(dopelniona(create(), LIMIT_LINII + 1, koniec=b""))
        drugi, _ = utworz(port)
        odpowiedz = klient.odbierz()
        assert odpowiedz["type"] == "error", odpowiedz
        assert str(LIMIT_LINII) in str(odpowiedz["message"])
        assert klient.nastepna() is None
        klient.close()
        drugi.close()


def test_error_dociera_przed_czystym_koncem_strumienia_mimo_nadmiaru_danych() -> None:
    # Zamknięcie z nieprzeczytanym nadmiarem wysłałoby RST zamiast końca strumienia.
    with nasluch(TableServer()) as port:
        klient = Klient(port)
        nadmiar = b" " * 100_000
        klient.wyslij_bajty(dopelniona(create(), LIMIT_LINII + 1, koniec=b"") + nadmiar)
        assert klient.odbierz()["type"] == "error"
        assert klient.file.readline() == b""
        klient.close()


def test_read_message_bez_limitu_czyta_linie_dluzsza_niz_limit_serwera() -> None:
    tekst: dict[str, object] = {"v": PROTOCOL_VERSION, "type": "text", "text": "x"}
    strumien: MessageStream = io.BytesIO(dopelniona(tekst, 2 * LIMIT_LINII))
    assert read_message(strumien) == tekst


# --- I-01: wyjątek kończy wyłącznie stół — komunikatem i zamknięciem połączeń ---------------

ZNACZNIK = "znacznik-awarii-7f3c1e"
ZAGNIEZDZONY_JSON = b"[" * 20_000 + b"\n"
GRANICA_ZETONOW = 2**52  # literał z tego samego powodu co LIMIT_LINII


def join(code: str) -> dict[str, object]:
    return {"v": PROTOCOL_VERSION, "type": "join", "code": code}


def wejscie(text: object) -> dict[str, object]:
    return {"v": PROTOCOL_VERSION, "type": "input", "text": text}


def linia(message: dict[str, object]) -> bytes:
    return json.dumps(message).encode("utf-8") + b"\n"


def typy(wiadomosci: Sequence[dict[str, object]]) -> list[object]:
    return [message["type"] for message in wiadomosci]


def blad_wewnetrzny() -> dict[str, object]:
    return {
        "v": PROTOCOL_VERSION, "type": "error", "message": lan_server.INTERNAL_ERROR_MESSAGE,
    }


def pasuj_do_konca(klient: Klient, zwloka: float = 0.0) -> list[dict[str, object]]:
    """Pasuje na każdy prompt (na pierwszy po `zwloka` s) aż serwer zamknie połączenie."""
    wiadomosci = []
    while (message := klient.nastepna()) is not None:
        wiadomosci.append(message)
        if message["type"] == "prompt":
            time.sleep(zwloka)
            zwloka = 0.0
            klient.wyslij(wejscie("fold"))
    return wiadomosci


def do_promptu(klient: Klient) -> None:
    while klient.odbierz()["type"] != "prompt":
        pass


def join_odrzucony(port: int, code: str) -> None:
    """Rejestr obserwowany z zewnątrz: stół o tym kodzie nie czeka na gracza."""
    klient = Klient(port)
    klient.wyslij(join(code))
    odpowiedz = klient.odbierz()
    assert odpowiedz["type"] == "error", odpowiedz
    assert "nie czeka na gracza" in str(odpowiedz["message"])
    assert klient.nastepna() is None
    klient.close()


def serwer_przyjmuje_stol(port: int) -> None:
    klient, _ = utworz(port)
    assert typy(pasuj_do_konca(klient))[-1] == "match_end"
    klient.close()


def json_rzuca_recursion_error_w_watku(dane: bytes) -> bool:
    # Warunek wstępny: bez RecursionError przypadek nie sprawdza ścieżki, którą deklaruje.
    wynik: list[bool] = []

    def parsuj() -> None:
        try:
            json.loads(dane)
        except RecursionError:
            wynik.append(True)

    watek = threading.Thread(target=parsuj)
    watek.start()
    watek.join()
    return wynik == [True]


def test_zagniezdzony_json_jako_pierwsza_wiadomosc_dostaje_error_i_zamkniecie() -> None:
    assert len(ZAGNIEZDZONY_JSON) == 20_001 < LIMIT_LINII
    assert json_rzuca_recursion_error_w_watku(ZAGNIEZDZONY_JSON)
    with nasluch(TableServer(match_rng=random.Random(1))) as port:
        klient = Klient(port)
        klient.wyslij_bajty(ZAGNIEZDZONY_JSON)
        odpowiedz = klient.odbierz()
        assert odpowiedz["type"] == "error", odpowiedz
        assert "recursion" in str(odpowiedz["message"])
        assert klient.nastepna() is None
        klient.close()
        serwer_przyjmuje_stol(port)


def test_wyjatek_rejestru_przy_create_to_error_ze_stala_trescia(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def rejestr_z_awaria() -> dict[str, Agent]:
        raise RuntimeError(ZNACZNIK)

    with nasluch(TableServer(match_rng=random.Random(1))) as port:
        monkeypatch.setattr(lan_server, "agent_registry", rejestr_z_awaria)
        klient = Klient(port)
        klient.wyslij(create())
        strumien = klient.do_konca()
        klient.close()
        assert typy(strumien) == ["error"]
        assert strumien == [blad_wewnetrzny()]
        monkeypatch.undo()
        serwer_przyjmuje_stol(port)
    assert ZNACZNIK.encode("utf-8") not in klient.raw
    assert f"RuntimeError: {ZNACZNIK}" in capsys.readouterr().err


def test_blad_konstrukcji_meczu_przy_create_wraca_z_trescia_wyjatku() -> None:
    with nasluch(TableServer()) as port:
        klient = Klient(port)
        klient.wyslij(create(hand_limit=0))
        assert klient.odbierz() == {
            "v": PROTOCOL_VERSION, "type": "error", "message": "limit rozdań musi być dodatni: 0",
        }
        assert klient.nastepna() is None
        klient.close()


NARUSZENIA = [
    "text-nie-jest-tekstem",
    "zagniezdzony-json",
    "linia-ponad-limit",
    "niepoprawny-json",
    "obca-wersja",
    "join-zamiast-input",
]


def naruszenie(nazwa: str) -> tuple[bytes, str]:
    """Linia naruszająca protokół w miejscu input i fragment treści error dla sprawcy."""
    match nazwa:
        case "text-nie-jest-tekstem":
            return linia(wejscie(5)), "'text'"
        case "zagniezdzony-json":
            assert json_rzuca_recursion_error_w_watku(ZAGNIEZDZONY_JSON)
            return ZAGNIEZDZONY_JSON, "recursion"
        case "linia-ponad-limit":
            return dopelniona(wejscie("fold"), LIMIT_LINII + 1), str(LIMIT_LINII)
        case "niepoprawny-json":
            return b"to nie jest json\n", "Expecting value"
        case "obca-wersja":
            return linia({"v": 1, "type": "input", "text": "fold"}), "wersj"
        case "join-zamiast-input":
            return linia(join("ABCDEFGH")), "'join'"
    raise AssertionError(nazwa)


@pytest.mark.parametrize("nazwa", NARUSZENIA)
def test_naruszenie_protokolu_na_stole_ludzi_error_dla_sprawcy_opponent_left_dla_rywala(
    nazwa: str,
) -> None:
    dane, fragment = naruszenie(nazwa)
    with nasluch(TableServer(match_rng=random.Random(1))) as port:
        tworca, code = utworz(port, opponent="human")
        dolaczajacy = Klient(port)
        dolaczajacy.wyslij(join(code))
        do_promptu(tworca)  # button 0: twórca działa pierwszy
        tworca.wyslij_bajty(dane)
        strumien_sprawcy = tworca.do_konca()
        strumien_rywala = dolaczajacy.do_konca()
        tworca.close()
        dolaczajacy.close()
        assert typy(strumien_sprawcy) == ["error"]
        assert fragment in str(strumien_sprawcy[0]["message"])
        assert typy(strumien_rywala) == ["started", "opponent_left"]
        join_odrzucony(port, code)
        serwer_przyjmuje_stol(port)


@pytest.mark.parametrize("nazwa", NARUSZENIA)
def test_naruszenie_protokolu_przy_stole_z_agentem_error_dla_sprawcy(nazwa: str) -> None:
    dane, fragment = naruszenie(nazwa)
    with nasluch(TableServer(match_rng=random.Random(1))) as port:
        czlowiek, _ = utworz(port)
        do_promptu(czlowiek)  # button 0: człowiek działa pierwszy
        czlowiek.wyslij_bajty(dane)
        strumien = czlowiek.do_konca()
        czlowiek.close()
        assert typy(strumien) == ["error"]
        assert fragment in str(strumien[0]["message"])
        serwer_przyjmuje_stol(port)


class AgentZAwaria:
    def __init__(self, blad: Exception) -> None:
        self._blad = blad

    def decide(self, view: PlayerView) -> Decision:
        raise self._blad


@pytest.mark.parametrize("typ", [RuntimeError, ValueError, OverflowError])
def test_wyjatek_agenta_konczy_stol_bledem_ze_stala_trescia(
    typ: type[Exception], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rejestr = {**agent_registry(), "rule": AgentZAwaria(typ(ZNACZNIK))}
    monkeypatch.setattr(lan_server, "agent_registry", lambda: rejestr)
    with nasluch(TableServer(match_rng=random.Random(1))) as port:
        czlowiek, _ = utworz(port, button=1)  # agent na guziku decyduje pierwszy
        strumien = czlowiek.do_konca()
        czlowiek.close()
        assert typy(strumien) == ["error"]
        assert strumien == [blad_wewnetrzny()]
        monkeypatch.setattr(lan_server, "agent_registry", agent_registry)
        serwer_przyjmuje_stol(port)
    assert ZNACZNIK.encode("utf-8") not in czlowiek.raw
    assert f"{typ.__name__}: {ZNACZNIK}" in capsys.readouterr().err


def test_wyjatek_raportu_rozdania_konczy_stol_ludzi_bledem_ze_stala_trescia(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raport_z_awaria(events: Sequence[HandEvent], seat: int) -> str:
        raise RuntimeError(ZNACZNIK)

    monkeypatch.setattr(lan_server, "render_hand_summary", raport_z_awaria)
    with nasluch(TableServer(match_rng=random.Random(1))) as port:
        tworca, code = utworz(port, opponent="human")
        dolaczajacy = Klient(port)
        dolaczajacy.wyslij(join(code))
        with ThreadPoolExecutor(2) as pula:
            przebieg_tworcy = pula.submit(pasuj_do_konca, tworca)
            przebieg_dolaczajacego = pula.submit(pasuj_do_konca, dolaczajacy)
            strumien_tworcy = przebieg_tworcy.result()
            strumien_dolaczajacego = przebieg_dolaczajacego.result()
        tworca.close()
        dolaczajacy.close()
        assert typy(strumien_tworcy) == ["started", "text", "prompt", "error"]
        assert typy(strumien_dolaczajacego) == ["started", "error"]
        assert strumien_tworcy[-1] == strumien_dolaczajacego[-1] == blad_wewnetrzny()
        monkeypatch.undo()
        serwer_przyjmuje_stol(port)
    for klient in (tworca, dolaczajacy):
        assert ZNACZNIK.encode("utf-8") not in klient.raw
    assert f"RuntimeError: {ZNACZNIK}" in capsys.readouterr().err


def test_awaria_eksportu_po_match_end_nie_wysyla_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    zwykly_plik = tmp_path / "to-nie-katalog"
    zwykly_plik.write_text("", encoding="utf-8")
    with nasluch(TableServer(export_directory=zwykly_plik, match_rng=random.Random(1))) as port:
        czlowiek, _ = utworz(port)
        strumien = pasuj_do_konca(czlowiek)
        czlowiek.close()
        serwer_przyjmuje_stol(port)
    assert typy(strumien)[-1] == "match_end"
    assert "error" not in typy(strumien)
    stderr = capsys.readouterr().err
    assert "FileExistsError" in stderr and str(zwykly_plik) in stderr


def test_max_chips_przybity() -> None:
    assert lan_server.MAX_CHIPS == GRANICA_ZETONOW == 4_503_599_627_370_496


@pytest.mark.parametrize(
    ("pole", "nadpisanie"),
    [
        ("stacks", {"stacks": [GRANICA_ZETONOW + 1, 100]}),
        ("small_blind", {"small_blind": GRANICA_ZETONOW + 1, "big_blind": 2}),
        ("big_blind", {"big_blind": GRANICA_ZETONOW + 1}),
    ],
)
def test_zadanie_ponad_max_chips_odrzucone_zanim_powstanie_stol(
    pole: str, nadpisanie: dict[str, object]
) -> None:
    with nasluch(TableServer()) as port:
        klient = Klient(port)
        klient.wyslij(create(**nadpisanie))
        odpowiedz = klient.odbierz()
        assert odpowiedz["type"] == "error", odpowiedz
        assert pole in str(odpowiedz["message"])
        assert str(GRANICA_ZETONOW) in str(odpowiedz["message"])
        assert klient.nastepna() is None
        klient.close()


def test_stacki_przepelniajace_float_odrzucone_zanim_agent_zdecyduje() -> None:
    with nasluch(TableServer()) as port:
        klient = Klient(port)
        klient.wyslij(create(stacks=[10**400, 10**400], opponent="clone", button=1))
        odpowiedz = klient.odbierz()
        assert odpowiedz["type"] == "error", odpowiedz
        assert "stacks" in str(odpowiedz["message"])
        assert klient.nastepna() is None
        klient.close()


class LiczacyAgent:
    """Agent rejestru z licznikiem decyzji: strażnik granicy bez decyzji agenta byłby ślepy."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        self.decyzje = 0

    def decide(self, view: PlayerView) -> Decision:
        self.decyzje += 1
        return self._agent.decide(view)


@pytest.mark.parametrize(
    ("przeciwnik", "small_blind", "big_blind"),
    [
        ("clone", 1, 2),
        ("mlp-clone", 1, 2),
        ("clone", GRANICA_ZETONOW // 2, GRANICA_ZETONOW),
    ],
)
def test_zadanie_na_granicy_max_chips_gra_z_agentem_do_konca(
    przeciwnik: str, small_blind: int, big_blind: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    rejestr = agent_registry()
    liczacy = LiczacyAgent(rejestr[przeciwnik])
    rejestr[przeciwnik] = liczacy
    monkeypatch.setattr(lan_server, "agent_registry", lambda: rejestr)
    with nasluch(TableServer(match_rng=random.Random(1))) as port:
        czlowiek, _ = utworz(
            port, opponent=przeciwnik, button=1, small_blind=small_blind, big_blind=big_blind,
            stacks=[GRANICA_ZETONOW, GRANICA_ZETONOW],
        )
        assert typy(pasuj_do_konca(czlowiek))[-1] == "match_end"
        czlowiek.close()
    assert liczacy.decyzje >= 1  # agent na guziku działa pierwszy przed flopem

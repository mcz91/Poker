"""Testy odporności serwera LAN (POKER-76): wadliwy klient, agent, gniazdo ani eksport nie
wyłączają serwera — awaria kończy wyłącznie dotknięty stół komunikatem do jego graczy
i zamknięciem ich połączeń, a wejście klienta ma jawne granice."""

import io
import json
import socket
from collections.abc import Iterator
from contextlib import contextmanager

from poker.adapters import protocol
from poker.adapters.lan_server import TableServer
from poker.adapters.protocol import PROTOCOL_VERSION, MessageStream, read_message

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

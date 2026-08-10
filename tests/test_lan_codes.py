"""Testy kodów stołu LAN (POKER-25): losowość, odtwarzalność z seeda, kolizje."""

import json
import socket
from typing import Any

import pytest

from poker.adapters import lan_server
from poker.adapters.lan_server import CODE_ALPHABET, CODE_LENGTH, TableServer
from poker.adapters.protocol import PROTOCOL_VERSION


def utworz_stol(port: int, seed_meczu: int = 1) -> tuple[socket.socket, dict[str, Any]]:
    sock = socket.create_connection(("127.0.0.1", port), timeout=10)
    plik = sock.makefile("rwb")
    plik.write(json.dumps({
        "v": PROTOCOL_VERSION, "type": "create", "small_blind": 1, "big_blind": 2,
        "stacks": [100, 100], "button": 0, "hand_limit": 1, "seed": seed_meczu,
        "opponent": "human",
    }).encode("utf-8") + b"\n")
    plik.flush()
    odpowiedz: dict[str, Any] = json.loads(plik.readline())
    return sock, odpowiedz


def kody(port: int, ile: int) -> list[str]:
    zebrane = []
    gniazda = []
    for _ in range(ile):
        sock, odpowiedz = utworz_stol(port)
        gniazda.append(sock)
        assert odpowiedz["type"] == "table_created", odpowiedz
        zebrane.append(odpowiedz["code"])
    for sock in gniazda:
        sock.close()
    return zebrane


def test_kod_jest_losowy_z_udokumentowanej_przestrzeni() -> None:
    server = TableServer(seed=11)
    try:
        _, port = server.start()
        zebrane = kody(port, 5)
    finally:
        server.close()
    assert len(set(zebrane)) == 5
    for kod in zebrane:
        assert len(kod) == CODE_LENGTH
        assert set(kod) <= set(CODE_ALPHABET)
        assert not kod.startswith("STOL-")  # koniec z licznikiem (F1 audytu POKER-21)
    # przestrzeń co najmniej kilkadziesiąt bitów
    assert CODE_LENGTH * len(CODE_ALPHABET).bit_length() >= 40


def test_kolejne_kody_nie_tworza_ciagu() -> None:
    server = TableServer(seed=11)
    try:
        _, port = server.start()
        zebrane = kody(port, 6)
    finally:
        server.close()
    wartosci = [
        sum(CODE_ALPHABET.index(znak) * len(CODE_ALPHABET) ** pozycja
            for pozycja, znak in enumerate(reversed(kod)))
        for kod in zebrane
    ]
    roznice = {
        nastepny - biezacy
        for biezacy, nastepny in zip(wartosci[:-1], wartosci[1:], strict=True)
    }
    assert len(roznice) > 1, "stała różnica kolejnych kodów zdradza licznik"
    assert 1 not in roznice


def test_ten_sam_seed_serwera_daje_te_same_kody() -> None:
    wyniki = []
    for _ in range(2):
        server = TableServer(seed=123)
        try:
            _, port = server.start()
            wyniki.append(kody(port, 3))
        finally:
            server.close()
    assert wyniki[0] == wyniki[1]


def test_bez_seeda_kody_sa_nieodtwarzalne() -> None:
    wyniki = []
    for _ in range(2):
        server = TableServer()
        try:
            _, port = server.start()
            wyniki.append(kody(port, 3))
        finally:
            server.close()
    assert wyniki[0] != wyniki[1]


def test_kolizja_kodu_nie_nadpisuje_cudzego_stolu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lan_server, "generate_code", lambda rng: "AAAAAAAA")
    server = TableServer(seed=5)
    try:
        _, port = server.start()
        pierwszy_sock, pierwszy = utworz_stol(port)
        assert pierwszy["type"] == "table_created"
        assert pierwszy["code"] == "AAAAAAAA"

        drugi_sock, drugi = utworz_stol(port)
        assert drugi["type"] == "error"
        assert "kod" in drugi["message"]

        # pierwszy stół żyje: dołączenie jego kodem nadal działa
        trzeci = socket.create_connection(("127.0.0.1", port), timeout=10)
        plik = trzeci.makefile("rwb")
        plik.write(json.dumps({
            "v": PROTOCOL_VERSION, "type": "join", "code": "AAAAAAAA",
        }).encode("utf-8") + b"\n")
        plik.flush()
        assert json.loads(plik.readline())["type"] == "started"
        for sock in (pierwszy_sock, drugi_sock, trzeci):
            sock.close()
    finally:
        server.close()


def test_bledny_kod_nie_zdradza_istniejacych_stolow() -> None:
    server = TableServer(seed=11)
    try:
        _, port = server.start()
        istniejace = kody(port, 3)
        sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        plik = sock.makefile("rwb")
        plik.write(json.dumps({
            "v": PROTOCOL_VERSION, "type": "join", "code": "ZZZZZZZZ",
        }).encode("utf-8") + b"\n")
        plik.flush()
        odpowiedz = json.loads(plik.readline())
        assert odpowiedz["type"] == "error"
        komunikat = odpowiedz["message"]
        assert "ZZZZZZZZ" in komunikat  # echo kodu podanego przez gracza
        for kod in istniejace:
            assert kod not in komunikat
        assert "3" not in komunikat  # ani liczby otwartych stołów
        sock.close()
    finally:
        server.close()

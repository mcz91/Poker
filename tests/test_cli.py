"""Testy CLI (POKER-9, POKER-69, POKER-77): punkt wejścia w procesie testów, wynik, eksport,
błędy, domyślny seed, wykluczenia trybów, ścieżki wyjścia i błędy I/O, kody wyjścia."""

import errno
import io
import json
import os
import re
import shutil
import socket
import struct
import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn

import pytest

from poker.adapters import cli
from poker.adapters.cli import build_parser, main
from poker.adapters.corpus import MANIFEST_NAME, generate_corpus
from poker.adapters.export import deserialize_match_history
from poker.adapters.protocol import send_message
from poker.projection import project
from poker.table import MatchConfig

REPO = Path(__file__).resolve().parents[1]


def test_mecz_z_domyslnymi_wartosciami_argumentow(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--seed", "7", "--hands", "5"]) == 0
    out = capsys.readouterr().out
    assert "rozdania: " in out
    assert "powód zakończenia: " in out
    assert "stacki końcowe: " in out


def test_eksport_do_pliku_z_round_tripem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "mecz.json"
    assert main(["--seed", "7", "--hands", "3", "--export", str(target)]) == 0
    histories = deserialize_match_history(target.read_text(encoding="utf-8"))
    assert len(histories) >= 1
    for history in histories:
        assert project(history).pot == 0


def test_eksport_bajt_w_bajt_dla_tych_samych_argumentow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    assert main(["--seed", "11", "--hands", "4", "--export", str(first)]) == 0
    assert main(["--seed", "11", "--hands", "4", "--export", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()


def test_wybor_agenta_wariantem_progow_zmienia_przebieg(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    default, aggressive = tmp_path / "rule.json", tmp_path / "aggressive.json"
    assert main(["--seed", "7", "--hands", "20", "--export", str(default)]) == 0
    assert (
        main(
            [
                "--seed",
                "7",
                "--hands",
                "20",
                "--agent1",
                "rule-aggressive",
                "--export",
                str(aggressive),
            ]
        )
        == 0
    )
    assert default.read_bytes() != aggressive.read_bytes()


@pytest.mark.parametrize(
    "tryb",
    [
        ["--hands", "5", "--export", "{wyjscie}/mecz.json"],
        ["--series", "2", "--hands", "5"],
        ["--corpus", "{wyjscie}/korpus", "--matches", "2", "--hands", "5"],
    ],
    ids=["mecz-z-eksportem", "seria", "korpus"],
)
def test_bez_czlowieka_domyslny_seed_to_zero_bajt_w_bajt(
    tryb: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    przebiegi = []
    for nazwa, jawny_seed in (("domyslny", []), ("zero", ["--seed", "0"])):
        wyjscie = tmp_path / nazwa
        wyjscie.mkdir()
        argv = [argument.format(wyjscie=wyjscie) for argument in tryb]
        assert main([*argv, *jawny_seed]) == 0
        pliki = {
            str(plik.relative_to(wyjscie)): plik.read_bytes()
            for plik in sorted(wyjscie.rglob("*"))
            if plik.is_file()
        }
        przebiegi.append((capsys.readouterr().out.replace(str(wyjscie), "<wyjscie>"), pliki))
    assert przebiegi[0] == przebiegi[1]
    assert "seed meczu" not in przebiegi[0][0]


def test_bledne_argumenty_daja_niezerowy_kod_i_komunikat(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--hands", "0"]) == 2
    assert "błąd" in capsys.readouterr().err
    assert main(["--agent0", "nieznany"]) == 2
    assert "błąd" in capsys.readouterr().err
    assert main(["--big-blind", "-2"]) == 2
    assert "błąd" in capsys.readouterr().err


# Macierz M1–M4 przybita literalnie: lista importowana z cli.py byłaby tautologią wobec tabeli
# walidacji, a help i README mają mówić to samo co ona.
TRYBY_PARAMI = (
    ("--serve", "--connect"),
    ("--serve", "--dataset"),
    ("--serve", "--corpus"),
    ("--serve", "--series"),
    ("--connect", "--dataset"),
    ("--connect", "--corpus"),
    ("--connect", "--series"),
    ("--dataset", "--corpus"),
    ("--dataset", "--series"),
    ("--corpus", "--series"),
)
CZLOWIEK_I_EKSPORT_Z_TRYBAMI = (
    ("--human", "--serve"),
    ("--human", "--connect"),
    ("--human", "--dataset"),
    ("--human", "--corpus"),
    ("--human", "--series"),
    ("--export", "--serve"),
    ("--export", "--connect"),
    ("--export", "--dataset"),
    ("--export", "--corpus"),
    ("--export", "--series"),
)
SEED_Z_TRYBAMI = (
    ("--seed", "--serve"),
    ("--seed", "--connect"),
    ("--seed", "--dataset"),
)
WYKLUCZENIA = TRYBY_PARAMI + CZLOWIEK_I_EKSPORT_Z_TRYBAMI + SEED_Z_TRYBAMI
ZALEZNOSCI = (
    ("--from-corpus", "--dataset"),
    ("--join", "--connect"),
    ("--serve-seed", "--serve"),
    ("--export-dir", "--serve"),
)
KODY_WYJSCIA = {"0": "praca zakończona", "1": "mecz przerwany", "2": "błąd użycia"}


class Wartownik:
    """Mock sieci: wywołanie znaczy, że CLI ruszyło serwer albo klienta LAN mimo błędu — test
    czerwienieje, zamiast wiązać porty maszyny albo wieszać bramkę."""

    def __init__(self, nazwa: str) -> None:
        self.nazwa = nazwa

    def __call__(self, *args: object, **kwargs: object) -> NoReturn:
        raise AssertionError(f"{self.nazwa} wywołany")


@pytest.fixture
def bez_sieci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "TableServer", Wartownik("TableServer"))
    monkeypatch.setattr(cli, "run_client", Wartownik("run_client"))


@pytest.fixture
def korpus(tmp_path: Path) -> Path:
    katalog = tmp_path / "korpus"
    generate_corpus(
        katalog,
        config=MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=2),
        agent_names=("rule", "rule"),
        matches=1,
        seed=0,
    )
    return katalog


def argumenty_flag(tmp_path: Path, korpus: Path) -> dict[str, list[str]]:
    """Wartości poprawne same w sobie: bez walidacji każda flaga trybu uruchomiłaby tryb."""
    return {
        "--serve": ["--serve", "0"],
        "--connect": ["--connect", "127.0.0.1:1"],
        "--dataset": ["--dataset", str(tmp_path / "zbior.json"), "--from-corpus", str(korpus)],
        "--corpus": ["--corpus", str(tmp_path / "nowy"), "--matches", "1"],
        "--series": ["--series", "2"],
        "--human": ["--human", "0"],
        "--export": ["--export", str(tmp_path / "mecz.json")],
        "--seed": ["--seed", "1"],
        "--from-corpus": ["--from-corpus", str(korpus)],
        "--join": ["--join", "ABCDEFGH"],
        "--serve-seed": ["--serve-seed", "1"],
        "--export-dir": ["--export-dir", str(tmp_path / "eksport")],
    }


def migawka(katalog: Path) -> dict[str, bytes | None]:
    return {
        str(sciezka.relative_to(katalog)): sciezka.read_bytes() if sciezka.is_file() else None
        for sciezka in sorted(katalog.rglob("*"))
    }


def zawiera_flage(tekst: str, flaga: str) -> bool:
    """Flaga jako całe słowo: '--serve' nie trafia w '--serve-seed'."""
    return re.search(rf"{re.escape(flaga)}(?![\w-])", tekst) is not None


@pytest.mark.usefixtures("bez_sieci")
@pytest.mark.parametrize(
    ("pierwsza", "druga"), WYKLUCZENIA, ids=[f"{a}+{b}" for a, b in WYKLUCZENIA]
)
def test_sprzeczne_flagi_koncza_sie_bledem_przed_jakakolwiek_praca(
    pierwsza: str,
    druga: str,
    tmp_path: Path,
    korpus: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    flagi = argumenty_flag(tmp_path, korpus)
    wejscie = io.StringIO("fold\n" * 4)
    przed = migawka(tmp_path)
    assert main([*flagi[pierwsza], *flagi[druga], "--hands", "2"], stdin=wejscie) == 2
    wyjscie = capsys.readouterr()
    assert wyjscie.err.startswith("błąd: ")
    assert zawiera_flage(wyjscie.err, pierwsza) and zawiera_flage(wyjscie.err, druga)
    assert "Traceback" not in wyjscie.err
    assert wyjscie.out == ""
    assert wejscie.tell() == 0
    assert migawka(tmp_path) == przed


@pytest.mark.usefixtures("bez_sieci")
@pytest.mark.parametrize(("flaga", "tryb"), ZALEZNOSCI, ids=[flaga for flaga, _ in ZALEZNOSCI])
def test_flaga_bez_swojego_trybu_konczy_sie_bledem(
    flaga: str, tryb: str, tmp_path: Path, korpus: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    przed = migawka(tmp_path)
    assert main([*argumenty_flag(tmp_path, korpus)[flaga], "--hands", "2"]) == 2
    wyjscie = capsys.readouterr()
    assert wyjscie.err.startswith("błąd: ")
    assert zawiera_flage(wyjscie.err, flaga) and zawiera_flage(wyjscie.err, tryb)
    assert "Traceback" not in wyjscie.err
    assert wyjscie.out == ""
    assert migawka(tmp_path) == przed


WZOR_WYKLUCZENIA = re.compile(r"\s*(--[a-z-]+) nie łączy się z (--[a-z-]+(?:, --[a-z-]+)*)")
WZOR_ZALEZNOSCI = re.compile(r"\s*(--[a-z-]+) wymaga (--[a-z-]+)")


def macierz_z_tekstu(tekst: str) -> tuple[set[frozenset[str]], set[tuple[str, str]]]:
    pary: set[frozenset[str]] = set()
    zaleznosci: set[tuple[str, str]] = set()
    for linia in tekst.splitlines():
        if wykluczenie := WZOR_WYKLUCZENIA.fullmatch(linia):
            pary |= {frozenset((wykluczenie[1], inna)) for inna in wykluczenie[2].split(", ")}
        elif zaleznosc := WZOR_ZALEZNOSCI.fullmatch(linia):
            zaleznosci.add((zaleznosc[1], zaleznosc[2]))
    return pary, zaleznosci


def test_pomoc_i_readme_podaja_te_sama_macierz_trybow_i_kody_wyjscia() -> None:
    parser = build_parser()
    pomoc = parser.format_help().rstrip("\n")
    epilog = parser.epilog
    # Epilog w pomocy dosłownie — bez przełamywania wierszy, które rozbiłoby listy flag.
    assert epilog is not None and pomoc.endswith(epilog)
    poza_epilogiem = pomoc[: -len(epilog)]
    assert "wyklucza" not in poza_epilogiem
    assert "nie łączy się" not in poza_epilogiem

    readme = (REPO / "README.md").read_text(encoding="utf-8")
    naglowek = "\n### Tryby CLI i kody wyjścia\n"
    sekcja_meczu = readme.index("\n## Uruchomienie meczu\n")
    poczatek = readme.index(naglowek, sekcja_meczu) + len(naglowek)
    assert poczatek < readme.index("\n## ", sekcja_meczu + 1)
    nastepny_naglowek = re.compile(r"^#", flags=re.MULTILINE).search(readme, poczatek)
    assert nastepny_naglowek is not None
    podsekcja = readme[poczatek : nastepny_naglowek.start()]

    oczekiwana = ({frozenset(para) for para in WYKLUCZENIA}, set(ZALEZNOSCI))
    for tekst in (epilog, podsekcja):
        assert macierz_z_tekstu(tekst) == oczekiwana
        for kod, opis in KODY_WYJSCIA.items():
            assert re.search(rf"^\s*{kod} — {opis}", tekst, flags=re.MULTILINE), kod


def odbierz_prawo_zapisu(monkeypatch: pytest.MonkeyPatch, zablokowana: Path) -> None:
    """Mock systemu operacyjnego: bramka biegnie jako root, więc chmod prawa zapisu nie odbiera
    (os.access(katalog 0o555, W_OK) jest prawdziwe, a zapis się udaje)."""
    prawdziwy = os.access

    def dostep(sciezka: str | os.PathLike[str], tryb: int) -> bool:
        if tryb == os.W_OK and Path(sciezka) == zablokowana:
            return False
        return prawdziwy(sciezka, tryb)

    monkeypatch.setattr(os, "access", dostep)


@pytest.mark.usefixtures("bez_sieci")
@pytest.mark.parametrize(
    ("argumenty", "w_komunikacie", "bez_prawa_zapisu"),
    [
        pytest.param(["--export", "{tmp}/nie-ma/m.json"], "{tmp}/nie-ma", None, id="W1"),
        pytest.param(["--export", "{katalog}"], "{katalog}", None, id="W2"),
        pytest.param(["--export", "{plik}/m.json"], "{plik}", None, id="W3"),
        pytest.param(
            ["--dataset", "{tmp}/nie-ma/z.json", "--from-corpus", "{korpus}"],
            "{tmp}/nie-ma",
            None,
            id="W4",
        ),
        pytest.param(
            ["--dataset", "{plik}/z.json", "--from-corpus", "{korpus}"], "{plik}", None, id="W5"
        ),
        pytest.param(["--corpus", "{plik}", "--matches", "1"], "{plik}", None, id="W6"),
        pytest.param(["--corpus", "{plik}/k", "--matches", "1"], "{plik}", None, id="W7"),
        pytest.param(["--serve", "0", "--export-dir", "{plik}"], "{plik}", None, id="W8"),
        pytest.param(["--export", "{katalog}/m.json"], "{katalog}", "{katalog}", id="W9a"),
        pytest.param(
            ["--dataset", "{katalog}/z.json", "--from-corpus", "{korpus}"],
            "{katalog}",
            "{katalog}",
            id="W9b",
        ),
        pytest.param(
            ["--corpus", "{tmp}/d/k", "--matches", "1"], "{tmp}/d/k", "{tmp}/d/k", id="W9c"
        ),
        pytest.param(
            ["--serve", "0", "--export-dir", "{katalog}"], "{katalog}", "{katalog}", id="W9d"
        ),
        pytest.param(["--export", "{istniejacy}"], "{istniejacy}", "{istniejacy}", id="W9e"),
    ],
)
def test_nieuzywalna_sciezka_wyjscia_konczy_sie_bledem_przed_praca(
    argumenty: list[str],
    w_komunikacie: str,
    bez_prawa_zapisu: str | None,
    tmp_path: Path,
    korpus: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Korpus bez pliku meczu: błąd ścieżki wyjścia musi paść przed odczytem korpusu.
    (korpus / "match-000000.json").unlink()
    (tmp_path / "plik").write_text("zwykły plik", encoding="utf-8")
    (tmp_path / "katalog").mkdir()
    (tmp_path / "istniejacy.json").write_text("stara treść", encoding="utf-8")
    miejsca = {
        "tmp": tmp_path,
        "korpus": korpus,
        "plik": tmp_path / "plik",
        "katalog": tmp_path / "katalog",
        "istniejacy": tmp_path / "istniejacy.json",
    }
    if bez_prawa_zapisu is not None:
        odbierz_prawo_zapisu(monkeypatch, Path(bez_prawa_zapisu.format(**miejsca)))
    przed = migawka(tmp_path)
    assert main([*(argument.format(**miejsca) for argument in argumenty), "--hands", "2"]) == 2
    wyjscie = capsys.readouterr()
    assert wyjscie.err.startswith("błąd: ")
    assert w_komunikacie.format(**miejsca) in wyjscie.err
    assert "match-000000.json" not in wyjscie.err
    assert "Traceback" not in wyjscie.err
    assert "rozdania:" not in wyjscie.out
    for sciezka, tresc in przed.items():
        if tresc is not None:
            assert (tmp_path / sciezka).read_bytes() == tresc


def test_zla_sciezka_eksportu_odrzucona_zanim_czlowiek_zagra(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    brak = tmp_path / "nie-ma"
    wejscie = io.StringIO("fold\n" * 3)
    argv = ["--human", "0", "--hands", "3", "--seed", "1", "--export", str(brak / "m.json")]
    assert main(argv, stdin=wejscie) == 2
    wyjscie = capsys.readouterr()
    assert wejscie.tell() == 0
    assert "twoja decyzja" not in wyjscie.out
    assert wyjscie.err.startswith("błąd: ")
    assert str(brak) in wyjscie.err


class WejscieUsuwajaceKatalog(io.StringIO):
    """Pierwszy odczyt decyzji usuwa katalog eksportu, który CLI sprawdziło przed meczem."""

    def __init__(self, tekst: str, katalog: Path) -> None:
        super().__init__(tekst)
        self.katalog = katalog

    # Tekstowe readline zwraca str, a _IOBase w typeshed — bytes; stub StringIO wycisza to
    # samo nadpisanie tym samym kodem.
    def readline(self, size: int = -1, /) -> str:  # type: ignore[override]
        if self.katalog.exists():
            shutil.rmtree(self.katalog)
        return super().readline(size)


def test_blad_zapisu_eksportu_po_meczu_konczy_sie_kodem_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    katalog = tmp_path / "d"
    katalog.mkdir()
    wejscie = WejscieUsuwajaceKatalog("fold\n" * 4, katalog)
    argv = ["--human", "0", "--hands", "2", "--seed", "1", "--export", str(katalog / "m.json")]
    assert main(argv, stdin=wejscie) == 2
    wyjscie = capsys.readouterr()
    assert "rozdania: 2" in wyjscie.out
    assert wyjscie.err.startswith("błąd: ")
    assert str(katalog) in wyjscie.err
    assert "Traceback" not in wyjscie.err


class ZepsuteWejscie(io.StringIO):
    def readline(self, size: int = -1, /) -> str:  # type: ignore[override]  # jak wyżej
        raise OSError(errno.EIO, "Input/output error")


def test_blad_wejscia_czlowieka_w_trakcie_meczu_konczy_sie_kodem_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--human", "0", "--hands", "1", "--seed", "1"], stdin=ZepsuteWejscie()) == 2
    wyjscie = capsys.readouterr()
    assert wyjscie.err.startswith("błąd: ")
    assert "Traceback" not in wyjscie.err


@contextmanager
def falszywy_serwer(scenariusz: Callable[[socket.socket], None]) -> Iterator[int]:
    """Serwer LAN trzymany przez test: jedno połączenie prowadzone scenariuszem."""
    with socket.create_server(("127.0.0.1", 0)) as nasluch:
        nasluch.settimeout(10)

        def obsluz() -> None:
            polaczenie, _ = nasluch.accept()
            with polaczenie:
                polaczenie.settimeout(10)
                scenariusz(polaczenie)

        watek = threading.Thread(target=obsluz, daemon=True)
        watek.start()
        port: int = nasluch.getsockname()[1]
        yield port
        watek.join(timeout=10)


def zamknij_po_create(polaczenie: socket.socket) -> None:
    with polaczenie.makefile("rb") as plik:
        plik.readline()


def zerwij_po_create(polaczenie: socket.socket) -> None:
    zamknij_po_create(polaczenie)
    # SO_LINGER 0: zamknięcie wysyła RST zamiast FIN.
    polaczenie.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))


def przeciwnik_odchodzi(polaczenie: socket.socket) -> None:
    with polaczenie.makefile("rwb") as plik:
        plik.readline()
        send_message(plik, {"type": "table_created", "code": "ABCDEFGH"})
        send_message(plik, {"type": "opponent_left"})


def prosi_o_decyzje(polaczenie: socket.socket) -> None:
    with polaczenie.makefile("rwb") as plik:
        plik.readline()
        send_message(plik, {"type": "prompt"})


class CzekanieZabronione:
    """W miejscu czekania serwera CLI na Ctrl+C: start serwera czerwieni test zamiast wisieć."""

    def wait(self) -> None:
        raise AssertionError("serwer wystartował")


Przypadek = tuple[list[str], str | None]


@contextmanager
def manifest_bez_match_config(
    tmp_path: Path, korpus: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Przypadek]:
    manifest = korpus / MANIFEST_NAME
    dokument = json.loads(manifest.read_text(encoding="utf-8"))
    del dokument["match_config"]
    manifest.write_text(json.dumps(dokument), encoding="utf-8")
    zbior = tmp_path / "zbior.json"
    yield ["--dataset", str(zbior), "--from-corpus", str(korpus)], "match_config"
    assert not zbior.exists()


@contextmanager
def brak_pliku_meczu(
    tmp_path: Path, korpus: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Przypadek]:
    (korpus / "match-000000.json").unlink()
    zbior = tmp_path / "zbior.json"
    yield ["--dataset", str(zbior), "--from-corpus", str(korpus)], "match-000000.json"
    assert not zbior.exists()


@contextmanager
def port_bez_nasluchu(
    tmp_path: Path, korpus: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Przypadek]:
    # Gniazdo związane bez listen i trzymane do końca testu: odmowa połączenia, a portu nie
    # przejmie w tym czasie nikt inny.
    with socket.socket() as zwiazane:
        zwiazane.bind(("127.0.0.1", 0))
        adres = f"127.0.0.1:{zwiazane.getsockname()[1]}"
        yield ["--connect", adres], adres


@contextmanager
def zajety_port(
    tmp_path: Path, korpus: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Przypadek]:
    monkeypatch.setattr(cli, "threading", SimpleNamespace(Event=CzekanieZabronione))
    with socket.create_server(("127.0.0.1", 0)) as nasluch:
        port = str(nasluch.getsockname()[1])
        yield ["--serve", port, "--serve-host", "127.0.0.1"], None


@contextmanager
def zerwane_polaczenie(
    tmp_path: Path, korpus: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Przypadek]:
    with falszywy_serwer(zerwij_po_create) as port:
        adres = f"127.0.0.1:{port}"
        yield ["--connect", adres, "--opponent", "rule"], adres


@contextmanager
def nieznany_host(
    tmp_path: Path, korpus: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Przypadek]:
    def bez_dns(*args: object, **kwargs: object) -> NoReturn:
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(socket, "create_connection", bez_dns)
    yield ["--connect", "nie-ma.invalid:7777"], "nie-ma.invalid:7777"


@contextmanager
def port_serwera_70000(
    tmp_path: Path, korpus: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Przypadek]:
    monkeypatch.setattr(cli, "TableServer", Wartownik("TableServer"))
    yield ["--serve", "70000"], "--serve"


@contextmanager
def port_serwera_ujemny(
    tmp_path: Path, korpus: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Przypadek]:
    monkeypatch.setattr(cli, "TableServer", Wartownik("TableServer"))
    yield ["--serve", "-1"], "--serve"


@contextmanager
def port_klienta_70000(
    tmp_path: Path, korpus: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Przypadek]:
    monkeypatch.setattr(cli, "run_client", Wartownik("run_client"))
    yield ["--connect", "127.0.0.1:70000"], "--connect"


Scenariusz = Callable[[Path, Path, pytest.MonkeyPatch], AbstractContextManager[Przypadek]]


@pytest.mark.parametrize(
    "scenariusz",
    [
        pytest.param(manifest_bez_match_config, id="R1"),
        pytest.param(brak_pliku_meczu, id="R2"),
        pytest.param(port_bez_nasluchu, id="R3"),
        pytest.param(zajety_port, id="R4"),
        pytest.param(zerwane_polaczenie, id="R5"),
        pytest.param(nieznany_host, id="R6"),
        pytest.param(port_serwera_70000, id="U1-70000"),
        pytest.param(port_serwera_ujemny, id="U1-ujemny"),
        pytest.param(port_klienta_70000, id="U2"),
    ],
)
def test_blad_odczytu_sieci_albo_portu_konczy_sie_kodem_2_bez_tracebacku(
    scenariusz: Scenariusz,
    tmp_path: Path,
    korpus: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with scenariusz(tmp_path, korpus, monkeypatch) as (argv, w_komunikacie):
        assert main(argv, stdin=io.StringIO("")) == 2
    err = capsys.readouterr().err
    assert err.startswith("błąd: ")
    assert "Traceback" not in err
    if w_komunikacie is not None:
        assert w_komunikacie in err


@pytest.mark.parametrize(
    ("scenariusz", "komunikat"),
    [
        pytest.param(zamknij_po_create, "serwer zamknął połączenie", id="FIN"),
        pytest.param(przeciwnik_odchodzi, "przeciwnik rozłączył się", id="opponent_left"),
        pytest.param(prosi_o_decyzje, "koniec wejścia — opuszczasz stół", id="koniec-wejscia"),
    ],
)
def test_uporzadkowane_przerwanie_klienta_lan_zostaje_kodem_1(
    scenariusz: Callable[[socket.socket], None],
    komunikat: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with falszywy_serwer(scenariusz) as port:
        wynik = main(
            ["--connect", f"127.0.0.1:{port}", "--opponent", "rule"], stdin=io.StringIO("")
        )
    wyjscie = capsys.readouterr()
    assert wynik == 1
    assert komunikat in wyjscie.out
    assert "błąd: " not in wyjscie.err


class CtrlC:
    """W miejscu czekania serwera CLI na przerwanie: operator naciska Ctrl+C."""

    def wait(self) -> None:
        raise KeyboardInterrupt


def test_serwer_zamkniety_ctrl_c_zostaje_kodem_0_z_istniejacym_katalogiem_eksportu(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "threading", SimpleNamespace(Event=CtrlC))
    katalog = tmp_path / "eksport"
    katalog.mkdir()
    (katalog / "BJC3QJD5.json").write_text("historia poprzedniego uruchomienia", encoding="utf-8")
    przed = migawka(katalog)
    argv = ["--serve", "0", "--serve-host", "127.0.0.1", "--export-dir", str(katalog)]
    assert main(argv) == 0
    assert "słucha" in capsys.readouterr().out
    assert migawka(katalog) == przed

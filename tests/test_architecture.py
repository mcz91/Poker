"""Test architektury (POKER-9, 10, 12, 80): importy płyną od adapterów do silnika (INV-P7).

Wszystkie reguły importów liczy jeden strażnik (`_straznik`) na zbiorze plików
(ścieżka względna → źródło), wyłącznie na AST, bez importowania badanych modułów.
Obejmuje każdą instrukcję importu w dowolnej formie: import względny (liczony od
pakietu pliku), nazwę z pakietu (`from poker import adapters` → `poker.adapters`),
podmoduł po kropce (reguły I/O i importu dynamicznego dopasowują prefiks pakietu,
więc `import os.path` narusza je jak `import os`) i import wewnątrz funkcji; w silniku
także `importlib` i nazwę `__import__`. Import względny, którego nie da się rozwiązać, jest
naruszeniem, nie pominięciem. Poza strażnikiem zostaje kod wykonywany z napisu
(`exec`, `eval`, `compile`) i dostęp do modułu atrybutem pakietu albo `builtins`
(np. `builtins.__import__`, `getattr`) bez instrukcji importu: strażnik chroni przed
przypadkowym importem w złą stronę, nie przed celowym obejściem AST.
"""

import ast
import inspect
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path, PurePosixPath

import pytest

from poker.views import PlayerView

REPO = Path(__file__).resolve().parent.parent
SRC_POKER = REPO / "src" / "poker"
IO_FORBIDDEN_IN_ENGINE = {
    "argparse",
    "datetime",
    "io",
    "json",
    "os",
    "pathlib",
    "socket",
    "subprocess",
    "sys",
    "time",
}


class Regula(StrEnum):
    ADAPTERY_ZALEZA_OD_SILNIKA = "adaptery zależne od silnika"
    SILNIK_BEZ_ADAPTEROW = "silnik bez adapterów"
    SILNIK_BEZ_IO = "silnik bez I/O"
    IMPORT_DYNAMICZNY = "import dynamiczny w silniku"
    PREFLOP = "moduły preflop"
    ARENA = "arena i cli→arena"
    SPIN_ARENA = "spin_arena"
    KORPUS = "korpus i cli→korpus"
    ENKODOWANIE = "enkodowanie"
    DATASET = "dataset i cli→dataset"
    KLON = "klon i trening"
    NUMPY = "numpy poza pakietem"
    MLP = "agent mlp"
    LAN = "LAN"
    SILNIK_BEZ_PROTOKOLU = "silnik bez protokołu"
    ABSTRAKCJA = "abstrakcja"
    KONSUMENT_ABSTRAKCJI = "jedyny konsument abstrakcji"
    AGENT_STRATEGII = "agent strategii"
    CZYTNIK = "czytnik blueprintu"
    KONSUMENT_CZYTNIKA = "jedyny konsument czytnika blueprintu"
    AGENT_BLUEPRINTU = "agent blueprintu"
    KIERUNEK_PORTU = "kierunek portu"
    NIEROZWIAZYWALNY = "import nierozwiązywalny"


@dataclass(frozen=True, order=True)
class Naruszenie:
    regula: Regula
    plik: str
    nazwa: str
    """Rozwiązana nazwa (zakaz), brakujący moduł albo opis wymogu (wymóg),
    `linia N, level L` (import nierozwiązywalny) albo `brak pliku`."""
    komunikat: str


@dataclass(frozen=True)
class _Wyciag:
    instrukcje: tuple[ast.Import | ast.ImportFrom, ...]
    import_wbudowany: bool


@dataclass(frozen=True)
class Importy:
    nazwy: frozenset[str]
    nierozwiazywalne: tuple[tuple[int, int], ...]
    """Importy względne bez pakietu docelowego: (linia, level)."""
    import_wbudowany: bool


# Klucz pamięci to samo źródło: zbiór z dysku (w tym wielomegabajtowy strategy_table.py)
# parsujemy raz na bieg, a przypadek syntetyczny płaci tylko za plik zmieniony.
@cache
def _wyciag(zrodlo: str) -> _Wyciag:
    instrukcje: list[ast.Import | ast.ImportFrom] = []
    import_wbudowany = False
    for node in ast.walk(ast.parse(zrodlo)):
        if isinstance(node, ast.Import | ast.ImportFrom):
            instrukcje.append(node)
        elif isinstance(node, ast.Name) and node.id == "__import__":
            import_wbudowany = True
    return _Wyciag(tuple(instrukcje), import_wbudowany)


def _pakiet(sciezka: str) -> str | None:
    czesci = PurePosixPath(sciezka).parts
    if czesci[0] != "src" or len(czesci) < 3:
        return None
    return ".".join(czesci[1:-1])


def _jest_modulem(nazwa: str, pliki: Mapping[str, str]) -> bool:
    katalog = "src/" + nazwa.replace(".", "/")
    return f"{katalog}.py" in pliki or f"{katalog}/__init__.py" in pliki


def _baza(sciezka: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    pakiet = _pakiet(sciezka)
    if pakiet is None:
        return None
    czesci = pakiet.split(".")
    if node.level - 1 >= len(czesci):
        return None
    baza = czesci[: len(czesci) - (node.level - 1)]
    if node.module is not None:
        baza.append(node.module)
    return ".".join(baza)


def _rozwiaz_importy(sciezka: str, zrodlo: str, pliki: Mapping[str, str]) -> Importy:
    wyciag = _wyciag(zrodlo)
    nazwy: set[str] = set()
    nierozwiazywalne: list[tuple[int, int]] = []
    for node in wyciag.instrukcje:
        if isinstance(node, ast.Import):
            nazwy.update(alias.name for alias in node.names)
            continue
        baza = _baza(sciezka, node)
        if baza is None:
            nierozwiazywalne.append((node.lineno, node.level))
            continue
        for alias in node.names:
            podmodul = f"{baza}.{alias.name}"
            nazwy.add(podmodul if _jest_modulem(podmodul, pliki) else baza)
    return Importy(frozenset(nazwy), tuple(sorted(nierozwiazywalne)), wyciag.import_wbudowany)


def _w_pakietach(nazwa: str, pakiety: Iterable[str]) -> bool:
    return any(nazwa == pakiet or nazwa.startswith(f"{pakiet}.") for pakiet in pakiety)


_CLI = "src/poker/adapters/cli.py"
_CZYTNIK = "src/poker/blueprint_reader.py"
_AGENT_BLUEPRINTU = "src/poker/blueprint_agent.py"
_SPIN_ARENA = "src/poker/spin_arena.py"
_ADAPTERY = (
    "cli.py", "corpus.py", "dataset.py", "export.py", "human.py",
    "lan_client.py", "lan_server.py", "protocol.py", "registry.py",
)
_LISCIE_PROTOKOLU = ("protocol.py", "lan_client.py")  # zależą wyłącznie od innych adapterów
_STDLIB_TYPOWANIE = frozenset({"collections.abc", "dataclasses", "enum", "typing", "itertools"})
_PREFLOP_DOZWOLONE = _STDLIB_TYPOWANIE | {
    "random",
    "poker.cards",
    "poker.evaluation",
    "poker.preflop",
    "poker.preflop_equity_data",
}

_PELNE_LISTY: dict[str, tuple[Regula, frozenset[str]]] = {
    **{
        f"src/poker/{name}": (Regula.PREFLOP, _PREFLOP_DOZWOLONE)
        for name in ("preflop.py", "preflop_sim.py", "preflop_equity.py", "preflop_equity_data.py")
    },
    "src/poker/arena.py": (Regula.ARENA, frozenset({
        "random",
        "math",
        "statistics",
        "dataclasses",
        "collections.abc",
        "poker.agent",
        "poker.events",
        "poker.table",
    })),
    _CZYTNIK: (Regula.CZYTNIK, frozenset({
        "struct", "zlib", "array", "dataclasses", "typing", "collections.abc",
    })),
    _AGENT_BLUEPRINTU: (Regula.AGENT_BLUEPRINTU, frozenset({
        "__future__",
        "random",
        "collections.abc",
        "dataclasses",
        "typing",
        "poker.blueprint_reader",
        "poker.spin",
        "poker.spin_arena",
    })),
}

_DOZWOLONE_Z_PAKIETU: dict[str, tuple[Regula, frozenset[str]]] = {
    _SPIN_ARENA: (Regula.SPIN_ARENA, frozenset({
        "poker.cards",
        "poker.dealing",
        "poker.evaluation",
        "poker.openfold",
        "poker.preflop",
        "poker.spin",
    })),
    "src/poker/adapters/corpus.py": (Regula.KORPUS, frozenset({
        "poker.adapters.export",
        "poker.adapters.registry",
        "poker.agent",
        "poker.events",
        "poker.table",
    })),
    "src/poker/encoding.py": (Regula.ENKODOWANIE, frozenset({
        "poker.cards",
        "poker.evaluation",
        "poker.events",
        "poker.preflop",
        "poker.preflop_equity",
        "poker.projection",
        "poker.views",
    })),
    "src/poker/adapters/dataset.py": (Regula.DATASET, frozenset({
        "poker.adapters.corpus",
        "poker.encoding",
        "poker.events",
    })),
    "src/poker/clone_agent.py": (Regula.KLON, frozenset({
        "poker.agent",
        "poker.cards",
        "poker.clone_weights",
        "poker.encoding",
        "poker.events",
        "poker.views",
    })),
    "src/poker/clone_training.py": (Regula.KLON, frozenset({
        "poker.encoding",
        "poker.events",
    })),
    "src/poker/mlp_agent.py": (Regula.MLP, frozenset({
        "poker.agent",
        "poker.clone_agent",
        "poker.encoding",
        "poker.events",
        "poker.mlp_weights",
        "poker.views",
    })),
    "src/poker/adapters/lan_server.py": (Regula.LAN, frozenset({
        "poker.adapters.export",
        "poker.adapters.human",
        "poker.adapters.protocol",
        "poker.adapters.registry",
        "poker.agent",
        "poker.events",
        "poker.table",
    })),
    "src/poker/adapters/lan_client.py": (Regula.LAN, frozenset({
        "poker.adapters.protocol",
    })),
    "src/poker/abstraction.py": (Regula.ABSTRAKCJA, frozenset({
        "poker.agent",
        "poker.cards",
        "poker.evaluation",
        "poker.events",  # typy akcji i jawnych akcji — słownik widoku i decyzji
        "poker.preflop",
        "poker.preflop_equity",
        "poker.views",
    })),
    "src/poker/strategy_agent.py": (Regula.AGENT_STRATEGII, frozenset({
        "poker.abstraction",
        "poker.agent",
        "poker.events",
        "poker.strategy_table",
        "poker.views",
    })),
}

_WYMOGI: tuple[tuple[Regula, str, str], ...] = (
    (Regula.ARENA, _CLI, "poker.arena"),
    (Regula.KORPUS, _CLI, "poker.adapters.corpus"),
    (Regula.ENKODOWANIE, "src/poker/encoding.py", "poker.evaluation"),
    (Regula.ENKODOWANIE, "src/poker/encoding.py", "poker.preflop"),
    (Regula.ENKODOWANIE, "src/poker/encoding.py", "poker.preflop_equity"),
    (Regula.DATASET, _CLI, "poker.adapters.dataset"),
    (Regula.CZYTNIK, _CZYTNIK, "struct"),
    (Regula.CZYTNIK, _CZYTNIK, "zlib"),
    # Konwerter (numpy) mieszka poza pakietem i to on zależy od czytnika,
    # a nie odwrotnie — jedno źródło układu bajtowego formatu.
    (Regula.CZYTNIK, "tools/blueprint/pack_blueprint.py", "poker.blueprint_reader"),
    (Regula.KONSUMENT_CZYTNIKA, _AGENT_BLUEPRINTU, "poker.blueprint_reader"),
    (Regula.AGENT_BLUEPRINTU, _AGENT_BLUEPRINTU, "poker.blueprint_reader"),
    (Regula.AGENT_BLUEPRINTU, _AGENT_BLUEPRINTU, "poker.spin_arena"),
    (Regula.AGENT_BLUEPRINTU, "tools/run_arena.py", "poker.blueprint_agent"),
    (Regula.AGENT_BLUEPRINTU, "tools/run_arena.py", "poker.blueprint_reader"),
    (Regula.AGENT_BLUEPRINTU, "tools/run_arena.py", "json"),
)


def _straznik(pliki: Mapping[str, str]) -> list[Naruszenie]:
    importy = {
        sciezka: _rozwiaz_importy(sciezka, zrodlo, pliki) for sciezka, zrodlo in pliki.items()
    }
    naruszenia: set[Naruszenie] = set()

    def zakaz(regula: Regula, sciezka: str, nazwa: str) -> None:
        komunikat = f"[{regula}] {sciezka} importuje {nazwa}"
        naruszenia.add(Naruszenie(regula, sciezka, nazwa, komunikat))

    def nazwy(regula: Regula, sciezka: str) -> frozenset[str]:
        if sciezka in importy:
            return importy[sciezka].nazwy
        komunikat = f"[{regula}] brak pliku {sciezka}"
        naruszenia.add(Naruszenie(regula, sciezka, "brak pliku", komunikat))
        return frozenset()

    for sciezka, wynik in importy.items():
        for linia, level in wynik.nierozwiazywalne:
            nazwa = f"linia {linia}, level {level}"
            komunikat = f"[{Regula.NIEROZWIAZYWALNY}] {sciezka}, {nazwa}: import poza pakietem"
            naruszenia.add(Naruszenie(Regula.NIEROZWIAZYWALNY, sciezka, nazwa, komunikat))
        if not sciezka.startswith("src/poker/"):
            continue
        nazwa_pliku = PurePosixPath(sciezka).name
        for nazwa in wynik.nazwy:
            if _w_pakietach(nazwa, {"numpy"}):
                zakaz(Regula.NUMPY, sciezka, nazwa)
            # Od c2b (POKER-23) abstrakcja ma dokładnie jednego konsumenta: agenta strategii.
            if nazwa == "poker.abstraction" and nazwa_pliku not in (
                "abstraction.py", "strategy_agent.py",
            ):
                zakaz(Regula.KONSUMENT_ABSTRAKCJI, sciezka, nazwa)
            if nazwa == "poker.blueprint_reader" and nazwa_pliku != "blueprint_agent.py":
                zakaz(Regula.KONSUMENT_CZYTNIKA, sciezka, nazwa)
        if PurePosixPath(sciezka).parent != PurePosixPath("src/poker"):
            continue
        for nazwa in wynik.nazwy:
            if nazwa.startswith("poker.adapters"):
                zakaz(Regula.SILNIK_BEZ_ADAPTEROW, sciezka, nazwa)
            if nazwa == "poker.adapters.protocol":
                zakaz(Regula.SILNIK_BEZ_PROTOKOLU, sciezka, nazwa)
            if _w_pakietach(nazwa, IO_FORBIDDEN_IN_ENGINE):
                zakaz(Regula.SILNIK_BEZ_IO, sciezka, nazwa)
            if _w_pakietach(nazwa, {"importlib"}):
                zakaz(Regula.IMPORT_DYNAMICZNY, sciezka, nazwa)
        if wynik.import_wbudowany:
            komunikat = f"[{Regula.IMPORT_DYNAMICZNY}] {sciezka} używa __import__"
            naruszenia.add(Naruszenie(Regula.IMPORT_DYNAMICZNY, sciezka, "__import__", komunikat))

    for sciezka, (regula, dozwolone) in _PELNE_LISTY.items():
        for nazwa in nazwy(regula, sciezka) - dozwolone:
            zakaz(regula, sciezka, nazwa)
    for sciezka, (regula, dozwolone) in _DOZWOLONE_Z_PAKIETU.items():
        for nazwa in nazwy(regula, sciezka) - dozwolone:
            if nazwa.startswith("poker."):
                zakaz(regula, sciezka, nazwa)
    for nazwa in nazwy(Regula.CZYTNIK, _CZYTNIK):
        # czytnik dostaje strumień, nie ścieżkę
        if nazwa.startswith("poker.") or _w_pakietach(nazwa, IO_FORBIDDEN_IN_ENGINE):
            zakaz(Regula.CZYTNIK, _CZYTNIK, nazwa)
    for nazwa in nazwy(Regula.AGENT_BLUEPRINTU, _AGENT_BLUEPRINTU):
        if _w_pakietach(nazwa, IO_FORBIDDEN_IN_ENGINE):
            zakaz(Regula.AGENT_BLUEPRINTU, _AGENT_BLUEPRINTU, nazwa)
    # Kierunek portu: arena definiuje port i nic nie wie o agencie blueprintu.
    if "poker.blueprint_agent" in nazwy(Regula.KIERUNEK_PORTU, _SPIN_ARENA):
        zakaz(Regula.KIERUNEK_PORTU, _SPIN_ARENA, "poker.blueprint_agent")

    for module in _ADAPTERY:
        if module in _LISCIE_PROTOKOLU:
            continue
        sciezka = f"src/poker/adapters/{module}"
        regula = Regula.ADAPTERY_ZALEZA_OD_SILNIKA
        if not any(
            nazwa.startswith("poker.") and not nazwa.startswith("poker.adapters.")
            for nazwa in nazwy(regula, sciezka)
        ):
            komunikat = f"[{regula}] {sciezka}: brak importu silnika"
            naruszenia.add(Naruszenie(regula, sciezka, "brak importu silnika", komunikat))
    for regula, sciezka, modul in _WYMOGI:
        if modul not in nazwy(regula, sciezka):
            komunikat = f"[{regula}] {sciezka} nie importuje {modul}"
            naruszenia.add(Naruszenie(regula, sciezka, modul, komunikat))
    return sorted(naruszenia)


@cache
def _pliki_z_dysku() -> Mapping[str, str]:
    sciezki = [
        *sorted(SRC_POKER.rglob("*.py")),
        REPO / "tools" / "run_arena.py",
        REPO / "tools" / "blueprint" / "pack_blueprint.py",
    ]
    return {
        sciezka.relative_to(REPO).as_posix(): sciezka.read_text(encoding="utf-8")
        for sciezka in sciezki
        if sciezka.is_file()
    }


@cache
def _naruszenia_z_dysku() -> list[Naruszenie]:
    return _straznik(_pliki_z_dysku())


def _bez_naruszen(*reguly: Regula) -> None:
    naruszenia = [n for n in _naruszenia_z_dysku() if n.regula in reguly]
    assert not naruszenia, "\n".join(n.komunikat for n in naruszenia)


def test_adaptery_istnieja_i_zaleza_od_silnika() -> None:
    adapters = SRC_POKER / "adapters"
    for module in _ADAPTERY:
        assert (adapters / module).is_file(), module
    _bez_naruszen(Regula.ADAPTERY_ZALEZA_OD_SILNIKA)


def test_silnik_nie_importuje_adapterow() -> None:
    _bez_naruszen(Regula.SILNIK_BEZ_ADAPTEROW)


def test_silnik_nie_wykonuje_io() -> None:
    _bez_naruszen(Regula.SILNIK_BEZ_IO)


def test_silnik_nie_importuje_dynamicznie() -> None:
    _bez_naruszen(Regula.IMPORT_DYNAMICZNY)


def test_kazdy_import_wzgledny_jest_rozwiazywalny() -> None:
    _bez_naruszen(Regula.NIEROZWIAZYWALNY)


def test_moduly_preflop_importuja_wylacznie_karty_i_ewaluator() -> None:
    for name in ("preflop.py", "preflop_sim.py", "preflop_equity.py", "preflop_equity_data.py"):
        assert (SRC_POKER / name).is_file(), name
    _bez_naruszen(Regula.PREFLOP)


def test_arena_zalezy_od_silnika_a_cli_od_areny() -> None:
    assert (SRC_POKER / "arena.py").is_file()
    _bez_naruszen(Regula.ARENA)


def test_spin_arena_zalezy_od_silnika_spin_bez_adapterow() -> None:
    assert (SRC_POKER / "spin_arena.py").is_file()
    _bez_naruszen(Regula.SPIN_ARENA)


def test_korpus_zalezy_od_silnika_rejestru_i_eksportu() -> None:
    assert (SRC_POKER / "adapters" / "corpus.py").is_file()
    _bez_naruszen(Regula.KORPUS)


def test_enkodowanie_zalezy_od_zdarzen_kart_i_widocznosci() -> None:
    assert (SRC_POKER / "encoding.py").is_file()
    _bez_naruszen(Regula.ENKODOWANIE, Regula.DATASET)


def test_clone_agent_i_trening_maja_ograniczone_importy() -> None:
    assert (SRC_POKER / "clone_agent.py").is_file()
    assert (SRC_POKER / "clone_training.py").is_file()
    assert (REPO / "tools" / "train_behavior_clone.py").is_file()
    _bez_naruszen(Regula.KLON)


def test_zadna_czesc_pakietu_nie_importuje_numpy() -> None:
    _bez_naruszen(Regula.NUMPY)


def test_mlp_agent_ma_ograniczone_importy_a_narzedzie_istnieje() -> None:
    assert (SRC_POKER / "mlp_agent.py").is_file()
    assert (SRC_POKER / "mlp_weights.py").is_file()
    assert (REPO / "tools" / "train_mlp_clone.py").is_file()
    _bez_naruszen(Regula.MLP)


def test_lan_zyje_w_adapterach_i_zalezy_od_silnika_widokow_rejestru_i_eksportu() -> None:
    for name in ("lan_server.py", "lan_client.py"):
        assert (SRC_POKER / "adapters" / name).is_file()
    _bez_naruszen(Regula.LAN, Regula.SILNIK_BEZ_PROTOKOLU)


def test_abstrakcja_ma_ograniczone_importy_i_nikt_jej_nie_importuje() -> None:
    assert (SRC_POKER / "abstraction.py").is_file()
    _bez_naruszen(Regula.ABSTRAKCJA, Regula.KONSUMENT_ABSTRAKCJI)


def test_agent_strategii_ma_ograniczone_importy_a_trener_zyje_w_tools() -> None:
    assert (SRC_POKER / "strategy_agent.py").is_file()
    assert (SRC_POKER / "strategy_table.py").is_file()
    assert (REPO / "tools" / "train_mccfr.py").is_file()
    _bez_naruszen(Regula.AGENT_STRATEGII)


def test_renderer_przyjmuje_wylacznie_playerview() -> None:
    from poker.adapters.human import render_view

    parameters = list(inspect.signature(render_view).parameters.values())
    assert len(parameters) == 1
    assert parameters[0].annotation is PlayerView


def test_czytnik_blueprintu_czyta_w_stdlib_i_nie_zna_silnika() -> None:
    """Czytnik artefaktu blueprintu (POKER-51) żyje w pakiecie na czystym stdlib.

    Konsumentem formatu jest agent (POKER-52) i AIVAT, więc czytnik nie może
    wciągać ani silnika, ani adapterów, ani narzędzi z tools/ — a numpy pilnuje
    osobno `test_zadna_czesc_pakietu_nie_importuje_numpy`. Zbiór modułów jest
    wypisany, nie odsiany regułą: nowy import ma być decyzją, nie skutkiem.
    """
    assert (SRC_POKER / "blueprint_reader.py").is_file()
    assert (REPO / "tools" / "blueprint" / "pack_blueprint.py").is_file()
    _bez_naruszen(Regula.CZYTNIK, Regula.KONSUMENT_CZYTNIKA)


def test_agent_blueprintu_ma_ograniczone_importy_a_plik_otwiera_narzedzie() -> None:
    """Agent blueprintu (POKER-52) zna czytnik, prymitywy Spina i model stanu areny.

    Zbiór jest wypisany, nie odsiany regułą: silnik zdarzeniowy, adaptery,
    `tools` i numpy mają zostać poza agentem, a `json` i otwarcie pliku należą
    do narzędzia (INV-P7), więc agent nie widzi ani jednego, ani drugiego.
    """
    assert (SRC_POKER / "blueprint_agent.py").is_file()
    assert (REPO / "tools" / "run_arena.py").is_file()
    _bez_naruszen(Regula.AGENT_BLUEPRINTU, Regula.KIERUNEK_PORTU)


_NOWY_MODUL = "src/poker/zz_syntetyczny.py"


def _z_dopiskiem(sciezka: str, fragment: str, w_funkcji: bool) -> tuple[dict[str, str], int]:
    """Zbiór z dysku z `fragment` dopisanym do pliku (albo nowego modułu) i linia fragmentu."""
    pliki = dict(_pliki_z_dysku())
    if sciezka == _NOWY_MODUL:
        assert sciezka not in pliki
    zrodlo = pliki.get(sciezka, "")
    if zrodlo and not zrodlo.endswith("\n"):
        zrodlo += "\n"
    linia = zrodlo.count("\n") + 1
    if w_funkcji:
        zrodlo += f"\n\ndef _syntetyczna() -> None:\n    {fragment}\n"
        linia += 3
    else:
        zrodlo += f"{fragment}\n"
    pliki[sciezka] = zrodlo
    return pliki, linia


def _z_podmiana(sciezka: str, modul: str, nowa: str) -> dict[str, str]:
    """Zbiór z dysku, w którym każda instrukcja `from <modul> import …` pliku to `nowa`."""
    pliki = dict(_pliki_z_dysku())
    zrodlo = pliki[sciezka]
    linie = zrodlo.splitlines(keepends=True)
    instrukcje = [
        node
        for node in _wyciag(zrodlo).instrukcje
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == modul
    ]
    for node in sorted(instrukcje, key=lambda node: node.lineno, reverse=True):
        assert node.end_lineno is not None
        linie[node.lineno - 1 : node.end_lineno] = [" " * node.col_offset + nowa + "\n"]
    pliki[sciezka] = "".join(linie)
    assert pliki[sciezka] != zrodlo, f"{sciezka} nie ma instrukcji from {modul} import …"
    return pliki


def _sprawdz_czerwien(
    pliki: Mapping[str, str], sciezka: str, oczekiwane: set[tuple[Regula, str]]
) -> None:
    naruszenia = _straznik(pliki)
    znalezione = {(n.regula, n.nazwa) for n in naruszenia}
    assert oczekiwane <= znalezione, "\n".join(n.komunikat for n in naruszenia)
    for naruszenie in naruszenia:
        assert naruszenie.plik == sciezka, naruszenie.komunikat
        assert sciezka in naruszenie.komunikat
        assert naruszenie.nazwa in naruszenie.komunikat
        assert str(naruszenie.regula) in naruszenie.komunikat


_W_FUNKCJI = pytest.mark.parametrize("w_funkcji", [False, True], ids=["modul", "funkcja"])


def _ids(przypadki: Iterable[tuple[str, str, object]]) -> list[str]:
    return [
        f"{sciezka.removeprefix('src/poker/')}|{fragment}" for sciezka, fragment, _ in przypadki
    ]


_ROZWIAZANIA: list[tuple[str, str, set[str]]] = [
    ("src/poker/cards.py", "from .adapters.export import serialize_match_history",
     {"poker.adapters.export"}),
    ("src/poker/cards.py", "from . import adapters", {"poker.adapters"}),
    ("src/poker/cards.py", "from poker import adapters", {"poker.adapters"}),
    ("src/poker/cards.py", "from .adapters import protocol", {"poker.adapters.protocol"}),
    ("src/poker/cards.py", "import os.path", {"os.path"}),
    ("src/poker/cards.py", "from poker import export", {"poker"}),
    ("src/poker/spin_arena.py", "from poker.cards import Card", {"poker.cards"}),
    ("src/poker/__init__.py", "from . import adapters", {"poker.adapters"}),
    ("src/poker/adapters/__init__.py", "from . import export", {"poker.adapters.export"}),
    ("src/poker/adapters/corpus.py", "from ..table import MatchConfig", {"poker.table"}),
    ("src/poker/adapters/corpus.py", "from .. import table", {"poker.table"}),
    ("src/poker/adapters/corpus.py", "from poker import table", {"poker.table"}),
    ("src/poker/adapters/corpus.py", "from poker.table import MatchConfig", {"poker.table"}),
]


@pytest.mark.parametrize(("sciezka", "zrodlo", "oczekiwane"), _ROZWIAZANIA, ids=_ids(_ROZWIAZANIA))
def test_straznik_rozwiazuje_import_do_pelnej_nazwy_modulu(
    sciezka: str, zrodlo: str, oczekiwane: set[str]
) -> None:
    importy = _rozwiaz_importy(sciezka, zrodlo, _pliki_z_dysku())
    assert importy.nazwy == oczekiwane
    assert importy.nierozwiazywalne == ()


_NIEROZWIAZYWALNE: list[tuple[str, str, int]] = [
    ("src/poker/cards.py", "from ... import x", 3),
    ("tools/run_arena.py", "from . import x", 1),
]


@_W_FUNKCJI
@pytest.mark.parametrize(
    ("sciezka", "fragment", "level"), _NIEROZWIAZYWALNE, ids=_ids(_NIEROZWIAZYWALNE)
)
def test_straznik_zglasza_import_wzgledny_nierozwiazywalny(
    sciezka: str, fragment: str, level: int, w_funkcji: bool
) -> None:
    pliki, linia = _z_dopiskiem(sciezka, fragment, w_funkcji)
    naruszenia = [n for n in _straznik(pliki) if n.regula is Regula.NIEROZWIAZYWALNY]
    assert len(naruszenia) == 1, naruszenia
    komunikat = naruszenia[0].komunikat
    assert sciezka in komunikat
    assert f"linia {linia}," in komunikat
    assert f"level {level}" in komunikat


_WARIANTY_CZERWIENI: list[tuple[str, str, set[tuple[Regula, str]]]] = [
    (_NOWY_MODUL, "from .adapters.export import serialize_match_history",
     {(Regula.SILNIK_BEZ_ADAPTEROW, "poker.adapters.export")}),
    (_NOWY_MODUL, "from . import adapters", {(Regula.SILNIK_BEZ_ADAPTEROW, "poker.adapters")}),
    (_NOWY_MODUL, "from poker import adapters",
     {(Regula.SILNIK_BEZ_ADAPTEROW, "poker.adapters")}),
    (_NOWY_MODUL, "from .adapters import protocol", {
        (Regula.SILNIK_BEZ_ADAPTEROW, "poker.adapters.protocol"),
        (Regula.SILNIK_BEZ_PROTOKOLU, "poker.adapters.protocol"),
    }),
    ("src/poker/__init__.py", "from . import adapters",
     {(Regula.SILNIK_BEZ_ADAPTEROW, "poker.adapters")}),
    (_NOWY_MODUL, "import os.path", {(Regula.SILNIK_BEZ_IO, "os.path")}),
    (_NOWY_MODUL, "from os.path import join", {(Regula.SILNIK_BEZ_IO, "os.path")}),
    (_NOWY_MODUL, "import json.decoder", {(Regula.SILNIK_BEZ_IO, "json.decoder")}),
    (_SPIN_ARENA, "from .table import play_match", {(Regula.SPIN_ARENA, "poker.table")}),
    (_SPIN_ARENA, "from . import betting", {(Regula.SPIN_ARENA, "poker.betting")}),
    (_SPIN_ARENA, "from poker import table", {(Regula.SPIN_ARENA, "poker.table")}),
    ("src/poker/encoding.py", "from . import table", {(Regula.ENKODOWANIE, "poker.table")}),
    ("src/poker/clone_agent.py", "from . import table", {(Regula.KLON, "poker.table")}),
    ("src/poker/clone_training.py", "from . import table", {(Regula.KLON, "poker.table")}),
    ("src/poker/mlp_agent.py", "from . import table", {(Regula.MLP, "poker.table")}),
    ("src/poker/abstraction.py", "from . import table", {(Regula.ABSTRAKCJA, "poker.table")}),
    ("src/poker/strategy_agent.py", "from . import table",
     {(Regula.AGENT_STRATEGII, "poker.table")}),
    ("src/poker/adapters/corpus.py", "from ..betting import HeadsUpHand",
     {(Regula.KORPUS, "poker.betting")}),
    ("src/poker/adapters/dataset.py", "from .. import table", {(Regula.DATASET, "poker.table")}),
    ("src/poker/adapters/lan_client.py", "from .. import table", {(Regula.LAN, "poker.table")}),
    ("src/poker/adapters/lan_server.py", "from .. import spin", {(Regula.LAN, "poker.spin")}),
    ("src/poker/arena.py", "from . import spin", {(Regula.ARENA, "poker.spin")}),
    ("src/poker/preflop.py", "from . import table", {(Regula.PREFLOP, "poker.table")}),
    (_CZYTNIK, "from . import spin", {(Regula.CZYTNIK, "poker.spin")}),
    (_AGENT_BLUEPRINTU, "from . import table", {(Regula.AGENT_BLUEPRINTU, "poker.table")}),
    (_NOWY_MODUL, "from .abstraction import ABSTRACTION_VERSION",
     {(Regula.KONSUMENT_ABSTRAKCJI, "poker.abstraction")}),
    (_NOWY_MODUL, "from . import abstraction",
     {(Regula.KONSUMENT_ABSTRAKCJI, "poker.abstraction")}),
    (_NOWY_MODUL, "from poker import abstraction",
     {(Regula.KONSUMENT_ABSTRAKCJI, "poker.abstraction")}),
    (_NOWY_MODUL, "from . import blueprint_reader",
     {(Regula.KONSUMENT_CZYTNIKA, "poker.blueprint_reader")}),
    (_SPIN_ARENA, "from poker import blueprint_reader",
     {(Regula.KONSUMENT_CZYTNIKA, "poker.blueprint_reader")}),
    (_SPIN_ARENA, "from . import blueprint_agent",
     {(Regula.KIERUNEK_PORTU, "poker.blueprint_agent")}),
]


@_W_FUNKCJI
@pytest.mark.parametrize(
    ("sciezka", "fragment", "oczekiwane"), _WARIANTY_CZERWIENI, ids=_ids(_WARIANTY_CZERWIENI)
)
def test_straznik_czerwieni_import_w_zla_strone_w_kazdej_formie(
    sciezka: str, fragment: str, oczekiwane: set[tuple[Regula, str]], w_funkcji: bool
) -> None:
    pliki, _ = _z_dopiskiem(sciezka, fragment, w_funkcji)
    _sprawdz_czerwien(pliki, sciezka, oczekiwane)


@_W_FUNKCJI
@pytest.mark.parametrize(
    ("fragment", "nazwa"),
    [
        ("import importlib", "importlib"),
        ("from importlib import import_module", "importlib"),
        ("m = __import__('poker.adapters')", "__import__"),
    ],
    ids=["import importlib", "from importlib import import_module", "__import__"],
)
def test_straznik_czerwieni_import_dynamiczny_w_silniku(
    fragment: str, nazwa: str, w_funkcji: bool
) -> None:
    pliki, _ = _z_dopiskiem(_NOWY_MODUL, fragment, w_funkcji)
    _sprawdz_czerwien(pliki, _NOWY_MODUL, {(Regula.IMPORT_DYNAMICZNY, nazwa)})


_FORMY_ABSOLUTNE: list[tuple[str, str, set[tuple[Regula, str]]]] = [
    (_NOWY_MODUL, "import poker.adapters.export",
     {(Regula.SILNIK_BEZ_ADAPTEROW, "poker.adapters.export")}),
    (_NOWY_MODUL, "from poker.adapters import protocol", {
        (Regula.SILNIK_BEZ_ADAPTEROW, "poker.adapters.protocol"),
        (Regula.SILNIK_BEZ_PROTOKOLU, "poker.adapters.protocol"),
    }),
    (_NOWY_MODUL, "import os", {(Regula.SILNIK_BEZ_IO, "os")}),
    (_NOWY_MODUL, "from os import path", {(Regula.SILNIK_BEZ_IO, "os")}),
    (_SPIN_ARENA, "from poker.table import play_match", {(Regula.SPIN_ARENA, "poker.table")}),
]


@_W_FUNKCJI
@pytest.mark.parametrize(
    ("sciezka", "fragment", "oczekiwane"), _FORMY_ABSOLUTNE, ids=_ids(_FORMY_ABSOLUTNE)
)
def test_straznik_czerwieni_formy_absolutne(
    sciezka: str, fragment: str, oczekiwane: set[tuple[Regula, str]], w_funkcji: bool
) -> None:
    pliki, _ = _z_dopiskiem(sciezka, fragment, w_funkcji)
    _sprawdz_czerwien(pliki, sciezka, oczekiwane)


def test_cli_z_arena_importowana_wzglednie_nie_narusza_regul() -> None:
    pliki = _z_podmiana(_CLI, "poker.arena", "from ..arena import SeriesConfig, run_series")
    assert _straznik(pliki) == []


def test_cli_z_arena_importowana_z_pakietu_nie_narusza_regul() -> None:
    assert _straznik(_z_podmiana(_CLI, "poker.arena", "from poker import arena")) == []


def test_korpus_ze_stolem_importowanym_wzglednie_nie_narusza_regul() -> None:
    sciezka = "src/poker/adapters/corpus.py"
    pliki = dict(_pliki_z_dysku())
    pliki[sciezka] = pliki[sciezka].replace("from poker.table import", "from ..table import")
    assert pliki[sciezka] != _pliki_z_dysku()[sciezka]
    assert _straznik(pliki) == []


def test_init_adapterow_importujacy_eksport_nie_narusza_regul() -> None:
    sciezka = "src/poker/adapters/__init__.py"
    pliki, _ = _z_dopiskiem(sciezka, "from . import export", False)
    assert pliki[sciezka] != _pliki_z_dysku()[sciezka]
    assert _straznik(pliki) == []


def test_cli_bez_importu_areny_narusza_wymog() -> None:
    # `pass`, bo instrukcja mogłaby być jedyną w bloku
    naruszenia = _straznik(_z_podmiana(_CLI, "poker.arena", "pass"))
    assert [(n.regula, n.plik, n.nazwa) for n in naruszenia] == [
        (Regula.ARENA, _CLI, "poker.arena")
    ]
    assert "cli.py" in naruszenia[0].komunikat
    assert "poker.arena" in naruszenia[0].komunikat


def test_adapter_bez_importu_silnika_narusza_wymog() -> None:
    sciezka = "src/poker/adapters/registry.py"
    pliki = dict(_pliki_z_dysku())
    assert pliki[sciezka] != ""
    pliki[sciezka] = ""
    naruszenia = _straznik(pliki)
    assert [(n.regula, n.plik, n.nazwa) for n in naruszenia] == [
        (Regula.ADAPTERY_ZALEZA_OD_SILNIKA, sciezka, "brak importu silnika")
    ]
    assert "registry.py" in naruszenia[0].komunikat
    assert "brak importu silnika" in naruszenia[0].komunikat


def test_straznik_zglasza_brak_pliku_reguly() -> None:
    pliki = dict(_pliki_z_dysku())
    del pliki["src/poker/arena.py"]
    naruszenia = _straznik(pliki)
    assert [(n.regula, n.plik, n.nazwa) for n in naruszenia] == [
        (Regula.ARENA, "src/poker/arena.py", "brak pliku")
    ]
    assert "src/poker/arena.py" in naruszenia[0].komunikat

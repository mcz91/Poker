"""Tożsamość artefaktu blueprintu porównywalna między regeneracjami (POKER-75).

Manifesty biegu niosą pola ulotne: ścieżki bezwzględne, model CPU, czasy
ścienne i liczbę procesów. Zostają w plikach, bo czytają je narzędzia
(`expost.py` i `margins.py` ładują tensor spod `tensor_dir`, `eps_curve.py`
go cytuje, bezpiecznik kosztu liczy z czasów), ale dwie bezbłędne regeneracje tym samym
kodem różnią się nimi zawsze — sha256 surowego manifestu nie potwierdzi więc
żadnej regeneracji (finding B5 audytu 2026-09-26). Tożsamością manifestu jest
sha256 jego kanonicznej projekcji (`canonical_projection`: pola ulotne
pominięte, reszta bez zmian, JSON z posortowanymi kluczami i bez spacji),
tożsamością każdego innego pliku — sha256 pliku. Konwerter `.bpk` wkłada do
metadanych tę samą projekcję, więc plik `.bpk` porównuje się sha256 pliku.

Wersje python i numpy zostają w projekcji — należą do tożsamości (numpy jest
przypięty w `pyproject.toml`); model CPU do niej nie należy.

Uruchomienie (venv z extras train):

    python tools/blueprint/identity.py --run KATALOG

wypisuje JSON z blokiem `pliki` w formacie `control/prod_identity.json`: każdy
plik pod KATALOG-iem (ścieżka względna) z metodą i sha256.
"""

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def _sibling(name: str) -> ModuleType:
    """Moduł siostrzany z tools/blueprint — tools nie jest pakietem (jak testy reprodukcji)."""
    module = sys.modules.get(name)
    if module is not None:
        return module
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"brak modułu siostrzanego {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


artifacts = _sibling("artifacts")

METHOD_FILE = "sha256 pliku"
METHOD_PROJECTION = "sha256 projekcji"

ANY_KEY = "*"

# Pola ulotne per manifest: ścieżka kluczy od korzenia, `ANY_KEY` = każdy klucz
# na tym poziomie. Wszystko spoza tej listy należy do tożsamości.
EPHEMERAL: dict[str, tuple[tuple[str, ...], ...]] = {
    "solve_manifest.json": (
        ("tensor_dir",),
        ("provenance", "cpu_model"),
        ("seconds_total_this_run",),
        # Raport bezpiecznika w całości: jego ekstrapolacja stoi na czasach ściennych.
        ("cost_fuse",),
        # Tych samych dwóch pól nie bierze `solve_grid.config_hash`: nie zmieniają wyniku.
        ("config", "jobs"),
        ("config", "cost_limit_core_hours"),
        ("boundary", "seconds"),
        ("boundary", "core_seconds_wall"),
        ("boundary", "modes", ANY_KEY, "core_seconds"),
        ("boundary", "source", "dir"),
        ("layers", ANY_KEY, "seconds"),
        ("layers", ANY_KEY, "seconds_per_state"),
        ("layers", ANY_KEY, "core_seconds_wall"),
        ("layers", ANY_KEY, "modes", ANY_KEY, "core_seconds"),
    ),
    "rollout_manifest.json": (("seconds",), ("cpu_model",), ("jobs",)),
    "eps_decomposition.json": (("run",),),
}


def _drop(node: Any, path: tuple[str, ...]) -> None:
    """Usuwa pole spod `path`; brak pola nie jest błędem (bieg częściowy, brzeg liczony)."""
    if not isinstance(node, dict):
        return
    head, rest = path[0], path[1:]
    for key in list(node) if head == ANY_KEY else [head]:
        if key not in node:
            continue
        if rest:
            _drop(node[key], rest)
        else:
            del node[key]


def canonical_projection(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Manifest `name` bez pól ulotnych; wejście zostaje nietknięte."""
    if name not in EPHEMERAL:
        raise ValueError(f"{name}: brak projekcji kanonicznej — tożsamością jest sha256 pliku")
    projected = copy.deepcopy(payload)
    for path in EPHEMERAL[name]:
        _drop(projected, path)
    return projected


def projection_sha256(name: str, payload: dict[str, Any]) -> str:
    """Sha256 kanonicznego JSON projekcji — tożsamość manifestu `name`."""
    canonical = json.dumps(
        canonical_projection(name, payload),
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def position_identity(path: Path) -> dict[str, Any]:
    """Tożsamość jednej pozycji: manifest — sha256 projekcji, każdy inny plik — sha256 pliku.

    Rozmiar w bajtach ma wyłącznie pozycja porównywana po pliku: długość
    manifestu zależy od pól ulotnych, więc rozmiar nie należy do jego tożsamości.
    """
    if path.name in EPHEMERAL:
        return {
            "metoda": METHOD_PROJECTION,
            "sha256": projection_sha256(path.name, artifacts.read_json(path)),
        }
    return {
        "metoda": METHOD_FILE,
        "sha256": artifacts.sha256_file(path),
        "bytes": path.stat().st_size,
    }


def run_identity(root: Path) -> dict[str, Any]:
    """Tożsamość każdego pliku pod `root` kluczem ścieżki względnej — blok `pliki`."""
    files = sorted(path for path in root.rglob("*") if path.is_file())
    return {"pliki": {path.relative_to(root).as_posix(): position_identity(path) for path in files}}


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run_identity(args.run), indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

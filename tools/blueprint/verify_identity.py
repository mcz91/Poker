"""Weryfikacja tożsamości artefaktu wobec manifestu (decyzja 30, POKER-58).

Porównuje katalog biegu z `prod_identity.json` po sha256 i rozmiarze.
Zgodność = pomiary przy tym artefakcie nadal obowiązują (PUŁAPKA POKER-24).
Jakikolwiek rozjazd → kod wyjścia różny od zera.

    python tools/blueprint/verify_identity.py --dir PROD
    python tools/blueprint/verify_identity.py --dir PROD \
        --manifest tools/blueprint/control/prod_identity.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parent / "control" / "prod_identity.json"
)


@dataclass(frozen=True, slots=True)
class FileMismatch:
    """Jeden plik, który nie zgadza się z manifestem."""

    path: str
    kind: str
    expected_sha256: str | None
    actual_sha256: str | None
    expected_bytes: int | None
    actual_bytes: int | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_identity(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"manifest tożsamości nie jest obiektem JSON: {path}")
    files = payload.get("pliki")
    if not isinstance(files, dict) or not files:
        raise ValueError(f"manifest tożsamości nie ma słownika 'pliki': {path}")
    return payload


def compare_tree(run_dir: Path, identity: dict[str, Any]) -> list[FileMismatch]:
    """Rozjazdy per plik z manifestu; pliki poza manifestem są ignorowane."""
    files = identity["pliki"]
    mismatches: list[FileMismatch] = []
    for relative, spec in sorted(files.items()):
        if not isinstance(spec, dict):
            raise ValueError(f"wpis '{relative}' nie jest obiektem")
        expected_sha = spec.get("sha256")
        expected_bytes = spec.get("bytes")
        if not isinstance(expected_sha, str) or not isinstance(expected_bytes, int):
            raise ValueError(f"wpis '{relative}' wymaga pól sha256 i bytes")
        target = run_dir / relative
        if not target.is_file():
            mismatches.append(
                FileMismatch(
                    path=relative,
                    kind="brak",
                    expected_sha256=expected_sha,
                    actual_sha256=None,
                    expected_bytes=expected_bytes,
                    actual_bytes=None,
                )
            )
            continue
        actual_bytes = target.stat().st_size
        actual_sha = sha256_file(target)
        if actual_bytes != expected_bytes or actual_sha != expected_sha:
            kind = "rozmiar" if actual_bytes != expected_bytes else "sha256"
            if actual_bytes != expected_bytes and actual_sha != expected_sha:
                kind = "rozmiar+sha256"
            mismatches.append(
                FileMismatch(
                    path=relative,
                    kind=kind,
                    expected_sha256=expected_sha,
                    actual_sha256=actual_sha,
                    expected_bytes=expected_bytes,
                    actual_bytes=actual_bytes,
                )
            )
    return mismatches


def format_report(mismatches: list[FileMismatch]) -> str:
    if not mismatches:
        return "tożsamość zgodna: wszystkie pliki manifestu mają ten sam sha256 i rozmiar"
    lines = [f"tożsamość ROZJEŻDŻA SIĘ na {len(mismatches)} plikach:"]
    for item in mismatches:
        lines.append(
            f"  {item.path}: {item.kind}"
            f" oczekiwano {item.expected_bytes} B {item.expected_sha256}"
            f" jest {item.actual_bytes} B {item.actual_sha256}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Porównuje katalog artefaktu z manifestem tożsamości."
    )
    parser.add_argument("--dir", required=True, type=Path, help="katalog biegu (PROD/)")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="prod_identity.json (domyślnie tools/blueprint/control/prod_identity.json)",
    )
    args = parser.parse_args(argv)
    if not args.dir.is_dir():
        print(f"brak katalogu biegu: {args.dir}", file=sys.stderr)
        return 2
    try:
        identity = load_identity(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"manifest nieczytelny: {error}", file=sys.stderr)
        return 2
    mismatches = compare_tree(args.dir, identity)
    print(format_report(mismatches))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())

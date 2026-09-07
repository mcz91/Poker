"""Testy weryfikatora tożsamości artefaktu (POKER-58, decyzja 30)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BLUEPRINT = REPO / "tools" / "blueprint"


def _load(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_zgodny_katalog_nie_zglasza_rozjazdu(tmp_path: Path) -> None:
    mod = _load("verify_identity")
    payload = b"artefakt-kontrolny\n"
    (tmp_path / "a.bin").write_bytes(payload)
    (tmp_path / "pod").mkdir()
    (tmp_path / "pod" / "b.txt").write_text("ok\n", encoding="utf-8")
    identity = {
        "pliki": {
            "a.bin": {"bytes": len(payload), "sha256": mod.sha256_file(tmp_path / "a.bin")},
            "pod/b.txt": {
                "bytes": 3,
                "sha256": mod.sha256_file(tmp_path / "pod" / "b.txt"),
            },
        }
    }
    assert mod.compare_tree(tmp_path, identity) == []


def test_podmieniony_bajt_jest_czerwony(tmp_path: Path) -> None:
    mod = _load("verify_identity")
    path = tmp_path / "layer.npz"
    path.write_bytes(b"ABCDEFGH")
    identity = {
        "pliki": {"layer.npz": {"bytes": 8, "sha256": mod.sha256_file(path)}}
    }
    path.write_bytes(b"ABCXEFGH")
    mismatches = mod.compare_tree(tmp_path, identity)
    assert len(mismatches) == 1
    assert mismatches[0].path == "layer.npz"
    assert mismatches[0].kind == "sha256"
    assert mismatches[0].actual_bytes == 8


def test_brak_pliku_i_rozmiar_sa_osobnymi_rozjazdami(tmp_path: Path) -> None:
    mod = _load("verify_identity")
    (tmp_path / "jest.bin").write_bytes(b"xx")
    identity = {
        "pliki": {
            "jest.bin": {"bytes": 4, "sha256": "00" * 32},
            "nie ma.bin": {"bytes": 1, "sha256": "ff" * 32},
        }
    }
    mismatches = {item.path: item for item in mod.compare_tree(tmp_path, identity)}
    assert mismatches["nie ma.bin"].kind == "brak"
    assert mismatches["jest.bin"].kind == "rozmiar+sha256"


def test_cli_zielone_na_zgodnym_i_czerwone_po_mutacji(tmp_path: Path) -> None:
    mod = _load("verify_identity")
    blob = tmp_path / "run" / "tensor" / "x.npz"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"kontrolny")
    manifest = tmp_path / "identity.json"
    manifest.write_text(
        json.dumps(
            {
                "pliki": {
                    "tensor/x.npz": {
                        "bytes": blob.stat().st_size,
                        "sha256": mod.sha256_file(blob),
                    }
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert mod.main(["--dir", str(tmp_path / "run"), "--manifest", str(manifest)]) == 0
    blob.write_bytes(b"kontrolnX")
    assert mod.main(["--dir", str(tmp_path / "run"), "--manifest", str(manifest)]) == 1


def test_domyslny_manifest_w_repo_ma_32_pliki() -> None:
    identity = _load("verify_identity").load_identity(
        REPO / "tools" / "blueprint" / "control" / "prod_identity.json"
    )
    assert len(identity["pliki"]) == 32
    assert identity["pliki"]["blueprint.bpk"]["bytes"] == 19_016_752
    assert identity["pliki"]["blueprint_v2.bpk"]["bytes"] == 40_490_256

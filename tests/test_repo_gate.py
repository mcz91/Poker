"""Test zgodności bramki repozytorium (POKER-4): czerwienieje przy rozjeździe bramki."""

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_konfiguracja_mypy_obejmuje_pakiet_testy_i_narzedzia_blueprintu() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    mypy_config = pyproject["tool"]["mypy"]
    assert mypy_config.get("strict") is True
    # `tools/blueprint` dołożone w POKER-49: narzędzia treningu dostarczają kod
    # do bramki tak samo jak pakiet, więc mają być typowane tak samo.
    assert set(mypy_config.get("files", [])) == {"src", "tests", "tools/blueprint"}


def test_numpy_w_extras_train_przypiety_dokladnie() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    train = pyproject["project"]["optional-dependencies"]["train"]
    assert len(train) == 1
    assert re.fullmatch(r"numpy==\d+\.\d+\.\d+", train[0]), (
        "determinizm bajtowy artefaktów trenowanych numpy wymaga przypiętej wersji"
    )


def test_readme_wylicza_bramke_o_pelnym_zakresie() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "ruff check ." in readme
    assert "ruff check src tests" not in readme
    assert "\nmypy\n" in readme
    assert "\npytest\n" in readme

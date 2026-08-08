"""Test architektury (POKER-9, POKER-10): importy płyną od adapterów do silnika (INV-P7)."""

import ast
import inspect
from pathlib import Path

from poker.views import PlayerView

SRC_POKER = Path(__file__).resolve().parent.parent / "src" / "poker"
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


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_adaptery_istnieja_i_zaleza_od_silnika() -> None:
    adapters = SRC_POKER / "adapters"
    assert (adapters / "cli.py").is_file()
    assert (adapters / "export.py").is_file()
    assert (adapters / "human.py").is_file()
    for module in ("cli.py", "export.py", "human.py"):
        imported = _imports(adapters / module)
        assert any(
            name.startswith("poker.") and not name.startswith("poker.adapters.")
            for name in imported
        ), f"adapter {module} nie zależy od silnika"


def test_silnik_nie_importuje_adapterow() -> None:
    for module in SRC_POKER.glob("*.py"):
        for name in _imports(module):
            assert not name.startswith("poker.adapters"), f"{module.name} importuje {name}"


def test_silnik_nie_wykonuje_io() -> None:
    for module in SRC_POKER.glob("*.py"):
        found = _imports(module) & IO_FORBIDDEN_IN_ENGINE
        assert not found, f"moduł silnika {module.name} importuje I/O: {sorted(found)}"


def test_renderer_przyjmuje_wylacznie_playerview() -> None:
    from poker.adapters.human import render_view

    parameters = list(inspect.signature(render_view).parameters.values())
    assert len(parameters) == 1
    assert parameters[0].annotation is PlayerView

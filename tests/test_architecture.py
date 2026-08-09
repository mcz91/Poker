"""Test architektury (POKER-9, 10, 12): importy płyną od adapterów do silnika (INV-P7)."""

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
    for module in (
        "cli.py", "corpus.py", "dataset.py", "export.py", "human.py", "registry.py",
    ):
        assert (adapters / module).is_file(), module
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


def test_moduly_preflop_importuja_wylacznie_karty_i_ewaluator() -> None:
    allowed = {
        "random",
        "poker.cards",
        "poker.evaluation",
        "poker.preflop",
        "poker.preflop_equity_data",
    }
    for name in ("preflop.py", "preflop_sim.py", "preflop_equity.py", "preflop_equity_data.py"):
        path = SRC_POKER / name
        assert path.is_file(), name
        poza = {
            imported
            for imported in _imports(path)
            if imported not in allowed and not _is_stdlib_typing(imported)
        }
        assert not poza, f"{name} importuje poza dozwolonym zbiorem: {sorted(poza)}"


def _is_stdlib_typing(name: str) -> bool:
    return name in {"collections.abc", "dataclasses", "enum", "typing", "itertools"}


def test_arena_zalezy_od_silnika_a_cli_od_areny() -> None:
    allowed = {
        "random",
        "math",
        "statistics",
        "dataclasses",
        "collections.abc",
        "poker.agent",
        "poker.events",
        "poker.table",
    }
    arena = SRC_POKER / "arena.py"
    assert arena.is_file()
    poza = _imports(arena) - allowed
    assert not poza, f"arena.py importuje poza dozwolonym zbiorem: {sorted(poza)}"
    assert "poker.arena" in _imports(SRC_POKER / "adapters" / "cli.py")


def test_korpus_zalezy_od_silnika_rejestru_i_eksportu() -> None:
    corpus = SRC_POKER / "adapters" / "corpus.py"
    assert corpus.is_file()
    poker_imports = {name for name in _imports(corpus) if name.startswith("poker.")}
    assert poker_imports <= {
        "poker.adapters.export",
        "poker.adapters.registry",
        "poker.agent",
        "poker.events",
        "poker.table",
    }, f"corpus.py importuje poza dozwolonym zbiorem: {sorted(poker_imports)}"
    assert "poker.adapters.corpus" in _imports(SRC_POKER / "adapters" / "cli.py")


def test_enkodowanie_zalezy_od_zdarzen_kart_i_widocznosci() -> None:
    encoding = SRC_POKER / "encoding.py"
    assert encoding.is_file()
    poker_imports = {name for name in _imports(encoding) if name.startswith("poker.")}
    assert poker_imports <= {
        "poker.cards",
        "poker.evaluation",
        "poker.events",
        "poker.preflop",
        "poker.preflop_equity",
        "poker.projection",
        "poker.views",
    }, f"encoding.py importuje poza dozwolonym zbiorem: {sorted(poker_imports)}"
    assert {"poker.evaluation", "poker.preflop", "poker.preflop_equity"} <= poker_imports
    dataset = SRC_POKER / "adapters" / "dataset.py"
    poker_imports = {name for name in _imports(dataset) if name.startswith("poker.")}
    assert poker_imports <= {
        "poker.adapters.corpus",
        "poker.encoding",
        "poker.events",
    }, f"dataset.py importuje poza dozwolonym zbiorem: {sorted(poker_imports)}"
    assert "poker.adapters.dataset" in _imports(SRC_POKER / "adapters" / "cli.py")


def test_clone_agent_i_trening_maja_ograniczone_importy() -> None:
    agent = SRC_POKER / "clone_agent.py"
    assert agent.is_file()
    poker_imports = {name for name in _imports(agent) if name.startswith("poker.")}
    assert poker_imports <= {
        "poker.agent",
        "poker.cards",
        "poker.clone_weights",
        "poker.encoding",
        "poker.events",
        "poker.views",
    }, f"clone_agent.py importuje poza dozwolonym zbiorem: {sorted(poker_imports)}"
    training = SRC_POKER / "clone_training.py"
    assert training.is_file()
    poker_imports = {name for name in _imports(training) if name.startswith("poker.")}
    assert poker_imports <= {
        "poker.encoding",
        "poker.events",
    }, f"clone_training.py importuje poza dozwolonym zbiorem: {sorted(poker_imports)}"
    assert (SRC_POKER.parent.parent / "tools" / "train_behavior_clone.py").is_file()


def test_renderer_przyjmuje_wylacznie_playerview() -> None:
    from poker.adapters.human import render_view

    parameters = list(inspect.signature(render_view).parameters.values())
    assert len(parameters) == 1
    assert parameters[0].annotation is PlayerView

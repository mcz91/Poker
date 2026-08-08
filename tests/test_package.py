"""Testy szkieletu pakietu (POKER-1)."""

from importlib import metadata

import poker


def test_wersja_pakietu_zgodna_z_dystrybucja() -> None:
    assert poker.__version__ == metadata.version("poker")

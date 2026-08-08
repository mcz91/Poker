"""Testy historii rozdania (POKER-3): append-only, zamknięcie po końcu rozdania."""

import pytest

from poker.events import BlindPosted, BlindType, HandConfig, HandEnded, HandStarted
from poker.history import HandHistory

CONFIG = HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0)


def test_historia_zachowuje_kolejnosc_dopisywania() -> None:
    history = HandHistory()
    started = HandStarted(config=CONFIG)
    blind = BlindPosted(seat=0, blind=BlindType.SMALL, amount=1)
    history.append(started)
    history.append(blind)
    assert history.events() == (started, blind)


def test_zwrocone_zdarzenia_sa_niemutowalna_migawka() -> None:
    history = HandHistory()
    history.append(HandStarted(config=CONFIG))
    snapshot = history.events()
    history.append(BlindPosted(seat=0, blind=BlindType.SMALL, amount=1))
    assert isinstance(snapshot, tuple)
    assert len(snapshot) == 1
    assert len(history.events()) == 2


def test_zapis_po_koncu_rozdania_jest_bledem() -> None:
    history = HandHistory()
    history.append(HandStarted(config=CONFIG))
    history.append(HandEnded())
    with pytest.raises(ValueError, match="zamkni"):
        history.append(BlindPosted(seat=0, blind=BlindType.SMALL, amount=1))


def test_api_historii_nie_udostepnia_mutacji_ani_usuwania() -> None:
    public_api = [name for name in dir(HandHistory) if not name.startswith("_")]
    assert public_api == ["append", "events"]

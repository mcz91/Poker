"""Testy eksportu historii (POKER-9): round-trip, determinizm, wersja formatu."""

import json

import pytest

from poker.adapters.export import (
    FORMAT_VERSION,
    deserialize_match_history,
    serialize_match_history,
)
from poker.events import DeckSeeded, HandEvent
from poker.projection import project
from poker.rule_agent import RuleAgent
from poker.table import MatchConfig, play_match

CONFIG = MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=5)


def rozegrane_historie() -> tuple[tuple[HandEvent, ...], ...]:
    return play_match(CONFIG, seed=7, agents=(RuleAgent(), RuleAgent())).histories


def test_eksport_ma_jawne_pole_wersji_formatu() -> None:
    text = serialize_match_history(rozegrane_historie())
    assert json.loads(text)["format_version"] == FORMAT_VERSION


def test_round_trip_odtwarza_zdarzenia_i_stany_koncowe() -> None:
    histories = rozegrane_historie()
    restored = deserialize_match_history(serialize_match_history(histories))
    assert restored == histories
    for original, back in zip(histories, restored, strict=True):
        assert project(back) == project(original)


def test_eksport_zawiera_zdarzenia_silnikowe() -> None:
    histories = rozegrane_historie()
    assert any(isinstance(event, DeckSeeded) for event in histories[0])
    assert "DeckSeeded" in serialize_match_history(histories)


def test_ten_sam_seed_daje_identyczny_eksport_bajt_w_bajt() -> None:
    first = serialize_match_history(rozegrane_historie())
    second = serialize_match_history(rozegrane_historie())
    assert first.encode("utf-8") == second.encode("utf-8")


def test_deserializacja_odrzuca_zla_wersje_i_nieznany_typ() -> None:
    with pytest.raises(ValueError, match="wersj"):
        deserialize_match_history(json.dumps({"format_version": 999, "hands": []}))
    unknown = json.dumps({"format_version": FORMAT_VERSION, "hands": [[{"type": "Nieznane"}]]})
    with pytest.raises(ValueError, match="typ"):
        deserialize_match_history(unknown)


def test_deserializacja_odrzuca_small_blind_wiekszy_od_big_blinda() -> None:
    config = MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=1)
    histories = play_match(config, seed=0, agents=(RuleAgent(), RuleAgent())).histories
    document = json.loads(serialize_match_history(histories))
    start = document["hands"][0][0]
    assert start["type"] == "HandStarted"
    start["config"]["small_blind"], start["config"]["big_blind"] = 10, 5
    with pytest.raises(ValueError, match=r"small_blind.*big_blind"):
        deserialize_match_history(json.dumps(document))

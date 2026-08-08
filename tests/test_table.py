"""Testy stołu i pętli meczu (POKER-7): rotacja, determinizm, zakończenia."""

from dataclasses import FrozenInstanceError

import pytest

from poker.agent import Agent, Decision
from poker.events import ActionType, BlindPosted, HandEvent, HandStarted
from poker.projection import project
from poker.table import MatchConfig, MatchEndReason, MatchResult, play_match
from poker.views import PlayerView

CONFIG = MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=3)


class Sprawdzajacy:
    """Deterministyczny skrypt testowy: check gdy można, inaczej call, inaczej fold."""

    def decide(self, view: PlayerView) -> Decision:
        legal = view.legal_actions
        assert legal is not None
        if legal.check_allowed:
            return Decision(action=ActionType.CHECK)
        if legal.call_amount is not None:
            return Decision(action=ActionType.CALL)
        return Decision(action=ActionType.FOLD)


class WszystkoDoSrodka:
    """Deterministyczny skrypt testowy: all-in przy pierwszej okazji, inaczej call."""

    def decide(self, view: PlayerView) -> Decision:
        legal = view.legal_actions
        assert legal is not None
        if legal.raise_range is not None:
            return Decision(action=ActionType.RAISE, amount=legal.raise_range.maximum)
        if legal.bet_range is not None:
            return Decision(action=ActionType.BET, amount=legal.bet_range.maximum)
        if legal.call_amount is not None:
            return Decision(action=ActionType.CALL)
        return Decision(action=ActionType.CHECK)


PASYWNI: tuple[Agent, ...] = (Sprawdzajacy(), Sprawdzajacy())
JAMUJACY: tuple[Agent, ...] = (WszystkoDoSrodka(), WszystkoDoSrodka())


def config_startowa(history: tuple[HandEvent, ...]) -> tuple[tuple[int, ...], int]:
    start = history[0]
    assert isinstance(start, HandStarted)
    return start.config.stacks, start.config.button


def test_button_rotuje_a_stacki_przechodza_miedzy_rozdaniami() -> None:
    result = play_match(CONFIG, seed=7, agents=PASYWNI)
    assert len(result.histories) == 3
    buttons = [config_startowa(h)[1] for h in result.histories]
    assert buttons == [0, 1, 0]
    for previous, following in zip(result.histories, result.histories[1:], strict=False):
        assert config_startowa(following)[0] == project(previous).stacks
    assert result.stacks == project(result.histories[-1]).stacks


def test_konfiguracja_meczu_to_parametry() -> None:
    config = MatchConfig(small_blind=5, big_blind=10, stacks=(60, 40), button=1, hand_limit=1)
    result = play_match(config, seed=7, agents=PASYWNI)
    stacks, button = config_startowa(result.histories[0])
    assert (stacks, button) == ((60, 40), 1)
    blinds = [e for e in result.histories[0] if isinstance(e, BlindPosted)]
    assert blinds[0].seat == 1
    assert (blinds[0].amount, blinds[1].amount) == (5, 10)


def test_mecz_konczy_sie_po_limicie_rozdan() -> None:
    result = play_match(CONFIG, seed=7, agents=PASYWNI)
    assert result.reason is MatchEndReason.HAND_LIMIT
    assert result.hands_played == 3
    assert sum(result.stacks) == 200


def test_mecz_konczy_sie_bustem_dokladnie_przy_zerze() -> None:
    config = MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=50)
    result = play_match(config, seed=7, agents=JAMUJACY)
    assert result.reason is MatchEndReason.BUST
    assert result.hands_played < 50
    assert 0 in result.stacks
    assert sum(result.stacks) == 200
    for history in result.histories[:-1]:
        assert 0 not in project(history).stacks


def test_stack_ponizej_blindu_gra_o_pomniejszona_pule() -> None:
    config = MatchConfig(small_blind=1, big_blind=2, stacks=(1, 9), button=1, hand_limit=10)
    result = play_match(config, seed=7, agents=PASYWNI)
    first_hand_blinds = [e for e in result.histories[0] if isinstance(e, BlindPosted)]
    big_blind_event = next(e for e in first_hand_blinds if e.seat == 0)
    assert big_blind_event.amount == 1
    assert all(stack >= 0 for stack in result.stacks)
    assert result.reason is MatchEndReason.BUST
    assert result.hands_played == 2
    assert result.stacks == (0, 10)


def test_ten_sam_seed_meczu_daje_identyczna_historie() -> None:
    first = play_match(CONFIG, seed=42, agents=JAMUJACY)
    second = play_match(CONFIG, seed=42, agents=JAMUJACY)
    assert first == second
    other = play_match(CONFIG, seed=43, agents=JAMUJACY)
    assert first.histories != other.histories


def test_suma_zetonow_stala_przez_caly_mecz() -> None:
    result = play_match(CONFIG, seed=11, agents=JAMUJACY)
    total = sum(CONFIG.stacks)
    for history in result.histories:
        for length in range(1, len(history) + 1):
            state = project(history[:length])
            assert sum(state.stacks) + state.pot == config_startowa(history)[0][0] + (
                config_startowa(history)[0][1]
            )
        assert project(history).pot == 0
    assert sum(result.stacks) == total


def test_wynik_i_historie_sa_niemutowalne() -> None:
    result = play_match(CONFIG, seed=7, agents=PASYWNI)
    assert isinstance(result, MatchResult)
    assert isinstance(result.histories, tuple)
    assert all(isinstance(history, tuple) for history in result.histories)
    with pytest.raises(FrozenInstanceError):
        result.hands_played = 99  # type: ignore[misc]


def test_walidacja_konfiguracji_meczu() -> None:
    with pytest.raises(ValueError, match="limit"):
        MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=0)
    with pytest.raises(ValueError, match="2 miejsc"):
        play_match(
            MatchConfig(small_blind=1, big_blind=2, stacks=(50, 60, 70), button=0, hand_limit=1),
            seed=7,
            agents=PASYWNI,
        )
    with pytest.raises(ValueError, match="agent"):
        play_match(CONFIG, seed=7, agents=(Sprawdzajacy(),))

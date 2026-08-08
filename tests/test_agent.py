"""Testy kontraktu agenta (POKER-6): protokół decyzji, brak mutacji, pełne rozdanie."""

import dataclasses

import pytest

from poker.agent import Agent, Decision, apply_decision
from poker.betting import HeadsUpHand
from poker.events import ActionType, HandConfig, HandEnded
from poker.projection import project
from poker.views import PlayerView

CONFIG = HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0)


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


class MinimalnyAgresor:
    """Deterministyczny skrypt testowy: minimalny bet, gdy dostępny, inaczej jak Sprawdzajacy."""

    def decide(self, view: PlayerView) -> Decision:
        legal = view.legal_actions
        assert legal is not None
        if legal.bet_range is not None:
            return Decision(action=ActionType.BET, amount=legal.bet_range.minimum)
        if legal.check_allowed:
            return Decision(action=ActionType.CHECK)
        if legal.call_amount is not None:
            return Decision(action=ActionType.CALL)
        return Decision(action=ActionType.FOLD)


class Mutant:
    """Agent próbujący zmutować widok zamiast decydować."""

    def decide(self, view: PlayerView) -> Decision:
        view.pot = 10_000  # type: ignore[misc]
        return Decision(action=ActionType.CHECK)


def test_pelne_rozdanie_rozgrywaja_agenci_wylacznie_na_widokach() -> None:
    hand = HeadsUpHand(config=CONFIG, seed=13)
    agents: dict[int, Agent] = {0: Sprawdzajacy(), 1: MinimalnyAgresor()}
    while (seat := hand.to_act()) is not None:
        apply_decision(hand, agents[seat])
    events = hand.events()
    assert isinstance(events[-1], HandEnded)
    state = project(events)
    assert sum(state.stacks) + state.pot == 200
    assert state.pot == 0


def test_agent_nie_moze_zmutowac_widoku_ani_historii() -> None:
    hand = HeadsUpHand(config=CONFIG, seed=13)
    before = hand.events()
    with pytest.raises(dataclasses.FrozenInstanceError):
        apply_decision(hand, Mutant())
    assert hand.events() == before


def test_silnik_przyjmuje_dowolny_obiekt_z_protokolem_decide() -> None:
    class AnonimowyFolder:
        def decide(self, view: PlayerView) -> Decision:
            return Decision(action=ActionType.FOLD)

    hand = HeadsUpHand(config=CONFIG, seed=13)
    apply_decision(hand, AnonimowyFolder())
    assert isinstance(hand.events()[-1], HandEnded)
    with pytest.raises(ValueError, match="ruchu"):
        apply_decision(hand, AnonimowyFolder())

"""Kontrakt agenta (INV-P4): decyzja to funkcja z widoku w akcję, bez mutacji gry."""

from dataclasses import dataclass
from typing import Protocol

from poker.betting import HeadsUpHand
from poker.events import ActionType
from poker.views import PlayerView, player_view


@dataclass(frozen=True, slots=True)
class Decision:
    action: ActionType
    amount: int = 0


class Agent(Protocol):
    def decide(self, view: PlayerView) -> Decision: ...


def apply_decision(hand: HeadsUpHand, agent: Agent) -> None:
    seat = hand.to_act()
    if seat is None:
        raise ValueError("żadne miejsce nie jest na ruchu")
    decision = agent.decide(player_view(hand, seat))
    hand.act(seat, decision.action, decision.amount)

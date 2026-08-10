"""Agent strategii MCCFR (c2b, decyzja 07): inferencja stdlib, mieszanie bez stanu.

Decyzja powstaje trzema krokami: widok -> infoset abstrakcji c2a ->
rozkład z artefaktu -> akcja abstrakcyjna -> legalna `Decision`
odwzorowaniem abstrakcji. Mieszanie jest **bez stanu** (decyzja 07,
pkt 4): losowanie to deterministyczna funkcja seeda konstrukcji
i widoku, liczona stabilnym haszem (blake2b — wbudowany `hash()`
jest solony per proces, więc nie nadaje się na kontrakt), a nie
generator trzymany między wywołaniami. Ten sam widok i seed zawsze
dają tę samą akcję, więc replay, lustro areny i INV-P4 działają bez
zmian.

Fallback: infoset nieobecny w artefakcie (albo rozkład bez akcji
dostępnych w tym stanie) daje check-call, a gdy i to niedostępne —
fold; ta sama reguła co w klonach z POKER-16.
"""

from dataclasses import dataclass
from hashlib import blake2b

from poker.abstraction import (
    AbstractAction,
    AbstractActionKind,
    AbstractionConfig,
    abstract_actions,
    decision_for,
    infoset,
)
from poker.agent import Decision
from poker.strategy_table import BET_SIZES, POSTFLOP_BUCKETS, PREFLOP_BUCKETS, STRATEGY
from poker.views import PlayerView

_FALLBACK = AbstractAction(kind=AbstractActionKind.CHECK_CALL)

ABSTRACTION_CONFIG = AbstractionConfig(
    preflop_buckets=PREFLOP_BUCKETS,
    postflop_buckets=POSTFLOP_BUCKETS,
    bet_sizes=tuple(BET_SIZES),
)


def action_key(action: AbstractAction) -> str:
    """Stabilny klucz akcji abstrakcyjnej w artefakcie strategii."""
    if action.size is None:
        return action.kind.value
    return f"{action.kind.value}:{action.size}"


def action_from_key(key: str) -> AbstractAction:
    kind_name, _, size = key.partition(":")
    return AbstractAction(kind=AbstractActionKind(kind_name), size=size or None)


@dataclass(frozen=True, slots=True)
class StrategyAgent:
    seed: int = 0

    def decide(self, view: PlayerView) -> Decision:
        available = {
            action_key(action): action
            for action in abstract_actions(view, ABSTRACTION_CONFIG)
        }
        distribution = [
            (available[key], weight)
            for key, weight in STRATEGY.get(infoset(view, ABSTRACTION_CONFIG), ())
            if key in available and weight > 0
        ]
        if not distribution:
            return decision_for(_FALLBACK, view)
        total = sum(weight for _, weight in distribution)
        draw = _stable_draw(self.seed, view) % total
        for action, weight in distribution:
            draw -= weight
            if draw < 0:
                return decision_for(action, view)
        return decision_for(distribution[-1][0], view)


def _stable_draw(seed: int, view: PlayerView) -> int:
    hole = "".join(f"{card.rank.value}{card.suit.value}" for card in view.hole_cards or ())
    board = "".join(f"{card.rank.value}{card.suit.value}" for card in view.board)
    material = f"{seed}|{infoset(view, ABSTRACTION_CONFIG)}|{hole}|{board}"
    digest = blake2b(material.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")

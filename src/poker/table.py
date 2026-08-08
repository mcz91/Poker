"""Stół i pętla meczu heads-up: wiele rozdań, rotacja buttona, wynik meczu."""

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum, unique

from poker.agent import Agent, apply_decision
from poker.betting import HeadsUpHand
from poker.events import HandConfig, HandEvent
from poker.projection import project


@dataclass(frozen=True, slots=True)
class MatchConfig:
    small_blind: int
    big_blind: int
    stacks: tuple[int, ...]
    button: int
    hand_limit: int

    def __post_init__(self) -> None:
        if self.hand_limit < 1:
            raise ValueError(f"limit rozdań musi być dodatni: {self.hand_limit}")
        if any(stack <= 0 for stack in self.stacks):
            raise ValueError("każde miejsce startuje z dodatnim stackiem")
        # Pozostałe granice (blindy, button, niepustość) waliduje HandConfig.
        HandConfig(
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            stacks=self.stacks,
            button=self.button,
        )


@unique
class MatchEndReason(Enum):
    BUST = "bust"
    HAND_LIMIT = "hand_limit"


@dataclass(frozen=True, slots=True)
class MatchResult:
    stacks: tuple[int, ...]
    hands_played: int
    reason: MatchEndReason
    histories: tuple[tuple[HandEvent, ...], ...]


def play_match(
    config: MatchConfig,
    seed: int,
    agents: Sequence[Agent],
    *,
    on_hand: Callable[[tuple[HandEvent, ...]], None] | None = None,
) -> MatchResult:
    if len(config.stacks) != 2:
        raise ValueError(
            "stół obsługuje dokładnie 2 miejsca (heads-up); multiway to gałąź pokerroom"
        )
    if len(agents) != len(config.stacks):
        raise ValueError(f"mecz wymaga agenta na każde miejsce: {len(agents)} podano")

    rng = random.Random(seed)
    stacks: tuple[int, ...] = config.stacks
    button = config.button
    histories: list[tuple[HandEvent, ...]] = []
    reason = MatchEndReason.HAND_LIMIT

    while len(histories) < config.hand_limit:
        hand = HeadsUpHand(
            config=HandConfig(
                small_blind=config.small_blind,
                big_blind=config.big_blind,
                stacks=stacks,
                button=button,
            ),
            seed=rng.getrandbits(64),
        )
        while (seat := hand.to_act()) is not None:
            apply_decision(hand, agents[seat])
        histories.append(hand.events())
        if on_hand is not None:
            on_hand(hand.events())
        stacks = project(hand.events()).stacks
        button = (button + 1) % len(stacks)
        if any(stack == 0 for stack in stacks):
            reason = MatchEndReason.BUST
            break

    return MatchResult(
        stacks=stacks,
        hands_played=len(histories),
        reason=reason,
        histories=tuple(histories),
    )

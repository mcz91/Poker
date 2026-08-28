"""Arena porównawcza agentów: mecze na lustrzanych rozdaniach, wynik w BB/100 (INV-P1)."""

import random
from dataclasses import dataclass
from math import sqrt
from statistics import stdev

from poker.agent import Agent
from poker.table import MatchConfig, MatchResult, play_match

_CI95_Z = 1.96


@dataclass(frozen=True, slots=True)
class SeriesConfig:
    small_blind: int
    big_blind: int
    stacks: tuple[int, ...]
    button: int
    hand_limit: int
    pairs: int

    def __post_init__(self) -> None:
        if self.pairs < 2:
            raise ValueError(f"seria wymaga co najmniej 2 par meczów: {self.pairs}")
        # Pozostałe granice waliduje konfiguracja pojedynczego meczu.
        self.match_config()

    def match_config(self) -> MatchConfig:
        return MatchConfig(
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            stacks=self.stacks,
            button=self.button,
            hand_limit=self.hand_limit,
        )


@dataclass(frozen=True, slots=True)
class SeriesReport:
    pairs: int
    hands: int
    pair_results_bb_per_100: tuple[float, ...]
    bb_per_100: float
    std_bb_per_100: float
    ci95_low: float
    ci95_high: float


def series_pair_seeds(seed: int, pairs: int) -> tuple[int, ...]:
    """Seedy par meczów pochodne od seeda serii — jawny kontrakt odtwarzalności."""
    rng = random.Random(seed)
    return tuple(rng.getrandbits(64) for _ in range(pairs))


def play_mirrored_pair(
    config: SeriesConfig, seed: int, agent_a: Agent, agent_b: Agent
) -> tuple[MatchResult, MatchResult]:
    """Ten sam seed meczu dwukrotnie z zamianą miejsc: obie strony grają te same karty."""
    match_config = config.match_config()
    first = play_match(match_config, seed=seed, agents=(agent_a, agent_b))
    second = play_match(match_config, seed=seed, agents=(agent_b, agent_a))
    return first, second


def run_series(
    config: SeriesConfig, seed: int, agent_a: Agent, agent_b: Agent
) -> SeriesReport:
    pair_results: list[float] = []
    total_hands = 0
    for pair_seed in series_pair_seeds(seed, config.pairs):
        first, second = play_mirrored_pair(config, pair_seed, agent_a, agent_b)
        delta_a = (first.stacks[0] - config.stacks[0]) + (second.stacks[1] - config.stacks[1])
        hands = first.hands_played + second.hands_played
        total_hands += hands
        pair_results.append(delta_a / config.big_blind / hands * 100)
    mean = sum(pair_results) / config.pairs
    std = stdev(pair_results)
    margin = _CI95_Z * std / sqrt(config.pairs)
    return SeriesReport(
        pairs=config.pairs,
        hands=total_hands,
        pair_results_bb_per_100=tuple(pair_results),
        bb_per_100=mean,
        std_bb_per_100=std,
        ci95_low=mean - margin,
        ci95_high=mean + margin,
    )

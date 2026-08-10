"""Trener MCCFR (external sampling) w self-play na abstrakcji c2a — plaster c2b decyzji 07.

Uruchomienie (z korzenia repozytorium, w venv z zainstalowanym pakietem):

    python tools/train_mccfr.py --iterations 1000 --seed 7

Trening jest w pełni seedowany i deterministyczny: seedy rozdań
i losowania przy węzłach przeciwnika pochodzą z jednego seeda
głównego, a przebieg rekurencji jest ustalony — ten sam seed, liczba
iteracji i parametry abstrakcji dają bajt w bajt ten sam artefakt
`src/poker/strategy_table.py`. Węzeł drzewa to (seed rozdania, prefiks
akcji): stan odtwarzamy powtórnym odegraniem prefiksu przez publiczne
API maszyny licytacji, więc trener nie zagląda do wnętrza silnika.

Standard library wystarcza (regret matching na ≤5 akcjach) — numpy,
dozwolony decyzją 06 w tools/, nie był potrzebny.
"""

import argparse
import random
import sys
from pathlib import Path

from poker.abstraction import (
    ABSTRACTION_VERSION,
    AbstractionConfig,
    abstract_actions,
    decision_for,
    infoset,
)
from poker.betting import HeadsUpHand
from poker.events import ActionType, HandConfig
from poker.strategy_agent import action_key
from poker.views import player_view

DENOMINATOR = 10000

Prefix = tuple[tuple[int, ActionType, int], ...]
Table = dict[str, dict[str, float]]


def _replay(config: HandConfig, seed: int, prefix: Prefix) -> HeadsUpHand:
    hand = HeadsUpHand(config=config, seed=seed)
    for seat, action, amount in prefix:
        hand.act(seat, action, amount)
    return hand


def _regret_matching(regrets: dict[str, float], keys: list[str]) -> dict[str, float]:
    positives = {key: max(regrets.get(key, 0.0), 0.0) for key in keys}
    total = sum(positives.values())
    if total <= 0.0:
        return {key: 1.0 / len(keys) for key in keys}
    return {key: value / total for key, value in positives.items()}


def _traverse(
    config: HandConfig,
    seed: int,
    prefix: Prefix,
    player: int,
    regrets: Table,
    average: Table,
    abstraction: AbstractionConfig,
    rng: random.Random,
) -> float:
    hand = _replay(config, seed, prefix)
    seat = hand.to_act()
    if seat is None:
        return float(hand.state().stacks[player] - config.stacks[player])

    view = player_view(hand, seat)
    key = infoset(view, abstraction)
    actions = {action_key(action): action for action in abstract_actions(view, abstraction)}
    keys = sorted(actions)
    strategy = _regret_matching(regrets.setdefault(key, {}), keys)

    def child(name: str) -> Prefix:
        decision = decision_for(actions[name], view)
        return (*prefix, (seat, decision.action, decision.amount))

    if seat != player:
        node_average = average.setdefault(key, {})
        for name in keys:
            node_average[name] = node_average.get(name, 0.0) + strategy[name]
        sampled = _sample(strategy, keys, rng)
        return _traverse(
            config, seed, child(sampled), player, regrets, average, abstraction, rng
        )

    utilities = {
        name: _traverse(config, seed, child(name), player, regrets, average, abstraction, rng)
        for name in keys
    }
    value = sum(strategy[name] * utilities[name] for name in keys)
    node_regrets = regrets[key]
    for name in keys:
        node_regrets[name] = node_regrets.get(name, 0.0) + utilities[name] - value
    return value


def _sample(strategy: dict[str, float], keys: list[str], rng: random.Random) -> str:
    draw = rng.random()
    for name in keys:
        draw -= strategy[name]
        if draw <= 0.0:
            return name
    return keys[-1]


def train(
    config: HandConfig, abstraction: AbstractionConfig, iterations: int, seed: int
) -> Table:
    if iterations < 1:
        raise ValueError(f"liczba iteracji musi być dodatnia: {iterations}")
    regrets: Table = {}
    average: Table = {}
    master = random.Random(seed)
    for _ in range(iterations):
        hand_seed = master.getrandbits(64)
        for player in (0, 1):
            rng = random.Random(master.getrandbits(64))
            _traverse(config, hand_seed, (), player, regrets, average, abstraction, rng)
    return average


def quantize(average: Table) -> dict[str, tuple[tuple[str, int], ...]]:
    """Rozkłady jako całkowite wagi sumujące się dokładnie do DENOMINATOR."""
    table: dict[str, tuple[tuple[str, int], ...]] = {}
    for key in sorted(average):
        weights = average[key]
        total = sum(weights.values())
        names = sorted(weights)
        if total <= 0.0:
            shares = [DENOMINATOR // len(names)] * len(names)
        else:
            shares = [int(weights[name] / total * DENOMINATOR) for name in names]
        remainders = sorted(
            range(len(names)),
            key=lambda index: (
                -((weights[names[index]] / total * DENOMINATOR) - shares[index]
                  if total > 0.0 else 0.0),
                names[index],
            ),
        )
        for position in range(DENOMINATOR - sum(shares)):
            shares[remainders[position % len(names)]] += 1
        table[key] = tuple(zip(names, shares, strict=True))
    return table


def render_module(
    table: dict[str, tuple[tuple[str, int], ...]],
    config: HandConfig,
    abstraction: AbstractionConfig,
    iterations: int,
    seed: int,
) -> str:
    lines = [
        '"""Wygenerowana strategia MCCFR (POKER-23) — nie edytować ręcznie.',
        "",
        "Pełny przepis pochodzenia w stałych poniżej; regeneracja od zera",
        "wyłącznie z tego repozytorium:",
        "",
        f"    python tools/train_mccfr.py --iterations {iterations} --seed {seed}",
        "",
        "STRATEGY: infoset abstrakcji c2a -> krotka (klucz akcji, waga);",
        "wagi sumują się dokładnie do DENOMINATOR.",
        '"""',
        "",
        f"ABSTRACTION_VERSION = {ABSTRACTION_VERSION}",
        f"ITERATIONS = {iterations}",
        f"SEED = {seed}",
        f"DENOMINATOR = {DENOMINATOR}",
        f"PREFLOP_BUCKETS = {abstraction.preflop_buckets}",
        f"POSTFLOP_BUCKETS = {abstraction.postflop_buckets}",
        f"BET_SIZES = {abstraction.bet_sizes!r}",
        f"SMALL_BLIND = {config.small_blind}",
        f"BIG_BLIND = {config.big_blind}",
        f"STACKS = {config.stacks!r}",
        f"BUTTON = {config.button}",
        f"INFOSETS = {len(table)}",
        "",
        "STRATEGY: dict[str, tuple[tuple[str, int], ...]] = {",
    ]
    for key, distribution in table.items():
        lines.append(f"    {key!r}: (")
        lines.extend(f"        ({name!r}, {weight})," for name, weight in distribution)
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--iterations", type=int, default=1000,
                        help="liczba iteracji MCCFR (domyślnie 1000)")
    parser.add_argument("--seed", type=int, default=7, help="seed treningu (domyślnie 7)")
    parser.add_argument("--small-blind", type=int, default=1, help="mały blind (domyślnie 1)")
    parser.add_argument("--big-blind", type=int, default=2, help="duży blind (domyślnie 2)")
    parser.add_argument("--stack", type=int, nargs=2, default=[100, 100],
                        metavar=("MIEJSCE0", "MIEJSCE1"),
                        help="stacki startowe treningu (domyślnie 100 100)")
    parser.add_argument("--button", type=int, default=0, help="button treningu (domyślnie 0)")
    parser.add_argument("--preflop-buckets", type=int, default=8,
                        help="kubełki preflop abstrakcji (domyślnie 8)")
    parser.add_argument("--postflop-buckets", type=int, default=9,
                        help="kubełki postflop abstrakcji (domyślnie 9)")
    parser.add_argument("--bet-sizes", nargs="+", default=["half", "pot"],
                        help="rozmiary zakładów abstrakcji (domyślnie half pot)")
    parser.add_argument("--output", type=Path, default=Path("src/poker/strategy_table.py"),
                        help="ścieżka generowanego artefaktu strategii")
    args = parser.parse_args(argv)
    config = HandConfig(
        small_blind=args.small_blind,
        big_blind=args.big_blind,
        stacks=(args.stack[0], args.stack[1]),
        button=args.button,
    )
    abstraction = AbstractionConfig(
        preflop_buckets=args.preflop_buckets,
        postflop_buckets=args.postflop_buckets,
        bet_sizes=tuple(args.bet_sizes),
    )
    average = train(config, abstraction, iterations=args.iterations, seed=args.seed)
    table = quantize(average)
    args.output.write_text(
        render_module(table, config, abstraction, args.iterations, args.seed), encoding="utf-8"
    )
    print(f"zapisano: {args.output} ({len(table)} infosetów)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

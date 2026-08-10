"""Trener MCCFR (external sampling) na abstrakcji c2a — plastry c2b/c2c decyzji 07.

Uruchomienie (z korzenia repozytorium, w venv z zainstalowanym pakietem):

    python tools/train_mccfr.py --iterations 50000 --seed 7 \
        --checkpoint checkpoint.json --checkpoint-every 1000

Trening jest w pełni seedowany i deterministyczny: losowość iteracji
zależy wyłącznie od pary (seed, numer iteracji), więc bieg przerwany
i wznowiony z checkpointu daje artefakt bajt w bajt identyczny z biegiem
jednorazowym o tej samej łącznej liczbie iteracji (POKER-24). Wznowienie
wymaga `--resume` ze ścieżką checkpointu; bez niego istniejący
checkpoint jest nadpisywany od zera.

Węzeł drzewa to (seed rozdania, prefiks akcji): stan odtwarzamy
publicznym API maszyny licytacji, więc trener nie zagląda do wnętrza
silnika. Standard library wystarcza (regret matching na ≤5 akcjach) —
numpy, dozwolony decyzją 06 w tools/, nie był potrzebny.
"""

import argparse
import json
import random
import sys
from dataclasses import dataclass
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

CHECKPOINT_VERSION = 1

Prefix = tuple[tuple[int, ActionType, int], ...]
Table = dict[str, dict[str, float]]


@dataclass(frozen=True, slots=True)
class TrainingState:
    """Stan treningu wystarczający do wznowienia: liczba iteracji i tablice."""

    done: int
    regrets: Table
    average: Table


def write_checkpoint(path: Path, state: TrainingState) -> None:
    payload = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "done": state.done,
        "regrets": state.regrets,
        "average": state.average,
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def read_checkpoint(path: Path) -> TrainingState:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("checkpoint_version") != CHECKPOINT_VERSION:
        raise ValueError(f"nieobsługiwana wersja checkpointu: {raw!r:.60}")
    done = raw["done"]
    regrets = raw["regrets"]
    average = raw["average"]
    if not isinstance(done, int) or not isinstance(regrets, dict) or not isinstance(average, dict):
        raise ValueError("checkpoint musi zawierać liczbę iteracji i dwie tablice")
    return TrainingState(done=done, regrets=regrets, average=average)


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
    hand: HeadsUpHand,
    player: int,
    regrets: Table,
    average: Table,
    abstraction: AbstractionConfig,
    rng: random.Random,
) -> float:
    """Wartość węzła dla gracza `player`; `hand` musi odpowiadać `prefix`.

    Węzeł przeciwnika schodzi w dół mutując `hand` w miejscu (stan rodzica
    nie jest już potrzebny), a węzeł trenującego gracza odbudowuje rodzica
    tylko dla rodzeństwa — ostatnie dziecko przejmuje `hand`. To tnie liczbę
    odbudów z |A| na |A|-1 przy pełnym rozwinięciu i do zera na ścieżce
    losowanej.
    """
    while True:
        seat = hand.to_act()
        if seat is None:
            return float(hand.state().stacks[player] - config.stacks[player])

        view = player_view(hand, seat)
        key = infoset(view, abstraction)
        actions = {action_key(action): action for action in abstract_actions(view, abstraction)}
        keys = sorted(actions)
        strategy = _regret_matching(regrets.setdefault(key, {}), keys)

        if seat != player:
            node_average = average.setdefault(key, {})
            for name in keys:
                node_average[name] = node_average.get(name, 0.0) + strategy[name]
            name = _sample(strategy, keys, rng)
            decision = decision_for(actions[name], view)
            hand.act(seat, decision.action, decision.amount)
            prefix = (*prefix, (seat, decision.action, decision.amount))
            continue

        utilities: dict[str, float] = {}
        for index, name in enumerate(keys):
            decision = decision_for(actions[name], view)
            child = hand if index == len(keys) - 1 else _replay(config, seed, prefix)
            child.act(seat, decision.action, decision.amount)
            utilities[name] = _traverse(
                config,
                seed,
                (*prefix, (seat, decision.action, decision.amount)),
                child,
                player,
                regrets,
                average,
                abstraction,
                rng,
            )
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


def iteration_rng(seed: int, index: int) -> random.Random:
    """RNG iteracji zależy wyłącznie od (seed, numer) — warunek wznowień."""
    return random.Random(f"{seed}:{index}")


def train(
    config: HandConfig,
    abstraction: AbstractionConfig,
    iterations: int,
    seed: int,
    state: TrainingState | None = None,
    checkpoint: Path | None = None,
    checkpoint_every: int = 0,
) -> TrainingState:
    if iterations < 1:
        raise ValueError(f"liczba iteracji musi być dodatnia: {iterations}")
    current = state if state is not None else TrainingState(done=0, regrets={}, average={})
    if current.done >= iterations:
        return current
    for index in range(current.done, iterations):
        source = iteration_rng(seed, index)
        hand_seed = source.getrandbits(64)
        for player in (0, 1):
            rng = random.Random(source.getrandbits(64))
            _traverse(
                config,
                hand_seed,
                (),
                HeadsUpHand(config=config, seed=hand_seed),
                player,
                current.regrets,
                current.average,
                abstraction,
                rng,
            )
        current = TrainingState(
            done=index + 1, regrets=current.regrets, average=current.average
        )
        if checkpoint is not None and checkpoint_every > 0 and current.done % checkpoint_every == 0:
            write_checkpoint(checkpoint, current)
    if checkpoint is not None:
        write_checkpoint(checkpoint, current)
    return current


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
    parser.add_argument("--iterations", type=int, default=50000,
                        help="łączna liczba iteracji MCCFR (domyślnie 50000)")
    parser.add_argument("--checkpoint", type=Path, default=None, metavar="PLIK",
                        help="zapis stanu treningu do PLIKU (domyślnie brak)")
    parser.add_argument("--checkpoint-every", type=int, default=1000,
                        help="co ile iteracji zapisywać checkpoint (domyślnie 1000)")
    parser.add_argument("--resume", action="store_true",
                        help="wznów z istniejącego --checkpoint zamiast zaczynać od zera")
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
    state = None
    if args.resume:
        if args.checkpoint is None or not args.checkpoint.is_file():
            raise SystemExit("--resume wymaga istniejącego pliku --checkpoint")
        state = read_checkpoint(args.checkpoint)
        print(f"wznowienie od iteracji {state.done}", file=sys.stderr)
    state = train(
        config,
        abstraction,
        iterations=args.iterations,
        seed=args.seed,
        state=state,
        checkpoint=args.checkpoint,
        checkpoint_every=args.checkpoint_every,
    )
    table = quantize(state.average)
    args.output.write_text(
        render_module(table, config, abstraction, state.done, args.seed), encoding="utf-8"
    )
    print(f"zapisano: {args.output} ({len(table)} infosetów)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI meczu heads-up: adapter terminalowy nad play_match (INV-P7)."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from poker.adapters.export import serialize_match_history
from poker.agent import Agent
from poker.evaluation import HandCategory
from poker.rule_agent import RuleAgent, RuleAgentThresholds
from poker.table import MatchConfig, play_match


def _agent_registry() -> dict[str, Agent]:
    return {
        "rule": RuleAgent(),
        "rule-aggressive": RuleAgent(
            thresholds=RuleAgentThresholds(aggress_from=HandCategory.ONE_PAIR)
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    agents = sorted(_agent_registry())
    parser = argparse.ArgumentParser(
        prog="python -m poker.adapters.cli",
        description="Rozgrywa mecz heads-up dwóch agentów i eksportuje pełną historię.",
        exit_on_error=False,
    )
    parser.add_argument("--small-blind", type=int, default=1, help="small blind (domyślnie 1)")
    parser.add_argument("--big-blind", type=int, default=2, help="big blind (domyślnie 2)")
    parser.add_argument(
        "--stack",
        type=int,
        nargs=2,
        default=[100, 100],
        metavar=("MIEJSCE0", "MIEJSCE1"),
        help="stacki startowe (domyślnie 100 100)",
    )
    parser.add_argument("--button", type=int, choices=(0, 1), default=0,
                        help="pozycja startowa buttona (domyślnie 0)")
    parser.add_argument("--hands", type=int, default=100,
                        help="limit rozdań meczu (domyślnie 100)")
    parser.add_argument("--seed", type=int, default=0, help="seed meczu (domyślnie 0)")
    parser.add_argument("--agent0", choices=agents, default="rule",
                        help="agent miejsca 0 (domyślnie rule)")
    parser.add_argument("--agent1", choices=agents, default="rule",
                        help="agent miejsca 1 (domyślnie rule)")
    parser.add_argument("--export", type=Path, default=None, metavar="PLIK",
                        help="ścieżka pliku eksportu historii JSON (domyślnie bez eksportu)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        registry = _agent_registry()
        config = MatchConfig(
            small_blind=args.small_blind,
            big_blind=args.big_blind,
            stacks=(args.stack[0], args.stack[1]),
            button=args.button,
            hand_limit=args.hands,
        )
        result = play_match(config, seed=args.seed, agents=(
            registry[args.agent0], registry[args.agent1],
        ))
    except (argparse.ArgumentError, ValueError) as error:
        print(f"błąd: {error}", file=sys.stderr)
        return 2
    print(f"rozdania: {result.hands_played}")
    print(f"powód zakończenia: {result.reason.value}")
    print(f"stacki końcowe: {result.stacks[0]} {result.stacks[1]}")
    if args.export is not None:
        args.export.write_text(serialize_match_history(result.histories), encoding="utf-8")
        print(f"eksport: {args.export}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

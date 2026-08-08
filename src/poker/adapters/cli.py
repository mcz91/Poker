"""CLI meczu heads-up: adapter terminalowy nad play_match (INV-P7)."""

import argparse
import sys
from collections.abc import Callable, Sequence
from itertools import count
from pathlib import Path
from typing import TextIO

from poker.adapters.corpus import generate_corpus
from poker.adapters.dataset import extract_dataset
from poker.adapters.export import serialize_match_history
from poker.adapters.human import HumanAgent, InputEnded, render_hand_summary
from poker.adapters.registry import agent_registry
from poker.agent import Agent
from poker.arena import SeriesConfig, run_series
from poker.events import HandEvent
from poker.table import MatchConfig, play_match


def build_parser() -> argparse.ArgumentParser:
    agents = sorted(agent_registry())
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
    parser.add_argument("--human", type=int, choices=(0, 1), default=None, metavar="MIEJSCE",
                        help="miejsce człowieka: decyzje z wejścia zamiast agenta tego "
                             "miejsca (domyślnie brak)")
    parser.add_argument("--series", type=int, default=None, metavar="PARY",
                        help="arena: seria PAR meczów agent0 vs agent1 na lustrzanych "
                             "rozdaniach z raportem BB/100 (domyślnie brak; wyklucza "
                             "--human i --export)")
    parser.add_argument("--corpus", type=Path, default=None, metavar="KATALOG",
                        help="korpus self-play: generuje --matches meczów agent0 vs "
                             "agent1 do pustego KATALOGU w formacie eksportu z manifestem "
                             "(domyślnie brak; wyklucza --human, --export i --series)")
    parser.add_argument("--matches", type=int, default=100,
                        help="liczba meczów korpusu (domyślnie 100)")
    parser.add_argument("--jobs", type=int, default=1,
                        help="procesy robocze generacji korpusu (domyślnie 1; zawartość "
                             "korpusu nie zależy od tej liczby)")
    parser.add_argument("--dataset", type=Path, default=None, metavar="PLIK",
                        help="zbiór przykładów decyzyjnych: ekstrakcja z korpusu "
                             "wskazanego przez --from-corpus do nowego PLIKU (domyślnie "
                             "brak; wyklucza pozostałe tryby)")
    parser.add_argument("--from-corpus", type=Path, default=None, metavar="KATALOG",
                        help="katalog korpusu źródłowego dla --dataset")
    parser.add_argument("--export", type=Path, default=None, metavar="PLIK",
                        help="ścieżka pliku eksportu historii JSON (domyślnie bez eksportu)")
    return parser


def _live_reporter(seat: int) -> Callable[[tuple[HandEvent, ...]], None]:
    numbers = count(1)

    def report(history: tuple[HandEvent, ...]) -> None:
        print(f"koniec rozdania {next(numbers)}: {render_hand_summary(history, seat)}")

    return report


def _run_dataset_command(args: argparse.Namespace) -> int:
    for flaga, wartosc in (
        ("--human", args.human), ("--export", args.export),
        ("--series", args.series), ("--corpus", args.corpus),
    ):
        if wartosc is not None:
            raise ValueError(f"--dataset nie łączy się z {flaga}")
    if args.from_corpus is None:
        raise ValueError("--dataset wymaga --from-corpus ze wskazaniem katalogu korpusu")
    report = extract_dataset(args.from_corpus, args.dataset)
    print(
        f"zbiór: przykładów: {report.examples}, rozdań: {report.hands}, "
        f"meczów: {report.matches}"
    )
    print(f"plik: {report.path}")
    return 0


def _run_corpus_command(args: argparse.Namespace) -> int:
    if args.human is not None:
        raise ValueError("--corpus nie łączy się z --human — korpus to self-play agentów")
    if args.export is not None:
        raise ValueError("--corpus nie łączy się z --export — korpus sam zapisuje mecze")
    if args.series is not None:
        raise ValueError("--corpus nie łączy się z --series — arena mierzy, korpus generuje")
    config = MatchConfig(
        small_blind=args.small_blind,
        big_blind=args.big_blind,
        stacks=(args.stack[0], args.stack[1]),
        button=args.button,
        hand_limit=args.hands,
    )
    report = generate_corpus(
        args.corpus,
        config=config,
        agent_names=(args.agent0, args.agent1),
        matches=args.matches,
        seed=args.seed,
        jobs=args.jobs,
    )
    print(f"korpus: meczów: {report.matches}, rozdań: {report.hands}")
    print(f"katalog: {report.directory}")
    return 0


def _run_series_command(args: argparse.Namespace, registry: dict[str, Agent]) -> int:
    if args.human is not None:
        raise ValueError("--series nie łączy się z --human — arena mierzy agentów")
    if args.export is not None:
        raise ValueError("--series nie łączy się z --export — eksport dotyczy meczu")
    config = SeriesConfig(
        small_blind=args.small_blind,
        big_blind=args.big_blind,
        stacks=(args.stack[0], args.stack[1]),
        button=args.button,
        hand_limit=args.hands,
        pairs=args.series,
    )
    report = run_series(
        config, seed=args.seed, agent_a=registry[args.agent0], agent_b=registry[args.agent1]
    )
    print(f"seria: {report.pairs} par meczów (lustrzane rozdania), rozdań: {report.hands}")
    print(f"wynik {args.agent0} vs {args.agent1}: {report.bb_per_100:.2f} BB/100")
    print(f"odchylenie std po parach: {report.std_bb_per_100:.2f}")
    print(f"95% przedział ufności: [{report.ci95_low:.2f}, {report.ci95_high:.2f}]")
    return 0


def main(argv: Sequence[str] | None = None, *, stdin: TextIO | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        registry = agent_registry()
        if args.dataset is not None:
            return _run_dataset_command(args)
        if args.corpus is not None:
            return _run_corpus_command(args)
        if args.series is not None:
            return _run_series_command(args, registry)
        config = MatchConfig(
            small_blind=args.small_blind,
            big_blind=args.big_blind,
            stacks=(args.stack[0], args.stack[1]),
            button=args.button,
            hand_limit=args.hands,
        )
        agents: list[Agent] = [registry[args.agent0], registry[args.agent1]]
        if args.human is not None:
            agents[args.human] = HumanAgent(
                input_stream=stdin if stdin is not None else sys.stdin,
                output_stream=sys.stdout,
            )
    except (argparse.ArgumentError, ValueError) as error:
        print(f"błąd: {error}", file=sys.stderr)
        return 2
    try:
        result = play_match(
            config,
            seed=args.seed,
            agents=(agents[0], agents[1]),
            on_hand=_live_reporter(args.human) if args.human is not None else None,
        )
    except InputEnded as error:
        print(f"koniec wejścia — mecz przerwany: {error}", file=sys.stderr)
        return 1
    if args.human is not None:
        print("przebieg rozdań:")
        for number, history in enumerate(result.histories, start=1):
            print(f"rozdanie {number}: {render_hand_summary(history, args.human)}")
    print(f"rozdania: {result.hands_played}")
    print(f"powód zakończenia: {result.reason.value}")
    print(f"stacki końcowe: {result.stacks[0]} {result.stacks[1]}")
    if args.export is not None:
        args.export.write_text(serialize_match_history(result.histories), encoding="utf-8")
        print(f"eksport: {args.export}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

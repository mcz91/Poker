"""CLI meczu heads-up: adapter terminalowy nad play_match (INV-P7)."""

import argparse
import os
import random
import sys
import threading
from collections.abc import Callable, Sequence
from itertools import count
from pathlib import Path
from typing import TextIO

from poker.adapters.corpus import generate_corpus
from poker.adapters.dataset import extract_dataset
from poker.adapters.export import serialize_match_history
from poker.adapters.human import HumanAgent, InputEnded, render_hand_summary
from poker.adapters.lan_client import run_client
from poker.adapters.lan_server import HUMAN_OPPONENT, TableServer
from poker.adapters.registry import agent_registry
from poker.agent import Agent
from poker.arena import SeriesConfig, run_series
from poker.events import HandEvent
from poker.table import MatchConfig, play_match

_MAX_PORT = 65_535
_ONE_MODE = "jedno wywołanie to jeden tryb"
# Jedno źródło reguł łączenia flag dla walidacji i epilogu pomocy — pomoc nie rozjedzie się
# z tym, co CLI odrzuca. Tabele obejmują wyłącznie flagi z domyślnym None: tylko te da się
# odróżnić od pominiętych bez zmiany parsera.
_EXCLUSIONS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("--serve", ("--connect", "--dataset", "--corpus", "--series"), _ONE_MODE),
    ("--connect", ("--dataset", "--corpus", "--series"), _ONE_MODE),
    ("--dataset", ("--corpus", "--series"), _ONE_MODE),
    ("--corpus", ("--series",), _ONE_MODE),
    (
        "--human",
        ("--serve", "--connect", "--dataset", "--corpus", "--series"),
        "--human wybiera miejsce człowieka w meczu lokalnym",
    ),
    (
        "--export",
        ("--serve", "--connect", "--dataset", "--corpus", "--series"),
        "--export zapisuje historię meczu lokalnego",
    ),
    (
        "--seed",
        ("--serve", "--connect", "--dataset"),
        "seed meczu przy stole LAN losuje serwer, a zbiór nie gra meczów",
    ),
)
_REQUIRED_MODES: tuple[tuple[str, str], ...] = (
    ("--from-corpus", "--dataset"),
    ("--join", "--connect"),
    ("--serve-seed", "--serve"),
    ("--export-dir", "--serve"),
)
_EXIT_CODES = """\
kody wyjścia:
  0 — praca zakończona: mecz, seria, korpus, zbiór, mecz klienta LAN do końca;
      serwer (--serve) zamknięty Ctrl+C
  1 — mecz przerwany: koniec wejścia człowieka; klient LAN: serwer zamknął
      połączenie, przeciwnik się rozłączył albo koniec wejścia (kod 1 daje też
      nieobsłużony wyjątek)
  2 — błąd użycia (argumenty, wykluczenia i zależności flag, ścieżki wyjścia,
      port) albo błąd I/O (pliki, katalogi, sieć, protokół, błąd zgłoszony
      przez serwer LAN)"""


def _epilog() -> str:
    return "\n".join([
        "tryby: --serve, --connect, --dataset, --corpus, --series (bez trybu: mecz lokalny)",
        "sprzeczne flagi albo flaga bez swojego trybu — kod 2, zanim ruszy praca:",
        *(f"  {flag} nie łączy się z {', '.join(others)}" for flag, others, _ in _EXCLUSIONS),
        *(f"  {flag} wymaga {mode}" for flag, mode in _REQUIRED_MODES),
        "",
        _EXIT_CODES,
    ])


def build_parser() -> argparse.ArgumentParser:
    agents = sorted(agent_registry())
    parser = argparse.ArgumentParser(
        prog="python -m poker.adapters.cli",
        description="Rozgrywa mecz heads-up dwóch agentów i eksportuje pełną historię.",
        epilog=_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    parser.add_argument("--seed", type=int, default=None,
                        help="seed meczu: talia każdego rozdania jest jego czystą funkcją "
                             "(domyślnie 0; z --human domyślnie 64 bity entropii systemu, "
                             "wypisane dopiero po meczu — jawny seed czyni talię wyliczalną "
                             "dla każdego, kto go zna; łączenie flag — niżej)")
    parser.add_argument("--agent0", choices=agents, default="rule",
                        help="agent miejsca 0 (domyślnie rule)")
    parser.add_argument("--agent1", choices=agents, default="rule",
                        help="agent miejsca 1 (domyślnie rule)")
    parser.add_argument("--human", type=int, choices=(0, 1), default=None, metavar="MIEJSCE",
                        help="miejsce człowieka: decyzje z wejścia zamiast agenta tego "
                             "miejsca (domyślnie brak)")
    parser.add_argument("--series", type=int, default=None, metavar="PARY",
                        help="arena: seria PAR meczów agent0 vs agent1 na lustrzanych "
                             "rozdaniach z raportem BB/100 (domyślnie brak; łączenie flag "
                             "— niżej)")
    parser.add_argument("--corpus", type=Path, default=None, metavar="KATALOG",
                        help="korpus self-play: generuje --matches meczów agent0 vs "
                             "agent1 do pustego KATALOGU w formacie eksportu z manifestem "
                             "(domyślnie brak; łączenie flag — niżej)")
    parser.add_argument("--matches", type=int, default=100,
                        help="liczba meczów korpusu (domyślnie 100)")
    parser.add_argument("--jobs", type=int, default=1,
                        help="procesy robocze generacji korpusu (domyślnie 1; zawartość "
                             "korpusu nie zależy od tej liczby)")
    parser.add_argument("--dataset", type=Path, default=None, metavar="PLIK",
                        help="zbiór przykładów decyzyjnych: ekstrakcja z korpusu "
                             "wskazanego przez --from-corpus do nowego PLIKU (domyślnie "
                             "brak; łączenie flag — niżej)")
    parser.add_argument("--from-corpus", type=Path, default=None, metavar="KATALOG",
                        help="katalog korpusu źródłowego dla --dataset")
    parser.add_argument("--serve", type=int, default=None, metavar="PORT",
                        help="serwer stołów LAN na PORT (0 = efemeryczny; działa do "
                             "przerwania; domyślnie brak)")
    parser.add_argument("--serve-host", default="0.0.0.0",
                        help="interfejs nasłuchu serwera (domyślnie 0.0.0.0)")
    parser.add_argument("--serve-seed", type=int, default=None, metavar="SEED",
                        help="serwer: seed generatora kodów stołu — przybija wyłącznie "
                             "sekwencję kodów, nie talie (seed meczu każdego stołu serwer "
                             "losuje z entropii systemu); domyślnie brak — kody "
                             "nieodtwarzalne między uruchomieniami")
    parser.add_argument("--export-dir", type=Path, default=None, metavar="KATALOG",
                        help="serwer: eksport historii zakończonych stołów do KATALOGU "
                             "(domyślnie wyłączony)")
    parser.add_argument("--connect", default=None, metavar="HOST:PORT",
                        help="klient LAN: połącz z serwerem; z --join dołącza kodem, "
                             "bez niego tworzy stół z konfiguracją meczu (domyślnie brak)")
    parser.add_argument("--join", default=None, metavar="KOD",
                        help="klient LAN: kod stołu do dołączenia")
    parser.add_argument("--opponent", default=HUMAN_OPPONENT,
                        help="klient LAN przy tworzeniu stołu: 'human' czeka na gracza, "
                             "nazwa agenta z rejestru gra od razu (domyślnie human)")
    parser.add_argument("--export", type=Path, default=None, metavar="PLIK",
                        help="ścieżka pliku eksportu historii JSON (domyślnie bez eksportu)")
    return parser


def _live_reporter(seat: int) -> Callable[[tuple[HandEvent, ...]], None]:
    numbers = count(1)

    def report(history: tuple[HandEvent, ...]) -> None:
        print(f"koniec rozdania {next(numbers)}: {render_hand_summary(history, seat)}")

    return report


def _given(args: argparse.Namespace, flag: str) -> bool:
    return getattr(args, flag.removeprefix("--").replace("-", "_")) is not None


def _check_flag_combinations(args: argparse.Namespace) -> None:
    for flag, others, reason in _EXCLUSIONS:
        for other in others:
            if _given(args, flag) and _given(args, other):
                raise ValueError(f"{flag} nie łączy się z {other} — {reason}")
    for flag, mode in _REQUIRED_MODES:
        if _given(args, flag) and not _given(args, mode):
            raise ValueError(f"{flag} wymaga {mode}")


def _check_output_file(flag: str, path: Path) -> None:
    """Ścieżka wyjścia sprawdzana przed pracą: błąd przy zapisie przepaliłby wynik, np. mecz
    człowieka. Plik celu nie powstaje."""
    directory = path.parent
    if not directory.exists():
        raise ValueError(f"{flag}: katalog {directory} nie istnieje")
    if not directory.is_dir():
        raise ValueError(f"{flag}: {directory} nie jest katalogiem")
    if not os.access(directory, os.W_OK):
        raise ValueError(f"{flag}: brak prawa zapisu do katalogu {directory}")
    if path.is_dir():
        raise ValueError(f"{flag}: {path} jest katalogiem, nie plikiem")
    if path.exists() and not os.access(path, os.W_OK):
        raise ValueError(f"{flag}: brak prawa zapisu do pliku {path}")


def _checked_port(flag: str, port: int) -> int:
    if not 0 <= port <= _MAX_PORT:
        raise ValueError(f"{flag}: port {port} poza zakresem 0–{_MAX_PORT}")
    return port


def _error_exit(error: Exception) -> int:
    print(f"błąd: {error}", file=sys.stderr)
    return 2


def _run_serve_command(args: argparse.Namespace) -> int:
    port = _checked_port("--serve", args.serve)
    if args.export_dir is not None:
        # Serwer eksportuje dopiero po meczu stołu, a błąd zapisu trafia wtedy tylko do jego
        # logu — katalog i prawo zapisu sprawdzane przed startem.
        args.export_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(args.export_dir, os.W_OK):
            raise ValueError(f"--export-dir: brak prawa zapisu do katalogu {args.export_dir}")
    server = TableServer(
        host=args.serve_host,
        port=port,
        export_directory=args.export_dir,
        seed=args.serve_seed,
    )
    host, port = server.start()
    print(f"serwer stołów LAN słucha na {host}:{port} (przerwij Ctrl+C)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
    return 0


def _run_connect_command(args: argparse.Namespace, stdin: TextIO | None) -> int:
    host, _, port_text = args.connect.partition(":")
    if not host or not port_text.isdigit():
        raise ValueError(f"--connect wymaga adresu HOST:PORT, otrzymano {args.connect!r}")
    port = _checked_port("--connect", int(port_text))
    if args.join is not None:
        request: dict[str, object] = {"type": "join", "code": args.join}
    else:
        request = {
            "type": "create",
            "small_blind": args.small_blind,
            "big_blind": args.big_blind,
            "stacks": [args.stack[0], args.stack[1]],
            "button": args.button,
            "hand_limit": args.hands,
            "opponent": args.opponent,
        }
    effective_stdin: TextIO = stdin if stdin is not None else sys.stdin
    try:
        return run_client(host, port, request=request, stdin=effective_stdin, stdout=sys.stdout)
    except OSError as error:
        # Błąd gniazda nie niesie adresu, z którym klient się łączył.
        raise OSError(f"--connect {args.connect}: {error}") from error


def _run_dataset_command(args: argparse.Namespace) -> int:
    if args.from_corpus is None:
        raise ValueError("--dataset wymaga --from-corpus ze wskazaniem katalogu korpusu")
    _check_output_file("--dataset", args.dataset)
    report = extract_dataset(args.from_corpus, args.dataset)
    print(
        f"zbiór: przykładów: {report.examples}, rozdań: {report.hands}, "
        f"meczów: {report.matches}"
    )
    print(f"plik: {report.path}")
    return 0


def _run_corpus_command(args: argparse.Namespace) -> int:
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
        _check_flag_combinations(args)
        registry = agent_registry()
        if args.serve is not None:
            return _run_serve_command(args)
        if args.connect is not None:
            return _run_connect_command(args, stdin)
        # Talia jest czystą funkcją seeda meczu: człowiek przy stole nie może go znać przed
        # końcem gry. Tryby bez człowieka zachowują bajtową odtwarzalność od seeda 0.
        seed_from_entropy = args.seed is None and args.human is not None
        if args.seed is None:
            args.seed = random.SystemRandom().getrandbits(64) if seed_from_entropy else 0
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
        if args.export is not None:
            _check_output_file("--export", args.export)
        agents: list[Agent] = [registry[args.agent0], registry[args.agent1]]
        if args.human is not None:
            agents[args.human] = HumanAgent(
                input_stream=stdin if stdin is not None else sys.stdin,
                output_stream=sys.stdout,
            )
    except (argparse.ArgumentError, ValueError, OSError) as error:
        return _error_exit(error)
    try:
        result = play_match(
            config,
            seed=args.seed,
            agents=(agents[0], agents[1]),
            on_hand=_live_reporter(args.human) if args.human is not None else None,
        )
    except InputEnded as error:
        print(f"koniec wejścia — mecz przerwany: {error}", file=sys.stderr)
        if seed_from_entropy:
            print(f"seed meczu: {args.seed}", file=sys.stderr)
        return 1
    except OSError as error:
        return _error_exit(error)
    if args.human is not None:
        print("przebieg rozdań:")
        for number, history in enumerate(result.histories, start=1):
            print(f"rozdanie {number}: {render_hand_summary(history, args.human)}")
    print(f"rozdania: {result.hands_played}")
    print(f"powód zakończenia: {result.reason.value}")
    print(f"stacki końcowe: {result.stacks[0]} {result.stacks[1]}")
    if seed_from_entropy:
        print(f"seed meczu: {args.seed}")
    if args.export is not None:
        try:
            args.export.write_text(serialize_match_history(result.histories), encoding="utf-8")
        except OSError as error:
            return _error_exit(error)
        print(f"eksport: {args.export}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

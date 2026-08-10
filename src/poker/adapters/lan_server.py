"""Serwer stołów heads-up w LAN (krok 1 pokerroom, decyzja 08) — adapter (INV-P7).

Serwer jest autorytatywny: do klienta wychodzi wyłącznie to, co
wyrenderował `HumanAgent` z widoku jego miejsca (INV-P3 na granicy
procesu) oraz komunikaty protokołu. Każdy stół gra we własnym wątku;
rozłączenie gracza kończy wyłącznie jego stół.
"""

import random
import socket
import threading
from dataclasses import dataclass, field
from pathlib import Path

from poker.adapters.export import serialize_match_history
from poker.adapters.human import HumanAgent, InputEnded, render_hand_summary
from poker.adapters.protocol import (
    MessageStream,
    int_field,
    read_message,
    send_message,
    text_field,
)
from poker.adapters.registry import agent_registry
from poker.agent import Agent
from poker.events import HandEvent
from poker.table import MatchConfig, MatchResult, play_match

HUMAN_OPPONENT = "human"

# Alfabet bez znaków mylących w mowie i piśmie (0/O, 1/I/L); 31**8 ≈ 8.5e11
# możliwych kodów, czyli ~39.6 bita — zgadywanie kodu istniejącego stołu jest
# nieopłacalne, choć to nie jest zabezpieczenie kryptograficzne (decyzja 08 pkt 5).
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
CODE_ATTEMPTS = 16


def generate_code(rng: random.Random) -> str:
    return "".join(rng.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


@dataclass
class _Client:
    stream: MessageStream
    lock: threading.Lock = field(default_factory=threading.Lock)

    def send(self, message: dict[str, object]) -> None:
        with self.lock:
            send_message(self.stream, message)

    def send_quietly(self, message: dict[str, object]) -> None:
        try:
            self.send(message)
        except OSError:
            pass


class _ProtocolIO:
    """Most strumieni HumanAgent <-> protokół: tekst wychodzi wiadomościami,
    readline wysyła prompt i czeka na wejście klienta."""

    def __init__(self, client: _Client) -> None:
        self._client = client
        self._buffer = ""
        self._disconnected = False

    def write(self, text: str) -> None:
        self._buffer += text

    def flush(self) -> None:
        if self._buffer and not self._disconnected:
            try:
                self._client.send({"type": "text", "text": self._buffer})
            except OSError:
                self._disconnected = True
            self._buffer = ""

    def readline(self) -> str:
        # Zerwane łącze zgłaszamy pustą linią: HumanAgent zamienia ją na InputEnded.
        self.flush()
        if self._disconnected:
            return ""
        try:
            self._client.send({"type": "prompt"})
            message = read_message(self._client.stream)
        except (OSError, ValueError):
            self._disconnected = True
            return ""
        if message is None or message.get("type") != "input":
            self._disconnected = True
            return ""
        return text_field(message, "text") + "\n"


@dataclass
class _Table:
    code: str
    config: MatchConfig
    seed: int
    creator: _Client
    opponent_name: str
    joiner: _Client | None = None


class TableServer:
    """Wiele niezależnych stołów heads-up na jednym gnieździe nasłuchującym."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        export_directory: Path | None = None,
        seed: int | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._export_directory = export_directory
        self._listener: socket.socket | None = None
        self._tables: dict[str, _Table] = {}
        self._tables_lock = threading.Lock()
        # Seed podany jawnie daje odtwarzalną sekwencję kodów; pominięty —
        # kody nieodtwarzalne między uruchomieniami. Losowość żyje wyłącznie
        # tutaj, w adapterze (INV-P1).
        self._rng = random.Random(seed)
        self._closing = False

    def start(self) -> tuple[str, int]:
        self._listener = socket.create_server((self._host, self._port))
        host, port = self._listener.getsockname()[:2]
        threading.Thread(target=self._accept_loop, daemon=True).start()
        return str(host), int(port)

    def close(self) -> None:
        self._closing = True
        if self._listener is not None:
            self._listener.close()

    def _accept_loop(self) -> None:
        assert self._listener is not None
        while not self._closing:
            try:
                connection, _ = self._listener.accept()
            except OSError:
                return
            threading.Thread(
                target=self._serve_client, args=(connection,), daemon=True
            ).start()

    def _serve_client(self, connection: socket.socket) -> None:
        stream: MessageStream = connection.makefile("rwb")
        client = _Client(stream=stream)
        try:
            message = read_message(stream)
        except ValueError as error:
            client.send_quietly({"type": "error", "message": str(error)})
            connection.close()
            return
        if message is None:
            connection.close()
            return
        try:
            match message.get("type"):
                case "create":
                    self._handle_create(client, message)
                case "join":
                    self._handle_join(client, message)
                case unknown:
                    raise ValueError(f"nieznany typ wiadomości: {unknown!r}")
        except ValueError as error:
            client.send_quietly({"type": "error", "message": str(error)})
            connection.close()

    def _handle_create(self, client: _Client, message: dict[str, object]) -> None:
        stacks_value = message.get("stacks")
        if not isinstance(stacks_value, list) or len(stacks_value) != 2 or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in stacks_value
        ):
            raise ValueError("pole 'stacks' musi być listą dwóch liczb całkowitych")
        config = MatchConfig(
            small_blind=int_field(message, "small_blind"),
            big_blind=int_field(message, "big_blind"),
            stacks=(stacks_value[0], stacks_value[1]),
            button=int_field(message, "button"),
            hand_limit=int_field(message, "hand_limit"),
        )
        opponent = text_field(message, "opponent")
        if opponent != HUMAN_OPPONENT and opponent not in agent_registry():
            raise ValueError(
                f"nieznany przeciwnik: {opponent!r}; dostępni: "
                f"{[HUMAN_OPPONENT, *sorted(agent_registry())]}"
            )
        with self._tables_lock:
            code = next(
                (
                    candidate
                    for candidate in (
                        generate_code(self._rng) for _ in range(CODE_ATTEMPTS)
                    )
                    if candidate not in self._tables
                ),
                None,
            )
            if code is None:
                raise ValueError("nie udało się wylosować wolnego kodu stołu")
            table = _Table(
                code=code,
                config=config,
                seed=int_field(message, "seed"),
                creator=client,
                opponent_name=opponent,
            )
            self._tables[code] = table
        client.send({"type": "table_created", "code": code})
        if opponent != HUMAN_OPPONENT:
            threading.Thread(target=self._run_match, args=(table,), daemon=True).start()

    def _handle_join(self, client: _Client, message: dict[str, object]) -> None:
        code = text_field(message, "code")
        with self._tables_lock:
            table = self._tables.get(code)
            if table is None or table.opponent_name != HUMAN_OPPONENT:
                raise ValueError(f"stół {code!r} nie czeka na gracza")
            if table.joiner is not None:
                raise ValueError(f"stół {code!r} jest już skompletowany")
            table.joiner = client
        table.creator.send_quietly({"type": "started"})
        client.send({"type": "started"})
        threading.Thread(target=self._run_match, args=(table,), daemon=True).start()

    def _run_match(self, table: _Table) -> None:
        creator_io = _ProtocolIO(table.creator)
        agents: list[Agent] = [HumanAgent(input_stream=creator_io, output_stream=creator_io)]
        clients = [table.creator]
        human_seats = [0]
        if table.joiner is not None:
            joiner_io = _ProtocolIO(table.joiner)
            agents.append(HumanAgent(input_stream=joiner_io, output_stream=joiner_io))
            clients.append(table.joiner)
            human_seats.append(1)
        else:
            agents.append(agent_registry()[table.opponent_name])
        hand_numbers = iter(range(1, table.config.hand_limit + 1))

        def report_hand(history: tuple[HandEvent, ...]) -> None:
            number = next(hand_numbers)
            for seat, seat_client in zip(human_seats, clients, strict=False):
                summary = render_hand_summary(history, seat)
                seat_client.send_quietly(
                    {"type": "text", "text": f"koniec rozdania {number}: {summary}"}
                )

        try:
            result = play_match(
                table.config,
                seed=table.seed,
                agents=(agents[0], agents[1]),
                on_hand=report_hand,
            )
        except InputEnded:
            for seat_client in clients:
                seat_client.send_quietly({"type": "opponent_left"})
        else:
            self._finish(table, clients, result)
        finally:
            with self._tables_lock:
                self._tables.pop(table.code, None)

    def _finish(self, table: _Table, clients: list[_Client], result: MatchResult) -> None:
        for seat_client in clients:
            seat_client.send_quietly({
                "type": "match_end",
                "stacks": list(result.stacks),
                "hands": result.hands_played,
                "reason": result.reason.value,
            })
        if self._export_directory is not None:
            self._export_directory.mkdir(parents=True, exist_ok=True)
            target = self._export_directory / f"{table.code}.json"
            target.write_text(serialize_match_history(result.histories), encoding="utf-8")

"""Serwer stołów heads-up w LAN (krok 1 pokerroom, decyzja 08) — adapter (INV-P7).

Serwer jest autorytatywny: do klienta wychodzi wyłącznie to, co
wyrenderował `HumanAgent` z widoku jego miejsca (INV-P3 na granicy
procesu) oraz komunikaty protokołu. Seed meczu, z którego wynika talia
każdego rozdania, losuje serwer — żaden gracz go nie podaje ani nie poznaje
(decyzja 31 pkt 1). Każdy stół gra we własnym wątku. Rozłączenie gracza,
naruszenie protokołu i wyjątek agenta albo serwera kończą wyłącznie dotknięty
stół: jego gracze dostają opponent_left albo error, a serwer zamyka ich połączenia.
"""

import itertools
import random
import socket
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from io import BufferedRWPair
from pathlib import Path

from poker.adapters.export import serialize_match_history
from poker.adapters.human import HumanAgent, InputEnded, render_hand_summary
from poker.adapters.protocol import (
    MAX_LINE_BYTES,
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

# Żetony trafiają także do obliczeń zmiennoprzecinkowych, a liczby całkowite do 2**53 są
# w float dokładne: 2**52 na miejsce trzyma w tej granicy sumę stacków stołu heads-up.
MAX_CHIPS = 2**52

# Tekst wyjątku silnika albo agenta mógłby nieść karty (INV-P3), więc do graczy idzie
# wyłącznie ta stała, a traceback — na stderr serwera.
INTERNAL_ERROR_MESSAGE = "wewnętrzny błąd serwera (szczegóły w logu serwera)"

# Połączenie, które nic nie przysyła, trzyma deskryptor i wątek; klient wysyła żądanie
# zaraz po połączeniu, więc 10 s to zapas nad opóźnieniem LAN. Liczy bezczynność gniazda
# (każdy odczyt), nie czas całej linii. Tylko pierwsza wiadomość: decyzje przy stole nie
# mają timerów (decyzja 08 pkt 5).
GREETING_TIMEOUT = 10

# Błąd accept bywa przejściowy (EMFILE przy wyczerpanych deskryptorach): pauza zamiast
# końca nasłuchu, a zarazem zamiast pętli na pełnym CPU, zanim deskryptory wrócą.
ACCEPT_RETRY_DELAY = 0.1

# Zamknięcie gniazda z nieprzeczytanymi danymi wysyła RST, który może skasować u klienta
# nieodebrany jeszcze error; po error serwer doczytuje wejście — z limitem czasu i bajtów,
# żeby klient nie trzymał nim wątku.
DRAIN_SECONDS = 0.5
DRAIN_BYTES = 4 * MAX_LINE_BYTES


def generate_code(rng: random.Random) -> str:
    return "".join(rng.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _log_exception(context: str) -> None:
    print(f"serwer stołów LAN: {context}\n{traceback.format_exc()}", end="", file=sys.stderr)


def _export_history(directory: Path, code: str, result: MatchResult) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    history = serialize_match_history(result.histories)
    # Restart z tym samym --serve-seed powtarza kody stołów: pierwszy wolny sufiks zamiast
    # nadpisania, a tryb 'x' czyni wybór nazwy atomowym także dla dwóch procesów.
    for number in itertools.count(1):
        name = f"{code}.json" if number == 1 else f"{code}-{number}.json"
        try:
            with (directory / name).open("x", encoding="utf-8") as target:
                target.write(history)
        except FileExistsError:
            continue
        return


@dataclass
class _Client:
    connection: socket.socket
    stream: BufferedRWPair
    lock: threading.Lock = field(default_factory=threading.Lock)

    def send(self, message: dict[str, object]) -> None:
        with self.lock:
            send_message(self.stream, message)

    def send_quietly(self, message: dict[str, object]) -> None:
        try:
            self.send(message)
        except OSError:
            pass

    def close(self) -> None:
        # Koniec strumienia do klienta wyznacza serwer: bez jawnego zamknięcia gniazdo
        # żyje do odśmiecenia, a pętla accept trzyma ostatnie przyjęte połączenie do
        # następnego accept albo do swojego końca w close() serwera.
        # shutdown przed close budzi wątek czekający w recv na tym gnieździe (twórca stołu
        # ludzi przed dołączeniem) — samo close ani go nie budzi, ani nie wysyła FIN.
        with self.lock:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.stream.close()
            except OSError:
                pass
            self.connection.close()

    def reject(self, reason: str) -> None:
        """error z powodem, potem zamknięcie połączenia bez RST (patrz DRAIN_SECONDS)."""
        self.send_quietly({"type": "error", "message": reason})
        try:
            self.connection.shutdown(socket.SHUT_WR)
            deadline = time.monotonic() + DRAIN_SECONDS
            drained = 0
            while drained < DRAIN_BYTES and (remaining := deadline - time.monotonic()) > 0:
                self.connection.settimeout(remaining)
                chunk = self.connection.recv(MAX_LINE_BYTES)
                if not chunk:
                    break
                drained += len(chunk)
        except OSError:
            pass
        self.close()


class _ProtocolViolation(Exception):
    """Naruszenie protokołu przez gracza przy stole: sprawca dostaje error z jego treścią."""

    def __init__(self, client: _Client, reason: str) -> None:
        super().__init__(reason)
        self.client = client
        self.reason = reason


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
        # Naruszenie protokołu rozpoznaje miejsce wykrycia — odczyt wejścia klienta —
        # nie typ wyjątku: także RecursionError zagnieżdżonego JSON-a jest naruszeniem.
        self.flush()
        if self._disconnected:
            return ""
        try:
            self._client.send({"type": "prompt"})
        except OSError:
            self._disconnected = True
            return ""
        try:
            message = read_message(self._client.stream, MAX_LINE_BYTES)
        except OSError:
            self._disconnected = True
            return ""
        except Exception as error:
            raise _ProtocolViolation(self._client, str(error)) from error
        if message is None:
            self._disconnected = True
            return ""
        if message.get("type") != "input":
            raise _ProtocolViolation(
                self._client,
                f"oczekiwano wiadomości 'input', otrzymano {message.get('type')!r}",
            )
        try:
            return text_field(message, "text") + "\n"
        except ValueError as error:
            raise _ProtocolViolation(self._client, str(error)) from error


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
        match_rng: random.Random | None = None,
        greeting_timeout: float = GREETING_TIMEOUT,
    ) -> None:
        self._host = host
        self._port = port
        self._export_directory = export_directory
        self._greeting_timeout = greeting_timeout
        self._listener: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._tables: dict[str, _Table] = {}
        self._tables_lock = threading.Lock()
        # Losowość żyje wyłącznie tutaj, w adapterze (INV-P1), w dwóch generatorach.
        # Kody stołów: seed podany jawnie daje odtwarzalną sekwencję, pominięty —
        # nieodtwarzalną. Seedy meczów: osobny generator, domyślnie CSPRNG systemu —
        # kod stołu dostaje każdy gracz, więc mały seed kodów da się odzyskać przeszukaniem
        # i nie może wyznaczać talii; wstrzyknięty generator przybija talie w testach.
        self._code_rng = random.Random(seed)
        self._match_rng = match_rng if match_rng is not None else random.SystemRandom()
        self._closing = threading.Event()

    def start(self) -> tuple[str, int]:
        self._listener = socket.create_server((self._host, self._port))
        host, port = self._listener.getsockname()[:2]
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        return str(host), int(port)

    def close(self) -> None:
        self._closing.set()
        if self._listener is not None:
            # Samo close() nie budzi wątku zablokowanego w accept, a gniazdo nasłuchuje dalej
            # i przyjmuje jeszcze jedno połączenie; shutdown budzi accept i zamyka port.
            try:
                self._listener.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._listener.close()
        if self._accept_thread is not None:
            # Limit wyłącznie na wypadek platformy, na której shutdown nie budzi accept.
            self._accept_thread.join(timeout=1.0)

    def _accept_loop(self) -> None:
        assert self._listener is not None
        while not self._closing.is_set():
            try:
                connection, _ = self._listener.accept()
            except OSError as error:
                if self._closing.is_set():
                    return
                print(
                    f"serwer stołów LAN: accept nie powiódł się ({error}); "
                    f"ponowienie za {ACCEPT_RETRY_DELAY} s",
                    file=sys.stderr,
                )
                self._closing.wait(ACCEPT_RETRY_DELAY)
                continue
            threading.Thread(
                target=self._serve_client, args=(connection,), daemon=True
            ).start()

    def _serve_client(self, connection: socket.socket) -> None:
        stream = connection.makefile("rwb")
        client = _Client(connection=connection, stream=stream)
        try:
            connection.settimeout(self._greeting_timeout)
            message = read_message(stream, MAX_LINE_BYTES)
            connection.settimeout(None)
        except TimeoutError:
            client.reject(
                f"brak żądania create ani join przez {self._greeting_timeout} s — "
                "połączenie zamknięte"
            )
            return
        except OSError:
            client.close()
            return
        except Exception as error:  # naruszenie protokołu w pierwszej linii, np. RecursionError
            client.reject(str(error))
            return
        if message is None:
            client.close()
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
            client.reject(str(error))
        except Exception:
            _log_exception(f"obsługa żądania {message.get('type')!r} nie powiodła się")
            client.reject(INTERNAL_ERROR_MESSAGE)

    def _handle_create(self, client: _Client, message: dict[str, object]) -> None:
        if "seed" in message:
            raise ValueError("pole 'seed' nie należy do żądania create: seed meczu losuje serwer")
        stacks_value = message.get("stacks")
        if not isinstance(stacks_value, list) or len(stacks_value) != 2 or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in stacks_value
        ):
            raise ValueError("pole 'stacks' musi być listą dwóch liczb całkowitych")
        small_blind = int_field(message, "small_blind")
        big_blind = int_field(message, "big_blind")
        # Przed MatchConfig: granica nie zależy od kolejności jego walidacji.
        for name, value in (
            ("stacks", max(stacks_value)), ("small_blind", small_blind), ("big_blind", big_blind)
        ):
            if value > MAX_CHIPS:
                raise ValueError(f"pole {name!r} przekracza MAX_CHIPS = {MAX_CHIPS}")
        config = MatchConfig(
            small_blind=small_blind,
            big_blind=big_blind,
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
                        generate_code(self._code_rng) for _ in range(CODE_ATTEMPTS)
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
                seed=self._match_rng.getrandbits(64),
                creator=client,
                opponent_name=opponent,
            )
            # Od losowania do rejestracji kod rezerwuje zamek. table_created idzie pod nim,
            # bo kto zna kod z tej wiadomości, nie może szukać stołu przed powstaniem wpisu,
            # a po nieudanej wysyłce wpis nie powstaje. Wysyłka do świeżego połączenia
            # mieści się w pustym buforze gniazda, więc nie czeka.
            try:
                client.send({"type": "table_created", "code": code})
            except OSError:
                delivered = False
            else:
                delivered = True
                self._tables[code] = table
        if not delivered:
            client.close()
        elif opponent != HUMAN_OPPONENT:
            threading.Thread(target=self._run_match, args=(table,), daemon=True).start()
        else:
            self._await_joiner(table)

    def _await_joiner(self, table: _Table) -> None:
        """Twórca stołu ludzi czeka na dołączającego: koniec jego strumienia albo dane od
        niego przed dołączeniem wycofują stół — najpierw z rejestru, potem połączenie."""
        try:
            pending = table.creator.connection.recv(1, socket.MSG_PEEK)
        except OSError:
            pending = b""
        with self._tables_lock:
            if table.joiner is not None:
                return  # połączenie przejął mecz; MSG_PEEK zostawił mu dane
            self._tables.pop(table.code, None)
        if pending:
            table.creator.reject(
                f"stół {table.code} wycofany: wiadomość przed dołączeniem drugiego gracza"
            )
        else:
            table.creator.close()

    def _handle_join(self, client: _Client, message: dict[str, object]) -> None:
        code = text_field(message, "code")
        with self._tables_lock:
            table = self._tables.get(code)
            if table is None or table.opponent_name != HUMAN_OPPONENT:
                raise ValueError(f"stół {code!r} nie czeka na gracza")
            if table.joiner is not None:
                raise ValueError(f"stół {code!r} jest już skompletowany")
            table.joiner = client
        # Najpierw dołączający: jego nieudana wysyłka nie zostawia twórcy ze started przy
        # stole, który nie ruszy.
        for recipient, partner in ((client, table.creator), (table.creator, client)):
            try:
                recipient.send({"type": "started"})
            except OSError:
                self._unregister(table)
                partner.send_quietly({"type": "opponent_left"})
                recipient.close()
                partner.close()
                return
        threading.Thread(target=self._run_match, args=(table,), daemon=True).start()

    def _unregister(self, table: _Table) -> None:
        with self._tables_lock:
            self._tables.pop(table.code, None)

    def _run_match(self, table: _Table) -> None:
        clients = [table.creator] if table.joiner is None else [table.creator, table.joiner]
        violation: _ProtocolViolation | None = None
        try:
            result = self._play(table, clients)
        except _ProtocolViolation as error:
            violation = error
            for seat_client in clients:
                if seat_client is not violation.client:
                    seat_client.send_quietly({"type": "opponent_left"})
        except InputEnded:
            for seat_client in clients:
                seat_client.send_quietly({"type": "opponent_left"})
        except Exception:
            # opponent_left byłby nieprawdą: przeciwnik nie odszedł.
            _log_exception(f"stół {table.code} przerwany wyjątkiem")
            for seat_client in clients:
                seat_client.send_quietly({"type": "error", "message": INTERNAL_ERROR_MESSAGE})
        else:
            self._finish(table, clients, result)
        finally:
            self._unregister(table)
            for seat_client in clients:
                if violation is None or seat_client is not violation.client:
                    seat_client.close()
            if violation is not None:
                violation.client.reject(violation.reason)

    def _play(self, table: _Table, clients: list[_Client]) -> MatchResult:
        creator_io = _ProtocolIO(table.creator)
        agents: list[Agent] = [HumanAgent(input_stream=creator_io, output_stream=creator_io)]
        human_seats = [0]
        if table.joiner is not None:
            joiner_io = _ProtocolIO(table.joiner)
            agents.append(HumanAgent(input_stream=joiner_io, output_stream=joiner_io))
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

        return play_match(
            table.config,
            seed=table.seed,
            agents=(agents[0], agents[1]),
            on_hand=report_hand,
        )

    def _finish(self, table: _Table, clients: list[_Client], result: MatchResult) -> None:
        for seat_client in clients:
            seat_client.send_quietly({
                "type": "match_end",
                "stacks": list(result.stacks),
                "hands": result.hands_played,
                "reason": result.reason.value,
            })
        if self._export_directory is not None:
            try:
                _export_history(self._export_directory, table.code, result)
            except Exception:
                # Bez error do graczy: mają już prawdziwy wynik w match_end.
                _log_exception(f"eksport historii stołu {table.code} nie powiódł się")

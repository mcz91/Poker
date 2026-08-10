"""Klient terminalowy stołów LAN (krok 1 pokerroom, decyzja 08) — adapter (INV-P7)."""

import socket
from typing import Protocol

from poker.adapters.protocol import (
    MessageStream,
    read_message,
    send_message,
    text_field,
)


class TextInput(Protocol):
    def readline(self) -> str: ...


class TextOutput(Protocol):
    def write(self, text: str) -> object: ...


def run_client(
    host: str,
    port: int,
    request: dict[str, object],
    stdin: TextInput,
    stdout: TextOutput,
) -> int:
    """Wysyła create/join i prowadzi dialog do końca meczu; kody: 0 mecz, 1 przerwanie, 2 błąd."""
    with socket.create_connection((host, port)) as connection:
        stream: MessageStream = connection.makefile("rwb")
        send_message(stream, request)
        while True:
            try:
                message = read_message(stream)
            except ValueError as error:
                stdout.write(f"błąd protokołu: {error}\n")
                return 2
            if message is None:
                stdout.write("serwer zamknął połączenie\n")
                return 1
            match message.get("type"):
                case "text":
                    stdout.write(text_field(message, "text"))
                    if not text_field(message, "text").endswith("\n"):
                        stdout.write("\n")
                case "table_created":
                    stdout.write(f"kod stołu: {text_field(message, 'code')}\n")
                case "started":
                    stdout.write("stół skompletowany — mecz rusza\n")
                case "prompt":
                    line = stdin.readline()
                    if line == "":
                        stdout.write("koniec wejścia — opuszczasz stół\n")
                        return 1
                    send_message(stream, {"type": "input", "text": line.rstrip("\n")})
                case "match_end":
                    stacks = message.get("stacks")
                    reason = message.get("reason")
                    hands = message.get("hands")
                    stdout.write(
                        f"koniec meczu: stacki {stacks}, rozdań {hands}, powód {reason}\n"
                    )
                    return 0
                case "opponent_left":
                    stdout.write("przeciwnik rozłączył się — stół zamknięty\n")
                    return 1
                case "error":
                    stdout.write(f"błąd serwera: {text_field(message, 'message')}\n")
                    return 2
                case unknown:
                    stdout.write(f"nieznana wiadomość serwera: {unknown!r}\n")
                    return 2

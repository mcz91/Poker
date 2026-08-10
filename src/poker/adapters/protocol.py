"""Protokół klient-serwer LAN (decyzja 08): typowane JSON Lines z jawną wersją."""

import json
from typing import Protocol

PROTOCOL_VERSION = 1


class MessageStream(Protocol):
    """Dwukierunkowy strumień bajtów linii — spełnia go plik gniazda (makefile 'rwb')."""

    def readline(self) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def flush(self) -> None: ...


def send_message(stream: MessageStream, message: dict[str, object]) -> None:
    payload = {"v": PROTOCOL_VERSION, **message}
    stream.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
    stream.flush()


def read_message(stream: MessageStream) -> dict[str, object] | None:
    """Odczyt jednej wiadomości; None przy zamkniętym połączeniu."""
    line = stream.readline()
    if not line:
        return None
    parsed: object = json.loads(line)
    if not isinstance(parsed, dict):
        raise ValueError("wiadomość protokołu musi być obiektem JSON")
    if parsed.get("v") != PROTOCOL_VERSION:
        raise ValueError(f"nieznana wersja protokołu: {parsed.get('v')!r}")
    return parsed


def text_field(message: dict[str, object], key: str) -> str:
    value = message.get(key)
    if not isinstance(value, str):
        raise ValueError(f"pole {key!r} wiadomości musi być tekstem")
    return value


def int_field(message: dict[str, object], key: str) -> int:
    value = message.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"pole {key!r} wiadomości musi być liczbą całkowitą")
    return value

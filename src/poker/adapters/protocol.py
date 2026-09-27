"""Protokół klient-serwer LAN (decyzja 08): typowane JSON Lines z jawną wersją."""

import json
from typing import Protocol

# v2: żądanie create nie niesie seeda — seed meczu, z którego wynika talia, losuje
# serwer (decyzja 31 pkt 1); klient v1 jest odrzucany jawnie, nie po cichu.
PROTOCOL_VERSION = 2

# Limit linii czytanej przez serwer, łącznie z '\n': bez niego klient wysyłający bajty bez
# końca linii rozdyma pamięć serwera bez granicy. Żądanie create ze stackami i blindami po
# 2**52 i 18-cyfrowym hand_limit ma ok. 220 B, a z hand_limit o 4300 cyfrach (granica
# konwersji int w Pythonie) — 4499 B; limit ma zapas rzędu wielkości nad jednym i drugim.
# JSON zagnieżdżony na ok. 10 000 poziomów (RecursionError parsera) mieści się w limicie,
# więc limit go nie zatrzymuje.
MAX_LINE_BYTES = 65_536


class MessageStream(Protocol):
    """Dwukierunkowy strumień bajtów linii — spełnia go plik gniazda (makefile 'rwb')."""

    def readline(self, size: int = -1, /) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def flush(self) -> None: ...


def send_message(stream: MessageStream, message: dict[str, object]) -> None:
    payload = {"v": PROTOCOL_VERSION, **message}
    stream.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
    stream.flush()


def read_message(
    stream: MessageStream, max_line_bytes: int | None = None
) -> dict[str, object] | None:
    """Odczyt jednej wiadomości; None przy zamkniętym połączeniu. Z limitem linia dłuższa
    niż max_line_bytes (łącznie z '\\n') jest błędem od razu, bez czekania na koniec linii."""
    if max_line_bytes is None:
        line = stream.readline()
    else:
        line = stream.readline(max_line_bytes)
        if len(line) == max_line_bytes and not line.endswith(b"\n"):
            raise ValueError(
                f"linia wiadomości przekracza {max_line_bytes} bajtów łącznie z końcem linii"
            )
    if not line:
        return None
    parsed: object = json.loads(line)
    if not isinstance(parsed, dict):
        raise ValueError("wiadomość protokołu musi być obiektem JSON")
    if parsed.get("v") != PROTOCOL_VERSION:
        raise ValueError(
            f"nieznana wersja protokołu: {parsed.get('v')!r} (obsługiwana: {PROTOCOL_VERSION})"
        )
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

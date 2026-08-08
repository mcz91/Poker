"""Historia rozdania: append-only sekwencja zdarzeń, zamykana końcem rozdania."""

from poker.events import HandEnded, HandEvent


class HandHistory:
    def __init__(self) -> None:
        self._events: list[HandEvent] = []

    def append(self, event: HandEvent) -> None:
        if self._events and isinstance(self._events[-1], HandEnded):
            raise ValueError("historia rozdania jest zamknięta zdarzeniem końca")
        self._events.append(event)

    def events(self) -> tuple[HandEvent, ...]:
        return tuple(self._events)

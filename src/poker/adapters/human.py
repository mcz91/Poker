"""Człowiek przy stole: adapter portu Agent czytający decyzje z terminala (INV-P4, INV-P7)."""

from collections.abc import Sequence
from typing import TextIO

from poker.agent import Decision
from poker.betting import LegalActions
from poker.cards import Card, Rank
from poker.events import (
    ActionTaken,
    ActionType,
    BlindPosted,
    CardsRevealed,
    HandEvent,
    PotAwarded,
    UncalledBetReturned,
)
from poker.views import PlayerView, visible_events

_RANK_SYMBOLS = {Rank.TEN: "T", Rank.JACK: "J", Rank.QUEEN: "Q", Rank.KING: "K", Rank.ACE: "A"}
_INPUT_HINT = "fold, check, call, bet KWOTA, raise KWOTA"


class InputEnded(Exception):
    """Strumień wejścia człowieka się skończył — meczu nie da się kontynuować."""


def card_token(card: Card) -> str:
    return _RANK_SYMBOLS.get(card.rank, str(card.rank.value)) + card.suit.value


def _cards_text(cards: Sequence[Card]) -> str:
    return " ".join(card_token(card) for card in cards)


def _action_text(event: BlindPosted | ActionTaken) -> str:
    if isinstance(event, BlindPosted):
        return f"miejsce {event.seat}: {event.blind.value} blind {event.amount}"
    amount = f" {event.amount}" if event.amount else ""
    return f"miejsce {event.seat}: {event.action.value}{amount}"


def _legal_text(legal: LegalActions) -> str:
    options = ["fold"]
    if legal.check_allowed:
        options.append("check")
    if legal.call_amount is not None:
        options.append(f"call {legal.call_amount}")
    if legal.bet_range is not None:
        options.append(f"bet {legal.bet_range.minimum}..{legal.bet_range.maximum}")
    if legal.raise_range is not None:
        options.append(f"raise {legal.raise_range.minimum}..{legal.raise_range.maximum}")
    return " | ".join(options)


def render_view(view: PlayerView) -> str:
    lines = [
        f"faza: {view.phase.value} | button: miejsce {view.button} "
        f"| blindy: {view.small_blind}/{view.big_blind}",
        f"twoje miejsce: {view.seat} | twoje karty: "
        f"{_cards_text(view.hole_cards) if view.hole_cards else '(nierozdane)'}",
        f"board: {_cards_text(view.board) if view.board else '(pusty)'}",
        f"stacki: {' '.join(str(stack) for stack in view.stacks)} | pula: {view.pot}",
    ]
    if view.visible_actions:
        lines.append("akcje: " + "; ".join(_action_text(event) for event in view.visible_actions))
    revealed = [
        f"miejsce {seat}: {_cards_text(cards)}"
        for seat, cards in enumerate(view.revealed_cards)
        if cards is not None
    ]
    if revealed:
        lines.append("pokazane karty: " + "; ".join(revealed))
    if view.legal_actions is not None:
        lines.append(f"legalne akcje: {_legal_text(view.legal_actions)}")
    return "\n".join(lines)


def render_hand_summary(events: Sequence[HandEvent], seat: int) -> str:
    """Podsumowanie rozdania wyłącznie ze zdarzeń widocznych z danego miejsca (INV-P3)."""
    parts: list[str] = []
    for event in visible_events(events, seat):
        match event:
            case ActionTaken(seat=actor, action=ActionType.FOLD):
                parts.append(f"miejsce {actor} pasuje")
            case CardsRevealed(seat=owner, cards=cards):
                parts.append(f"miejsce {owner} pokazuje {_cards_text(cards)}")
            case UncalledBetReturned(seat=owner, amount=amount):
                parts.append(f"zwrot {amount} dla miejsca {owner}")
            case PotAwarded(seat=winner, amount=amount):
                parts.append(f"pula {amount} dla miejsca {winner}")
            case _:
                pass
    return "; ".join(parts)


def _parse_decision(text: str, legal: LegalActions) -> Decision:
    tokens = text.split()
    if not tokens:
        raise ValueError(f"pusta linia; dostępne: {_INPUT_HINT}")
    word, *rest = tokens
    match word:
        case "fold" | "check" | "call":
            if rest:
                raise ValueError(f"akcja {word} nie przyjmuje kwoty — wyznacza ją silnik")
            if word == "check" and not legal.check_allowed:
                raise ValueError("check niedostępny wobec zakładu do wyrównania")
            if word == "call" and legal.call_amount is None:
                raise ValueError("call niedostępny — brak zakładu do sprawdzenia")
            return Decision(action=ActionType(word))
        case "bet" | "raise":
            bounds = legal.bet_range if word == "bet" else legal.raise_range
            if bounds is None:
                raise ValueError(f"{word} niedostępny w tym stanie licytacji")
            if len(rest) != 1:
                raise ValueError(f"akcja {word} wymaga dokładnie jednej kwoty")
            try:
                amount = int(rest[0])
            except ValueError:
                raise ValueError(f"kwota nie jest liczbą całkowitą: {rest[0]!r}") from None
            if not bounds.minimum <= amount <= bounds.maximum:
                raise ValueError(
                    f"kwota {amount} poza granicami [{bounds.minimum}, {bounds.maximum}]"
                )
            return Decision(action=ActionType(word), amount=amount)
        case _:
            raise ValueError(f"nieznana akcja: {word!r}; dostępne: {_INPUT_HINT}")


class HumanAgent:
    """Port Agent dla człowieka: render widoku, odczyt i walidacja decyzji z wejścia."""

    def __init__(self, input_stream: TextIO, output_stream: TextIO) -> None:
        self._input = input_stream
        self._output = output_stream

    def decide(self, view: PlayerView) -> Decision:
        legal = view.legal_actions
        if legal is None:
            raise ValueError("decyzja wymaga widoku miejsca na ruchu")
        self._output.write(render_view(view) + "\n")
        while True:
            self._output.write("twoja decyzja: ")
            self._output.flush()
            line = self._input.readline()
            if line == "":
                raise InputEnded("koniec strumienia wejścia w trakcie meczu")
            try:
                return _parse_decision(line, legal)
            except ValueError as error:
                self._output.write(f"nieprawidłowe wejście: {error}\n")

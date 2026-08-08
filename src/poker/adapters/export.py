"""Eksport historii meczu: typowany, wersjonowany JSON — kanał operatora, nie widok gracza."""

import json
from collections.abc import Sequence

from poker.cards import Card, Rank, Suit
from poker.events import (
    ActionTaken,
    ActionType,
    BlindPosted,
    BlindType,
    CardsRevealed,
    DeckSeeded,
    FlopDealt,
    HandConfig,
    HandEnded,
    HandEvent,
    HandStarted,
    HoleCardsDealt,
    PotAwarded,
    RiverDealt,
    TurnDealt,
    UncalledBetReturned,
)

FORMAT_VERSION = 1

type _Json = dict[str, object]


def serialize_match_history(histories: Sequence[Sequence[HandEvent]]) -> str:
    payload: _Json = {
        "format_version": FORMAT_VERSION,
        "hands": [[_event_to_json(event) for event in history] for history in histories],
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def deserialize_match_history(text: str) -> tuple[tuple[HandEvent, ...], ...]:
    payload = _as_dict(json.loads(text), "dokument eksportu")
    version = payload.get("format_version")
    if version != FORMAT_VERSION:
        raise ValueError(f"nieobsługiwana wersja formatu eksportu: {version!r}")
    hands = _as_list(payload.get("hands"), "hands")
    return tuple(
        tuple(_event_from_json(_as_dict(raw, "zdarzenie")) for raw in _as_list(hand, "rozdanie"))
        for hand in hands
    )


def _card_to_json(card: Card) -> _Json:
    return {"rank": card.rank.value, "suit": card.suit.value}


def _card_from_json(value: object) -> Card:
    data = _as_dict(value, "karta")
    return Card(rank=Rank(_as_int(data.get("rank"), "rank")), suit=Suit(data.get("suit")))


def _event_to_json(event: HandEvent) -> _Json:
    match event:
        case HandStarted(config=config):
            return {
                "type": "HandStarted",
                "config": {
                    "small_blind": config.small_blind,
                    "big_blind": config.big_blind,
                    "stacks": list(config.stacks),
                    "button": config.button,
                },
            }
        case DeckSeeded(seed=seed):
            return {"type": "DeckSeeded", "seed": seed}
        case BlindPosted(seat=seat, blind=blind, amount=amount):
            return {"type": "BlindPosted", "seat": seat, "blind": blind.value, "amount": amount}
        case HoleCardsDealt(seat=seat, cards=cards):
            return {
                "type": "HoleCardsDealt",
                "seat": seat,
                "cards": [_card_to_json(card) for card in cards],
            }
        case FlopDealt(cards=cards):
            return {"type": "FlopDealt", "cards": [_card_to_json(card) for card in cards]}
        case TurnDealt(card=card):
            return {"type": "TurnDealt", "card": _card_to_json(card)}
        case RiverDealt(card=card):
            return {"type": "RiverDealt", "card": _card_to_json(card)}
        case ActionTaken(seat=seat, action=action, amount=amount):
            return {"type": "ActionTaken", "seat": seat, "action": action.value, "amount": amount}
        case CardsRevealed(seat=seat, cards=cards):
            return {
                "type": "CardsRevealed",
                "seat": seat,
                "cards": [_card_to_json(card) for card in cards],
            }
        case UncalledBetReturned(seat=seat, amount=amount):
            return {"type": "UncalledBetReturned", "seat": seat, "amount": amount}
        case PotAwarded(seat=seat, amount=amount):
            return {"type": "PotAwarded", "seat": seat, "amount": amount}
        case HandEnded():
            return {"type": "HandEnded"}


def _event_from_json(data: _Json) -> HandEvent:
    match data.get("type"):
        case "HandStarted":
            config = _as_dict(data.get("config"), "config")
            return HandStarted(
                config=HandConfig(
                    small_blind=_as_int(config.get("small_blind"), "small_blind"),
                    big_blind=_as_int(config.get("big_blind"), "big_blind"),
                    stacks=tuple(
                        _as_int(stack, "stack")
                        for stack in _as_list(config.get("stacks"), "stacks")
                    ),
                    button=_as_int(config.get("button"), "button"),
                )
            )
        case "DeckSeeded":
            return DeckSeeded(seed=_as_int(data.get("seed"), "seed"))
        case "BlindPosted":
            return BlindPosted(
                seat=_as_int(data.get("seat"), "seat"),
                blind=BlindType(data.get("blind")),
                amount=_as_int(data.get("amount"), "amount"),
            )
        case "HoleCardsDealt":
            first, second = (_card_from_json(raw) for raw in _as_list(data.get("cards"), "cards"))
            return HoleCardsDealt(seat=_as_int(data.get("seat"), "seat"), cards=(first, second))
        case "FlopDealt":
            one, two, three = (_card_from_json(raw) for raw in _as_list(data.get("cards"), "cards"))
            return FlopDealt(cards=(one, two, three))
        case "TurnDealt":
            return TurnDealt(card=_card_from_json(data.get("card")))
        case "RiverDealt":
            return RiverDealt(card=_card_from_json(data.get("card")))
        case "ActionTaken":
            return ActionTaken(
                seat=_as_int(data.get("seat"), "seat"),
                action=ActionType(data.get("action")),
                amount=_as_int(data.get("amount"), "amount"),
            )
        case "CardsRevealed":
            first, second = (_card_from_json(raw) for raw in _as_list(data.get("cards"), "cards"))
            return CardsRevealed(seat=_as_int(data.get("seat"), "seat"), cards=(first, second))
        case "UncalledBetReturned":
            return UncalledBetReturned(
                seat=_as_int(data.get("seat"), "seat"),
                amount=_as_int(data.get("amount"), "amount"),
            )
        case "PotAwarded":
            return PotAwarded(
                seat=_as_int(data.get("seat"), "seat"),
                amount=_as_int(data.get("amount"), "amount"),
            )
        case "HandEnded":
            return HandEnded()
        case unknown:
            raise ValueError(f"nieznany typ zdarzenia w eksporcie: {unknown!r}")


def _as_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"pole {label} musi być liczbą całkowitą, otrzymano {value!r}")
    return value


def _as_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"pole {label} musi być listą, otrzymano {value!r}")
    return value


def _as_dict(value: object, label: str) -> _Json:
    if not isinstance(value, dict):
        raise ValueError(f"{label} musi być obiektem JSON, otrzymano {value!r}")
    return value

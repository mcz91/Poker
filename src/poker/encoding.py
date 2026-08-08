"""Enkodowanie przykładów decyzyjnych (b4.1): cechy wyłącznie z widoku decydującego.

Wersja zbioru: `DATASET_VERSION`. Zestaw i kolejność cech v1 definiuje
`FEATURE_NAMES`; wszystkie cechy są liczbami całkowitymi. Kolory kart
indeksowane alfabetycznie po symbolu (c=0, d=1, h=2, s=3), rangi
wartościami 2–14, brak karty na slocie boardu to para (0, 0). Karty
własne w porządku malejącym (ranga, indeks koloru). Blindy nie są
decyzjami — przykład powstaje wyłącznie dla zdarzeń akcji, z prefiksu
zdarzeń widocznych z miejsca decydującego bezpośrednio przed akcją.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from poker.cards import Card, Suit
from poker.events import ActionTaken, ActionType, HandEvent, HandStarted, HoleCardsDealt
from poker.projection import Phase, project
from poker.views import visible_events

DATASET_VERSION = 1

FEATURE_NAMES: tuple[str, ...] = (
    "is_button",
    "small_blind",
    "big_blind",
    "own_stack",
    "opponent_stack",
    "pot",
    "phase",
    "hole_rank_high",
    "hole_suit_high",
    "hole_rank_low",
    "hole_suit_low",
    "board_rank_1",
    "board_suit_1",
    "board_rank_2",
    "board_suit_2",
    "board_rank_3",
    "board_suit_3",
    "board_rank_4",
    "board_suit_4",
    "board_rank_5",
    "board_suit_5",
)

_SUIT_INDEX = {suit: index for index, suit in enumerate(sorted(Suit, key=lambda s: s.value))}
_PHASE_INDEX = {Phase.PREFLOP: 0, Phase.FLOP: 1, Phase.TURN: 2, Phase.RIVER: 3}
_BOARD_SLOTS = 5


@dataclass(frozen=True, slots=True)
class DecisionExample:
    seat: int
    features: tuple[int, ...]
    action: ActionType
    amount: int


def encode_hand(events: Sequence[HandEvent]) -> tuple[DecisionExample, ...]:
    sequence = tuple(events)
    if not sequence or not isinstance(sequence[0], HandStarted):
        raise ValueError("enkodowanie wymaga zdarzenia startu rozdania na początku")
    config = sequence[0].config
    if len(config.stacks) != 2:
        raise ValueError("enkodowanie v1 obsługuje dokładnie 2 miejsca (heads-up)")
    examples: list[DecisionExample] = []
    for index, event in enumerate(sequence):
        if not isinstance(event, ActionTaken):
            continue
        seat = event.seat
        visible = visible_events(sequence[:index], seat)
        state = project(visible)
        hole = next(
            (e.cards for e in visible if isinstance(e, HoleCardsDealt) and e.seat == seat),
            None,
        )
        if hole is None:
            raise ValueError("decyzja przed rozdaniem kart własnych decydującego")
        phase = _PHASE_INDEX.get(state.phase)
        if phase is None:
            raise ValueError(f"decyzja w fazie bez licytacji: {state.phase.value}")
        high, low = sorted(
            hole, key=lambda card: (card.rank.value, _SUIT_INDEX[card.suit]), reverse=True
        )
        features = (
            1 if config.button == seat else 0,
            config.small_blind,
            config.big_blind,
            state.stacks[seat],
            state.stacks[1 - seat],
            state.pot,
            phase,
            high.rank.value,
            _SUIT_INDEX[high.suit],
            low.rank.value,
            _SUIT_INDEX[low.suit],
            *_board_features(state.board),
        )
        examples.append(
            DecisionExample(seat=seat, features=features, action=event.action, amount=event.amount)
        )
    return tuple(examples)


def _board_features(board: tuple[Card, ...]) -> tuple[int, ...]:
    features: list[int] = []
    for slot in range(_BOARD_SLOTS):
        if slot < len(board):
            features += [board[slot].rank.value, _SUIT_INDEX[board[slot].suit]]
        else:
            features += [0, 0]
    return tuple(features)

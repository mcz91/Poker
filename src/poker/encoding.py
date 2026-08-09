"""Enkodowanie przykładów decyzyjnych (b4.1, cechy v2 z POKER-18): wyłącznie widok decydującego.

Wersja zbioru: `DATASET_VERSION`. Zestaw i kolejność cech definiuje
`FEATURE_NAMES`; wszystkie cechy są liczbami całkowitymi. Kolory kart
indeksowane alfabetycznie po symbolu (c=0, d=1, h=2, s=3), rangi
wartościami 2–14, brak karty na slocie boardu to para (0, 0). Karty
własne w porządku malejącym (ranga, indeks koloru). Cechy v2:
`hole_equity_mille` — equity all-in klasy kart własnych przeciw polu
(średnia po klasach ważona kombinacjami, z macierzy preflop),
w promilach; `hand_category` — kategoria najlepszego układu z kart
własnych i boardu (wartość z ewaluatora), 0 przed flopem. Blindy nie
są decyzjami — przykład powstaje wyłącznie dla zdarzeń akcji,
z prefiksu zdarzeń widocznych z miejsca decydującego bezpośrednio
przed akcją.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from poker.cards import Card, Suit
from poker.evaluation import evaluate_best
from poker.events import ActionTaken, ActionType, HandEvent, HandStarted, HoleCardsDealt
from poker.preflop import ALL_CLASSES, PreflopClass, class_combos, classify
from poker.preflop_equity import equity
from poker.projection import Phase, project
from poker.views import PlayerView, visible_events

DATASET_VERSION = 2

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
    "hole_equity_mille",
    "hand_category",
)

_SUIT_INDEX = {suit: index for index, suit in enumerate(sorted(Suit, key=lambda s: s.value))}
_PHASE_INDEX = {Phase.PREFLOP: 0, Phase.FLOP: 1, Phase.TURN: 2, Phase.RIVER: 3}
_BOARD_SLOTS = 5
_ALL_COMBOS = 1326

_FIELD_EQUITY_MILLE: dict[PreflopClass, int] = {
    cls: round(
        1000
        * sum(len(class_combos(other)) * equity(cls, other) for other in ALL_CLASSES)
        / _ALL_COMBOS
    )
    for cls in ALL_CLASSES
}


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
        features = _features(
            seat=seat,
            button=config.button,
            small_blind=config.small_blind,
            big_blind=config.big_blind,
            stacks=state.stacks,
            pot=state.pot,
            phase=state.phase,
            hole=hole,
            board=state.board,
        )
        examples.append(
            DecisionExample(seat=seat, features=features, action=event.action, amount=event.amount)
        )
    return tuple(examples)


def view_features(view: PlayerView) -> tuple[int, ...]:
    """Cechy inferencji z widoku decydującego — ta sama definicja co cechy zbioru."""
    if view.hole_cards is None:
        raise ValueError("cechy wymagają kart własnych w widoku")
    return _features(
        seat=view.seat,
        button=view.button,
        small_blind=view.small_blind,
        big_blind=view.big_blind,
        stacks=view.stacks,
        pot=view.pot,
        phase=view.phase,
        hole=view.hole_cards,
        board=view.board,
    )


def _features(
    *,
    seat: int,
    button: int,
    small_blind: int,
    big_blind: int,
    stacks: tuple[int, ...],
    pot: int,
    phase: Phase,
    hole: tuple[Card, Card],
    board: tuple[Card, ...],
) -> tuple[int, ...]:
    phase_index = _PHASE_INDEX.get(phase)
    if phase_index is None:
        raise ValueError(f"decyzja w fazie bez licytacji: {phase.value}")
    high, low = sorted(
        hole, key=lambda card: (card.rank.value, _SUIT_INDEX[card.suit]), reverse=True
    )
    return (
        1 if button == seat else 0,
        small_blind,
        big_blind,
        stacks[seat],
        stacks[1 - seat],
        pot,
        phase_index,
        high.rank.value,
        _SUIT_INDEX[high.suit],
        low.rank.value,
        _SUIT_INDEX[low.suit],
        *_board_features(board),
        _FIELD_EQUITY_MILLE[classify(hole[0], hole[1])],
        evaluate_best(hole + board).category.value if len(board) >= 3 else 0,
    )


def _board_features(board: tuple[Card, ...]) -> tuple[int, ...]:
    features: list[int] = []
    for slot in range(_BOARD_SLOTS):
        if slot < len(board):
            features += [board[slot].rank.value, _SUIT_INDEX[board[slot].suit]]
        else:
            features += [0, 0]
    return tuple(features)

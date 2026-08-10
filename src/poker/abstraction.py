"""Abstrakcja gry pod trenera równowagi (c2a, decyzja 07) — czysty stdlib, bez I/O.

Wersja: `ABSTRACTION_VERSION` — zmiana definicji kubełków, zbioru akcji
albo formatu infosetu wymaga jej podbicia.

Kubełki kart:
- preflop: 169 klas uszeregowanych rosnąco po equity przeciw polu
  (średnia ważona kombinacjami z macierzy preflop; remis rozstrzyga
  kolejność `ALL_CLASSES`), podzielonych na `preflop_buckets` grup
  równolicznych pozycją w szeregu — kubełek 0 najsłabszy;
- postflop: kategoria najlepszego układu z ewaluatora na kartach
  własnych i boardzie, odwzorowana liniowo na `postflop_buckets`
  kubełków (indeks kategorii * liczba kubełków // 9).

Akcje abstrakcyjne: fold, check-call, bet o rozmiarach z `bet_sizes`
(rejestr rozmiarów: "half" = pula // 2, "pot" = pula) i all-in;
`decision_for` przycina kwotę do granic `legal_actions` i wybiera
BET/RAISE według dostępności; typ niedostępny w danej sytuacji ma
deterministyczny fallback check-call (a bez check/call — fold).

Infoset: `a{wersja}|ulica|k{kubełek}|pozycja|przebieg`, gdzie przebieg
to znormalizowana licytacja z jawnych akcji widoku: f/k/c oraz b/r
z sufiksem rozmiaru względem puli sprzed akcji (H: kwota*2 <= pula,
P: kwota <= pula, A: powyżej puli); blindy budują pulę, bez etykiet.
"""

from dataclasses import dataclass
from enum import Enum, unique

from poker.agent import Decision
from poker.cards import Card
from poker.evaluation import evaluate_best
from poker.events import ActionTaken, ActionType, BlindPosted
from poker.preflop import ALL_CLASSES, PreflopClass, class_combos, classify
from poker.preflop_equity import equity
from poker.views import PlayerView

ABSTRACTION_VERSION = 1

_HAND_CATEGORIES = 9
_SIZE_REGISTRY = ("half", "pot")


@dataclass(frozen=True, slots=True)
class AbstractionConfig:
    preflop_buckets: int = 8
    postflop_buckets: int = 9
    bet_sizes: tuple[str, ...] = ("half", "pot")

    def __post_init__(self) -> None:
        if self.preflop_buckets < 1 or self.postflop_buckets < 1:
            raise ValueError("liczby kubełków muszą być dodatnie")
        unknown = [size for size in self.bet_sizes if size not in _SIZE_REGISTRY]
        if unknown:
            raise ValueError(
                f"nieznane rozmiary zakładów: {unknown}; rejestr: {_SIZE_REGISTRY}"
            )


@unique
class AbstractActionKind(Enum):
    FOLD = "fold"
    CHECK_CALL = "check-call"
    BET = "bet"
    ALL_IN = "all-in"


@dataclass(frozen=True, slots=True)
class AbstractAction:
    kind: AbstractActionKind
    size: str | None = None

    def __post_init__(self) -> None:
        if (self.size is not None) != (self.kind is AbstractActionKind.BET):
            raise ValueError("rozmiar przysługuje wyłącznie akcji bet")


def _field_equity_mille(cls: PreflopClass) -> int:
    total = sum(len(class_combos(other)) * equity(cls, other) for other in ALL_CLASSES)
    return round(1000 * total / 1326)


_PREFLOP_ORDER: dict[PreflopClass, int] = {
    cls: position
    for position, cls in enumerate(
        sorted(ALL_CLASSES, key=lambda cls: (_field_equity_mille(cls), ALL_CLASSES.index(cls)))
    )
}


def preflop_bucket(cls: PreflopClass, config: AbstractionConfig) -> int:
    return _PREFLOP_ORDER[cls] * config.preflop_buckets // len(ALL_CLASSES)


def postflop_bucket(
    hole: tuple[Card, Card], board: tuple[Card, ...], config: AbstractionConfig
) -> int:
    category_index = evaluate_best(hole + board).category.value - 1
    return category_index * config.postflop_buckets // _HAND_CATEGORIES


def abstract_actions(view: PlayerView, config: AbstractionConfig) -> tuple[AbstractAction, ...]:
    legal = view.legal_actions
    if legal is None:
        raise ValueError("zbiór akcji wymaga widoku miejsca na ruchu")
    actions = [AbstractAction(kind=AbstractActionKind.FOLD)]
    if legal.check_allowed or legal.call_amount is not None:
        actions.append(AbstractAction(kind=AbstractActionKind.CHECK_CALL))
    if legal.bet_range is not None or legal.raise_range is not None:
        actions.extend(
            AbstractAction(kind=AbstractActionKind.BET, size=size)
            for size in config.bet_sizes
        )
        actions.append(AbstractAction(kind=AbstractActionKind.ALL_IN))
    return tuple(actions)


def decision_for(action: AbstractAction, view: PlayerView) -> Decision:
    legal = view.legal_actions
    if legal is None:
        raise ValueError("decyzja wymaga widoku miejsca na ruchu")
    bounds = legal.bet_range if legal.bet_range is not None else legal.raise_range
    action_type = ActionType.BET if legal.bet_range is not None else ActionType.RAISE
    match action.kind:
        case AbstractActionKind.FOLD:
            return Decision(action=ActionType.FOLD)
        case AbstractActionKind.BET | AbstractActionKind.ALL_IN if bounds is not None:
            if action.kind is AbstractActionKind.ALL_IN:
                amount = bounds.maximum
            else:
                target = view.pot // 2 if action.size == "half" else view.pot
                amount = min(max(target, bounds.minimum), bounds.maximum)
            return Decision(action=action_type, amount=amount)
        case _:
            pass
    if legal.check_allowed:
        return Decision(action=ActionType.CHECK)
    if legal.call_amount is not None:
        return Decision(action=ActionType.CALL)
    return Decision(action=ActionType.FOLD)


def infoset(view: PlayerView, config: AbstractionConfig) -> str:
    if view.hole_cards is None:
        raise ValueError("infoset wymaga kart własnych w widoku")
    if len(view.board) < 3:
        bucket = preflop_bucket(classify(*view.hole_cards), config)
    else:
        bucket = postflop_bucket(view.hole_cards, view.board, config)
    position = "btn" if view.button == view.seat else "oop"
    return (
        f"a{ABSTRACTION_VERSION}|{view.phase.value}|k{bucket}|{position}"
        f"|{_history_labels(view.visible_actions)}"
    )


def _history_labels(actions: tuple[BlindPosted | ActionTaken, ...]) -> str:
    labels: list[str] = []
    pot = 0
    for event in actions:
        if isinstance(event, BlindPosted):
            pot += event.amount
            continue
        match event.action:
            case ActionType.FOLD:
                labels.append("f")
            case ActionType.CHECK:
                labels.append("k")
            case ActionType.CALL:
                labels.append("c")
                pot += event.amount
            case ActionType.BET | ActionType.RAISE:
                prefix = "b" if event.action is ActionType.BET else "r"
                labels.append(prefix + _size_label(event.amount, pot))
                pot += event.amount
    return ".".join(labels)


def _size_label(amount: int, pot_before: int) -> str:
    if amount > pot_before:
        return "A"
    if amount * 2 <= pot_before:
        return "H"
    return "P"

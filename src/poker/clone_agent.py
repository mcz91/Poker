"""Agent behavior clone (b4.2): deterministyczna inferencja portem Agent (INV-P4, INV-P8).

Reguła kwot v1: model wybiera wyłącznie typ akcji (argmax po ACTIONS,
przy remisie pierwszy w kolejności); kwota dla bet/raise to minimum
legalne z widoku. Typ niedostępny w danej sytuacji ma deterministyczny
fallback: check, gdy dozwolony, inaczej call, gdy jest co sprawdzać,
inaczej fold.
"""

from dataclasses import dataclass

from poker.agent import Decision
from poker.clone_weights import ACTIONS, FEATURE_MEANS, FEATURE_SCALES, WEIGHTS
from poker.encoding import view_features
from poker.events import ActionType
from poker.views import PlayerView


def decision_for_action(action: ActionType, view: PlayerView) -> Decision:
    """Reguła kwot v1: kwota bet/raise to minimum legalne; typ niedostępny -> fallback."""
    legal = view.legal_actions
    if legal is None:
        raise ValueError("decyzja wymaga widoku miejsca na ruchu")
    match action:
        case ActionType.FOLD:
            return Decision(action=ActionType.FOLD)
        case ActionType.CHECK if legal.check_allowed:
            return Decision(action=ActionType.CHECK)
        case ActionType.CALL if legal.call_amount is not None:
            return Decision(action=ActionType.CALL)
        case ActionType.BET if legal.bet_range is not None:
            return Decision(action=ActionType.BET, amount=legal.bet_range.minimum)
        case ActionType.RAISE if legal.raise_range is not None:
            return Decision(action=ActionType.RAISE, amount=legal.raise_range.minimum)
        case _:
            pass
    if legal.check_allowed:
        return Decision(action=ActionType.CHECK)
    if legal.call_amount is not None:
        return Decision(action=ActionType.CALL)
    return Decision(action=ActionType.FOLD)


@dataclass(frozen=True, slots=True)
class CloneAgent:
    def decide(self, view: PlayerView) -> Decision:
        action = ActionType(ACTIONS[_predicted_class(view_features(view))])
        return decision_for_action(action, view)


def _predicted_class(features: tuple[int, ...]) -> int:
    standardized = [
        (value - mean) / scale
        for value, mean, scale in zip(features, FEATURE_MEANS, FEATURE_SCALES, strict=True)
    ] + [1.0]
    best_class, best_score = 0, float("-inf")
    for index, row in enumerate(WEIGHTS):
        score = sum(weight * x for weight, x in zip(row, standardized, strict=True))
        if score > best_score:
            best_class, best_score = index, score
    return best_class

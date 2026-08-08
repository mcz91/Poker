"""Agent regułowy: czysta funkcja widoku w decyzję, czytelne progi jako konfiguracja."""

from dataclasses import dataclass, field

from poker.agent import Decision
from poker.evaluation import HandCategory, evaluate_best
from poker.events import ActionType
from poker.views import PlayerView


@dataclass(frozen=True, slots=True)
class RuleAgentThresholds:
    """Domyślne progi: podbija od dwóch par, gra o wartość od pary, sprawdza tanio 2:1."""

    aggress_from: HandCategory = HandCategory.TWO_PAIR
    value_from: HandCategory = HandCategory.ONE_PAIR
    pot_odds_divisor: int = 2

    def __post_init__(self) -> None:
        if self.pot_odds_divisor < 1:
            raise ValueError(f"dzielnik puli musi być dodatni: {self.pot_odds_divisor}")


@dataclass(frozen=True, slots=True)
class RuleAgent:
    thresholds: RuleAgentThresholds = field(default_factory=RuleAgentThresholds)

    def decide(self, view: PlayerView) -> Decision:
        legal = view.legal_actions
        if legal is None:
            raise ValueError("decyzja wymaga widoku miejsca na ruchu")
        strength = _hand_category(view)

        if strength >= self.thresholds.aggress_from:
            if legal.raise_range is not None:
                return Decision(action=ActionType.RAISE, amount=legal.raise_range.minimum)
            if legal.bet_range is not None:
                return Decision(action=ActionType.BET, amount=legal.bet_range.minimum)
            if legal.call_amount is not None:
                return Decision(action=ActionType.CALL)
            return Decision(action=ActionType.CHECK)

        if legal.call_amount is None:
            if strength >= self.thresholds.value_from and legal.bet_range is not None:
                return Decision(action=ActionType.BET, amount=legal.bet_range.minimum)
            return Decision(action=ActionType.CHECK)

        cheap_call = legal.call_amount * self.thresholds.pot_odds_divisor <= view.pot
        if strength >= self.thresholds.value_from or cheap_call:
            return Decision(action=ActionType.CALL)
        return Decision(action=ActionType.FOLD)


def _hand_category(view: PlayerView) -> HandCategory:
    if view.hole_cards is None:
        raise ValueError("agent wymaga własnych kart w widoku")
    if len(view.board) < 3:
        pair_in_hand = view.hole_cards[0].rank == view.hole_cards[1].rank
        return HandCategory.ONE_PAIR if pair_in_hand else HandCategory.HIGH_CARD
    return evaluate_best(view.hole_cards + view.board).category

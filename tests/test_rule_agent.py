"""Testy agenta regułowego (POKER-8): reguły widok -> decyzja, determinizm, legalność."""

import pytest

from poker.agent import Agent, Decision
from poker.betting import ActionBounds, LegalActions
from poker.cards import Card, Rank, Suit
from poker.evaluation import HandCategory
from poker.events import ActionType, HandEnded
from poker.projection import Phase, project
from poker.rule_agent import RuleAgent, RuleAgentThresholds
from poker.table import MatchConfig, MatchEndReason, play_match
from poker.views import PlayerView

AS, AH = Card(Rank.ACE, Suit.SPADES), Card(Rank.ACE, Suit.HEARTS)
KS = Card(Rank.KING, Suit.SPADES)
TWO_C, SEVEN_D = Card(Rank.TWO, Suit.CLUBS), Card(Rank.SEVEN, Suit.DIAMONDS)
FLOP_NISKI = (
    Card(Rank.NINE, Suit.HEARTS),
    Card(Rank.FIVE, Suit.CLUBS),
    Card(Rank.THREE, Suit.DIAMONDS),
)
FLOP_Z_ASEM = (
    Card(Rank.ACE, Suit.CLUBS),
    Card(Rank.NINE, Suit.HEARTS),
    Card(Rank.FIVE, Suit.CLUBS),
)


def widok(
    hole_cards: tuple[Card, Card] | None,
    board: tuple[Card, ...],
    legal_actions: LegalActions | None,
    pot: int = 4,
) -> PlayerView:
    return PlayerView(
        seat=0,
        button=0,
        small_blind=1,
        big_blind=2,
        hole_cards=hole_cards,
        board=board,
        stacks=(98, 98),
        pot=pot,
        phase=Phase.PREFLOP if not board else Phase.FLOP,
        visible_actions=(),
        revealed_cards=(None, None),
        to_act=0,
        legal_actions=legal_actions,
    )


def legalne(
    check: bool = False,
    call: int | None = None,
    bet: ActionBounds | None = None,
    raise_range: ActionBounds | None = None,
) -> LegalActions:
    return LegalActions(
        seat=0,
        fold_allowed=True,
        check_allowed=check,
        call_amount=call,
        bet_range=bet,
        raise_range=raise_range,
    )


def test_silna_reka_podbija_minimalnie() -> None:
    view = widok((AS, AH), FLOP_Z_ASEM, legalne(call=10, raise_range=ActionBounds(20, 98)))
    assert RuleAgent().decide(view) == Decision(action=ActionType.RAISE, amount=20)


def test_silna_reka_bez_podbicia_sprawdza() -> None:
    view = widok((AS, AH), FLOP_Z_ASEM, legalne(call=10))
    assert RuleAgent().decide(view) == Decision(action=ActionType.CALL)


def test_srednia_reka_betuje_minimalnie_gdy_nikt_nie_postawil() -> None:
    view = widok((AS, AH), FLOP_NISKI, legalne(check=True, bet=ActionBounds(2, 98)))
    assert RuleAgent().decide(view) == Decision(action=ActionType.BET, amount=2)


def test_srednia_reka_sprawdza_zaklad() -> None:
    view = widok((AS, AH), FLOP_NISKI, legalne(call=30))
    assert RuleAgent().decide(view) == Decision(action=ActionType.CALL)


def test_slaba_reka_czeka_gdy_moze() -> None:
    view = widok((TWO_C, SEVEN_D), FLOP_Z_ASEM, legalne(check=True, bet=ActionBounds(2, 98)))
    assert RuleAgent().decide(view) == Decision(action=ActionType.CHECK)


def test_slaba_reka_sprawdza_tanio_wedle_puli() -> None:
    view = widok((TWO_C, SEVEN_D), FLOP_Z_ASEM, legalne(call=2), pot=8)
    assert RuleAgent().decide(view) == Decision(action=ActionType.CALL)


def test_slaba_reka_pasuje_wobec_drogiego_zakladu() -> None:
    view = widok((TWO_C, SEVEN_D), FLOP_Z_ASEM, legalne(call=30), pot=8)
    assert RuleAgent().decide(view) == Decision(action=ActionType.FOLD)


def test_para_na_reku_przed_flopem_jest_reka_srednia() -> None:
    view = widok((AS, AH), (), legalne(call=10), pot=4)
    assert RuleAgent().decide(view) == Decision(action=ActionType.CALL)


def test_progi_sa_parametrem_konstrukcji() -> None:
    view = widok((TWO_C, SEVEN_D), FLOP_NISKI, legalne(check=True, bet=ActionBounds(2, 98)))
    assert RuleAgent().decide(view) == Decision(action=ActionType.CHECK)
    agresywny = RuleAgent(
        thresholds=RuleAgentThresholds(aggress_from=HandCategory.HIGH_CARD)
    )
    assert agresywny.decide(view) == Decision(action=ActionType.BET, amount=2)


def test_ten_sam_widok_daje_te_sama_decyzje() -> None:
    view = widok((AS, KS), FLOP_NISKI, legalne(call=10))
    agent = RuleAgent()
    decisions = {agent.decide(view) for _ in range(5)}
    assert len(decisions) == 1
    assert RuleAgent().decide(view) in decisions


def test_agent_bez_pamieci_miedzy_wywolaniami() -> None:
    silny = widok((AS, AH), FLOP_Z_ASEM, legalne(call=10, raise_range=ActionBounds(20, 98)))
    slaby = widok((TWO_C, SEVEN_D), FLOP_Z_ASEM, legalne(call=30), pot=8)
    agent = RuleAgent()
    first = agent.decide(silny)
    agent.decide(slaby)
    assert agent.decide(silny) == first


def test_walidacja_widoku_i_progow() -> None:
    with pytest.raises(ValueError, match="ruchu"):
        RuleAgent().decide(widok((AS, AH), (), legal_actions=None))
    with pytest.raises(ValueError, match="kart"):
        RuleAgent().decide(widok(None, (), legalne(check=True)))
    with pytest.raises(ValueError, match="dzielnik"):
        RuleAgentThresholds(pot_odds_divisor=0)


class SkryptFold:
    def decide(self, view: PlayerView) -> Decision:
        legal = view.legal_actions
        assert legal is not None
        if legal.check_allowed:
            return Decision(action=ActionType.CHECK)
        return Decision(action=ActionType.FOLD)


def test_agent_zawsze_gra_legalnie_w_wielu_meczach() -> None:
    config = MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=20)
    opponents: list[Agent] = [RuleAgent(), SkryptFold()]
    for seed in range(30):
        for opponent in opponents:
            result = play_match(config, seed=seed, agents=(RuleAgent(), opponent))
            assert result.reason in (MatchEndReason.BUST, MatchEndReason.HAND_LIMIT)
            assert sum(result.stacks) == 200
            assert isinstance(result.histories[-1][-1], HandEnded)
            for history in result.histories:
                assert project(history).pot == 0

"""Testy behavior clone (POKER-16): zgodność cech, determinizm treningu, legalność, pomiar."""

from pathlib import Path

import pytest

from poker.adapters.cli import main
from poker.adapters.corpus import generate_corpus
from poker.adapters.dataset import extract_dataset, read_dataset
from poker.adapters.registry import agent_registry
from poker.agent import Decision
from poker.betting import ActionBounds, HeadsUpHand, LegalActions
from poker.cards import Card, Rank, Suit
from poker.clone_agent import CloneAgent
from poker.clone_training import render_weights_module, train_clone
from poker.encoding import FEATURE_NAMES, DecisionExample, encode_hand, view_features
from poker.events import ActionType, HandConfig
from poker.projection import Phase
from poker.rule_agent import RuleAgent
from poker.table import MatchConfig, play_match
from poker.views import PlayerView, player_view

CONFIG = MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=20)


def przyklady_z_malego_korpusu(tmp_path: Path) -> tuple[DecisionExample, ...]:
    generate_corpus(
        tmp_path / "korpus",
        config=MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0,
                           hand_limit=5),
        agent_names=("rule", "rule-aggressive"),
        matches=2,
        seed=5,
    )
    extract_dataset(tmp_path / "korpus", tmp_path / "zbior.json")
    return read_dataset(tmp_path / "zbior.json")


def test_cechy_inferencji_zgodne_z_cechami_zbioru() -> None:
    hand = HeadsUpHand(
        config=HandConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0), seed=3
    )
    collected = []
    while (seat := hand.to_act()) is not None:
        view = player_view(hand, seat)
        collected.append(view_features(view))
        legal = view.legal_actions
        assert legal is not None
        if legal.check_allowed:
            hand.act(seat, ActionType.CHECK)
        else:
            assert legal.call_amount is not None
            hand.act(seat, ActionType.CALL)
    examples = encode_hand(hand.events())
    assert [example.features for example in examples] == collected
    assert len(collected) > 0


def test_reprodukcja_treningu_bajt_w_bajt(tmp_path: Path) -> None:
    examples = przyklady_z_malego_korpusu(tmp_path)
    first = render_weights_module(train_clone(examples, learning_rate=0.1, epochs=5))
    second = render_weights_module(train_clone(examples, learning_rate=0.1, epochs=5))
    assert first.encode("utf-8") == second.encode("utf-8")
    other = render_weights_module(train_clone(examples, learning_rate=0.2, epochs=5))
    assert first != other


def test_modul_wag_ma_metadane_i_spojne_wymiary() -> None:
    from poker import clone_weights

    assert clone_weights.DATASET_VERSION == 1
    assert clone_weights.LEARNING_RATE > 0
    assert clone_weights.EPOCHS > 0
    assert clone_weights.EXAMPLES > 0
    assert len(clone_weights.ACTIONS) == 5
    assert len(clone_weights.FEATURE_MEANS) == len(FEATURE_NAMES)
    assert len(clone_weights.FEATURE_SCALES) == len(FEATURE_NAMES)
    assert len(clone_weights.WEIGHTS) == len(clone_weights.ACTIONS)
    for row in clone_weights.WEIGHTS:
        assert len(row) == len(FEATURE_NAMES) + 1  # ostatnia waga to bias


def widok(legal: LegalActions) -> PlayerView:
    return PlayerView(
        seat=0,
        button=0,
        small_blind=1,
        big_blind=2,
        hole_cards=(Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)),
        board=(),
        stacks=(94, 90),
        pot=16,
        phase=Phase.PREFLOP,
        visible_actions=(),
        revealed_cards=(None, None),
        to_act=0,
        legal_actions=legal,
    )


def legalna(decision: Decision, legal: LegalActions) -> bool:
    match decision.action:
        case ActionType.FOLD:
            return legal.fold_allowed and decision.amount == 0
        case ActionType.CHECK:
            return legal.check_allowed and decision.amount == 0
        case ActionType.CALL:
            return legal.call_amount is not None and decision.amount == 0
        case ActionType.BET:
            return legal.bet_range is not None and (
                legal.bet_range.minimum <= decision.amount <= legal.bet_range.maximum
            )
        case ActionType.RAISE:
            return legal.raise_range is not None and (
                legal.raise_range.minimum <= decision.amount <= legal.raise_range.maximum
            )


@pytest.mark.parametrize(
    "legal",
    [
        LegalActions(seat=0, fold_allowed=True, check_allowed=False, call_amount=6,
                     bet_range=None, raise_range=None),
        LegalActions(seat=0, fold_allowed=True, check_allowed=True, call_amount=None,
                     bet_range=ActionBounds(minimum=2, maximum=94), raise_range=None),
        LegalActions(seat=0, fold_allowed=True, check_allowed=False, call_amount=6,
                     bet_range=None, raise_range=ActionBounds(minimum=12, maximum=94)),
        LegalActions(seat=0, fold_allowed=True, check_allowed=True, call_amount=None,
                     bet_range=None, raise_range=None),
    ],
)
def test_mapowanie_na_granice_legalnosci_nigdy_nielegalne(legal: LegalActions) -> None:
    decision = CloneAgent().decide(widok(legal))
    assert legalna(decision, legal)


def test_wlasciwosciowy_mecze_bez_bledow_legalnosci() -> None:
    for seed in range(15):
        result = play_match(CONFIG, seed=seed, agents=(CloneAgent(), RuleAgent()))
        assert sum(result.stacks) == 200
        assert result.hands_played >= 1
    lustro = play_match(CONFIG, seed=3, agents=(CloneAgent(), CloneAgent()))
    assert sum(lustro.stacks) == 200


def test_clone_w_rejestrze_i_mierzalny_w_arenie(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert "clone" in agent_registry()
    argv = ["--series", "2", "--hands", "10", "--seed", "5", "--agent1", "clone"]
    assert main(argv) == 0
    first = capsys.readouterr().out
    assert "BB/100" in first
    assert main(argv) == 0
    assert capsys.readouterr().out == first

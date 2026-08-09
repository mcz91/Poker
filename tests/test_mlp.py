"""Testy MLP-klona (POKER-19): metadane wag, reprodukcja kontrolna, legalność, pomiar."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from poker.adapters.cli import main
from poker.adapters.corpus import generate_corpus
from poker.adapters.registry import agent_registry
from poker.agent import Decision
from poker.betting import ActionBounds, LegalActions
from poker.cards import Card, Rank, Suit
from poker.clone_agent import CloneAgent
from poker.encoding import FEATURE_NAMES
from poker.events import ActionType
from poker.mlp_agent import MlpCloneAgent
from poker.projection import Phase
from poker.rule_agent import RuleAgent
from poker.table import MatchConfig, play_match
from poker.views import PlayerView

REPO = Path(__file__).resolve().parent.parent
CONFIG = MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=20)


def narzedzie_treningu() -> Any:
    spec = importlib.util.spec_from_file_location(
        "train_mlp_clone", REPO / "tools" / "train_mlp_clone.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_modul_wag_mlp_ma_metadane_architekture_i_pochodzenie() -> None:
    from poker import mlp_weights

    assert mlp_weights.DATASET_VERSION == 2
    assert mlp_weights.ACTIVATION in ("relu", "tanh")
    assert mlp_weights.LEARNING_RATE > 0
    assert mlp_weights.EPOCHS > 0
    assert isinstance(mlp_weights.INIT_SEED, int)
    assert mlp_weights.EXAMPLES > 0
    assert mlp_weights.ACTIONS == ("fold", "check", "call", "bet", "raise")
    architecture = mlp_weights.ARCHITECTURE
    assert architecture[0] == len(FEATURE_NAMES)
    assert architecture[-1] == len(mlp_weights.ACTIONS)
    assert len(mlp_weights.LAYERS) == len(architecture) - 1
    for layer_index, layer in enumerate(mlp_weights.LAYERS):
        assert len(layer) == architecture[layer_index + 1]
        for row in layer:
            assert len(row) == architecture[layer_index] + 1  # ostatnia waga to bias
    assert mlp_weights.CORPUS_AGENTS == ("rule", "rule-aggressive")
    assert mlp_weights.CORPUS_MATCHES > 30
    assert len(mlp_weights.FEATURE_MEANS) == len(FEATURE_NAMES)
    assert len(mlp_weights.FEATURE_SCALES) == len(FEATURE_NAMES)


def test_reprodukcja_kontrolna_treningu_bajt_w_bajt(tmp_path: Path) -> None:
    generate_corpus(
        tmp_path / "korpus",
        config=MatchConfig(
            small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=5
        ),
        agent_names=("rule", "rule-aggressive"),
        matches=2,
        seed=5,
    )
    tool = narzedzie_treningu()
    argv = ["--from-corpus", str(tmp_path / "korpus"), "--hidden", "4",
            "--epochs", "3", "--seed", "1"]
    assert tool.main([*argv, "--output", str(tmp_path / "a.py")]) == 0
    assert tool.main([*argv, "--output", str(tmp_path / "b.py")]) == 0
    assert (tmp_path / "a.py").read_bytes() == (tmp_path / "b.py").read_bytes()
    inny_seed = ["--from-corpus", str(tmp_path / "korpus"), "--hidden", "4",
                 "--epochs", "3", "--seed", "2", "--output", str(tmp_path / "c.py")]
    assert tool.main(inny_seed) == 0
    assert (tmp_path / "a.py").read_bytes() != (tmp_path / "c.py").read_bytes()


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
def test_mlp_mapowanie_na_granice_legalnosci(legal: LegalActions) -> None:
    decision = MlpCloneAgent().decide(widok(legal))
    assert legalna(decision, legal)


def test_wlasciwosciowy_mecze_mlp_bez_bledow_legalnosci() -> None:
    for seed in range(10):
        result = play_match(CONFIG, seed=seed, agents=(MlpCloneAgent(), RuleAgent()))
        assert sum(result.stacks) == 200
        assert result.hands_played >= 1
    przeciw_liniowemu = play_match(CONFIG, seed=3, agents=(MlpCloneAgent(), CloneAgent()))
    assert sum(przeciw_liniowemu.stacks) == 200
    lustro = play_match(CONFIG, seed=4, agents=(MlpCloneAgent(), MlpCloneAgent()))
    assert sum(lustro.stacks) == 200


def test_mlp_w_rejestrze_i_mierzalny_w_arenie(capsys: pytest.CaptureFixture[str]) -> None:
    assert "mlp-clone" in agent_registry()
    argv = ["--series", "2", "--hands", "10", "--seed", "5",
            "--agent0", "mlp-clone", "--agent1", "clone"]
    assert main(argv) == 0
    first = capsys.readouterr().out
    assert "BB/100" in first
    assert main(argv) == 0
    assert capsys.readouterr().out == first

"""Testy strategii MCCFR (POKER-23): artefakt, reprodukcja kontrolna, mieszanie bez stanu."""

import importlib.util
import io
from pathlib import Path
from typing import Any

import pytest

from poker.abstraction import (
    ABSTRACTION_VERSION,
    AbstractionConfig,
    abstract_actions,
    infoset,
)
from poker.adapters.cli import main
from poker.adapters.lan_server import TableServer
from poker.adapters.registry import agent_registry
from poker.agent import Decision
from poker.betting import ActionBounds, LegalActions
from poker.cards import Card, Rank, Suit
from poker.clone_agent import CloneAgent
from poker.events import ActionTaken, ActionType
from poker.projection import Phase
from poker.rule_agent import RuleAgent
from poker.strategy_agent import (
    ABSTRACTION_CONFIG,
    StrategyAgent,
    action_from_key,
    action_key,
)
from poker.strategy_table import STRATEGY
from poker.table import MatchConfig, play_match
from poker.views import PlayerView

REPO = Path(__file__).resolve().parent.parent
CONFIG = MatchConfig(small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=20)

AS, KH = Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)
FLOP = (
    Card(Rank.NINE, Suit.HEARTS),
    Card(Rank.FIVE, Suit.CLUBS),
    Card(Rank.THREE, Suit.DIAMONDS),
)


def narzedzie_treningu() -> Any:
    spec = importlib.util.spec_from_file_location("train_mccfr", REPO / "tools" / "train_mccfr.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def widok(
    legal: LegalActions,
    board: tuple[Card, ...] = (),
    visible: tuple[ActionTaken, ...] = (),
) -> PlayerView:
    return PlayerView(
        seat=0,
        button=0,
        small_blind=1,
        big_blind=2,
        hole_cards=(AS, KH),
        board=board,
        stacks=(98, 98),
        pot=4,
        phase=Phase.PREFLOP if not board else Phase.FLOP,
        visible_actions=visible,
        revealed_cards=(None, None),
        to_act=0,
        legal_actions=legal,
    )


LEGAL_CALL_RAISE = LegalActions(
    seat=0, fold_allowed=True, check_allowed=False, call_amount=6,
    bet_range=None, raise_range=ActionBounds(minimum=12, maximum=98),
)
LEGAL_CHECK_BET = LegalActions(
    seat=0, fold_allowed=True, check_allowed=True, call_amount=None,
    bet_range=ActionBounds(minimum=2, maximum=98), raise_range=None,
)


def test_artefakt_ma_pochodzenie_i_poprawne_rozklady() -> None:
    from poker import strategy_table

    assert strategy_table.ABSTRACTION_VERSION == ABSTRACTION_VERSION
    assert strategy_table.ITERATIONS > 0
    assert isinstance(strategy_table.SEED, int)
    assert strategy_table.PREFLOP_BUCKETS >= 1
    assert strategy_table.POSTFLOP_BUCKETS >= 1
    assert strategy_table.BET_SIZES
    assert strategy_table.SMALL_BLIND >= 1 and strategy_table.BIG_BLIND >= 1
    assert len(strategy_table.STACKS) == 2
    assert strategy_table.DENOMINATOR > 0
    assert strategy_table.INFOSETS == len(strategy_table.STRATEGY) > 0
    for key, distribution in strategy_table.STRATEGY.items():
        assert key.startswith(f"a{ABSTRACTION_VERSION}|")
        assert sum(weight for _, weight in distribution) == strategy_table.DENOMINATOR
        assert all(weight >= 0 for _, weight in distribution)
        for action_name, _ in distribution:
            assert action_key(action_from_key(action_name)) == action_name


def test_reprodukcja_kontrolnego_biegu_bajt_w_bajt(tmp_path: Path) -> None:
    tool = narzedzie_treningu()
    # płytkie stacki: bieg kontrolny musi mieścić się w bramce (decyzja 06 pkt 3)
    argv = ["--iterations", "20", "--seed", "5", "--stack", "12", "12"]
    assert tool.main([*argv, "--output", str(tmp_path / "a.py")]) == 0
    assert tool.main([*argv, "--output", str(tmp_path / "b.py")]) == 0
    assert (tmp_path / "a.py").read_bytes() == (tmp_path / "b.py").read_bytes()
    inny = ["--iterations", "20", "--seed", "6", "--stack", "12", "12",
            "--output", str(tmp_path / "c.py")]
    assert tool.main(inny) == 0
    assert (tmp_path / "a.py").read_bytes() != (tmp_path / "c.py").read_bytes()


def test_mieszanie_bez_stanu_jest_funkcja_seeda_i_widoku() -> None:
    view = widok(LEGAL_CALL_RAISE)
    agent = StrategyAgent(seed=7)
    pierwsza = agent.decide(view)
    for _ in range(5):
        assert agent.decide(view) == pierwsza  # brak pamięci między wywołaniami
    assert StrategyAgent(seed=7).decide(view) == pierwsza  # świeża instancja

    # Mieszanie ma zależeć od seeda dokładnie tam, gdzie rozkład jest mieszany:
    # liczbę różnych decyzji po seedach wiążemy z liczbą niezerowych akcji w artefakcie.
    dostepne = {action_key(akcja) for akcja in abstract_actions(view, ABSTRACTION_CONFIG)}
    rozklad = [
        (nazwa, waga)
        for nazwa, waga in STRATEGY.get(infoset(view, ABSTRACTION_CONFIG), ())
        if nazwa in dostepne and waga > 0
    ]
    decyzje = {StrategyAgent(seed=seed).decide(view) for seed in range(200)}
    if len(rozklad) > 1:
        assert len(decyzje) > 1, "rozkład mieszany musi dawać różne akcje dla różnych seedów"
    else:
        assert len(decyzje) == 1, "rozkład czysty musi dawać tę samą akcję niezależnie od seeda"

    inny_widok = widok(LEGAL_CHECK_BET, board=FLOP)
    assert StrategyAgent(seed=7).decide(inny_widok) == StrategyAgent(seed=7).decide(inny_widok)


def test_nieznany_infoset_ma_deterministyczny_fallback() -> None:
    from poker import strategy_table

    # Sześć checków z rzędu nie powstaje w rozdaniu (na ulicę są najwyżej dwa),
    # więc ten infoset na pewno nie ma wpisu w artefakcie.
    niemozliwa_historia = tuple(
        ActionTaken(seat=miejsce % 2, action=ActionType.CHECK, amount=0)
        for miejsce in range(6)
    )
    view = widok(LEGAL_CALL_RAISE, visible=niemozliwa_historia)
    klucz = infoset(
        view,
        AbstractionConfig(
            preflop_buckets=strategy_table.PREFLOP_BUCKETS,
            postflop_buckets=strategy_table.POSTFLOP_BUCKETS,
            bet_sizes=tuple(strategy_table.BET_SIZES),
        ),
    )
    assert klucz not in strategy_table.STRATEGY
    assert StrategyAgent(seed=0).decide(view) == Decision(action=ActionType.CALL)
    assert StrategyAgent(seed=99).decide(view) == Decision(action=ActionType.CALL)


def test_wlasciwosciowy_mecze_bez_bledow_legalnosci() -> None:
    for seed in range(12):
        wynik = play_match(CONFIG, seed=seed, agents=(StrategyAgent(), RuleAgent()))
        assert sum(wynik.stacks) == 200
        assert wynik.hands_played >= 1
    przeciw_klonowi = play_match(CONFIG, seed=3, agents=(StrategyAgent(), CloneAgent()))
    assert sum(przeciw_klonowi.stacks) == 200
    lustro = play_match(CONFIG, seed=4, agents=(StrategyAgent(seed=1), StrategyAgent(seed=2)))
    assert sum(lustro.stacks) == 200


def test_agent_w_rejestrze_i_mierzalny_w_arenie(capsys: pytest.CaptureFixture[str]) -> None:
    assert "mccfr" in agent_registry()
    argv = ["--series", "2", "--hands", "10", "--seed", "5",
            "--agent0", "mccfr", "--agent1", "rule"]
    assert main(argv) == 0
    pierwszy = capsys.readouterr().out
    assert "BB/100" in pierwszy
    assert main(argv) == 0
    assert capsys.readouterr().out == pierwszy


def test_agent_gra_przez_serwer_lan(capsys: pytest.CaptureFixture[str]) -> None:
    server = TableServer()
    try:
        _, port = server.start()
        wynik = main(
            ["--connect", f"127.0.0.1:{port}", "--opponent", "mccfr",
             "--hands", "1", "--seed", "1"],
            stdin=io.StringIO("call\n" * 20),
        )
        assert wynik == 0
        assert "koniec meczu" in capsys.readouterr().out
    finally:
        server.close()

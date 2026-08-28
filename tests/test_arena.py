"""Testy areny (POKER-13): lustrzane rozdania, BB/100 z przedziałem ufności, determinizm."""

from pathlib import Path

import pytest

from poker.adapters.cli import main
from poker.agent import Decision
from poker.arena import SeriesConfig, play_mirrored_pair, run_series, series_pair_seeds
from poker.events import ActionType, FlopDealt, HoleCardsDealt, RiverDealt, TurnDealt
from poker.rule_agent import RuleAgent
from poker.views import PlayerView


class ZawszeFold:
    def decide(self, view: PlayerView) -> Decision:
        return Decision(action=ActionType.FOLD)


class Sprawdzajacy:
    """Check gdy można, inaczej call."""

    def decide(self, view: PlayerView) -> Decision:
        legal = view.legal_actions
        assert legal is not None
        if legal.check_allowed:
            return Decision(action=ActionType.CHECK)
        assert legal.call_amount is not None
        return Decision(action=ActionType.CALL)


class WszystkoDoSrodka:
    """All-in przy pierwszej okazji, inaczej call/check."""

    def decide(self, view: PlayerView) -> Decision:
        legal = view.legal_actions
        assert legal is not None
        if legal.raise_range is not None:
            return Decision(action=ActionType.RAISE, amount=legal.raise_range.maximum)
        if legal.bet_range is not None:
            return Decision(action=ActionType.BET, amount=legal.bet_range.maximum)
        if legal.call_amount is not None:
            return Decision(action=ActionType.CALL)
        return Decision(action=ActionType.CHECK)


CONFIG = SeriesConfig(
    small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=20, pairs=4
)


def karty_rozdan(histories: tuple[tuple[object, ...], ...]) -> list[list[object]]:
    return [
        [
            event
            for event in history
            if isinstance(event, HoleCardsDealt | FlopDealt | TurnDealt | RiverDealt)
        ]
        for history in histories
    ]


def test_lustrzane_przebiegi_maja_identyczne_karty() -> None:
    config = SeriesConfig(
        small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=2, pairs=2
    )
    first, second = play_mirrored_pair(config, 5, WszystkoDoSrodka(), Sprawdzajacy())
    assert karty_rozdan(first.histories) == karty_rozdan(second.histories)


def test_zawsze_fold_przegrywa_z_regulowym_calym_przedzialem() -> None:
    report = run_series(CONFIG, seed=7, agent_a=ZawszeFold(), agent_b=RuleAgent())
    assert report.bb_per_100 == -75.0  # blind mniejszy i większy tracone na przemian
    assert report.ci95_high < 0


def test_agent_przeciw_samemu_sobie_ma_przedzial_obejmujacy_zero() -> None:
    report = run_series(CONFIG, seed=7, agent_a=RuleAgent(), agent_b=RuleAgent())
    assert report.bb_per_100 == 0.0  # lustro znosi wynik identycznych agentów co do żetonu
    assert report.ci95_low <= 0.0 <= report.ci95_high


def test_wynik_pary_jest_suma_obu_przebiegow() -> None:
    seeds = series_pair_seeds(seed=7, pairs=CONFIG.pairs)
    assert len(seeds) == CONFIG.pairs
    report = run_series(CONFIG, seed=7, agent_a=ZawszeFold(), agent_b=RuleAgent())
    first, second = play_mirrored_pair(CONFIG, seeds[0], ZawszeFold(), RuleAgent())
    delta = (first.stacks[0] - 100) + (second.stacks[1] - 100)
    hands = first.hands_played + second.hands_played
    assert report.pair_results_bb_per_100[0] == delta / CONFIG.big_blind / hands * 100


def test_ten_sam_seed_serii_daje_identyczny_raport() -> None:
    first = run_series(CONFIG, seed=11, agent_a=WszystkoDoSrodka(), agent_b=RuleAgent())
    second = run_series(CONFIG, seed=11, agent_a=WszystkoDoSrodka(), agent_b=RuleAgent())
    assert first == second
    other = run_series(CONFIG, seed=12, agent_a=WszystkoDoSrodka(), agent_b=RuleAgent())
    assert first != other


def test_seria_wymaga_co_najmniej_dwoch_par() -> None:
    with pytest.raises(ValueError, match="par"):
        SeriesConfig(
            small_blind=1, big_blind=2, stacks=(100, 100), button=0, hand_limit=5, pairs=1
        )


def test_seria_przez_cli_z_deterministycznym_wynikiem(
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["--series", "2", "--hands", "10", "--seed", "5", "--agent1", "rule-aggressive"]
    assert main(argv) == 0
    first = capsys.readouterr().out
    assert "BB/100" in first
    assert "95%" in first
    assert "par" in first
    assert main(argv) == 0
    assert capsys.readouterr().out == first


def test_seria_przez_cli_odrzuca_niespojne_flagi(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert main(["--series", "1"]) == 2
    assert "par" in capsys.readouterr().err
    assert main(["--series", "2", "--human", "0"]) == 2
    assert "human" in capsys.readouterr().err
    assert main(["--series", "2", "--export", str(tmp_path / "x.json")]) == 2
    assert "export" in capsys.readouterr().err

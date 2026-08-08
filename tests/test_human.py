"""Testy interfejsu człowieka (POKER-10): render z PlayerView, walidacja wejścia, przecieki."""

import io
from pathlib import Path

import pytest

from poker.adapters.cli import main
from poker.adapters.export import deserialize_match_history
from poker.adapters.human import HumanAgent, InputEnded, card_token, render_view
from poker.agent import Decision
from poker.betting import ActionBounds, LegalActions
from poker.cards import Card, Rank, Suit
from poker.events import ActionTaken, ActionType, DeckSeeded, HoleCardsDealt
from poker.projection import Phase
from poker.views import PlayerView

AS, KH = Card(Rank.ACE, Suit.SPADES), Card(Rank.KING, Suit.HEARTS)
BOARD = (
    Card(Rank.NINE, Suit.HEARTS),
    Card(Rank.FIVE, Suit.CLUBS),
    Card(Rank.THREE, Suit.DIAMONDS),
)


def widok(legal: LegalActions | None) -> PlayerView:
    return PlayerView(
        seat=0,
        button=0,
        small_blind=1,
        big_blind=2,
        hole_cards=(AS, KH),
        board=BOARD,
        stacks=(94, 90),
        pot=16,
        phase=Phase.FLOP,
        visible_actions=(ActionTaken(seat=1, action=ActionType.BET, amount=6),),
        revealed_cards=(None, None),
        to_act=0,
        legal_actions=legal,
    )


LEGALNE = LegalActions(
    seat=0,
    fold_allowed=True,
    check_allowed=False,
    call_amount=6,
    bet_range=None,
    raise_range=ActionBounds(minimum=12, maximum=94),
)


def test_render_pokazuje_dane_widoku_i_granice_legalnych_akcji() -> None:
    tekst = render_view(widok(LEGALNE))
    assert "As Kh" in tekst
    assert "9h 5c 3d" in tekst
    assert "pula: 16" in tekst
    assert "94" in tekst and "90" in tekst
    assert "bet 6" in tekst  # jawna akcja przeciwnika
    assert "call 6" in tekst
    assert "raise 12..94" in tekst
    assert "check" not in tekst  # niedostępny — nie oferujemy


def test_bledne_wejscia_daja_komunikat_i_ponowne_pytanie() -> None:
    wejscie = io.StringIO("abrakadabra\ncall 5\nbet 10\ncheck\nraise 5\nraise 12\n")
    wyjscie = io.StringIO()
    agent = HumanAgent(input_stream=wejscie, output_stream=wyjscie)
    decyzja = agent.decide(widok(LEGALNE))
    assert decyzja == Decision(action=ActionType.RAISE, amount=12)
    tekst = wyjscie.getvalue()
    assert "nieznana akcja" in tekst
    assert "nie przyjmuje kwoty" in tekst
    assert "niedostępn" in tekst  # bet i check w tym stanie
    assert "poza granicami" in tekst


def test_koniec_strumienia_wejscia_przerywa_decyzje() -> None:
    agent = HumanAgent(input_stream=io.StringIO(""), output_stream=io.StringIO())
    with pytest.raises(InputEnded):
        agent.decide(widok(LEGALNE))


def _bot_hole_tokens(histories: tuple[tuple[object, ...], ...], bot_seat: int) -> set[str]:
    tokens: set[str] = set()
    for history in histories:
        for event in history:
            if isinstance(event, HoleCardsDealt) and event.seat == bot_seat:
                tokens |= {card_token(card) for card in event.cards}
    return tokens


def _seed_strings(histories: tuple[tuple[object, ...], ...]) -> set[str]:
    return {
        str(event.seed)
        for history in histories
        for event in history
        if isinstance(event, DeckSeeded)
    }


def test_fold_przed_showdownem_nie_ujawnia_kart_bota_ani_seeda(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    export = tmp_path / "mecz.json"
    stdin = io.StringIO("fold\nfold\n")
    assert main(
        ["--human", "0", "--hands", "2", "--seed", "3", "--export", str(export)], stdin=stdin
    ) == 0
    out = capsys.readouterr().out
    histories = deserialize_match_history(export.read_text(encoding="utf-8"))
    assert len(histories) == 2
    for token in _bot_hole_tokens(histories, bot_seat=1):
        assert token not in out
    for seed_text in _seed_strings(histories):
        assert seed_text not in out


def test_pelne_rozdanie_decyzjami_czlowieka_do_showdownu(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    export = tmp_path / "mecz.json"
    stdin = io.StringIO("call\ncall\ncall\ncall\n")
    assert main(
        ["--human", "0", "--hands", "1", "--seed", "1", "--export", str(export)], stdin=stdin
    ) == 0
    out = capsys.readouterr().out
    histories = deserialize_match_history(export.read_text(encoding="utf-8"))
    assert len(histories) == 1
    decyzje_czlowieka = [
        event
        for event in histories[0]
        if isinstance(event, ActionTaken) and event.seat == 0
    ]
    assert len(decyzje_czlowieka) == 4
    assert out.count("twoja decyzja") == 4
    assert "stacki końcowe: 92 108" in out
    assert "rozdania: 1" in out
    # showdown: karty bota pojawiają się wyłącznie po znaczniku przebiegu rozdań
    marker = out.index("przebieg rozdań")
    for token in _bot_hole_tokens(histories, bot_seat=1):
        assert token not in out[:marker]
        assert token in out[marker:]
    for seed_text in _seed_strings(histories):
        assert seed_text not in out


def test_bledne_wejscia_nie_zostawiaja_sladu_w_historii(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    export = tmp_path / "mecz.json"
    stdin = io.StringIO("xyzzy\nbet 10\ncheck\nraise 1\nfold\n")
    assert main(
        ["--human", "0", "--hands", "1", "--seed", "3", "--export", str(export)], stdin=stdin
    ) == 0
    out = capsys.readouterr().out
    assert "nieprawidłowe wejście" in out
    histories = deserialize_match_history(export.read_text(encoding="utf-8"))
    akcje_czlowieka = [
        event
        for event in histories[0]
        if isinstance(event, ActionTaken) and event.seat == 0
    ]
    assert akcje_czlowieka == [ActionTaken(seat=0, action=ActionType.FOLD, amount=0)]


def test_koniec_wejscia_konczy_mecz_niezerowym_kodem(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--human", "0", "--hands", "1", "--seed", "1"], stdin=io.StringIO("")) == 1
    assert "koniec wejścia" in capsys.readouterr().err


def test_identyczne_wejscie_daje_odtwarzalny_przebieg(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scenariusz = "call\ncall\ncall\ncall\n"
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    argv = ["--human", "0", "--hands", "1", "--seed", "1"]
    assert main([*argv, "--export", str(first)], stdin=io.StringIO(scenariusz)) == 0
    out_first = capsys.readouterr().out
    assert main([*argv, "--export", str(second)], stdin=io.StringIO(scenariusz)) == 0
    out_second = capsys.readouterr().out
    assert out_first.replace(str(first), "") == out_second.replace(str(second), "")
    assert first.read_bytes() == second.read_bytes()

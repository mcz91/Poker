"""Testy interfejsu człowieka (POKER-10, POKER-69, POKER-77): render z PlayerView, walidacja
wejścia, przecieki, seed meczu z entropii."""

import io
import random
import re
from dataclasses import replace
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


WIDOK_BEZ_ZAKLADU = replace(
    widok(
        LegalActions(
            seat=0,
            fold_allowed=True,
            check_allowed=True,
            call_amount=None,
            bet_range=ActionBounds(minimum=2, maximum=94),
            raise_range=None,
        )
    ),
    visible_actions=(),
)


def decyzja_po_wejsciu(stan: PlayerView, wejscie: str) -> tuple[Decision, str]:
    wyjscie = io.StringIO()
    agent = HumanAgent(input_stream=io.StringIO(wejscie), output_stream=wyjscie)
    return agent.decide(stan), wyjscie.getvalue()


def test_call_bez_zakladu_do_sprawdzenia_daje_komunikat_i_ponowne_pytanie() -> None:
    decyzja, tekst = decyzja_po_wejsciu(WIDOK_BEZ_ZAKLADU, "call\ncheck\n")
    assert decyzja == Decision(action=ActionType.CHECK)
    assert "call niedostępny" in tekst
    assert tekst.count("twoja decyzja") == 2


@pytest.mark.parametrize(
    ("stan", "bledne", "oczekiwana"),
    [
        pytest.param(widok(LEGALNE), "raise 12 13", Decision(ActionType.RAISE, 20), id="raise-2"),
        pytest.param(widok(LEGALNE), "raise", Decision(ActionType.RAISE, 20), id="raise-0"),
        pytest.param(WIDOK_BEZ_ZAKLADU, "bet 2 3", Decision(ActionType.BET, 4), id="bet-2"),
        pytest.param(WIDOK_BEZ_ZAKLADU, "bet", Decision(ActionType.BET, 4), id="bet-0"),
    ],
)
def test_bet_i_raise_wymagaja_dokladnie_jednej_kwoty(
    stan: PlayerView, bledne: str, oczekiwana: Decision
) -> None:
    poprawne = f"{oczekiwana.action.value} {oczekiwana.amount}"
    decyzja, tekst = decyzja_po_wejsciu(stan, f"{bledne}\n{poprawne}\n")
    # Kwota poprawnej decyzji różni się od pierwszego tokenu kwoty błędnej linii: przyjęcie
    # 'raise 12 13' jako 'raise 12' nie przejdzie po cichu.
    assert decyzja == oczekiwana
    assert "dokładnie jednej kwoty" in tekst
    assert tekst.count("twoja decyzja") == 2


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
    assert "koniec rozdania 1: " in out  # rozstrzygnięcia na żywo też bez przecieku
    assert "koniec rozdania 2: " in out
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
    # showdown na żywo: karty bota pojawiają się dopiero w rozstrzygnięciu rozdania
    marker = out.index("koniec rozdania 1: ")
    linia_na_zywo = out[marker : out.index("\n", marker)]
    assert "pokazuje" in linia_na_zywo
    assert marker < out.index("przebieg rozdań")  # podsumowanie po meczu pozostaje
    for token in _bot_hole_tokens(histories, bot_seat=1):
        assert token not in out[:marker]
        assert token in linia_na_zywo
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


def test_rozstrzygniecie_rozdania_na_zywo_przed_kolejna_decyzja(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stdin = io.StringIO("fold\nfold\n")
    assert main(["--human", "0", "--hands", "2", "--seed", "3"], stdin=stdin) == 0
    out = capsys.readouterr().out
    prompts = [index for index in range(len(out)) if out.startswith("twoja decyzja", index)]
    assert len(prompts) == 2
    live_first = out.index("koniec rozdania 1: ")
    assert prompts[0] < live_first < prompts[1]
    assert "koniec rozdania 2: " in out
    linia = out[live_first : out.index("\n", live_first)]
    assert "pasuje" in linia
    assert "pula" in linia and "dla miejsca" in linia


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


def _seed_z_linii(tekst: str) -> tuple[int, int]:
    """Wartość i pozycja jedynej linii 'seed meczu: N' w tekście."""
    (trafienie,) = re.finditer(r"^seed meczu: (\d+)$", tekst, flags=re.MULTILINE)
    return int(trafienie.group(1)), trafienie.start()


def _karty(path: Path) -> list[tuple[int, tuple[str, ...]]]:
    return [
        (event.seat, tuple(card_token(card) for card in event.cards))
        for history in deserialize_match_history(path.read_text(encoding="utf-8"))
        for event in history
        if isinstance(event, HoleCardsDealt)
    ]


def test_czlowiek_bez_seeda_gra_na_entropii_a_seed_poznaje_po_meczu(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    wejscie = "fold\n" * 3
    argv = ["--human", "0", "--hands", "3"]
    eksporty = [tmp_path / "a.json", tmp_path / "b.json"]
    seedy = []
    for eksport in eksporty:
        assert main([*argv, "--export", str(eksport)], stdin=io.StringIO(wejscie)) == 0
        out = capsys.readouterr().out
        seed, pozycja = _seed_z_linii(out)
        # po ostatnim rozdaniu i po liniach wyniku, nigdy wcześniej
        assert out.rindex("koniec rozdania") < out.index("stacki końcowe: ") < pozycja
        assert str(seed) not in out[:pozycja]
        assert 0 <= seed < 2**64
        seedy.append(seed)
    assert seedy[0] != seedy[1]
    assert max(seedy) >= 2**48  # 64 bity entropii, nie 32 (porażka z p = 2**-32)
    assert _karty(eksporty[0]) != _karty(eksporty[1])

    # replay: jawny --seed równy wypisanemu odtwarza mecz bajt w bajt i nie wypisuje seeda
    replay = tmp_path / "replay.json"
    assert main(
        [*argv, "--seed", str(seedy[0]), "--export", str(replay)], stdin=io.StringIO(wejscie)
    ) == 0
    assert "seed meczu" not in capsys.readouterr().out
    assert replay.read_bytes() == eksporty[0].read_bytes()


def test_seed_czlowieka_to_64_bity_csprng_systemu(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Entropia systemu to system zewnętrzny: podstawiamy ją, żeby zobaczyć, czy i ile z niej
    # CLI bierze.
    wartosc = 0xFACE_0000_0000_B00C
    pobrania: list[int] = []

    def entropia(self: random.SystemRandom, k: int) -> int:
        pobrania.append(k)
        return wartosc

    monkeypatch.setattr(random.SystemRandom, "getrandbits", entropia)
    wejscie = "fold\nfold\n"
    losowy, jawny = tmp_path / "losowy.json", tmp_path / "jawny.json"
    assert main(
        ["--human", "1", "--hands", "2", "--export", str(losowy)], stdin=io.StringIO(wejscie)
    ) == 0
    assert _seed_z_linii(capsys.readouterr().out)[0] == wartosc
    assert pobrania == [64]
    assert main(
        ["--human", "1", "--hands", "2", "--seed", str(wartosc), "--export", str(jawny)],
        stdin=io.StringIO(wejscie),
    ) == 0
    assert losowy.read_bytes() == jawny.read_bytes()


def test_przerwany_mecz_bez_seeda_wypisuje_seed_na_stderr_po_komunikacie(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--human", "0", "--hands", "2"], stdin=io.StringIO("")) == 1
    przechwycone = capsys.readouterr()
    assert "seed meczu" not in przechwycone.out
    _, pozycja = _seed_z_linii(przechwycone.err)
    assert przechwycone.err.index("koniec wejścia — mecz przerwany") < pozycja

    # jawny --seed działa jak dotąd: bez linii seeda
    assert main(["--human", "0", "--hands", "2", "--seed", "5"], stdin=io.StringIO("")) == 1
    przechwycone = capsys.readouterr()
    assert "seed meczu" not in przechwycone.out + przechwycone.err

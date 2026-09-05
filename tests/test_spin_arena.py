"""ROI arena: blok rotacji, wspólne seedy, bootstrap; determinizm INV-P1; ręka HU."""

from __future__ import annotations

import os
import random
import subprocess
import sys
from collections.abc import Sequence

import pytest

from poker import spin_arena
from poker.betting import HeadsUpHand
from poker.cards import Card
from poker.dealing import DealtHand, deal_hand, shuffled_deck
from poker.events import ActionType, HandConfig
from poker.openfold import _mass, threebet_vs_range
from poker.spin import PAYOUTS, STARTING_CHIPS, is_jam_fold_depth, open_amount
from poker.spin_arena import (
    Seat,
    SeatBook,
    SeatView,
    _play_hand,
    always_fold,
    always_jam,
    bootstrap_ci,
    call_vs_random,
    compare_blocks,
    dollar_fish,
    field_exploit,
    legal_actions,
    pick,
    play_block,
    play_spin,
    run_spin,
    sample_blocks,
    sample_seat,
    wide_call,
)


def test_trzech_jammerow_okolo_jednego_bi() -> None:
    jam = always_jam()
    hit = sample_blocks(jam, jam, PAYOUTS["3x"].prizes, n=30, seed=7)
    assert 0.6 < hit["mean_bi"] < 1.4


def test_foldbot_przegrywa_z_jammerem() -> None:
    hit = sample_blocks(always_fold(), always_jam(), PAYOUTS["3x"].prizes, n=20, seed=3)
    assert hit["mean_bi"] < 0.85


def test_rotacje_bloku_graja_te_same_karty() -> None:
    """Ten sam seed w trzech rotacjach: talia ręki i zależy tylko od (seed, i).

    Książki są asymetryczne, więc przebieg licytacji różni się między
    rotacjami — talie wspólnych rąk muszą mimo to być identyczne.
    """
    hero, villain = field_exploit(), dollar_fish()
    seat_books = (
        (hero, villain, villain),
        (villain, hero, villain),
        (villain, villain, hero),
    )
    decks: list[dict[int, tuple[Card, ...]]] = []
    for books in seat_books:
        seen: dict[int, tuple[Card, ...]] = {}
        run_spin(books, 5, on_deck=seen.__setitem__)
        decks.append(seen)
    common = min(len(seen) for seen in decks)
    assert common >= 2
    for hand_i in range(common):
        assert decks[0][hand_i] == decks[1][hand_i] == decks[2][hand_i], hand_i


def test_blok_to_srednia_hero_po_trzech_rotacjach() -> None:
    hero, villain = field_exploit(), always_jam()
    prizes = PAYOUTS["3x"].prizes
    rotations = [
        play_spin((hero, villain, villain), prizes, 9)[0],
        play_spin((villain, hero, villain), prizes, 9)[1],
        play_spin((villain, villain, hero), prizes, 9)[2],
    ]
    assert play_block(hero, villain, prizes, 9) == sum(rotations) / 3.0
    assert play_block(hero, villain, prizes, 9) == play_block(hero, villain, prizes, 9)


def test_sample_blocks_deterministyczne_z_bootstrapem() -> None:
    hit = sample_blocks(field_exploit(), always_jam(), PAYOUTS["3x"].prizes, n=12, seed=5)
    again = sample_blocks(field_exploit(), always_jam(), PAYOUTS["3x"].prizes, n=12, seed=5)
    assert hit == again
    assert hit["n"] == 12.0
    assert hit["ci_lo"] <= hit["roi"] <= hit["ci_hi"]
    assert hit["boot_lo"] <= hit["roi"] <= hit["boot_hi"]
    other = sample_blocks(
        field_exploit(), always_jam(), PAYOUTS["3x"].prizes, n=12, seed=5, bootstrap_seed=1
    )
    assert other["roi"] == hit["roi"]
    assert other["se"] == hit["se"]


def test_bootstrap_ci_deterministyczny_i_obejmuje_srednia_stalej_proby() -> None:
    xs = [0.0, 3.0, 0.0, 0.0, 3.0, 0.0, 3.0, 3.0, 0.0, 0.0]
    assert bootstrap_ci(xs, replications=500, seed=2) == bootstrap_ci(xs, replications=500, seed=2)
    lo, hi = bootstrap_ci(xs, replications=500, seed=2)
    assert lo <= sum(xs) / len(xs) <= hi
    assert bootstrap_ci([1.0, 1.0, 1.0, 1.0], replications=100, seed=0) == (1.0, 1.0)
    with pytest.raises(ValueError):
        bootstrap_ci([1.0], replications=100, seed=0)
    with pytest.raises(ValueError):
        bootstrap_ci(xs, replications=0, seed=0)


def test_compare_blocks_wspolne_seedy_znosza_identyczne_ramiona_do_zera() -> None:
    a = (field_exploit(), always_jam())
    hit = compare_blocks(a, a, PAYOUTS["3x"].prizes, n=8, seed=13)
    assert hit["diff"] == 0.0
    assert hit["se"] == 0.0
    assert (hit["ci_lo"], hit["ci_hi"]) == (0.0, 0.0)
    assert (hit["boot_lo"], hit["boot_hi"]) == (0.0, 0.0)


def test_compare_blocks_deterministyczne_i_spojne_z_ramionami() -> None:
    a = (field_exploit(), always_jam())
    b = (dollar_fish(), always_jam())
    hit = compare_blocks(a, b, PAYOUTS["3x"].prizes, n=10, seed=17)
    again = compare_blocks(a, b, PAYOUTS["3x"].prizes, n=10, seed=17)
    assert hit == again
    assert hit["diff"] == pytest.approx(hit["roi_a"] - hit["roi_b"])
    assert hit["ci_lo"] <= hit["diff"] <= hit["ci_hi"]


def test_sample_seat_mierzy_jedno_miejsce() -> None:
    prizes = PAYOUTS["3x"].prizes
    foldbot = sample_seat(always_fold(), always_jam(), prizes, n=20, seed=3, hero_seat=1)
    assert foldbot["mean_bi"] < 0.85
    assert foldbot["hero_seat"] == 1.0
    per_seat = [
        sample_seat(field_exploit(), always_jam(), prizes, n=20, seed=3, hero_seat=seat)
        for seat in range(3)
    ]
    for seat, hit in enumerate(per_seat):
        again = sample_seat(
            field_exploit(), always_jam(), prizes, n=20, seed=3, hero_seat=seat
        )
        assert hit == again
    # Te same seedy, inne miejsce: inne karty i pozycje, więc inny wynik.
    assert len({hit["mean_bi"] for hit in per_seat}) > 1


def test_spin_konczy_sie_bustem_bez_utraty_zetonow() -> None:
    """Powód końca i suma żetonów — nie suma nagród, która jest tożsamością wypłat."""
    books = (always_jam(), always_jam(), always_jam())
    stacks, reason = run_spin(books, 11)
    assert reason == "bust"
    assert sum(stacks) == 3 * STARTING_CHIPS
    assert sorted(stacks) == [0, 0, 3 * STARTING_CHIPS]
    money = play_spin(books, PAYOUTS["3x"].prizes, 11)
    assert money[stacks.index(3 * STARTING_CHIPS)] == 3.0


def test_kazda_reka_areny_zachowuje_sume_zetonow() -> None:
    books = (field_exploit(), dollar_fish(), always_jam())
    for seed in range(20):
        rng = random.Random(seed)
        deck = shuffled_deck(rng)
        for stacks in ([50, 50, 50], [16, 50, 84], [3, 1, 146], [0, 60, 90]):
            for button in range(3):
                if stacks[button] <= 0:
                    continue
                out = _play_hand(list(stacks), 3, button, 2, 4, books, deck, rng)
                assert sum(out) == sum(stacks), (seed, stacks, button, out)
                assert all(s >= 0 for s in out)


def test_call_vs_random_to_nie_jest_gto() -> None:
    mass = 100.0 * _mass(call_vs_random(0.50))
    assert 40.0 < mass < 58.0


def test_dollar_fish_otwiera_za_szeroko() -> None:
    fish = dollar_fish()
    assert 45.0 < 100.0 * _mass(fish.open) < 65.0
    assert 100.0 * _mass(fish.vs_open) < 100.0 * _mass(fish.open)
    hit = threebet_vs_range(
        fish.open, (50, 50, 50), PAYOUTS["3x"].prizes, continue_frac=0.45
    )
    assert 12.0 <= hit.btn_vs_open_pct <= 40.0
    assert hit.aa_jams
    assert hit.junk_folds


def test_field_exploit_kradnie_szerzej() -> None:
    book = field_exploit()
    assert 40.0 < 100.0 * _mass(book.open) < 60.0
    assert 25.0 < 100.0 * _mass(book.vs_open) < 50.0
    assert 100.0 * _mass(book.vs_jam) > 35.0


def test_ten_sam_seed_daje_ten_sam_wynik_przy_roznym_hash_seed() -> None:
    """INV-P1: wynik bloku zależy wyłącznie od seeda, nie od PYTHONHASHSEED procesu."""
    script = (
        "from poker.spin import PAYOUTS\n"
        "from poker.spin_arena import always_jam, field_exploit, play_block, play_spin\n"
        "books = (always_jam(), always_jam(), always_jam())\n"
        "print([play_spin(books, PAYOUTS['3x'].prizes, seed) for seed in range(5)])\n"
        "print([play_block(field_exploit(), always_jam(), PAYOUTS['3x'].prizes, seed)"
        " for seed in range(5)])\n"
    )
    runs = [
        subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for hash_seed in ("1", "2")
    ]
    assert runs[0] == runs[1]


def test_reka_hu_po_wybiciu_bb_obaj_zywi_jamuja_dla_kazdego_buttona() -> None:
    """Wybite miejsce na nominalnym BB nie może gubić żywego gracza: pot się rozstrzyga."""
    books = (always_jam(), always_jam(), always_jam())
    for button in range(3):
        busted = (button + 1) % 3
        stacks = [10, 10, 10]
        stacks[busted] = 0
        # Seed 0: rozdania rozstrzygające (bez split potu) dla każdej pozycji buttona.
        deck = shuffled_deck(random.Random(0))
        out = _play_hand(stacks, 0, button, 1, 2, books, deck, random.Random(0))
        assert sorted(out) == [0, 0, 20], (button, out)
        assert out[busted] == 0


def test_reka_hu_po_wybiciu_bb_blindy_pobierane_z_zywych_miejsc() -> None:
    """Button płaci SB, drugi żywy gracz BB; fold buttona oddaje SB przeciwnikowi."""
    books = (always_fold(), always_fold(), always_fold())
    for button in range(3):
        busted = (button + 1) % 3
        other = (button + 2) % 3
        stacks = [10, 10, 10]
        stacks[busted] = 0
        deck = shuffled_deck(random.Random(4))
        out = _play_hand(stacks, 0, button, 1, 2, books, deck, random.Random(4))
        assert out[button] == 9, (button, out)
        assert out[other] == 11, (button, out)
        assert out[busted] == 0


class _Script:
    """Miejsce grające zadaną listę akcji — stanowy port areny w roli skryptu.

    `log` zapisuje, kogo i w jakiej kolejności pytał rozgrywacz: miejsce
    wpuszczone do puli za darmo nie jest pytane, więc nie zostawia w nim śladu.
    """

    def __init__(self, *actions: str, log: list[int] | None = None) -> None:
        self.actions = list(actions)
        self.log = log

    def act(self, view: SeatView, rng: random.Random) -> str:
        rng.random()
        if self.log is not None:
            self.log.append(view.seat)
        return self.actions.pop(0)


def test_po_jamie_pyta_pierwszego_niedopasowanego_na_lewo_od_agresora() -> None:
    """POKER-54: po przebiciu akcja idzie od agresora, nie stałą kolejką od UTG.

    Guzik 1 sadza UTG na miejscu 0, guzik (SB) na 1, BB na 2. Po jamie guzika
    na open UTG pierwszym niedopasowanym graczem na lewo od agresora jest BB —
    tak pyta reguła pokera i tak wygląda drzewo gry etapowej treningu (węzeł
    „B wobec open UTG i jamu guzika" jest rodzicem węzła UTG).
    """
    log: list[int] = []
    books: tuple[Seat, Seat, Seat] = (
        _Script("open", "fold", log=log),
        _Script("jam", log=log),
        _Script("fold", log=log),
    )
    deck = shuffled_deck(random.Random(0))
    _play_hand([50, 50, 50], 0, 1, 2, 4, books, deck, random.Random(0))
    assert log == [0, 1, 2, 0]


def test_kolejnosc_od_agresora_obejmuje_jam_z_bb_i_hu_po_wybiciu() -> None:
    """Ta sama reguła dla agresora na BB i dla dwóch żywych miejsc po wybiciu."""
    log: list[int] = []
    books: tuple[Seat, Seat, Seat] = (
        _Script("open", "fold", log=log),
        _Script("fold", log=log),
        _Script("jam", log=log),
    )
    deck = shuffled_deck(random.Random(0))
    _play_hand([50, 50, 50], 0, 1, 2, 4, books, deck, random.Random(0))
    assert log == [0, 1, 2, 0]

    hu: list[int] = []
    hu_books: tuple[Seat, Seat, Seat] = (
        _Script("open", "fold", log=hu),
        always_fold(),
        _Script("jam", log=hu),
    )
    _play_hand([50, 0, 50], 0, 0, 2, 4, hu_books, deck, random.Random(0))
    assert hu == [0, 2, 0]


def test_darmowy_call_nie_jest_pytaniem_tylko_wejsciem() -> None:
    """POKER-54: dołożenie zerowe wchodzi automatycznie, bo fold za darmo nie istnieje.

    UTG jamuje cały stack 3 żetonów, a BB ma w puli blind 4 — jam nie
    przewyższa jego wkładu, więc trening wymusza mu wejście maską akcji
    (decyzja 28 pkt 2b). Rozgrywacz nie pyta: BB idzie do showdownu, a jego
    nadpłata (1 żeton ponad jam) wraca. Karty seeda 6 daje BB zwycięstwo.
    """
    log: list[int] = []
    books: tuple[Seat, Seat, Seat] = (
        _Script("jam", log=log),
        _Script("fold", log=log),
        _Script("fold", log=log),
    )
    deck = shuffled_deck(random.Random(6))
    out = _play_hand([3, 50, 50], 0, 1, 2, 4, books, deck, random.Random(0))
    assert log == [0, 1]
    assert out == [0, 48, 55]
    assert sum(out) == 103


def _asked_views(seeds: range, books: tuple[Seat, Seat, Seat]) -> list[SeatView]:
    """Widoki WSZYSTKICH decyzji, o które rozgrywacz zapytał w tych turniejach."""
    seen: list[SeatView] = []

    class Watch:
        def __init__(self, book: SeatBook) -> None:
            self.book = book

        def act(self, view: SeatView, rng: random.Random) -> str:
            seen.append(view)
            return pick(
                self.book,
                view.klass,
                jamfold=view.jamfold,
                opened=view.opened,
                jammed=view.jammed,
                rng=rng,
            )

    watched = tuple(Watch(book) for book in books if isinstance(book, SeatBook))
    for seed in seeds:
        run_spin((watched[0], watched[1], watched[2]), seed)
    return seen


def _zero_due_pending(view: SeatView) -> list[int]:
    """Miejsca (poza decydentem), których dołożenie do najwyższego wkładu to zero."""
    top = max(view.contrib)
    spoke = {seat for seat, _ in view.actions}
    return [
        seat
        for seat in range(3)
        if seat != view.seat
        and seat not in spoke
        and 0 < view.stacks[seat]
        and view.contrib[seat] >= top
        and view.contrib[seat] < view.stacks[seat]
    ]


def test_zadne_miejsce_nie_jest_pytane_o_dolozenie_zerowe() -> None:
    """Właściwość na turniejach: pytanie pada tylko tam, gdzie wejście kosztuje.

    Druga asercja pilnuje, żeby pierwsza nie była o pustce: w tej samej próbce
    sytuacja „ktoś ma dołożenie zerowe" naprawdę występuje (widzi ją miejsce
    pytane wcześniej w tej samej rundzie).
    """
    books = (field_exploit(), dollar_fish(), always_jam())
    views = _asked_views(range(60), books)
    assert len(views) > 500
    pending = 0
    for view in views:
        if view.jammed or view.opened:
            assert view.contrib[view.seat] < max(view.contrib), view
        pending += len(_zero_due_pending(view))
    assert pending > 0, "próbka bez dołożeń zerowych nie sprawdza niczego"


def _kolejnosc_sprzed_poker_54(order: Sequence[int], last_actor: int) -> tuple[int, ...]:
    """Kolejność areny SPRZED POKER-54: stała kolejka ról, ślepa na agresora.

    To jest kontrola eksperymentu do tezy o neutralności dystrybucyjnej, a nie
    atrapa testowanego zachowania: teza mówi o RÓŻNICY między dwiema
    kolejnościami, więc druga kolejność musi być czymś, co da się uruchomić.
    """
    return tuple(order)


def test_kolejnosc_od_agresora_jest_neutralna_dystrybucyjnie_dla_ksiazek(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zmiana kolejności permutuje pobory rng, nie rozkład łączny decyzji.

    Decyzja `SeatBooka` jest funkcją klasy ręki, trzech flag kontekstu i JEDNEGO
    poboru z rng — kolejności nie widzi. Po przebiciu każdy niedopasowany żywy
    gracz jest pytany dokładnie raz przy tych samych flagach w obu
    kolejnościach, więc zamiana kolejności podmienia tylko, który gracz dostaje
    który pobór ze wspólnego strumienia ręki. Pobory są jednakowe i niezależne,
    więc rozkład łączny decyzji się nie zmienia — zmieniają się trajektorie
    per seed, co test też przybija.

    Książki muszą mieć częstotliwości UŁAMKOWE: przy książce 0/1 decyzja nie
    zależy od poboru, więc permutacja strumienia nie ruszyłaby nawet
    trajektorii i test nie sprawdzałby niczego (PUŁAPKA z audytu POKER-52).
    """
    hero, villain = wide_call(0.3), wide_call(0.55)
    prizes = PAYOUTS["3x"].prizes
    n = 300
    after = [play_block(hero, villain, prizes, 5000 + i) for i in range(n)]
    monkeypatch.setattr(spin_arena, "speaking_order", _kolejnosc_sprzed_poker_54)
    before = [play_block(hero, villain, prizes, 5000 + i) for i in range(n)]

    assert before != after, "kolejność bez wpływu na żadną trajektorię = brak zmiany"
    diffs = [a - b for a, b in zip(after, before, strict=True)]
    mean = sum(diffs) / n
    sd = (sum((d - mean) ** 2 for d in diffs) / (n - 1)) ** 0.5
    se = sd / n**0.5
    assert mean - 1.96 * se <= 0.0 <= mean + 1.96 * se, (mean, se)
    sd_after = (sum((x - sum(after) / n) ** 2 for x in after) / (n - 1)) ** 0.5
    sd_before = (sum((x - sum(before) / n) ** 2 for x in before) / (n - 1)) ** 0.5
    assert abs(sd_after - sd_before) < 0.05 * sd_before, (sd_after, sd_before)


def test_ksiazki_referencyjne_nie_widza_kolejnosci_wcale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Przy książkach POKER-42/43/48 kolejność nie rusza nawet trajektorii.

    Ich częstotliwości są zero-jedynkowe, więc decyzja nie zależy od poboru
    z rng, a permutacja strumienia nie zmienia niczego. Stąd werdykt dla
    zamkniętych liczb: cała różnica zmierzona na tych parach należy do
    wymuszonego darmowego calla, a nie do kolejności licytacji.
    """
    prizes = PAYOUTS["3x"].prizes
    pairs = (
        (field_exploit(), dollar_fish()),
        (field_exploit(), always_jam()),
        (dollar_fish(), always_jam()),
    )
    for hero, villain in pairs:
        for book in (hero, villain):
            for freq in (book.open, book.overjam, book.vs_open, book.vs_jam):
                assert set(freq) <= {0.0, 1.0}, book
    after = [[play_block(h, v, prizes, 6000 + i) for i in range(40)] for h, v in pairs]
    monkeypatch.setattr(spin_arena, "speaking_order", _kolejnosc_sprzed_poker_54)
    before = [[play_block(h, v, prizes, 6000 + i) for i in range(40)] for h, v in pairs]
    assert after == before


def _arena_deck(dealt: DealtHand, seat_of_hu: dict[int, int]) -> tuple[Card, ...]:
    """Talia areny niosąca DOKŁADNIE karty rozdania silnika.

    Silnik rozdaje na przemian (`deal_hand`), arena blokami po dwie karty
    kolejnym żywym miejscom — kotwica porównuje rozliczenia, nie sposób
    rozdawania, więc talia jest tu przekładem, a nie założeniem.
    """
    hole = {event.seat: event.cards for event in dealt.hole_cards}
    board = (*dealt.flop.cards, dealt.turn.card, dealt.river.card)
    ordered = sorted(seat_of_hu.items(), key=lambda pair: pair[1])
    cards = [card for hu_seat, _ in ordered for card in hole[hu_seat]]
    cards.extend(board)
    used = set(cards)
    cards.extend(card for card in shuffled_deck(random.Random(0)) if card not in used)
    return tuple(cards)


# Linia licytacji w zamrożonym drzewie: (akcje guzika, akcje BB) oraz przekład
# na akcje silnika zdarzeniowego. `open` to podbicie do `open_amount(bb)`,
# `jam` to wejście za cały stack, `call` sprawdzenie all-inu.
ANCHOR_LINES = (
    (("fold",), ()),
    (("jam",), ("fold",)),
    (("jam",), ("jam",)),
    (("open",), ("fold",)),
    (("open", "fold"), ("jam",)),
    (("open", "jam"), ("jam",)),
)


def _drive_engine(
    hand: HeadsUpHand,
    button: int,
    line: tuple[tuple[str, ...], tuple[str, ...]],
    bb: int,
    stacks: tuple[int, int],
) -> None:
    """Ta sama linia w silniku zdarzeniowym: fold / podbicie do 2.2x / all-in / call."""
    queues = {button: list(line[0]), 1 - button: list(line[1])}
    while (legal := hand.legal_actions()) is not None:
        seat = legal.seat
        action = queues[seat].pop(0)
        state = hand.state()
        if action == "fold":
            hand.act(seat, ActionType.FOLD)
        elif action == "open":
            target = open_amount(bb)
            hand.act(seat, ActionType.RAISE, target - (stacks[seat] - state.stacks[seat]))
        elif legal.raise_range is not None:
            hand.act(seat, ActionType.RAISE, legal.raise_range.maximum)
        else:
            hand.act(seat, ActionType.CALL)


def test_kotwica_krzyzowa_rozgrywacz_areny_zgadza_sie_z_silnikiem() -> None:
    """Decyzja 27 pkt 4: rozliczenie ręki HU takie samo w arenie i w `HeadsUpHand`.

    Dług wymagalny z POKER-48: pierwszy kontrakt dotykający rozgrywacza spłaca
    kotwicę. Porównywane są wszystkie linie zamrożonego drzewa (fold, open 2.2x,
    3bet-jam, call) przy IDENTYCZNYCH kartach i identycznych decyzjach — łącznie
    z showdownem, bo talia areny jest przekładem rozdania silnika.
    """
    for seed in range(25):
        dealt = deal_hand(shuffled_deck(random.Random(seed)), seat_count=2)
        for sb, bb in ((1, 2), (5, 10)):
            for stacks in ((50, 50), (40, 60), (30, 21)):
                for button in range(3):
                    busted = (button + 2) % 3
                    other = next(s for s in range(3) if s not in (button, busted))
                    # Przy ≤7 bb efektywnych drzewo areny nie ma open (jam/fold),
                    # więc linie z podbiciem 2.2x wchodzą tylko na głębokich stackach.
                    jamfold = is_jam_fold_depth((stacks[0], stacks[1], 0), bb)
                    for line in (ANCHOR_LINES[:3] if jamfold else ANCHOR_LINES):
                        arena = [0, 0, 0]
                        arena[button], arena[other] = stacks
                        hu_button = 0
                        seat_of_hu = {hu_button: button, 1 - hu_button: other}
                        config = HandConfig(
                            small_blind=sb, big_blind=bb, stacks=stacks, button=hu_button
                        )
                        engine = HeadsUpHand(config, seed)
                        _drive_engine(engine, hu_button, line, bb, stacks)
                        books: list[Seat] = [always_fold(), always_fold(), always_fold()]
                        books[button] = _Script(*line[0])
                        books[other] = _Script(*line[1])
                        out = _play_hand(
                            list(arena),
                            0,
                            button,
                            sb,
                            bb,
                            (books[0], books[1], books[2]),
                            _arena_deck(dealt, seat_of_hu),
                            random.Random(seed),
                        )
                        expected = engine.state().stacks
                        assert out[busted] == 0
                        assert (out[button], out[other]) == expected, (
                            seed, sb, bb, stacks, button, line, out, expected,
                        )


def test_legal_actions_to_dokladnie_zbior_wyjsc_pick() -> None:
    """Legalność ma jedno źródło prawdy: co potrafi `pick`, to zwraca `legal_actions`.

    Gdyby zbiory się rozjechały, port albo odrzucałby akcję, którą książka gra
    bez przeszkód, albo przepuszczał akcję spoza zamrożonego drzewa.
    """
    books = (always_jam(), always_fold(), field_exploit(), dollar_fish(), wide_call(0.5))
    for jamfold in (False, True):
        for opened in (False, True):
            for jammed in (False, True):
                view = SeatView(
                    hand=0,
                    seat=0,
                    button=1,
                    stacks=(50, 50, 50),
                    contrib=(0, 1, 2),
                    actions=(),
                    bb=2,
                    klass=0,
                    jamfold=jamfold,
                    opened=opened,
                    jammed=jammed,
                )
                legal = set(legal_actions(view))
                seen = set()
                for book in books:
                    for klass in range(0, 169, 7):
                        for seed in range(5):
                            seen.add(
                                pick(
                                    book,
                                    klass,
                                    jamfold=jamfold,
                                    opened=opened,
                                    jammed=jammed,
                                    rng=random.Random(seed),
                                )
                            )
                assert seen == legal, (jamfold, opened, jammed, seen, legal)

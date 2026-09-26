"""ROI arena: blok rotacji, wspólne seedy, bootstrap; determinizm INV-P1; ręka HU."""

from __future__ import annotations

import itertools
import os
import random
import subprocess
import sys
from collections.abc import Sequence

import pytest

from poker import spin_arena
from poker.betting import HeadsUpHand
from poker.cards import FULL_DECK, Card, Rank, Suit
from poker.dealing import DealtHand, deal_hand, shuffled_deck
from poker.evaluation import evaluate_best
from poker.events import ActionType, HandConfig
from poker.openfold import _mass, threebet_vs_range
from poker.spin import (
    HANDS_PER_LEVEL,
    LEVELS,
    PAYOUTS,
    STARTING_CHIPS,
    is_jam_fold_depth,
    open_amount,
    roles,
)
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
    stacks, reason, _ = run_spin(books, 11)
    assert reason == "bust"
    assert sum(stacks) == 3 * STARTING_CHIPS
    assert sorted(stacks) == [0, 0, 3 * STARTING_CHIPS]
    money = play_spin(books, PAYOUTS["3x"].prizes, 11)
    assert money[stacks.index(3 * STARTING_CHIPS)] == 3.0


@pytest.mark.parametrize(
    ("seed", "busts", "money"),
    [
        # Miejsce 0 odpada w ręce 0, miejsce 1 dopiero w ręce 2: później wybity wyżej.
        (5, ((0, 50), (2, 47), None), (0.0, 2.0, 8.0)),
        # Oba odpadają w ręce 5; wyżej większy stack wejściowy (44 > 8), nie niższy indeks.
        (90, ((5, 8), (5, 44), None), (0.0, 2.0, 8.0)),
        # Oba odpadają w ręce 0 przy 50/50: nagrody 2. i 3. miejsca dzielone po równo.
        (26, ((0, 50), (0, 50), None), (1.0, 1.0, 8.0)),
    ],
)
def test_nagrody_10x_ida_za_kolejnoscia_wybicia(
    seed: int,
    busts: tuple[tuple[int, int] | None, ...],
    money: tuple[float, float, float],
) -> None:
    """Reguła turniejowa miejsc, end-to-end przez `play_spin` (finding B2 audytu 09-26)."""
    books = (field_exploit(), dollar_fish(), dollar_fish())
    assert play_spin(books, PAYOUTS["10x"].prizes, seed) == money
    assert run_spin(books, seed)[1:] == ("bust", busts)


def test_limit_rak_szereguje_zywych_stackiem_koncowym() -> None:
    """Koniec przez HAND_GUARD: żywi według stacków końcowych, jak przed regułą wybicia."""
    books = (always_fold(), always_fold(), always_fold())
    assert play_spin(books, PAYOUTS["10x"].prizes, 0) == (8.0, 0.0, 2.0)
    assert run_spin(books, 0) == ((60, 40, 50), "guard", (None, None, None))


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


def _stacked_deck(*top: tuple[int, str]) -> tuple[Card, ...]:
    """Talia z zadanymi kartami na wierzchu; arena rozdaje po dwie żywym miejscom, potem board."""
    head = [Card(Rank(rank), Suit(suit)) for rank, suit in top]
    rest = sorted(FULL_DECK - set(head), key=lambda card: (card.rank, card.suit.value))
    return (*head, *rest)


BOARD_3D_8H_9S_JC_4D = ((3, "d"), (8, "h"), (9, "s"), (11, "c"), (4, "d"))


def test_side_pot_wygrywa_najlepsza_reka_sposrod_uprawnionych() -> None:
    """Finding B3 audytu 09-26: pulę główną bierze najkrótszy, side pot — drugi w porządku rąk.

    AA (10 żetonów) / KK (30) / 72o (50), wszyscy all-in: pula główna 30 dla
    AA, side pot 40 między KK i 72o należy się KK, nadpłata 20 wraca do 72o.
    Rangi spłaszczone do {najlepszy, reszta} dzieliły side pot po równo między
    przegranych puli głównej: (30, 20, 40).
    """
    deck = _stacked_deck(
        (14, "h"), (14, "d"), (13, "h"), (13, "d"), (7, "c"), (2, "s"), *BOARD_3D_8H_9S_JC_4D
    )
    books = (always_jam(), always_jam(), always_jam())
    assert _play_hand([10, 30, 50], 0, 1, 1, 2, books, deck, random.Random(0)) == [30, 40, 20]


def test_remis_przegranych_puli_glownej_dzieli_side_pot_po_rowno() -> None:
    """Ta sama ręka co wyżej, ale KQ na miejscach 1 i 2: remis to ta sama ranga.

    Strażnik przed rozstrzyganiem remisu indeksem miejsca (np. rangą z pozycji
    na liście posortowanej): side pot 40 dzielony 20/20, nie cały dla miejsca 1.
    """
    deck = _stacked_deck(
        (14, "h"), (14, "d"), (13, "h"), (12, "c"), (13, "s"), (12, "d"), *BOARD_3D_8H_9S_JC_4D
    )
    books = (always_jam(), always_jam(), always_jam())
    assert _play_hand([10, 30, 50], 0, 1, 1, 2, books, deck, random.Random(0)) == [30, 20, 40]


def _replayed_bets(
    stacks: Sequence[int],
    button: int,
    sb: int,
    bb: int,
    events: Sequence[tuple[SeatView, str, bool]],
) -> tuple[list[int], list[bool]]:
    """Wkłady i foldy ręki trzech żywych miejsc odtworzone z blindów i logu `on_action`.

    Każdy widok w logu jest stanem SPRZED akcji, więc zgodność odtworzonych
    wkładów z widokiem sprawdza odtworzenie na każdym kroku poza ostatnim.
    Wejście za darmo (akcja bez pytania) nie dokłada żetonów.
    """
    _, button_seat, bb_seat = roles(button)
    contrib = [0, 0, 0]
    contrib[button_seat] = min(stacks[button_seat], sb)
    contrib[bb_seat] = min(stacks[bb_seat], bb)
    folded = [False, False, False]
    for view, act, asked in events:
        assert view.contrib == tuple(contrib), (view, contrib)
        if not asked:
            continue
        if act == "fold":
            folded[view.seat] = True
        elif act == "open":
            contrib[view.seat] = max(
                contrib[view.seat], min(stacks[view.seat], open_amount(bb))
            )
        else:
            contrib[view.seat] = stacks[view.seat]
    return contrib, folded


def _reference_settlement(
    stacks: Sequence[int],
    contrib: Sequence[int],
    folded: Sequence[bool],
    deck: Sequence[Card],
) -> tuple[list[int], int]:
    """Stacki po ręce z definicji puli (reguła NLHE) i liczba pul rozgrywanych przez ≥ 2.

    Warstwa jednego żetonu: płacą ją miejsca o wkładzie ≥ warstwa, gra o nią
    każdy płacący, który nie spasował. Warstwy o tym samym zbiorze płacących
    tworzą jedną pulę; pulę bierze najlepsza ręka uprawnionych wg
    `evaluate_best`, remis dzieli po równo, a niepodzielna reszta idzie do
    zwycięzcy o najniższym indeksie miejsca (reguła `award_allin`). Karty jak
    w arenie: po dwie każdemu miejscu z żetonami w kolejności miejsc, potem
    pięć kart boardu.
    """
    holes: dict[int, tuple[Card, Card]] = {}
    for seat in range(3):
        if stacks[seat] > 0:
            holes[seat] = (deck[2 * len(holes)], deck[2 * len(holes) + 1])
    board = tuple(deck[2 * len(holes) : 2 * len(holes) + 5])
    pots: list[tuple[frozenset[int], int]] = []
    for layer in range(1, max(contrib) + 1):
        payers = frozenset(seat for seat in range(3) if contrib[seat] >= layer)
        if pots and pots[-1][0] == payers:
            pots[-1] = (payers, pots[-1][1] + len(payers))
        else:
            pots.append((payers, len(payers)))
    won = [0, 0, 0]
    contested = 0
    for payers, size in pots:
        eligible = sorted(seat for seat in payers if not folded[seat])
        assert eligible, (contrib, folded)
        contested += len(eligible) >= 2
        value = {seat: evaluate_best((*holes[seat], *board)) for seat in eligible}
        best = max(value.values())
        winners = [seat for seat in eligible if value[seat] == best]
        share, rest = divmod(size, len(winners))
        for seat in winners:
            won[seat] += share
        won[winners[0]] += rest
    return [stacks[seat] - contrib[seat] + won[seat] for seat in range(3)], contested


def test_rozliczenie_reki_areny_zgadza_sie_z_definicja_puli() -> None:
    """Właściwość rozliczenia (finding B3): wynik `_play_hand` == rozliczenie z definicji.

    1000 rąk trzech always-jam (showdowny 3-way z side potami) i 1000 rąk
    z książkami, które foldują (field_exploit, dollar_fish, wide_call w losowym
    układzie miejsc); stacki 1…100 — także krótsze od blinda — losowy guzik
    i poziom zegara. Porównanie dokładne na int, wszystkie rozbieżności naraz.
    """
    sampler = random.Random(71)
    jam: tuple[Seat, Seat, Seat] = (always_jam(), always_jam(), always_jam())
    folding: list[Seat] = [field_exploit(), dollar_fish(), wide_call()]
    mismatches: list[object] = []
    side_pots = folded_in_pot = short_of_blind = 0
    for hand_i in range(2000):
        if hand_i < 1000:
            books = jam
        else:
            sampler.shuffle(folding)
            books = (folding[0], folding[1], folding[2])
        stacks = [sampler.randint(1, 100) for _ in range(3)]
        button = sampler.randrange(3)
        level = sampler.randrange(len(LEVELS))
        sb, bb = LEVELS[level]
        deck = shuffled_deck(random.Random(sampler.getrandbits(64)))
        log = _ActionLog()
        out = _play_hand(
            list(stacks),
            level * HANDS_PER_LEVEL,
            button,
            sb,
            bb,
            books,
            deck,
            random.Random(sampler.getrandbits(64)),
            on_action=log,
        )
        contrib, folded = _replayed_bets(stacks, button, sb, bb, log.events)
        expected, contested = _reference_settlement(stacks, contrib, folded, deck)
        if out != expected:
            mismatches.append((hand_i, stacks, button, (sb, bb), contrib, folded, out, expected))
        side_pots += contested >= 2
        folded_in_pot += any(folded[seat] and contrib[seat] > 0 for seat in range(3))
        short_of_blind += min(stacks) < bb
    # Próbka ma zawierać to, czego dotyczy finding: rozgrywane side poty,
    # martwe wkłady spasowanych i stacki krótsze od blinda.
    assert min(side_pots, folded_in_pot, short_of_blind) >= 50, (
        side_pots, folded_in_pot, short_of_blind,
    )
    assert not mismatches, (len(mismatches), mismatches[:3])


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


class _ActionLog:
    """Obserwator licytacji: (widok w chwili akcji, akcja, czy pytana)."""

    def __init__(self) -> None:
        self.events: list[tuple[SeatView, str, bool]] = []

    def __call__(self, view: SeatView, act: str, asked: bool) -> None:
        self.events.append((view, act, asked))

    def free_entries(self) -> list[SeatView]:
        """Widoki wejść, o które rozgrywacz nie pytał."""
        return [view for view, _, asked in self.events if not asked]


def test_darmowe_wejscie_obejmuje_najwyzszy_wklad_bez_przebicia() -> None:
    """F1 audytu POKER-54: dołożenie zerowe bywa też wtedy, gdy nikt nie przebił.

    Najwyższym wkładem bywa cudzy BLIND — gracz all-in z samego blindu nie ma
    czym zagrać, a ten, kto go pokrywa, nie ma czego oszczędzić foldem. Obie
    żywe sekwencje: w HU guzik all-in z SB (1 żeton przy sb = 2), w 3-max BB
    all-in z blindu (1 żeton przy bb = 4) po foldzie UTG. Wynik rozstrzyga
    o naprawie, nie tylko log: przy foldzie za darmo byłoby odpowiednio
    `[2, 0, 49]` i `[50, 49, 2]`.
    """
    deck = shuffled_deck(random.Random(0))
    log: list[int] = []
    hu: tuple[Seat, Seat, Seat] = (
        _Script("fold", log=log),
        always_fold(),
        _Script("fold", log=log),
    )
    assert _play_hand([1, 0, 50], 0, 0, 2, 4, hu, deck, random.Random(0)) == [0, 0, 51]
    assert log == []

    three: tuple[Seat, Seat, Seat] = (
        _Script("fold", log=log),
        _Script("fold", log=log),
        _Script("fold", log=log),
    )
    assert _play_hand([50, 50, 1], 0, 1, 2, 4, three, deck, random.Random(0)) == [50, 51, 0]
    assert log == [0]


def test_obserwator_licytacji_widzi_wejscie_bez_pytania() -> None:
    """`on_action` pokazuje, czego nie widać z widoków: wejście za darmo.

    Jest ono zawsze ostatnią akcją ręki, więc nie trafia do historii żadnej
    następnej decyzji (F4 audytu POKER-54) — obserwator jest jedynym miejscem,
    w którym widać jego trzy cechy: wpis w licytacji, brak pytania i brak
    poboru z rng. Obserwacja jest czysta: przebieg ręki z nią i bez niej jest
    identyczny.
    """
    seen = _ActionLog()
    books: tuple[Seat, Seat, Seat] = (always_fold(), always_fold(), always_fold())
    plain = _play_hand(
        [1, 0, 50], 0, 0, 2, 4, books, shuffled_deck(random.Random(0)), random.Random(0)
    )
    watched = _play_hand(
        [1, 0, 50],
        0,
        0,
        2,
        4,
        books,
        shuffled_deck(random.Random(0)),
        random.Random(0),
        on_action=seen,
    )
    assert plain == watched
    assert [(view.seat, act, asked) for view, act, asked in seen.events] == [(2, "jam", False)]
    entry = seen.events[0][0]
    assert (entry.contrib, entry.actions) == ((1, 0, 4), ())  # widok SPRZED wejścia
    assert max(entry.contrib) == entry.contrib[entry.seat]  # dołożenie zerowe


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


class _CountingRandom(random.Random):
    """RNG liczący pobory — wejście za darmo nie jest decyzją, więc nie pobiera."""

    draws = 0

    def random(self) -> float:
        self.draws += 1
        return super().random()


def test_wejscie_za_darmo_nie_pobiera_z_rng_i_jest_ostatnia_akcja_reki() -> None:
    """Dwie cechy wejścia za darmo, które DA się zaobserwować (F4 audytu POKER-54).

    Pobór z rng: rozgrywacz bierze jeden na DECYZJĘ, a wejścia za darmo nikt
    nie podejmuje — liczba poborów musi się równać liczbie pytań. Kolejność:
    po wejściu za darmo nie ma już czym zagrać, bo każdy, kto po nim mógłby
    mówić, wpłacił mniej niż wchodzący, a wpłacił mniej tylko wtedy, gdy jest
    all-in albo już grał. Ta druga cecha jest powodem, dla którego wpisu
    wejścia w `SeatView.actions` ani przesunięcia głosu po nim NIE widać
    z żadnego kolejnego widoku — i dlatego twierdzeń o nich nie ma
    w opisach: obserwowalny jest sam fakt akcji (log `on_action`).
    """
    sb, bb = 2, 4
    books: tuple[Seat, Seat, Seat] = (always_fold(), always_jam(), field_exploit())
    deck = shuffled_deck(random.Random(0))
    free_entries = 0
    for stacks in itertools.product(range(9), repeat=3):
        if sum(1 for chips in stacks if chips > 0) < 2:
            continue
        for button in range(3):
            if stacks[button] <= 0:
                continue
            seen = _ActionLog()
            rng = _CountingRandom(0)
            rng.draws = 0
            _play_hand(list(stacks), 0, button, sb, bb, books, deck, rng, on_action=seen)
            asked = [event for event in seen.events if event[2]]
            assert rng.draws == len(asked), (stacks, button, seen.events, rng.draws)
            for index, (_, _, was_asked) in enumerate(seen.events):
                if was_asked:
                    continue
                free_entries += 1
                assert index == len(seen.events) - 1, (stacks, button, seen.events)
    assert free_entries > 0, "siatka bez wejść za darmo nie sprawdza niczego"


def _posted_blinds(
    stacks: tuple[int, ...], button: int, sb: int, bb: int
) -> tuple[int, int, int]:
    """Blind postawiony przez każde miejsce w tej ręce (0 dla UTG i wybitych)."""
    live = [seat for seat in range(3) if stacks[seat] > 0]
    bb_seat = (
        next(seat for seat in live if seat != button)
        if len(live) <= 2
        else roles(button)[2]
    )
    posted = [0, 0, 0]
    posted[button] = sb
    posted[bb_seat] = bb
    return (posted[0], posted[1], posted[2])


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

    Asercja jest BEZWARUNKOWA — tak jak reguła: nie ma znaczenia, czy stoi
    przebicie, czy najwyższym wkładem jest cudzy blind (F1/F5 audytu
    POKER-54). Druga asercja pilnuje, żeby pierwsza nie była o pustce: w tej
    samej próbce sytuacja „ktoś ma dołożenie zerowe" naprawdę występuje
    (widzi ją miejsce pytane wcześniej w tej samej rundzie).
    """
    books = (field_exploit(), dollar_fish(), always_jam())
    views = _asked_views(range(60), books)
    assert len(views) > 500
    pending = 0
    for view in views:
        assert view.contrib[view.seat] < max(view.contrib), view
        pending += len(_zero_due_pending(view))
    assert pending > 0, "próbka bez dołożeń zerowych nie sprawdza niczego"


def test_zero_due_bez_przebicia_to_wylacznie_all_in_z_blindu() -> None:
    """Dlaczego reguła wejścia za darmo nie potrzebuje warunku „stoi przebicie".

    W zamrożonym drzewie nie ma limpa: każda akcja poza foldem podbija ponad
    blindy (open to 2,2 bb, a jam cały stack), więc przed pierwszym podbiciem
    wkłady w puli to DOKŁADNIE postawione blindy. Zerowe dołożenie znaczy
    wtedy, że czyjś blind nie przewyższa naszego, a to możliwe wyłącznie, gdy
    ten ktoś jest all-in z samego blindu. Test przybija oba ogniwa na
    wejściach z prawdziwych turniejów.
    """
    sb, bb = 2, 4
    books: tuple[Seat, Seat, Seat] = (always_fold(), always_fold(), always_fold())
    deck = shuffled_deck(random.Random(0))
    free_entries = 0
    for stacks in itertools.product(range(7), repeat=3):
        if sum(1 for chips in stacks if chips > 0) < 2:
            continue
        for button in range(3):
            if stacks[button] <= 0:
                continue
            seen = _ActionLog()
            _play_hand(
                list(stacks), 0, button, sb, bb, books, deck, random.Random(0), on_action=seen
            )
            posted = _posted_blinds(stacks, button, sb, bb)
            for entry in seen.free_entries():
                # Książka folduje wszystko, więc w tej próbce nikt nie podbija.
                free_entries += 1
                assert not (entry.jammed or entry.opened), entry
                assert any(
                    other != entry.seat and 0 < stacks[other] <= posted[other]
                    for other in range(3)
                ), (stacks, button, entry.seat)
    assert free_entries > 0, "siatka bez wejść za darmo nie sprawdza niczego"


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

    changed = sum(1 for a, b in zip(after, before, strict=True) if a != b)
    assert changed == 57, changed  # raport POKER-71 (blok POKER-54 CURRENT_STATE: 55)
    diffs = [a - b for a, b in zip(after, before, strict=True)]
    mean = sum(diffs) / n
    sd = (sum((d - mean) ** 2 for d in diffs) / (n - 1)) ** 0.5
    se = sd / n**0.5
    assert mean - 1.96 * se <= 0.0 <= mean + 1.96 * se, (mean, se)
    assert mean == pytest.approx(0.0167, abs=5e-4), mean
    assert (mean - 1.96 * se, mean + 1.96 * se) == pytest.approx((-0.0352, 0.0686), abs=5e-4)
    sd_after = (sum((x - sum(after) / n) ** 2 for x in after) / (n - 1)) ** 0.5
    sd_before = (sum((x - sum(before) / n) ** 2 for x in before) / (n - 1)) ** 0.5
    assert abs(sd_after - sd_before) < 0.02 * sd_before, (sd_after, sd_before)
    assert (sd_after, sd_before) == pytest.approx((0.6389, 0.6301), abs=5e-4)


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
            # Wszystkie SZEŚĆ wektorów, nie cztery: jam/fold ma własne dwa
            # i to one rządzą krótkim stołem (F7 audytu POKER-54).
            for freq in (
                book.open,
                book.overjam,
                book.vs_open,
                book.vs_jam,
                book.jf_first,
                book.jf_vs_jam,
            ):
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

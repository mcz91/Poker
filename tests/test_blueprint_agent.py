"""Agent blueprintu w arenie Spin (POKER-52): port, odwzorowania, fallback, kotwica.

Artefakt bramki powstaje tu i teraz: solver z `tools/blueprint` liczy bieg na
przestrzeni stanów areny (150 żetonów, start 50/50/50, pełny zegar blindów
`poker.spin.LEVELS`) przy zgrubnej siatce 50 żetonów i czterech klasach
tensora kontrolnego z repo, a konwerter pakuje go do `.bpk`. Bramka nie
dotyka artefaktu produkcyjnego spoza repozytorium; ceną jest zestaw klas —
mini-artefakt zna cztery ze 169, więc ręka spoza nich jest u agenta osobnym,
policzalnym przypadkiem (`class_misses`), a nie cichym rozkładem.
"""

import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from poker import blueprint_agent, spin_arena
from poker.blueprint_agent import (
    CYCLE_BASE,
    CYCLE_LENGTH,
    H_B_VS_JAM,
    H_B_VS_OPEN,
    H_ROOT,
    N_B_VS_T_JAM,
    N_B_VS_T_OPEN,
    N_B_VS_U_JAM_T_CALL,
    N_B_VS_U_JAM_T_FOLD,
    N_B_VS_U_OPEN,
    N_B_VS_U_OPEN_T_JAM,
    N_T_FI,
    N_T_VS_U_JAM,
    N_T_VS_U_OPEN,
    N_U_ROOT,
    NODES_3MAX,
    NODES_3MAX_OUT_OF_ORDER,
    NODES_HU,
    ORDER_COLLAPSE,
    ORDER_SWAP,
    ROOTS_3MAX,
    ROOTS_HU,
    SLOT_FOLD,
    SLOT_JAM,
    SLOT_MID,
    BlueprintAgent,
    cyclic_hand,
    jam_fold_slot,
    label_seats,
    node_slot,
    quantize_stacks,
    role_seats,
    sample,
    stale_history,
    state_keys,
)
from poker.blueprint_reader import (
    BlueprintLookupError,
    BlueprintReader,
    FingerprintMismatch,
    StateBlock,
    check_fingerprint,
)
from poker.dealing import shuffled_deck
from poker.spin import (
    LEVELS,
    PAYOUTS,
    SOLVER_MODES,
    STARTING_CHIPS,
    TIERS,
    blinds_for_hand,
    is_jam_fold_depth,
    roles,
)
from poker.spin_arena import (
    HAND_GUARD,
    SeatBook,
    SeatView,
    _play_hand,
    always_jam,
    dollar_fish,
    field_exploit,
    legal_actions,
    pick,
    play_block,
    run_spin,
    wide_call,
)

REPO = Path(__file__).resolve().parent.parent
BLUEPRINT = REPO / "tools" / "blueprint"


def _load(name: str) -> Any:
    """Moduł z tools/blueprint pod nazwą stem — jak testy reprodukcji treningu."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _mini_config() -> Any:
    """Konfiguracja biegu na przestrzeni stanów areny, siatka 50 żetonów."""
    sg, cc = _load("solve_grid"), _load("control_chain")
    return sg.GridConfig(
        levels=LEVELS,
        hands_per_level=3,
        total_chips=150,
        start_stacks=(50, 50, 50),
        grid_step=50,
        classes=cc.control_classes(),
        fp_max_iters=24,
        fp_check_every=8,
        fp_tol=1e-4,
        fp_restarts=2,
        cfr_iters=64,
        cfr_check_every=16,
        cfr_tol=1e-4,
        tail_max_cycles=1,
        tail_tol=2e-3,
    )


@pytest.fixture(scope="module")
def mini_artifact(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Artefakt `.bpk` na przestrzeni stanów areny — solver plus konwerter."""
    sg, pk = _load("solve_grid"), _load("pack_blueprint")
    out_dir = tmp_path_factory.mktemp("blueprint-agent") / "solve"
    sg.solve(_mini_config(), BLUEPRINT / "control" / "tensor", out_dir)
    packed = out_dir.parent / "mini.bpk"
    pk.pack(out_dir, packed)
    return packed


def _agent(path: Path) -> BlueprintAgent:
    stream = path.open("rb")
    reader = BlueprintReader(stream)
    config = json.loads(reader.meta_bytes())["run_manifest"]["config"]
    return BlueprintAgent(reader, grid_step=config["grid_step"], classes=config["classes"])


def _view(**changed: Any) -> SeatView:
    base: dict[str, Any] = {
        "hand": 0,
        "seat": 0,
        "button": 1,
        "stacks": (50, 50, 50),
        "contrib": (0, 1, 2),
        "actions": (),
        "bb": 2,
        "klass": 0,
        "jamfold": False,
        "opened": False,
        "jammed": False,
    }
    base.update(changed)
    return SeatView(**base)


class Spy:
    """Miejsce grające dokładnie jak `SeatBook`, ale zapisujące widoki.

    Jeden pobór z rng na decyzję — ten sam co `pick` — więc podmiana książki na
    szpiega nie może przesunąć ani decyzji, ani kart.
    """

    def __init__(self, book: SeatBook) -> None:
        self.book = book
        self.views: list[SeatView] = []
        self.actions: list[str] = []

    def act(self, view: SeatView, rng: Any) -> str:
        self.views.append(view)
        action = pick(
            self.book,
            view.klass,
            jamfold=view.jamfold,
            opened=view.opened,
            jammed=view.jammed,
            rng=rng,
        )
        self.actions.append(action)
        return action


class Script:
    """Miejsce grające zadaną listę akcji — do kotwicy krzyżowej z silnikiem."""

    def __init__(self, actions: tuple[str, ...]) -> None:
        self.actions = list(actions)

    def act(self, view: SeatView, rng: Any) -> str:
        rng.random()
        return self.actions.pop(0)


def _run_seen(books: tuple[Any, Any, Any], seed: int) -> tuple[Any, list[Any]]:
    """Turniej i sekwencja talii jego rąk — obserwacja bez wpływu na przebieg."""
    seen: list[Any] = []
    result = run_spin(books, seed, on_deck=lambda index, deck: seen.append(deck))
    return result, seen


def _spy_views(seeds: range, villains: tuple[SeatBook, SeatBook]) -> list[SeatView]:
    """Widoki wszystkich decyzji jednego miejsca na wielu turniejach."""
    out: list[SeatView] = []
    for seed in seeds:
        for seat in range(3):
            spy = Spy(field_exploit())
            books: list[Any] = [villains[0], villains[1], villains[0]]
            books[seat] = spy
            run_spin((books[0], books[1], books[2]), seed)
            out.extend(spy.views)
    return out


def test_port_agenta_nie_zmienia_przebiegu_reki() -> None:
    """Szpieg grający tą samą książką daje ten sam turniej co sama książka.

    To jest granica portu: nowe źródło decyzji, nie nowy przebieg ręki
    (decyzja 27). Test łapie każdą zmianę kolejności poborów z rng i kart.

    Książka MIESZANA jest tu konieczna, nie ozdobna: przy częstotliwościach 0/1
    wartość poboru nie zmienia decyzji, więc dodatkowy pobór przechodzi
    niezauważony (PUŁAPKA z audytu POKER-52 — na `wide_call(0.45)` ta sama
    mutacja zmienia 8 z 30 turniejów).
    """
    for book in (field_exploit(), wide_call(0.45)):
        for villain in (dollar_fish(), wide_call(0.45)):
            for seed in range(30):
                spy = Spy(book)
                plain, plain_decks = _run_seen((book, villain, villain), seed)
                ported, ported_decks = _run_seen((spy, villain, villain), seed)
                assert plain == ported, (seed, book is villain)
                assert plain_decks == ported_decks, seed


def test_kwantyzacja_stackow_jest_kopia_reguly_treningu() -> None:
    """Kopia `solve_grid.quantize_stacks` w pakiecie zgadza się z oryginałem.

    Silnik nie importuje `tools`, więc reguła siatki żyje w dwóch miejscach —
    a że rozjazd o jeden żeton przenosi agenta do innego stanu artefaktu,
    zgodność ma test, nie komentarz.
    """
    sg = _load("solve_grid")
    import random

    rng = random.Random(52)
    cases = [(50, 50, 50), (0, 75, 75), (1, 1, 148), (149, 1, 0), (2, 73, 75)]
    for _ in range(300):
        first = rng.randrange(0, 151)
        second = rng.randrange(0, 151 - first)
        cases.append((first, second, 150 - first - second))
    for step in (2, 5, 50):
        for stacks in cases:
            assert quantize_stacks(stacks, step) == sg.quantize_stacks(stacks, step), (
                stacks,
                step,
            )


def test_kwantyzacja_zachowuje_sume_i_zywych() -> None:
    """Własności, na których stoi odwzorowanie: suma stała i żywy zostaje żywy."""
    import random

    rng = random.Random(7)
    for _ in range(500):
        first = rng.randrange(0, 151)
        second = rng.randrange(0, 151 - first)
        stacks = (first, second, 150 - first - second)
        out = quantize_stacks(stacks, 2)
        assert sum(out) == 150
        assert all(value % 2 == 0 for value in out)
        for seat in range(3):
            assert (out[seat] > 0) == (stacks[seat] > 0), (stacks, out)


def _training_role_labels(layer: int, live_labels: tuple[int, ...]) -> tuple[int, ...]:
    """Role treningu wyrażone etykietami miejsc: guzik z `warstwa % 3` albo `% 2`."""
    if len(live_labels) == 3:
        utg, button, big = roles(layer % 3)
        return (utg, button, big)
    ordered = sorted(live_labels)
    button = ordered[layer % 2]
    return (button, ordered[1 - layer % 2])


def test_przenumerowanie_sadza_role_treningu_na_rolach_areny() -> None:
    """Rola areny czyta rozkład swojej roli: to jest cały sens przenumerowania.

    Guzik treningu wynika z numeru ręki, guzik areny z rotacji po żywych, więc
    bez przenumerowania UTG areny czytałby strategię BB — i żaden licznik
    fallbacku by tego nie pokazał, bo stan i węzeł istnieją.
    """
    vectors = ((50, 50, 50), (20, 100, 30), (0, 90, 60), (75, 0, 75), (60, 90, 0))
    for hand in range(22):
        for button in range(3):
            for stacks in vectors:
                if stacks[button] == 0:
                    continue
                view = _view(hand=hand, button=button, stacks=stacks, seat=button)
                arena = role_seats(view)
                for seat_of_label in label_seats(view, hand):
                    live_labels = tuple(
                        label
                        for label in range(3)
                        if stacks[seat_of_label[label]] > 0
                    )
                    training = _training_role_labels(hand, live_labels)
                    assert len(training) == len(arena)
                    for role, label in enumerate(training):
                        assert seat_of_label[label] == arena[role], (
                            hand, button, stacks, seat_of_label,
                        )
                    assert len(set(seat_of_label)) == 3


def test_cykl_horyzontu_stoi_na_zegarze_blindow() -> None:
    """Warunek decyzji 28 pkt 3 jako niezmiennik: od `CYCLE_BASE` blindy stoją.

    Odczyt cykliczny jest ścisły tylko dlatego, że ręce za horyzontem żyją
    w tym samym stacjonarnym cyklu co warstwy `CYCLE_BASE`…`+CYCLE_LENGTH−1`.
    Gdyby zegar dostał ósmy poziom albo inną długość poziomu, ta stałość
    znika — i wtedy ma czerwienieć test, a nie milczeć agent.
    """
    assert (CYCLE_BASE, CYCLE_LENGTH) == (18, 3)
    stale = blinds_for_hand(CYCLE_BASE)
    assert stale == (10, 20, len(LEVELS) - 1)
    assert blinds_for_hand(CYCLE_BASE - 1) != stale
    for hand in range(CYCLE_BASE, HAND_GUARD):
        assert blinds_for_hand(hand) == stale, hand
    # Ręka w zegarze warstw jest sobie równa; dalsza wraca w cykl 3 rąk.
    assert [cyclic_hand(hand) for hand in range(15, 28)] == [
        15, 16, 17, 18, 19, 20, 18, 19, 20, 18, 19, 20, 18,
    ]


def _cycle_value_spread(
    reader: BlueprintReader, step: int, layers: tuple[int, ...], misread: int = 0
) -> list[float]:
    """Rozstęp V po rolach między warstwami cyklu dla tej samej sytuacji fizycznej.

    Klucz każdej warstwy powstaje jej własną regułą ról, a odczytana wartość
    wraca na role tą samą regułą — chyba że `misread` przesuwa FAZĘ odczytu
    (mutacja: agent czyta wartość nie swojej roli).
    """
    total = sum(reader.state_key(layers[0], 0))
    out: list[float] = []
    for first in range(0, total + 1, step):
        for second in range(0, total - first + 1, step):
            situation = (first, second, total - first - second)
            live = tuple(value for value in situation if value > 0)
            if len(live) < 2:
                continue
            rows: list[tuple[float, ...] | None] = []
            for dead in ((None,) if len(live) == 3 else (0, 1, 2)):
                rows = []
                for index, layer in enumerate(layers):
                    labels = tuple(
                        label for label in range(3) if label != dead
                    ) if dead is not None else (0, 1, 2)
                    order = _training_role_labels(layer, labels)
                    read = _training_role_labels(
                        layer + (misread if index else 0), labels
                    )
                    key = [0, 0, 0]
                    for role, label in enumerate(order):
                        key[label] = live[role]
                    try:
                        row = reader.value(layer, (key[0], key[1], key[2]))
                    except BlueprintLookupError:
                        rows.append(None)
                        continue
                    rows.append(tuple(row[label] for label in read))
                if all(row is not None for row in rows):
                    break
            if any(row is None for row in rows):
                continue
            for role in range(len(live)):
                values = [row[role] for row in rows if row is not None]
                out.append(max(values) - min(values))
    return out


def test_warstwy_cyklu_opisuja_ten_sam_punkt_staly(mini_artifact: Path) -> None:
    """Artefaktowa strona odczytu cyklicznego: V warstw cyklu ma się zgadzać.

    Odczyt „ręka 21 → warstwa 18" jest wart tyle, ile zgodność warstw 18–20
    na tej samej sytuacji fizycznej (te same stacki tych samych ról). Na
    artefakcie bramki rozstęp nie przekracza 5e−5 udziału puli.

    Liczba, która niesie decyzję, jest jednak PRODUKCYJNA i nie mieści się
    w „rzędzie 1e−4" z pierwszej wersji decyzji 28 pkt 3 (KOREKTA F2 audytu
    POKER-55): na artefakcie produkcyjnym średnia 1,22e−3 i maks 1,67e−2
    (3-max; 6,58e−3 dla stacków ≥ 20 żetonów), HU maks 9,98e−4 — komenda
    pomiaru w bloku POKER-55 pkt 1. Tego artefaktu bramka nie dotyka.

    Mutacja fazy cyklu (odczyt wartości roli o jedną warstwę obok) czerwieni
    ten test na obu artefaktach: na bramkowym rozstęp rośnie z 2,0e−5 do
    0,20, na produkcyjnym z 1,67e−2 do 0,73.
    """
    stream = mini_artifact.open("rb")
    reader = BlueprintReader(stream)
    step = json.loads(reader.meta_bytes())["run_manifest"]["config"]["grid_step"]
    cycle = tuple(CYCLE_BASE + phase for phase in range(CYCLE_LENGTH))
    spread = _cycle_value_spread(reader, step, cycle)
    assert len(spread) == 15, spread
    assert max(spread) < 5e-5, max(spread)
    mutated = _cycle_value_spread(reader, step, cycle, misread=1)
    assert max(mutated) > 0.1, max(mutated)


def test_odczyt_cykliczny_sadza_role_warstwy_na_rolach_areny() -> None:
    """Kotwica przenumerowania przy odczycie cyklicznym (ręka 21 ↔ warstwa 18).

    Ról szuka się z numeru CZYTANEJ WARSTWY, a nie z numeru ręki areny: przy
    trzech żywych obie reguły dają to samo (cykl ma 3 ręce), ale w HU guzik
    treningu zmienia się co rękę i `21 % 2 ≠ 18 % 2` — pomyłka posadziłaby
    guzika areny na etykiecie dużego blinda, a żaden licznik by tego nie
    pokazał, bo stan i węzeł istnieją (to jest pułapka odwzorowania 2).
    """
    vectors = ((50, 50, 50), (20, 100, 30), (0, 90, 60), (75, 0, 75), (60, 90, 0))
    for hand in range(CYCLE_BASE + CYCLE_LENGTH, CYCLE_BASE + 4 * CYCLE_LENGTH):
        layer = cyclic_hand(hand)
        assert layer == CYCLE_BASE + (hand - CYCLE_BASE) % CYCLE_LENGTH
        for button in range(3):
            for stacks in vectors:
                if stacks[button] == 0:
                    continue
                view = _view(hand=hand, button=button, stacks=stacks, seat=button)
                arena = role_seats(view)
                for seat_of_label in label_seats(view, layer):
                    live_labels = tuple(
                        label for label in range(3) if stacks[seat_of_label[label]] > 0
                    )
                    training = _training_role_labels(layer, live_labels)
                    for role, label in enumerate(training):
                        assert seat_of_label[label] == arena[role], (hand, layer, stacks)
                # Trzy żywe: ręka i warstwa dają tę samą permutację (21 ≡ 18).
                if all(stacks):
                    assert label_seats(view, layer) == label_seats(view, hand)
    # HU: numer ręki NIE jest tu zamienny z numerem warstwy — parzystość różna.
    heads_up = _view(hand=21, button=2, stacks=(60, 0, 90), seat=2)
    assert label_seats(heads_up, 18) != label_seats(heads_up, 21)
    assert state_keys(heads_up, 18, 2)[0] != state_keys(heads_up, 21, 2)[0]


def test_klucz_stanu_to_przenumerowanie_i_kwantyzacja() -> None:
    """Klucz jest złożeniem dwóch reguł, obu osobno pod testem."""
    view = _view(hand=4, button=2, stacks=(47, 51, 52))
    keys = state_keys(view, view.hand, 2)
    assert len(keys) == 1
    seat_of_label = label_seats(view, view.hand)[0]
    assert keys[0] == quantize_stacks(
        (
            view.stacks[seat_of_label[0]],
            view.stacks[seat_of_label[1]],
            view.stacks[seat_of_label[2]],
        ),
        2,
    )


def test_hu_daje_trzy_rownowazne_klucze_o_tym_samym_ukladzie_sil() -> None:
    """W HU etykieta wybitego miejsca jest wolna — warianty opisują tę samą grę."""
    view = _view(hand=3, button=2, stacks=(60, 0, 90), seat=2)
    keys = state_keys(view, view.hand, 2)
    assert len(keys) == 3
    for key in keys:
        live_labels = tuple(label for label in range(3) if key[label] > 0)
        button_label, bb_label = _training_role_labels(view.hand, live_labels)
        assert key[button_label] == 90  # guzik areny to miejsce 2
        assert key[bb_label] == 60
    assert len(set(keys)) == 3


def _stage_problem(
    config: Any, stacks: tuple[int, int, int], hand: int, *, jam_fold: bool | None = None
) -> Any:
    """Gra etapowa treningu dla tego stanu i tej ręki (wypłaty liści nieużywane).

    `jam_fold=True` wymusza drzewo jam/fold niezależnie od głębokości — tak
    wygląda drzewo stanu, który kwantyzacja zepchnęła pod próg 7 bb.
    """
    sg = _load("solve_grid")
    import numpy as np

    tensors = _tensors(config)
    sb, bb_amt, _ = blinds_for_hand(hand)
    problem, _, _ = sg.build_stage_problem(
        tensors,
        config,
        stacks,
        hand,
        sb,
        bb_amt,
        lambda target: np.zeros(3),
        force_jamfold=jam_fold,
    )
    return problem


def _slot_of(action: str, root: bool) -> int:
    """Akcja areny → slot drzewa: w korzeniu open to slot środkowy, niżej — call."""
    if action == "fold":
        return SLOT_FOLD
    if action == "open":
        assert root, "open poza korzeniem nie istnieje w drzewie"
        return SLOT_MID
    return SLOT_JAM if root else SLOT_MID


def _tree_node(problem: Any, view: SeatView, order: tuple[int, ...]) -> tuple[int, int]:
    """Węzeł, do którego dochodzi DRZEWO TRENINGU po akcjach z historii areny.

    Zwraca (węzeł, miejsce na ruchu) — drzewo treningu samo mówi, KTO decyduje
    po tej historii; przy zgodnym modelu to nasze miejsce, przy rozjeździe
    kolejności areny — inne. Chodzenie po drzewie, nie sprawdzanie
    przynależności: tablica slotów przestawiona parami przechodzi test „węzeł
    istnieje w tej grze etapowej" bez mrugnięcia (PUŁAPKA POKER-46), a tu każdy
    krok musi zgadzać się z ról i akcji. Rola all-in z samego blinda ma
    w drzewie jedną dozwoloną akcję — walk ją konsumuje, bo rozgrywacz areny
    takiego miejsca nie pyta.
    """
    queues: dict[int, list[str]] = {role: [] for role in range(len(order))}
    for seat, action in view.actions:
        queues[order.index(seat)].append(action)
    tree = problem.tree
    roots = {0, 1} if len(order) == 3 else {0}
    while tree[0] == "node":
        node_id, actor, children = tree[1], tree[2], tree[3]
        queue = queues[actor]
        if not queue:
            allowed = problem.allowed[node_id]
            if order[actor] == view.seat or len(allowed) != 1:
                # Spacer musi ZUŻYĆ całą historię areny: akcja zapisana w ręce,
                # a nieskonsumowana przez ścieżkę drzewa, znaczy, że model tej
                # odpowiedzi nie widzi (dwa infosety areny kolapsują do jednego
                # węzła artefaktu) — to jest rozjazd, nie zgodność.
                assert not any(queues.values()), (
                    f"spacer stanął w węźle {node_id} z niezużytą historią "
                    f"{queues} — model nie widzi tej odpowiedzi"
                )
                return int(node_id), order[actor]
            slot = allowed[0]  # wejście wymuszone maską: arena tego miejsca nie pyta
        else:
            slot = _slot_of(queue.pop(0), node_id in roots)
        tree = next(child for child_slot, child in children if child_slot == slot)
    raise AssertionError(f"historia areny prowadzi do liścia, nie do decyzji: {view}")


_TENSORS: dict[int, Any] = {}


def _tensors(config: Any) -> Any:
    if not _TENSORS:
        sg = _load("solve_grid")
        _TENSORS[0] = sg.load_tensors(BLUEPRINT / "control" / "tensor", config.classes)
    return _TENSORS[0]


def test_slot_wezla_zgadza_sie_z_drzewem_gry_etapowej_treningu() -> None:
    """Kontekst licytacji areny trafia w węzeł treningu — po POKER-54 BEZ WYJĄTKÓW.

    Przed POKER-54 rozjazd miał trzy twarze (decyzja 28 pkt 2a z korektą i 2b):
    arena pytała UTG przed BB (`ORDER_SWAP`), pytała BB po odpowiedzi UTG na
    3bet (`ORDER_COLLAPSE` — dwa infosety areny na jeden węzeł modelu) i pytała
    o akcję, którą trening wymusza maską (call za darmo), więc wchodziła
    w gałąź, której w drzewie nie ma. Naprawiony rozgrywacz nie wytwarza
    żadnej z nich: spacer zużywający CAŁĄ historię ręki staje w tym samym
    węźle i na tym samym miejscu co odwzorowanie agenta, a węzeł jest
    osiągalny przy maskach tego stanu.

    Zero nie jest tu o pustce: próbka odwiedza wszystkie 14 węzłów modelu
    3-max i wszystkie 4 endgame'u HU — w tym węzeł 8 (BB wobec 3betu) oraz 9
    i 10 (odpowiedź UTG na 3bet), czyli dokładnie te, na których stara
    kolejność się rozjeżdżała.
    """
    config = _mini_config()
    views = _spy_views(range(40), (dollar_fish(), always_jam()))
    assert len(views) == 764  # liczba w bloku POKER-54 CURRENT_STATE
    seen_nodes: set[tuple[int, int]] = set()
    cache: dict[tuple[Any, int], Any] = {}
    for view in views:
        node, divergence = node_slot(view)
        assert divergence is None, (view, node)
        key = state_keys(view, view.hand, 1)[0]  # krok 1 = brak kwantyzacji: stacki areny
        cache_key = (key, view.hand)
        if cache_key not in cache:
            cache[cache_key] = _stage_problem(config, key, view.hand)
        problem = cache[cache_key]
        order = role_seats(view)
        seen_nodes.add((len(order), node))
        assert _tree_node(problem, view, order) == (node, view.seat), view
        assert node in problem.nodes, (view, node)
    assert {node for live, node in seen_nodes if live == 3} == set(range(14))
    assert {node for live, node in seen_nodes if live == 2} == set(range(4))


def test_wezel_blizniaczy_zgadza_sie_z_drzewem_jamfold_treningu() -> None:
    """Przeskok trybu: bliźniak czytany w artefakcie to węzeł drzewa JAM/FOLD.

    Reguła przekładu (otwarcie w historii czytane jako jam) jest sprawdzana
    CHODZENIEM po drzewie jam/fold gry etapowej treningu, nie przynależnością
    do tablicy: przestawiona parami tablica przechodzi test „węzeł istnieje",
    a nie przechodzi spaceru (PUŁAPKA POKER-46).

    Bliźniaka nie ma dokładnie dla DRUGIEGO wejścia roli, która otworzyła —
    w drzewie jam/fold odpowiedź na jam jest terminalna. Agent w stanie
    jam/fold nigdy nie otwiera, więc do tych infosetów nie dochodzi, ale
    `None` zostaje jawne zamiast cichego złego węzła.
    """
    config = _mini_config()
    views = _spy_views(range(40), (dollar_fish(), always_jam()))
    cache: dict[tuple[Any, int], Any] = {}
    pairs: set[tuple[int, int, int]] = set()
    second_entries = 0
    for view in views:
        if view.jamfold:
            continue
        node = node_slot(view)[0]
        twin = jam_fold_slot(view)
        if view.seat in {seat for seat, _ in view.actions}:
            assert twin is None, view
            second_entries += 1
            continue
        assert twin is not None, view
        order = role_seats(view)
        key = state_keys(view, view.hand, 1)[0]  # krok 1: dokładne stacki areny
        cache_key = (key, view.hand)
        if cache_key not in cache:
            cache[cache_key] = _stage_problem(config, key, view.hand, jam_fold=True)
        problem = cache[cache_key]
        as_jam = replace(
            view,
            actions=tuple(
                (seat, "jam" if action == "open" else action)
                for seat, action in view.actions
            ),
        )
        assert _tree_node(problem, as_jam, order) == (twin, view.seat), view
        assert twin in problem.nodes, view
        pairs.add((len(order), node, twin))
    assert second_entries > 0, "próbka bez drugich wejść nie sprawdza `None`"
    # Węzeł drzewa jam/fold jest sam sobie bliźniakiem (historia bez otwarcia);
    # przekład widać na czterech węzłach 3-max i jednym HU.
    jam_fold_3max = (N_U_ROOT, N_T_FI, N_B_VS_T_JAM, N_T_VS_U_JAM,
                     N_B_VS_U_JAM_T_FOLD, N_B_VS_U_JAM_T_CALL)
    assert {(node, twin) for live, node, twin in pairs if live == 3} == {
        *((node, node) for node in jam_fold_3max),
        (N_B_VS_T_OPEN, N_B_VS_T_JAM),
        (N_T_VS_U_OPEN, N_T_VS_U_JAM),
        (N_B_VS_U_OPEN, N_B_VS_U_JAM_T_FOLD),
        (N_B_VS_U_OPEN_T_JAM, N_B_VS_U_JAM_T_CALL),
    }
    assert {(node, twin) for live, node, twin in pairs if live == 2} == {
        (H_ROOT, H_ROOT),
        (H_B_VS_JAM, H_B_VS_JAM),
        (H_B_VS_OPEN, H_B_VS_JAM),
    }


def test_wymuszenie_maski_zgadza_sie_z_arena_w_obie_strony() -> None:
    """F2 audytu POKER-54: „arena pyta ⟺ model nie wymusza" sprawdzone w OBIE strony.

    Sam spacer po historii tego nie łapie: przy pustej kolejce i masce
    jednoelementowej konsumuje wymuszony slot milcząco. Ten test patrzy wprost
    na maskę węzła, do którego trafia KAŻDA akcja areny — także ta, o którą
    rozgrywacz nie pytał (widzi ją obserwator `on_action`, bo wejście za darmo
    jest zawsze ostatnią akcją ręki).

    Zerami są dokładnie te klasy, za które odpowiada rozgrywacz: nie ma
    pytania o dołożenie zerowe i nie ma wejścia za darmo poza maską wymuszoną
    w węźle nie-korzeniu. Zostają dwie klasy, które są cechami DRZEWA
    TRENINGU, nie areny, i dlatego mają policzone liczby zamiast zera:

    * `capped_call` — model kapuje call na stacku jamującego, a `jam` areny
      znaczy „cały stack", więc gdy duży stack sprawdza krótki all-in, arena
      stawia trzeciego gracza przed realnym dołożeniem, którego model nie ma;
    * `root_fold` — w korzeniu model daje fold graczowi, który pokrywa cudzy
      krótki blind, choć ten fold nic mu nie oszczędza; po POKER-54 to arena
      jest w tym miejscu bliżej pokera niż model.

    Naprawa obu należy do drzewa (treningu i zamrożonego drzewa decyzji 27),
    więc jest poza tym kontraktem — liczby są tu po to, żeby rosły widocznie.
    """
    config = _mini_config()
    cache: dict[tuple[Any, int], Any] = {}
    events: list[tuple[SeatView, str, bool]] = []
    log = events.append
    for books in (
        (field_exploit(), dollar_fish(), always_jam()),
        (dollar_fish(), always_jam(), field_exploit()),
        (wide_call(0.4), field_exploit(), dollar_fish()),
    ):
        for seed in range(60):
            run_spin(books, seed, on_action=lambda view, act, asked: log((view, act, asked)))
    assert len(events) == 3075  # liczba w bloku POKER-54 CURRENT_STATE

    forced_entry = root_fold = free_question = capped_call = 0
    for view, _, asked in events:
        node, divergence = node_slot(view)
        assert divergence is None, view
        key = state_keys(view, view.hand, 1)[0]  # krok 1: stacki areny, bez siatki
        cache_key = (key, view.hand)
        if cache_key not in cache:
            cache[cache_key] = _stage_problem(config, key, view.hand)
        allowed = cache[cache_key].allowed[node]
        live = sum(1 for seat in range(3) if view.stacks[seat] > 0)
        root = node in (ROOTS_3MAX if live == 3 else ROOTS_HU)
        if not asked:
            if len(allowed) == 1:
                forced_entry += 1
                continue
            root_fold += 1
            assert root and not (view.jammed or view.opened), view
        elif len(allowed) >= 2:
            free_question += 1
        else:
            capped_call += 1
            assert max(view.contrib) > view.contrib[view.seat], view
    assert (forced_entry, root_fold, free_question, capped_call) == (21, 8, 3044, 2)


def test_wejscie_za_darmo_areny_to_akcja_wymuszona_maska_treningu() -> None:
    """Rozgrywacz nie pyta dokładnie tam, gdzie trening ma jedną dozwoloną akcję.

    Ręka 4 sadza guzik na miejscu 1 w obu światach (arena: `button`, trening:
    `ręka % 3`), blindy 2/4. UTG ma 3 żetony, więc jego jam nie przewyższa
    blindu BB: maska modelu w węźle „BB po foldzie guzika" zostawia sam slot
    środkowy (call), a arena wpuszcza BB bez pytania — ten sam wybór po obu
    stronach, na tym samym stanie (decyzja 28 pkt 2b).
    """
    import random

    problem = _stage_problem(_mini_config(), (3, 50, 50), 4)
    assert problem.allowed[N_B_VS_U_JAM_T_FOLD] == (SLOT_MID,)
    bb_seat = Script(("fold",))
    books = (Script(("jam",)), Script(("fold",)), bb_seat)
    deck = shuffled_deck(random.Random(6))
    out = _play_hand([3, 50, 50], 4, 1, 2, 4, books, deck, random.Random(0))
    assert bb_seat.actions == ["fold"], "rozgrywacz zapytał o darmowy call"
    assert out[0] == 0 and out[2] == 55  # BB dograł do showdownu i wygrał pulę


def test_tablica_wezlow_pokrywa_caly_model_i_nic_ponadto() -> None:
    """Tablica slotów opisuje dokładnie 14 węzłów 3-max i 4 węzły HU."""
    assert sorted(NODES_3MAX.values()) == list(range(14))
    assert sorted(NODES_HU.values()) == list(range(4))
    assert set(NODES_3MAX_OUT_OF_ORDER) & set(NODES_3MAX) == set()


def test_agent_gra_wylacznie_akcje_zamrozonego_drzewa(mini_artifact: Path) -> None:
    """Właściwość na wielu seedach: żadna decyzja nie wychodzi poza drzewo.

    Rozgrywacz odrzuca akcję spoza `legal_actions`, więc sam przebieg turniejów
    jest dowodem; obok tego test sprawdza jawnie każdą decyzję na widoku.
    """
    agent = _agent(mini_artifact)
    prizes = PAYOUTS["10x"].prizes
    for villain in (field_exploit(), dollar_fish(), always_jam()):
        for seed in range(20):
            play_block(agent, villain, prizes, 100 + seed)
    assert agent.decisions > 400
    assert agent.from_artifact > 0
    views = _spy_views(range(15), (dollar_fish(), field_exploit()))
    import random

    for index, view in enumerate(views):
        action = agent.act(view, random.Random(index))
        assert action in legal_actions(view), (view, action)


def test_rozgrywacz_odrzuca_akcje_spoza_drzewa() -> None:
    """Port nie jest furtką: nielegalna akcja agenta zatrzymuje rozdanie błędem."""

    class Rogue:
        def act(self, view: SeatView, rng: Any) -> str:
            rng.random()
            return "open" if "open" not in legal_actions(view) else "check"

    with pytest.raises(ValueError, match="spoza zamrożonego drzewa"):
        run_spin((Rogue(), always_jam(), always_jam()), 1)


def test_liczniki_fallbacku_sa_rozlaczne_i_policzalne(mini_artifact: Path) -> None:
    """Cztery przyczyny, cztery liczniki: horyzont, stan, węzeł, klasa.

    Horyzont po POKER-55 to wyłącznie ręka, której artefakt nie ma nawet
    w warstwie cyklu; stan spoza warstwy i węzeł spoza maski to sygnał
    odwzorowania; klasa spoza zestawu biegu to granica artefaktu, nie
    odwzorowania.
    """
    import random

    agent = _agent(mini_artifact)
    rng = random.Random(0)
    # Ręka za zegarem warstw czyta warstwę cyklu (POKER-55), więc horyzont
    # zapala się dopiero tam, gdzie artefakt nie ma nawet jej — tu wyłącznie
    # przy wyłączonej regule cyklu (osobny test) — a ręka w zegarze i tak nie.
    assert agent.act(_view(hand=21, jammed=True), rng) in ("jam", "fold")
    assert agent.counters()["horizon_fallbacks"] == 0
    assert agent.counters()["grid_fallbacks"] == 0

    # Warstwa 0 zna wyłącznie stan startowy — każdy inny to stan spoza warstwy.
    assert agent.act(_view(hand=0, stacks=(0, 50, 100), seat=1, button=1), rng) == "fold"
    assert agent.counters()["state_misses"] == 1
    assert agent.counters()["grid_fallbacks"] == 1

    # Ręka 20 gra się przy blindach 10/20, więc stan 50/50/50 jest jam/fold:
    # węzeł „BB wobec open" nie istnieje w masce tego stanu.
    opened = _view(
        hand=20,
        seat=2,
        button=1,
        stacks=(50, 50, 50),
        contrib=(4, 10, 20),
        actions=((0, "fold"), (1, "open")),
        bb=20,
        opened=True,
        jamfold=True,
    )
    assert node_slot(opened)[0] == 2
    assert agent.act(opened, rng) == "fold"
    assert agent.counters()["node_misses"] == 1
    assert agent.counters()["grid_fallbacks"] == 2

    # Warstwa 20 jest pełna, a mimo to pudło było w węźle, nie w stanie:
    # licznik stanu w warstwie pełnej zostaje zerem.
    assert agent.counters()["full_layer_state_misses"] == 0
    assert agent.act(_view(hand=1, klass=168), rng) == "fold"
    assert agent.counters()["class_misses"] == 1
    assert agent.counters()["grid_fallbacks"] == 2
    counters = agent.counters()
    assert counters["decisions"] == 4
    assert counters["from_artifact"] == 1  # ręka 21 z warstwy cyklu
    assert counters["cyclic_reads"] == 1
    assert (
        counters["grid_fallbacks"]
        == counters["state_misses"] + counters["node_misses"] + counters["mass_misses"]
    )


def test_fallback_poza_horyzontem_to_check_call_fold(
    mini_artifact: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bez warstwy strategii agent sprawdza all-in, a bez all-inu pasuje (jak mccfr).

    Po POKER-55 artefakt o pełnym zegarze (bramkowy i produkcyjny) nie ma już
    ręki bez warstwy: każda za horyzontem czyta warstwę cyklu. Przyczyna
    zostaje dla artefaktu o zegarze KRÓTSZYM niż gra (np. pilotowego), a że
    bramka takiego nie buduje, ścieżkę osiąga się tu wyłączeniem reguły cyklu.
    Sam fallback jest prawdziwy: to ta sama `passive_action` i ten sam licznik,
    który bieg kontrolny w `test_horyzont_czyta_warstwe_cyklu_punktu_stalego`
    zapala 109 razy.
    """
    import random

    monkeypatch.setattr(blueprint_agent, "cyclic_hand", lambda hand: hand)
    agent = _agent(mini_artifact)
    rng = random.Random(1)
    assert agent.act(_view(hand=30, jammed=True, jamfold=True), rng) == "jam"
    assert agent.act(_view(hand=30, opened=True), rng) == "fold"
    assert agent.act(_view(hand=30), rng) == "fold"
    assert agent.counters()["horizon_fallbacks"] == 3


def test_decyzje_sa_deterministyczne_w_procesie(mini_artifact: Path) -> None:
    """Ten sam artefakt, seed i ciąg widoków → ten sam ciąg decyzji."""
    import random

    views = _spy_views(range(10), (dollar_fish(), always_jam()))
    runs = []
    for _ in range(2):
        agent = _agent(mini_artifact)
        runs.append(
            [agent.act(view, random.Random(index)) for index, view in enumerate(views)]
        )
    assert runs[0] == runs[1]
    assert len(set(runs[0])) > 1


def test_decyzje_sa_deterministyczne_miedzy_procesami(mini_artifact: Path) -> None:
    """INV-P1 dla agenta: wynik nie zależy od PYTHONHASHSEED procesu."""
    script = (
        "import json,sys\n"
        "from poker.blueprint_agent import BlueprintAgent\n"
        "from poker.blueprint_reader import BlueprintLookupError, BlueprintReader, StateBlock\n"
        "from poker.spin import PAYOUTS\n"
        "from poker.spin_arena import dollar_fish, field_exploit, play_block\n"
        "stream = open(sys.argv[1], 'rb')\n"
        "reader = BlueprintReader(stream)\n"
        "cfg = json.loads(reader.meta_bytes())['run_manifest']['config']\n"
        "agent = BlueprintAgent(reader, grid_step=cfg['grid_step'], classes=cfg['classes'])\n"
        "print([play_block(agent, field_exploit(), PAYOUTS['10x'].prizes, s)"
        " for s in range(5)])\n"
        "print([play_block(agent, dollar_fish(), PAYOUTS['3x'].prizes, s) for s in range(5)])\n"
        "print(json.dumps(agent.counters(), sort_keys=True))\n"
    )
    runs = [
        subprocess.run(
            [sys.executable, "-c", script, str(mini_artifact)],
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for hash_seed in ("1", "2")
    ]
    assert runs[0] == runs[1]
    assert runs[0].count("\n") == 3


def test_karty_bloku_nie_zaleza_od_tego_kto_gra(mini_artifact: Path) -> None:
    """Rotacje bloku widzą tę samą sekwencję kart także z agentem w składzie."""
    agent = _agent(mini_artifact)
    villain = dollar_fish()
    for seed in (11, 12, 13):
        decks = []
        for seat in range(3):
            books: list[Any] = [villain, villain, villain]
            books[seat] = agent
            decks.append(_run_seen((books[0], books[1], books[2]), seed)[1])
        shortest = min(len(seen) for seen in decks)
        assert shortest > 0
        for seen in decks[1:]:
            assert seen[:shortest] == decks[0][:shortest], seed


def test_cli_rejestruje_agenta_blueprintu(mini_artifact: Path) -> None:
    """Rejestr CLI: ścieżka artefaktu, otwarcie pliku i metadane po stronie narzędzia."""
    out = subprocess.run(
        [sys.executable, str(REPO / "tools" / "run_arena.py"),
         "blueprint", str(mini_artifact), "4", "10x"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    ).stdout
    payload = json.loads(out)
    assert payload["pay"] == "10x"
    assert payload["artifact"] == str(mini_artifact)
    assert len(payload["config_hash"]) == 64
    for name in ("blueprint_vs_field", "blueprint_vs_dollar", "blueprint_vs_always_jam"):
        entry = payload[name]
        assert entry["n"] == 4.0
        assert entry["ci_lo"] <= entry["roi"] <= entry["ci_hi"]
        assert entry["fallbacks"]["decisions"] > 0
    assert payload["fallbacks_total"]["decisions"] == sum(
        payload[name]["fallbacks"]["decisions"]
        for name in ("blueprint_vs_field", "blueprint_vs_dollar", "blueprint_vs_always_jam")
    )


def test_cli_mierzy_koszt_reguly_fallbacku(mini_artifact: Path) -> None:
    """Ile ROI robi sama reguła fallbacku: różnica sparowana wobec „zawsze pasuj"."""
    out = subprocess.run(
        [sys.executable, str(REPO / "tools" / "run_arena.py"),
         "fallback", str(mini_artifact), "4", "3x"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    ).stdout
    payload = json.loads(out)
    assert payload["n_blocks"] == 4
    for name in ("vs_field", "vs_dollar", "vs_always_jam"):
        entry = payload[name]
        assert entry["ci_lo"] <= entry["diff"] <= entry["ci_hi"]
        assert entry["diff"] == pytest.approx(entry["roi_a"] - entry["roi_b"], abs=1e-9)
    assert payload["fallbacks_total"]["decisions"] > 0


def test_stan_spoza_warstwy_zdarza_sie_tylko_w_warstwie_przycietej(
    mini_artifact: Path,
) -> None:
    """Doostrzone kryterium POKER-52: pudło stanu w warstwie PEŁNEJ = błąd odwzorowania.

    Bieg tnie wczesne warstwy osiągalnością (blok POKER-50), więc stan spoza
    warstwy przyciętej jest granicą artefaktu — arena idzie łańcuchem dokładnym,
    trening szedł skwantowanym. W warstwie niosącej pełną siatkę takiego pudła
    być nie może i ten licznik ma zostać zerem przez cały pomiar.
    """
    agent = _agent(mini_artifact)
    prizes = PAYOUTS["3x"].prizes
    for villain in (field_exploit(), dollar_fish(), always_jam()):
        for seed in range(25):
            play_block(agent, villain, prizes, 300 + seed)
    counters = agent.counters()
    assert counters["decisions"] > 500
    # Odczyt stanu miała każda decyzja (po POKER-55 także te za horyzontem,
    # z warstwy cyklu) — zero pudeł w warstwie pełnej jest więc twierdzeniem
    # o czymś, a nie o pustce.
    reads = counters["from_artifact"] + counters["class_misses"] + counters["node_misses"]
    assert reads > 1000, counters
    assert counters["state_misses"] == 0, counters
    assert counters["full_layer_state_misses"] == 0, counters
    assert agent.layer_is_full(0) is False  # warstwa startowa: jeden stan
    assert agent.layer_is_full(20) is True


class _NodesSeen:
    """Miejsce grające agentem, ale zapisujące węzeł modelu i zegar każdej decyzji."""

    def __init__(self, agent: BlueprintAgent) -> None:
        self.agent = agent
        self.nodes: set[tuple[int, int]] = set()
        self.hands: list[int] = []

    def act(self, view: SeatView, rng: Any) -> str:
        live = sum(1 for seat in range(3) if view.stacks[seat] > 0)
        self.nodes.add((live, node_slot(view)[0]))
        self.hands.append(view.hand)
        return self.agent.act(view, rng)


def _kolejnosc_sprzed_poker_54(order: Any, last_actor: int) -> tuple[int, ...]:
    """Kolejność areny SPRZED POKER-54: stała kolejka ról, ślepa na agresora.

    Kontrola eksperymentu do niepustki zer: pokazuje, że TA SAMA próbka
    naprawdę wytwarza rozjazd kolejności, gdy kolejność jest ta stara.
    """
    return tuple(order)


def _agent_run(agent: BlueprintAgent) -> _NodesSeen:
    """Próbka biegu agenta: 4 przeciwników × 80 seedów bloków od 300."""
    seen = _NodesSeen(agent)
    prizes = PAYOUTS["3x"].prizes
    for villain in (field_exploit(), dollar_fish(), always_jam(), wide_call(0.5)):
        for seed in range(80):
            play_block(seen, villain, prizes, 300 + seed)
    return seen


def test_rozjazd_areny_z_kolejnoscia_i_maska_treningu_jest_zerem(
    mini_artifact: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kryterium POKER-54, blokująco: trzy liczniki rozjazdu = 0 na artefakcie bramki.

    `out_of_order` i `order_collapse` to dwie twarze kolejności licytacji,
    `forced_action_misses` to wejście w gałąź za akcją wymuszoną maską (pytanie
    o darmowy call). Pomiar POKER-52 miał tu odpowiednio 21 348, 19 458
    i 1 092 wpisów na 1 582 048 decyzji; naprawiony rozgrywacz nie wytwarza
    żadnego z tych infosetów.

    Zero jest niepuste NA TEJ SAMEJ PRÓBCE, a nie na innej (F3 audytu
    POKER-54): ten sam bieg powtórzony z kolejnością sprzed POKER-54 zapala
    oba liczniki kolejności (2 i 136), a agent odwiedza w nim wszystkie 14
    węzłów modelu 3-max — w tym 8, 9 i 10, na których rozjazd siedział.

    `forced_action_misses` ma na artefakcie bramki wąskie gardło: rozkład
    czyta się dopiero po klasie, a mini-artefakt zna cztery klasy ze 169, więc
    większość decyzji kończy się na `class_misses` przed odczytem węzła. Za tę
    przyczynę odpowiada dodatkowo `test_wymuszenie_maski_zgadza_sie_z_arena_w_obie_strony`,
    który patrzy na maski modelu dla KAŻDEJ akcji areny, niezależnie od klas
    artefaktu.
    """
    agent = _agent(mini_artifact)
    seen = _agent_run(agent)
    counters = agent.counters()
    assert counters["decisions"] == 5770, counters
    assert counters["out_of_order"] == 0, counters
    assert counters["order_collapse"] == 0, counters
    assert counters["forced_action_misses"] == 0, counters
    assert counters["node_misses"] == 0, counters
    # Węzeł 7 (UTG wobec 3betu BB po foldzie guzika) w tej próbce nie wypada;
    # rozjazd kolejności siedział na 8, 9 i 10 i te agent odwiedza.
    assert {node for live, node in seen.nodes if live == 3} == set(range(14)) - {7}

    monkeypatch.setattr(spin_arena, "speaking_order", _kolejnosc_sprzed_poker_54)
    before = _agent(mini_artifact)
    _agent_run(before)
    stale = before.counters()
    assert (stale["out_of_order"], stale["order_collapse"]) == (2, 136), stale


def test_horyzont_czyta_warstwe_cyklu_punktu_stalego(
    mini_artifact: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kryterium POKER-55, blokująco: ręka ≥ 21 czyta artefakt, nie fallback.

    Zero jest niepuste NA TEJ SAMEJ PRÓBCE (lekcja F3 audytu POKER-54): ten
    sam bieg z wyłączoną regułą cyklu zapala `horizon_fallbacks` 109 razy,
    czyli dokładnie na tych decyzjach rąk ≥ 21, które teraz idą do artefaktu.
    Z artefaktu wychodzi ich sześć, bo mini-artefakt zna cztery klasy ze 169
    i reszta kończy się na `class_misses` — na artefakcie produkcyjnym (169
    klas) cały ten ruch jest odczytem.

    Stan spoza siatki w warstwie cyklu nadal ma iść do licznika osiągalności,
    a nie do cichej gry: `state_misses` = 0 znaczy tu, że warstwy cyklu mają
    wszystkie stany, o które arena pyta po horyzoncie.
    """
    agent = _agent(mini_artifact)
    seen = _agent_run(agent)
    counters = agent.counters()
    late = [hand for hand in seen.hands if hand >= CYCLE_BASE + CYCLE_LENGTH]
    assert len(late) == 106, len(late)
    assert counters["horizon_fallbacks"] == 0, counters
    assert counters["cyclic_reads"] == 6, counters
    assert counters["state_misses"] == 0, counters
    assert counters["full_layer_state_misses"] == 0, counters
    assert agent.layer_hand(21) == 18 and agent.layer_hand(20) == 20

    monkeypatch.setattr(blueprint_agent, "cyclic_hand", lambda hand: hand)
    before = _agent(mini_artifact)
    _agent_run(before)
    stale = before.counters()
    assert stale["horizon_fallbacks"] == 109, stale
    assert stale["cyclic_reads"] == 0, stale


def test_przeskok_trybu_gra_rozkladem_jamfold_zamiast_fallbacku(
    mini_artifact: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kryterium POKER-55, blokująco: przeskok trybu czyta artefakt, nie fallback.

    Zero jest niepuste NA TEJ SAMEJ PRÓBCE: ten sam bieg z wyłączonym węzłem
    bliźniaczym zapala `mode_flip_misses` trzy razy (w pomiarze POKER-52 było
    to 1 098 wpisów). Dziesięć odczytów to wszystkie decyzje, w których stan
    artefaktu jest jam/fold, a arena gra drzewem głębokim; `mode_flip_translated`
    wydziela z nich te, w których bliźniak jest INNYM węzłem niż węzeł areny —
    tylko tam pula modelu różni się od puli areny (F1 audytu POKER-55). Trzy
    przekłady to dokładnie te trzy decyzje, które przedtem szły do fallbacku;
    pozostałe siedem to korzenie, gdzie węzeł jest w obu drzewach ten sam,
    a rozkład i tak jest jam/fold.
    """
    agent = _agent(mini_artifact)
    _agent_run(agent)
    counters = agent.counters()
    assert counters["mode_flip_reads"] == 10, counters
    assert counters["mode_flip_translated"] == 3, counters
    assert counters["mode_flip_misses"] == 0, counters
    assert counters["node_misses"] == 0, counters
    assert counters["grid_fallbacks"] == 0, counters

    monkeypatch.setattr(blueprint_agent, "jam_fold_slot", lambda view: None)
    without = _agent(mini_artifact)
    _agent_run(without)
    stale = without.counters()
    assert stale["mode_flip_misses"] == 3, stale
    assert stale["mode_flip_reads"] == 0, stale


def test_przeskok_trybu_czyta_rozklad_jamfold_stanu_artefaktu(
    mini_artifact: Path,
) -> None:
    """Decyzja przy przeskoku trybu: rozkład jam/fold stanu, nigdy open.

    HU ręki 12 (blindy 5/10): arena ma 75/75 żetonów, czyli 7,5 bb (drzewo
    głębokie), a siatka 50 żetonów kwantyzuje ten stan do (100, 50, 0), czyli
    5 bb — drzewo jam/fold. Agent wobec otwarcia czyta więc węzeł „BB wobec
    jamu" i gra jego rozkładem zamiast fallbacku; slot środkowy znaczy tam
    „sprawdź all-in", nie „podbij".

    To jest PRZEKŁAD, nie tożsamość: węzeł areny (1) i węzeł czytany (3) to
    dwa różne węzły modelu, więc pula modelu (przeciwnik all-in za 100) różni
    się od puli areny (przeciwnik po otwarciu za 22) — akcje są te same, pula
    nie, i dlatego przekład ma osobny licznik (F1 audytu POKER-55).
    """
    import random

    agent = _agent(mini_artifact)
    view = _view(
        hand=12,
        seat=1,
        button=0,
        stacks=(75, 75, 0),
        contrib=(22, 10, 0),
        actions=((0, "open"),),
        bb=10,
        klass=next(iter(agent.column)),
        opened=True,
    )
    assert state_keys(view, view.hand, agent.grid_step)[0] == (100, 50, 0)
    assert agent.mode_flipped(view) is True
    assert node_slot(view)[0] == H_B_VS_OPEN
    assert jam_fold_slot(view) == H_B_VS_JAM
    mass = agent.action_mass(view)
    assert set(mass) == {"fold", "jam"} == set(legal_actions(view))
    assert agent.act(view, random.Random(0)) in legal_actions(view)
    counters = agent.counters()
    assert counters["mode_flip_reads"] == 2  # `action_mass` i `act`
    assert counters["mode_flip_translated"] == 2, counters
    assert counters["mode_flip_misses"] == 0, counters
    assert counters["from_artifact"] == 1


def test_przeskok_trybu_na_progu_siedmiu_bb_jest_rozpoznany(mini_artifact: Path) -> None:
    """Kwantyzacja potrafi przerzucić stan przez próg jam/fold — i to jest widziane.

    Predykat liczy się z widoku i kroku siatki, więc testuje się go krokiem
    produkcyjnym (2) na czytniku mini-artefaktu: 71 żetonów przy bb = 10 to
    7,1 bb (drzewo głębokie), a stan siatki obok ma 70 żetonów, czyli 7,0 bb —
    jam/fold. Krok 50 mini-artefaktu nie ma takiej pary.
    """
    stream = mini_artifact.open("rb")
    reader = BlueprintReader(stream)
    classes = json.loads(reader.meta_bytes())["run_manifest"]["config"]["classes"]
    agent = BlueprintAgent(reader, grid_step=2, classes=classes)
    deep = _view(hand=13, seat=2, button=2, stacks=(79, 0, 71), bb=10, jamfold=False)
    assert state_keys(deep, deep.hand, 2)[0] == (80, 0, 70)
    assert agent.mode_flipped(deep) is True
    even = _view(hand=13, seat=2, button=2, stacks=(80, 0, 70), bb=10, jamfold=True)
    assert agent.mode_flipped(even) is False


def test_liczniki_rozjazdu_kolejnosci_rosna_kazdy_na_swoim_przypadku() -> None:
    """Dwie twarze usterki kolejności mają dwa rozłączne liczniki.

    Bez tego testu mutacja „licz kolaps jako swap" przechodzi bramkę, a raport
    pomiaru pokazuje jedną liczbę zamiast dwóch przyczyn (audyt POKER-52, F1).
    """
    swap = _view(
        hand=6,
        seat=0,
        button=1,
        stacks=(50, 50, 50),
        contrib=(13, 3, 6),
        actions=((0, "open"), (1, "jam")),
        bb=6,
        klass=0,
    )
    node, divergence = node_slot(swap)
    assert (node, divergence) == (9, ORDER_SWAP)
    assert stale_history(swap) is False

    collapse = _view(
        hand=6,
        seat=2,
        button=1,
        stacks=(50, 50, 50),
        contrib=(13, 50, 6),
        actions=((0, "open"), (1, "jam"), (0, "fold")),
        bb=6,
        klass=0,
        jammed=True,
    )
    assert stale_history(collapse) is True
    assert node_slot(collapse) == (8, ORDER_COLLAPSE)
    # Ten sam węzeł 8 czyta też infoset BEZ odpowiedzi UTG — to jest kolaps.
    fresh = replace(collapse, actions=((0, "open"), (1, "jam")))
    assert node_slot(fresh) == (8, None)


def test_liczniki_rozjazdu_kolejnosci_sa_rozlaczne_w_agencie(mini_artifact: Path) -> None:
    """Agent zlicza swap i kolaps osobno — każdy licznik rośnie tylko na swoim."""
    import random

    agent = _agent(mini_artifact)
    rng = random.Random(0)
    swap = _view(
        hand=6, seat=0, button=1, stacks=(50, 50, 50), contrib=(13, 3, 6),
        actions=((0, "open"), (1, "jam")), bb=6, klass=0, jammed=True,
    )
    agent.act(swap, rng)
    assert (agent.out_of_order, agent.order_collapse) == (1, 0)
    collapse = replace(swap, seat=2, actions=((0, "open"), (1, "jam"), (0, "fold")))
    agent.act(collapse, rng)
    assert (agent.out_of_order, agent.order_collapse) == (1, 1)


def test_licznik_pudel_w_warstwie_pelnej_rosnie_przy_zlym_kroku_siatki(
    mini_artifact: Path,
) -> None:
    """Kryterium aneksu: `full_layer_state_misses` = 0 znaczy coś tylko wtedy,
    gdy licznik potrafi rosnąć. Agent z krokiem siatki innym niż krok artefaktu
    pyta o stany, których warstwa pełna nie ma — i to jest właśnie błąd
    odwzorowania, przed którym kryterium chroni."""
    import random

    stream = mini_artifact.open("rb")
    reader = BlueprintReader(stream)
    classes = json.loads(reader.meta_bytes())["run_manifest"]["config"]["classes"]
    agent = BlueprintAgent(reader, grid_step=2, classes=classes)
    rng = random.Random(0)
    agent.act(_view(hand=8, stacks=(48, 52, 50), bb=6, klass=classes[0]), rng)
    counters = agent.counters()
    assert counters["state_misses"] == 1
    assert counters["full_layer_state_misses"] == 1, counters
    assert agent.layer_is_full(8) is True


def test_licznik_przeskoku_trybu_rosnie_gdy_artefakt_oferuje_open(
    mini_artifact: Path,
) -> None:
    """Kryterium aneksu: `mode_mismatches` = 0 z pomiaru wymaga licznika, który
    umie rosnąć. Przy kroku siatki 50 stan (30, 60, 60) kwantyzuje się do
    50/50/50: arena przy bb = 6 jest jam/fold (5 bb), a stan artefaktu głęboki
    (8,33 bb), więc rozkład niesie open, którego arena nie ma."""
    import random

    agent = _agent(mini_artifact)
    view = _view(
        hand=6,
        seat=0,
        button=1,
        stacks=(30, 60, 60),
        contrib=(0, 3, 6),
        bb=6,
        klass=next(iter(agent.column)),
        jamfold=True,
    )
    assert state_keys(view, view.hand, agent.grid_step)[0] == (50, 50, 50)
    action = agent.act(view, random.Random(3))
    assert action in legal_actions(view)
    assert agent.counters()["mode_mismatches"] == 1, agent.counters()
    assert agent.counters()["from_artifact"] == 1


def test_licznik_rozkladu_bez_legalnej_masy_rosnie(mini_artifact: Path) -> None:
    """Kryterium aneksu: `mass_misses` = 0 z pomiaru wymaga żywego licznika.

    Artefakt bramki nie ma stanu o rozkładzie „100% open" (sprawdzone), więc
    blok stanu jest tu zbudowany wprost — to jest dana formatu, nie podmieniona
    logika agenta: bajty bloku idą przez tę samą dekwantyzację co z pliku.
    """
    import random

    agent = _agent(mini_artifact)
    klass = next(iter(agent.column))
    width = agent.reader.n_classes
    payload = bytes(width) + bytes([255] * width)  # slot fold = 0, slot open = pełny
    block = StateBlock(
        hand=6,
        stacks=(50, 50, 50),
        node_mask=1,  # wyłącznie korzeń UTG
        n_classes=width,
        quant_bits=8,
        payload=payload,
    )
    assert block.policy(0, agent.column[klass]) == (0.0, 1.0, 0.0)
    agent.state_block = lambda view, layer: block  # type: ignore[method-assign]
    view = _view(hand=6, seat=0, button=1, bb=6, klass=klass, jamfold=True)
    assert agent.act(view, random.Random(0)) == "fold"
    counters = agent.counters()
    assert counters["mass_misses"] == 1, counters
    assert counters["grid_fallbacks"] == 1
    assert counters["mode_mismatches"] == 1  # open poza drzewem areny — też liczony
    # F3 audytu: ścieżka bez legalnej masy nie jest decyzją zagraną z artefaktu,
    # więc liczniki odczytu na niej nie rosną (inkrementy stoją za tym testem).
    assert counters["cyclic_reads"] == 0, counters
    assert counters["mode_flip_reads"] == 0, counters
    assert counters["mode_flip_translated"] == 0, counters


def test_brak_legalnej_masy_nie_spotyka_sie_z_odczytem_cyklicznym() -> None:
    """Dlaczego zera z testu wyżej są dziś nieosiągalne inaczej niż wprost.

    Rozkład bez legalnej masy wymaga korzenia drzewa GŁĘBOKIEGO (tylko tam slot
    środkowy znaczy „podbij") przy arenie jam/fold. Odczyt cykliczny zaczyna
    się od ręki `CYCLE_BASE + CYCLE_LENGTH`, a tam blindy stoją na ostatnim
    poziomie: 7 bb to 140 żetonów, więc przy 150 w grze i dwóch żywych
    najkrótszy stack nigdy nie przekracza progu i KAŻDY stan siatki jest
    jam/fold. Te dwie ścieżki nie mogą się więc dziś spotkać — kolejność
    inkrementów w `action_mass` nie zależy od tego faktu, ale dokument tak.
    """
    _, big, _ = blinds_for_hand(CYCLE_BASE + CYCLE_LENGTH)
    assert big == LEVELS[-1][1]
    total = 3 * STARTING_CHIPS
    for first in range(0, total + 1, 2):
        for second in range(0, total - first + 1, 2):
            stacks = (first, second, total - first - second)
            if sum(1 for value in stacks if value > 0) < 2:
                continue
            assert is_jam_fold_depth(stacks, big), stacks


def test_licznik_wejscia_wymuszonego_rosnie_za_galezia_spoza_maski(
    mini_artifact: Path,
) -> None:
    """Kryterium POKER-54: `forced_action_misses` = 0 wymaga licznika, który umie rosnąć.

    Gdy jam nie przewyższa blinda guzika, maska treningu wymusza guzikowi
    wejście i gałąź „guzik spasował" nie ma w artefakcie węzła — pytanie
    o darmowy call wprowadzało arenę dokładnie tam. Artefakt bramki takiego
    stanu nie ma (krok siatki 50 nie schodzi poniżej blinda), więc maska bez
    węzła 12 jest tu daną formatu, a nie podmienioną logiką agenta: bajty
    bloku idą przez tę samą dekwantyzację co z pliku.
    """
    import random

    agent = _agent(mini_artifact)
    width = agent.reader.n_classes
    block = StateBlock(
        hand=20,
        stacks=(50, 50, 50),
        node_mask=(1 << N_U_ROOT) | (1 << N_T_VS_U_JAM),
        n_classes=width,
        quant_bits=8,
        payload=bytes(4 * width),
    )
    assert block.has_node(N_B_VS_U_JAM_T_FOLD) is False
    agent.state_block = lambda view, layer: block  # type: ignore[method-assign]
    view = _view(
        hand=20,
        seat=2,
        button=1,
        stacks=(50, 50, 50),
        contrib=(50, 10, 20),
        actions=((0, "jam"), (1, "fold")),
        bb=20,
        klass=next(iter(agent.column)),
        jamfold=True,
        jammed=True,
    )
    assert node_slot(view) == (N_B_VS_U_JAM_T_FOLD, None)
    assert agent.act(view, random.Random(0)) == "jam"  # fallback: sprawdza all-in
    counters = agent.counters()
    assert counters["node_misses"] == 1, counters
    assert counters["forced_action_misses"] == 1, counters
    assert counters["mode_flip_misses"] == 0, counters


def test_klasa_z_artefaktu_nie_zapala_licznika_klas(mini_artifact: Path) -> None:
    """Kryterium aneksu: `class_misses` = 0 dla klas, które bieg policzył."""
    import random

    agent = _agent(mini_artifact)
    rng = random.Random(0)
    for klass in agent.column:
        agent.act(_view(hand=6, stacks=(50, 50, 50), bb=6, klass=klass), rng)
    counters = agent.counters()
    assert counters["from_artifact"] == len(agent.column) == 4
    assert counters["class_misses"] == 0, counters
    agent.act(_view(hand=6, stacks=(50, 50, 50), bb=6, klass=168), rng)
    assert agent.counters()["class_misses"] == 1


def test_drugie_wejscie_roli_wyklucza_wejscie_wymuszone() -> None:
    """Dlaczego wymuszenie dolicza się tylko rolom PRZED decydentem (F5 audytu).

    Druga akcja roli istnieje wyłącznie po otwarciu, otwarcie wyłącznie poza
    trybem jam/fold, a poza nim najkrótszy żywy stack przekracza 7 bb — więc
    żadne miejsce nie jest all-in z samego blinda i nie ma czego doliczać po
    decydencie. Test trzyma oba ogniwa na widokach z prawdziwych turniejów
    (bez nich gałąź `again` byłaby martwym kodem bez wyjaśnienia).
    """
    views = _spy_views(range(40), (dollar_fish(), always_jam()))
    second_actions = 0
    forced_before = 0
    for view in views:
        first: dict[int, str] = {}
        for seat, action in view.actions:
            first.setdefault(seat, action)
        order = role_seats(view)
        actor = order.index(view.seat)
        pending = [
            (index, seat)
            for index, seat in enumerate(order)
            if seat not in first and view.contrib[seat] >= view.stacks[seat]
        ]
        if view.seat in first:
            second_actions += 1
            assert not view.jamfold, view  # druga akcja tylko po otwarciu
            assert not pending, view  # a wtedy nikt nie jest all-in z blinda
        for index, _ in pending:
            # Wejście wymuszone zdarza się wyłącznie w trybie jam/fold; role
            # PO decydencie po prostu jeszcze nie grały i nic im nie liczymy.
            assert view.jamfold, view
            if index < actor:
                forced_before += 1
    assert second_actions > 0, "próbka bez drugich akcji nie sprawdza niczego"
    assert forced_before > 0, "próbka bez wejść wymuszonych nie sprawdza niczego"


def test_losowanie_normalizuje_rozklad_przycietych_akcji() -> None:
    """`sample` losuje z masy PO przycięciu, więc waży ją sumą, nie jedynką.

    Bez normalizacji rozkład bez „open" (arena w jam/fold) folduje tym
    częściej, im więcej masy artefakt trzymał na otwarciu — a to jest cicha
    zmiana strategii, nie szczegół implementacji.
    """
    import random

    mass = {"fold": 0.2, "jam": 0.2}
    draws = [sample(mass, random.Random(seed)) for seed in range(400)]
    jams = draws.count("jam")
    assert 150 < jams < 250, jams  # bez normalizacji byłoby ~80 (0,2 z 1,0)
    assert all(action in mass for action in draws)
    assert sample({"jam": 0.4}, random.Random(0)) == "jam"


def test_widok_niesie_zegar_rotacje_i_wklady_areny() -> None:
    """Pola `SeatView` opisują TEN stan areny, nie sąsiedni (F7 audytu).

    `bb` zasila próg jam/fold agenta, `hand` warstwę, `button` role — pomyłka
    w którymkolwiek przesuwa odczyt artefaktu po cichu, bo każdy z tych stanów
    w artefakcie istnieje. Test porównuje widoki z zegarem i rotacją areny.
    """
    seen: list[tuple[int, SeatView]] = []

    class Watcher(Spy):
        def act(self, view: SeatView, rng: Any) -> str:
            seen.append((view.hand, view))
            return super().act(view, rng)

    for seed in range(25):
        watcher = Watcher(field_exploit())
        run_spin((watcher, dollar_fish(), wide_call(0.45)), seed)
    assert len({view.hand for _, view in seen}) > 3
    assert len(seen) > 100
    for hand, view in seen:
        sb, bb, _ = blinds_for_hand(hand)
        assert view.bb == bb, view
        assert view.hand == hand
        assert view.stacks[view.button] > 0, view
        assert sum(view.stacks) == 3 * STARTING_CHIPS
        assert view.hand < HAND_GUARD
        live = [seat for seat in range(3) if view.stacks[seat] > 0]
        if len(live) == 3:
            utg, button, big = role_seats(view)
            assert {utg, button, big} == {0, 1, 2}
            acted = {seat for seat, _ in view.actions}
            # Guzik płaci SB, lewy sąsiad BB — dopóki nie zagrali, wkład widoku
            # to dokładnie ich blind (potem rośnie o open albo all-in).
            if button not in acted:
                assert view.contrib[button] == min(sb, view.stacks[button]), view
            if big not in acted:
                assert view.contrib[big] == min(bb, view.stacks[big]), view
            if utg not in acted:
                assert view.contrib[utg] == 0, view


def test_agent_bierze_dokladnie_jeden_pobor_rng_na_decyzje(
    mini_artifact: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Strumień losowań ręki ma być taki sam jak przy `SeatBook` na tym miejscu.

    `pick` bierze jeden pobór w każdej gałęzi; agent musi brać tyle samo —
    inaczej podmiana książki na agenta przesuwa decyzje PRZECIWNIKÓW w tej
    samej ręce i porównania na wspólnych seedach przestają być porównaniami.
    Test liczy pobory na wszystkich ścieżkach: z artefaktu (wprost i z warstwy
    cyklu) i na każdym fallbacku (horyzont, stan, węzeł, klasa).
    """
    import random

    class Counting(random.Random):
        draws = 0

        def random(self) -> float:
            type(self).draws += 1
            return super().random()

    agent = _agent(mini_artifact)
    rng = Counting(5)
    views = [
        _view(hand=6, stacks=(50, 50, 50), bb=6, klass=next(iter(agent.column))),
        _view(hand=30, bb=20, klass=next(iter(agent.column))),  # z warstwy cyklu
        _view(hand=0, stacks=(0, 50, 100), seat=1, button=1, bb=2),  # stan spoza warstwy
        _view(hand=6, stacks=(50, 50, 50), bb=6, klass=168),  # klasa spoza artefaktu
    ]
    for view in views:
        agent.act(view, rng)
    counters = agent.counters()
    assert counters["decisions"] == len(views) == Counting.draws
    assert counters["from_artifact"] == 2
    assert counters["cyclic_reads"] == 1
    assert counters["state_misses"] == 1
    assert counters["class_misses"] == 1

    # Ścieżka horyzontu (artefakt bez warstwy nawet w cyklu) bierze tyle samo.
    monkeypatch.setattr(blueprint_agent, "cyclic_hand", lambda hand: hand)
    agent.act(_view(hand=30, bb=20, jammed=True), rng)
    assert agent.counters()["horizon_fallbacks"] == 1
    assert agent.counters()["decisions"] == Counting.draws == 5


def test_wyplata_nie_wchodzi_do_decyzji_tylko_do_punktacji(mini_artifact: Path) -> None:
    """Ten sam bieg pod 3x i 10x daje identyczne liczniki — nagrody widzi
    dopiero punktacja bloku, nie agent i nie książki. Na tym stoi zdanie
    dokumentu „liczniki BG są identyczne co do sztuki z BF"."""
    counters = []
    for pay in ("3x", "10x"):
        agent = _agent(mini_artifact)
        for villain in (field_exploit(), dollar_fish()):
            for seed in range(8):
                play_block(agent, villain, PAYOUTS[pay].prizes, 40 + seed)
        counters.append(agent.counters())
    assert counters[0] == counters[1], counters
    assert counters[0]["decisions"] > 100


def test_fingerprint_przebiegu_jedzie_w_manifescie_i_w_metadanych(mini_artifact: Path) -> None:
    """Artefakt niesie odcisk gry, którą policzył — jednym polem, nie do wydedukowania.

    Rodzina blueprintów per tier (decyzja 29 pkt 3A) sprawia, że pomyłka o jeden
    plik jest cicha: te same warstwy, ta sama siatka, inna gra. Odcisk jest
    w metadanych `.bpk` i w manifeście biegu, i w obu miejscach ten sam.
    """
    with mini_artifact.open("rb") as stream:
        meta = json.loads(BlueprintReader(stream).meta_bytes())
    assert meta["fingerprint"] == meta["run_manifest"]["fingerprint"]
    assert meta["fingerprint"] == {
        "prizes": [0.8, 0.2, 0.0],
        "total_chips": 150,
        "levels": [list(pair) for pair in LEVELS],
        "hands_per_level": 3,
        "grid_step": 50,
        "profile": "blueprint",
        "hero": "symmetric",
    }


def test_artefakt_8020_czytany_z_oczekiwaniem_wta_rzuca(mini_artifact: Path) -> None:
    """Konsument oczekujący WTA nie zagra z artefaktu 80/20 — dostaje wyjątek.

    Cicha zgoda kosztowałaby tu grę w inną grę: przy (1, 0, 0) Malmuth-Harville
    degeneruje się do udziału w stacku, a przy (0,8, 0,2, 0) stack dwóch żetonów
    niesie +88% equity ponad udział (decyzja 29 pkt 1).
    """
    with mini_artifact.open("rb") as stream:
        fingerprint = json.loads(BlueprintReader(stream).meta_bytes())["fingerprint"]
    # Zgodne oczekiwanie przechodzi — inaczej test świeciłby na czerwono zawsze.
    check_fingerprint(fingerprint, {"prizes": TIERS["T-DEEP"].prizes, "grid_step": 50})
    with pytest.raises(FingerprintMismatch, match="prizes"):
        check_fingerprint(fingerprint, {"prizes": TIERS["T-MODAL"].prizes})
    with pytest.raises(FingerprintMismatch, match="total_chips"):
        check_fingerprint(fingerprint, {"total_chips": TIERS["T-MODAL"].total_chips})
    with pytest.raises(FingerprintMismatch, match="hero"):
        check_fingerprint(fingerprint, {"hero": "seat-restricted"})
    # Pole, którego odcisk nie niesie, jest różnicą tak samo jak inna wartość.
    with pytest.raises(FingerprintMismatch, match="nie niesie"):
        check_fingerprint(fingerprint, {"model_prior": "blueprint"})


def test_licznik_udzialu_decyzyjnego_trybow_jest_zupelny_i_niepusty(
    mini_artifact: Path,
) -> None:
    """Udział decyzyjny trybów: cztery liczniki sumują się do decyzji, żaden nie jest pusty.

    Otwarte pytanie 2 decyzji 29 zmierzone na artefakcie bramki: udział KOMÓREK
    siatki nie jest udziałem ODWIEDZIN. Ten sam bieg ma 6,4% komórek `deep`
    (9 stanów-warstw na 141) i 51,4% decyzji `deep` — osiem razy więcej, bo
    turniej zaczyna się w komórce głębokiej i wraca do niej co rotację, a płaci
    się za komórki. Obie liczby są z TEGO SAMEGO artefaktu.
    """
    agent = _agent(mini_artifact)
    _agent_run(agent)
    counters = agent.counters()
    modes = {mode: counters[f"decisions_{mode}"] for mode in SOLVER_MODES}
    assert sum(modes.values()) == counters["decisions"] == 5770
    assert all(count > 0 for count in modes.values()), modes
    assert modes == {"deep": 2966, "jamfold": 192, "hu-deep": 1440, "hu-jamfold": 1172}
    cells = _load("mode_census").census(_mini_config(), 1).layer_totals()
    cell_share = cells["deep"] / sum(cells.values())
    visit_share = modes["deep"] / counters["decisions"]
    assert cell_share == pytest.approx(0.0638, abs=0.0005)
    assert visit_share == pytest.approx(0.5140, abs=0.0005)


def test_licznik_trybu_opisuje_komorke_artefaktu_a_nie_arene(mini_artifact: Path) -> None:
    """Tryb liczy się ze stanu PO KWANTYZACJI — tym samym, którego szuka odczyt.

    Kontrola: ten sam widok przy dwóch poziomach blindów wpada w dwa różne tryby,
    a przy przeskoku trybu (arena głęboka, stan artefaktu jam/fold) licznik idzie
    za artefaktem, bo mianownikiem porównania jest mieszanka trybów biegu.
    """
    import random

    agent = _agent(mini_artifact)
    rng = random.Random(0)
    deep = _view(hand=0, bb=2)
    short = _view(hand=20, bb=20, jamfold=True, jammed=True)
    assert agent.decision_mode(deep) == "deep"
    assert agent.decision_mode(short) == "jamfold"
    assert agent.decision_mode(_view(hand=2, stacks=(0, 75, 75), seat=1, bb=2)) == "hu-deep"
    agent.act(deep, rng)
    agent.act(short, rng)
    assert agent.counters()["decisions_deep"] == 1
    assert agent.counters()["decisions_jamfold"] == 1
    # Przeskok trybu: arena liczy próg z dokładnych stacków (71 przy bb 10 to
    # 7,1 bb), a stan artefaktu po kwantyzacji krokiem 50 jest jam/fold.
    flipped = _view(hand=15, seat=0, button=0, stacks=(71, 0, 79), bb=10, jamfold=False)
    assert not is_jam_fold_depth(flipped.stacks, flipped.bb)
    assert state_keys(flipped, 15, 50)[0] == (100, 0, 50)
    assert agent.decision_mode(flipped) == "hu-jamfold"

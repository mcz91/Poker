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

from poker.blueprint_agent import (
    N_B_VS_U_JAM_T_FOLD,
    N_T_VS_U_JAM,
    N_U_ROOT,
    NODES_3MAX,
    NODES_3MAX_OUT_OF_ORDER,
    NODES_HU,
    ORDER_COLLAPSE,
    ORDER_SWAP,
    SLOT_FOLD,
    SLOT_JAM,
    SLOT_MID,
    BlueprintAgent,
    label_seats,
    node_slot,
    quantize_stacks,
    role_seats,
    sample,
    stale_history,
    state_keys,
)
from poker.blueprint_reader import BlueprintReader, StateBlock
from poker.dealing import shuffled_deck
from poker.spin import LEVELS, PAYOUTS, STARTING_CHIPS, blinds_for_hand, roles
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


def _training_role_labels(hand: int, live_labels: tuple[int, ...]) -> tuple[int, ...]:
    """Role treningu wyrażone etykietami miejsc: guzik z `ręka % 3` albo `ręka % 2`."""
    if len(live_labels) == 3:
        utg, button, big = roles(hand % 3)
        return (utg, button, big)
    ordered = sorted(live_labels)
    button = ordered[hand % 2]
    return (button, ordered[1 - hand % 2])


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
                for seat_of_label in label_seats(view):
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


def test_klucz_stanu_to_przenumerowanie_i_kwantyzacja() -> None:
    """Klucz jest złożeniem dwóch reguł, obu osobno pod testem."""
    view = _view(hand=4, button=2, stacks=(47, 51, 52))
    keys = state_keys(view, 2)
    assert len(keys) == 1
    seat_of_label = label_seats(view)[0]
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
    keys = state_keys(view, 2)
    assert len(keys) == 3
    for key in keys:
        live_labels = tuple(label for label in range(3) if key[label] > 0)
        button_label, bb_label = _training_role_labels(view.hand, live_labels)
        assert key[button_label] == 90  # guzik areny to miejsce 2
        assert key[bb_label] == 60
    assert len(set(keys)) == 3


def _stage_problem(config: Any, stacks: tuple[int, int, int], hand: int) -> Any:
    """Gra etapowa treningu dla tego stanu i tej ręki (wypłaty liści nieużywane)."""
    sg = _load("solve_grid")
    import numpy as np

    tensors = _tensors(config)
    sb, bb_amt, _ = blinds_for_hand(hand)
    problem, _, _ = sg.build_stage_problem(
        tensors, config, stacks, hand, sb, bb_amt, lambda target: np.zeros(3)
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
    assert len(views) > 500
    seen_nodes: set[tuple[int, int]] = set()
    cache: dict[tuple[Any, int], Any] = {}
    for view in views:
        node, divergence = node_slot(view)
        assert divergence is None, (view, node)
        key = state_keys(view, 1)[0]  # krok 1 = brak kwantyzacji: dokładne stacki areny
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

    Horyzont to warstwa brzegowa (samo V) i ręka spoza artefaktu; stan spoza
    warstwy i węzeł spoza maski to sygnał odwzorowania; klasa spoza zestawu
    biegu to granica artefaktu, nie odwzorowania.
    """
    import random

    agent = _agent(mini_artifact)
    rng = random.Random(0)
    assert agent.act(_view(hand=21, jammed=True), rng) == "jam"
    assert agent.counters()["horizon_fallbacks"] == 1
    assert agent.act(_view(hand=99), rng) == "fold"
    assert agent.counters()["horizon_fallbacks"] == 2
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
    assert counters["decisions"] == 5
    assert counters["from_artifact"] == 0
    assert (
        counters["grid_fallbacks"]
        == counters["state_misses"] + counters["node_misses"] + counters["mass_misses"]
    )


def test_fallback_poza_horyzontem_to_check_call_fold(mini_artifact: Path) -> None:
    """Poza zegarem warstw agent sprawdza all-in, a bez all-inu pasuje (jak mccfr)."""
    import random

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
        "from poker.blueprint_reader import BlueprintReader, StateBlock\n"
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
    # Odczytów stanu było tyle, ile decyzji poza horyzontem — zero pudeł
    # w warstwie pełnej jest więc twierdzeniem o czymś, a nie o pustce.
    reads = counters["from_artifact"] + counters["class_misses"] + counters["node_misses"]
    assert reads > 1000, counters
    assert counters["state_misses"] == 0, counters
    assert counters["full_layer_state_misses"] == 0, counters
    assert agent.layer_is_full(0) is False  # warstwa startowa: jeden stan
    assert agent.layer_is_full(20) is True


def test_rozjazd_areny_z_kolejnoscia_i_maska_treningu_jest_zerem(
    mini_artifact: Path,
) -> None:
    """Kryterium POKER-54, blokująco: trzy liczniki rozjazdu = 0 na artefakcie bramki.

    `out_of_order` i `order_collapse` to dwie twarze kolejności licytacji,
    `forced_action_misses` to wejście w gałąź za akcją wymuszoną maską (pytanie
    o darmowy call). Pomiar POKER-52 miał tu odpowiednio 21 348, 19 458
    i 1 092 wpisów na 1 582 048 decyzji; naprawiony rozgrywacz nie wytwarza
    żadnego z tych infosetów.

    Zero nie jest o pustce: ta sama próbka odwiedza węzły, na których rozjazd
    siedział — odpowiedź UTG na 3bet (węzły 9 i 10) i decyzję BB wobec 3betu
    (węzeł 8) — a każdy z trzech liczników ma osobny test wzrostu.
    """
    agent = _agent(mini_artifact)
    prizes = PAYOUTS["3x"].prizes
    for villain in (field_exploit(), dollar_fish(), always_jam()):
        for seed in range(25):
            play_block(agent, villain, prizes, 300 + seed)
    counters = agent.counters()
    assert counters["decisions"] > 500, counters
    assert counters["out_of_order"] == 0, counters
    assert counters["order_collapse"] == 0, counters
    assert counters["forced_action_misses"] == 0, counters
    assert counters["node_misses"] == counters["mode_flip_misses"], counters
    nodes = [node_slot(view)[0] for view in _spy_views(range(25), (field_exploit(), always_jam()))]
    assert {8, 9, 10} <= set(nodes), sorted(set(nodes))


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
    assert state_keys(deep, 2)[0] == (80, 0, 70)
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
    assert state_keys(view, agent.grid_step)[0] == (50, 50, 50)
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
    agent.state_block = lambda view: block  # type: ignore[method-assign]
    view = _view(hand=6, seat=0, button=1, bb=6, klass=klass, jamfold=True)
    assert agent.act(view, random.Random(0)) == "fold"
    counters = agent.counters()
    assert counters["mass_misses"] == 1, counters
    assert counters["grid_fallbacks"] == 1
    assert counters["mode_mismatches"] == 1  # open poza drzewem areny — też liczony


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
    agent.state_block = lambda view: block  # type: ignore[method-assign]
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


def test_agent_bierze_dokladnie_jeden_pobor_rng_na_decyzje(mini_artifact: Path) -> None:
    """Strumień losowań ręki ma być taki sam jak przy `SeatBook` na tym miejscu.

    `pick` bierze jeden pobór w każdej gałęzi; agent musi brać tyle samo —
    inaczej podmiana książki na agenta przesuwa decyzje PRZECIWNIKÓW w tej
    samej ręce i porównania na wspólnych seedach przestają być porównaniami.
    Test liczy pobory na wszystkich ścieżkach: z artefaktu i na każdym
    fallbacku (horyzont, stan, węzeł, klasa).
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
        _view(hand=30, bb=20, jammed=True),  # poza horyzontem warstw
        _view(hand=0, stacks=(0, 50, 100), seat=1, button=1, bb=2),  # stan spoza warstwy
        _view(hand=6, stacks=(50, 50, 50), bb=6, klass=168),  # klasa spoza artefaktu
    ]
    for view in views:
        agent.act(view, rng)
    counters = agent.counters()
    assert counters["decisions"] == len(views) == Counting.draws
    assert counters["from_artifact"] == 1
    assert counters["horizon_fallbacks"] == 1
    assert counters["state_misses"] == 1
    assert counters["class_misses"] == 1


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

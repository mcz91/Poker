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
from pathlib import Path
from typing import Any

import pytest

from poker.blueprint_agent import (
    NODES_3MAX,
    NODES_3MAX_OUT_OF_ORDER,
    NODES_HU,
    SLOT_FOLD,
    SLOT_JAM,
    SLOT_MID,
    BlueprintAgent,
    label_seats,
    node_slot,
    quantize_stacks,
    role_seats,
    state_keys,
)
from poker.blueprint_reader import BlueprintReader
from poker.spin import LEVELS, PAYOUTS, blinds_for_hand, roles
from poker.spin_arena import (
    SeatBook,
    SeatView,
    always_jam,
    dollar_fish,
    field_exploit,
    legal_actions,
    pick,
    play_block,
    run_spin,
)

REPO = Path(__file__).resolve().parent.parent
BLUEPRINT = REPO / "tools" / "blueprint"

# Rodzic slotu węzła w drzewie gry etapowej: węzeł → (rodzic, slot dojścia).
PARENT_3MAX = {
    1: (0, SLOT_FOLD), 2: (1, SLOT_MID), 3: (2, SLOT_MID), 4: (1, SLOT_JAM),
    5: (0, SLOT_MID), 6: (5, SLOT_FOLD), 7: (6, SLOT_MID), 8: (5, SLOT_MID),
    9: (8, SLOT_FOLD), 10: (8, SLOT_MID), 11: (0, SLOT_JAM), 12: (11, SLOT_FOLD),
    13: (11, SLOT_MID),
}
PARENT_HU = {1: (0, SLOT_MID), 2: (1, SLOT_MID), 3: (0, SLOT_JAM)}


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
    """
    book, villain = field_exploit(), dollar_fish()
    for seed in range(30):
        spy = Spy(book)
        plain, plain_decks = _run_seen((book, villain, villain), seed)
        ported, ported_decks = _run_seen((spy, villain, villain), seed)
        assert plain == ported, seed
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
    """Każdy kontekst licytacji areny trafia w węzeł, który trening naprawdę ma.

    Wyjątki są dwa i oba są rozjazdem areny z modelem, nie luzem odwzorowania:
    (1) kolejność po ponownym otwarciu licytacji — arena pyta UTG przed BB
    (`NODES_3MAX_OUT_OF_ORDER`); (2) arena pyta o akcję, którą trening wymusza
    maską (call za darmo), więc gałąź nie istnieje w drzewie. Test przybija, że
    NIE MA rozjazdów innego rodzaju, i że oba te rodzaje naprawdę występują.
    """
    config = _mini_config()
    views = _spy_views(range(40), (dollar_fish(), always_jam()))
    assert len(views) > 500
    seen_nodes: set[int] = set()
    out_of_order = 0
    forced_by_mask = 0
    cache: dict[tuple[Any, int], Any] = {}
    for view in views:
        node, in_model = node_slot(view)
        seen_nodes.add(node)
        key = state_keys(view, 1)[0]  # krok 1 = brak kwantyzacji: dokładne stacki areny
        cache_key = (key, view.hand)
        if cache_key not in cache:
            cache[cache_key] = _stage_problem(config, key, view.hand)
        problem = cache[cache_key]
        order = role_seats(view)
        if not in_model:
            out_of_order += 1
            assert _tree_node(problem, view, order)[1] != view.seat, view
            continue
        assert _tree_node(problem, view, order) == (node, view.seat), view
        if node in problem.nodes:
            continue
        parent, slot = (PARENT_3MAX if len(order) == 3 else PARENT_HU)[node]
        assert slot not in problem.allowed[parent], (view, node)
        forced_by_mask += 1
    assert out_of_order > 0, "kolejność licytacji areny nie rozjechała się ani razu"
    assert forced_by_mask > 0, "arena nie zapytała o żadną akcję wymuszoną w treningu"
    assert seen_nodes >= {0, 1, 2, 4, 5, 8, 11, 12, 13}, seen_nodes


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
        "from poker.blueprint_reader import BlueprintReader\n"
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

"""Agent areny Spin grający ze skwantowanego blueprintu (POKER-52).

Agent nie ma własnej strategii: każdą decyzję czyta z artefaktu `.bpk`
czytnikiem `poker.blueprint_reader` i losuje z odczytanego rozkładu rng-iem
akcji ręki. Cała trudność siedzi w trzech odwzorowaniach stanu areny na
model treningu (`tools/blueprint/solve_grid.py`), bo arena i trening opisują
tę samą grę w dwóch układach współrzędnych (numer ręki wchodzi do odwzorowań
1 i 2, więc przy odczycie cyklicznym role treningu liczą się z numeru WARSTWY,
a role areny — jak zawsze — z rotacji guzika areny):

1. **Zegar → warstwa.** Numer ręki turnieju jest numerem warstwy artefaktu,
   a ręka za ostatnią warstwą strategii czyta warstwę **cyklu punktu stałego**
   (POKER-55, decyzja 28 pkt 3): od ręki `CYCLE_BASE` blindy stoją, więc ręce
   dalsze żyją w tym samym stacjonarnym cyklu `CYCLE_LENGTH` rąk, którego
   punktem stałym jest brzeg horyzontu z POKER-49/50. Fallback pasywny zostaje
   dla ręki, której nawet warstwa cyklu nie ma (`LayerNotFound`/`PolicyMissing`).
2. **Stacki → klucz stanu.** Trening sadza guzik na miejscu `ręka % 3`
   (przy dwóch żywych: `sorted(żywi)[ręka % 2]`), a arena rotuje guzik po
   żywych miejscach, więc ten sam numer ręki opisuje w obu światach inny
   układ ról. Numery miejsc są jednak wyłącznie etykietami — model jest
   równoważny na ich permutacje (nagrody i ICM są symetryczne) — więc agent
   pyta artefakt o wektor stacków **przenumerowany** tak, żeby role
   treningu pokryły się z rolami areny, a potem kwantyzuje go metodą
   największych reszt z kroku siatki (`quantize_stacks`, kopia reguły
   treningu pod testem zgodności).
3. **Kontekst licytacji → slot węzła.** Drzewo areny (fold / open 2.2x /
   jam, potem fold / call-jam) jest tym samym drzewem, które solver opisuje
   14 slotami przy trzech żywych i 4 slotami w endgame'ie HU. Węzeł liczy
   się z ról i akcji już podjętych w ręce; miejsce all-in z samego blinda
   rozgrywacz pomija, a trening wymusza mu wejście maską akcji, więc agent
   dolicza mu akcję wymuszoną, inaczej trafiłby w zły slot. Gdy kwantyzacja
   zepchnie stan pod próg 7 bb, drzewo stanu w artefakcie jest jam/fold,
   choć arena z dokładnych stacków oferuje drzewo głębokie: rozkład jam/fold
   jest wtedy legalnym PODZBIOREM akcji areny ({jam, fold} ⊂ {jam, open,
   fold}), więc agent czyta bliźniaczy węzeł drzewa jam/fold (`jam_fold_slot`,
   otwarcie w historii czytane jako jam) zamiast wołać fallback — POKER-55,
   decyzja 28 pkt 2c.

Fallback jest jawny i policzalny, w rozłącznych licznikach: `horizon_fallbacks`
(ręka bez warstwy strategii nawet w cyklu — `LayerNotFound`/`PolicyMissing`),
`grid_fallbacks` (warstwa jest, ale artefakt nie ma tam strategii: stan spoza
warstwy, węzeł spoza maski, rozkład bez masy na akcjach legalnych)
i `class_misses` (klasa spoza zestawu policzonego w biegu — w artefakcie
produkcyjnym zawsze zero, bo liczy wszystkie 169). Każda ścieżka fallbacku gra
check-call → fold: gdy jedynym wejściem jest sprawdzenie all-inu, agent
sprawdza, inaczej pasuje.

Wierność artefaktowi tam, gdzie kiedyś był fallback, ma własne liczniki
(rosną dopiero wtedy, gdy rozkład naprawdę wraca do gry — po sprawdzeniu masy
na akcjach legalnych): `cyclic_reads` (decyzja zagrana z warstwy cyklu, czyli
ręka za horyzontem warstw), `mode_flip_reads` (decyzja zagrana z drzewa
jam/fold przy głębokim drzewie areny) i jego podzbiór `mode_flip_translated`
— odczyty, w których bliźniak jest INNYM węzłem niż węzeł areny, więc pula
modelu różni się od puli areny (patrz `jam_fold_slot`).

Liczniki diagnostyczne rozdzielają rozjazd areny z modelem treningu od braku
w artefakcie: `full_layer_state_misses` (stan spoza warstwy niosącej PEŁNĄ
siatkę — dopiero to jest błąd odwzorowania, bo warstwy wczesne bieg tnie
osiągalnością), `mode_flip_misses` (przeskok trybu, którego nie ratuje nawet
węzeł bliźniaczy: drzewo jam/fold nie ma tej historii albo jej węzła w masce)
i `mode_mismatches` (przeskok w drugą stronę: stan artefaktu głęboki, arena
jam/fold, więc rozkład niesie open, którego arena nie ma) oraz trzy liczniki
rozjazdu, który POKER-54 naprawił w rozgrywaczu: `out_of_order`,
`order_collapse` (kolejność licytacji po ponownym otwarciu — patrz
`NODES_3MAX_OUT_OF_ORDER`) i `forced_action_misses` (gałąź za akcją, którą
trening wymusza maską). Na naprawionym rozgrywaczu wszystkie trzy są zerami
i bramka trzyma je zerami; zostają, bo mierzą wejście areny w infoset, którego
model nie ma.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from poker.blueprint_reader import (
    BlueprintLookupError,
    BlueprintReader,
    LayerNotFound,
    NodeUnreachable,
    PolicyMissing,
    StateBlock,
    StateNotFound,
)
from poker.spin import HANDS_PER_LEVEL, LEVELS, is_jam_fold_depth, roles
from poker.spin_arena import SeatView, legal_actions

# Zegar blindów staje na ostatnim poziomie od ręki CYCLE_BASE (`blinds_for_hand`),
# więc ręce dalsze żyją w tym samym stacjonarnym cyklu CYCLE_LENGTH rąk co
# warstwy CYCLE_BASE…CYCLE_BASE + CYCLE_LENGTH − 1 (guzik treningu: warstwa ≡
# ręka mod 3, bo CYCLE_BASE ≡ 0). Oba warunki trzyma test bramki.
CYCLE_BASE = (len(LEVELS) - 1) * HANDS_PER_LEVEL
CYCLE_LENGTH = HANDS_PER_LEVEL

# Publiczne sloty węzłów drzewa 3-max i endgame'u HU — numeracja artefaktu
# (`tools/blueprint/solve_grid.py`); nazwy ról: U = UTG, T = guzik (płaci SB),
# B = duży blind, N = guzik w HU.
(
    N_U_ROOT,
    N_T_FI,
    N_B_VS_T_OPEN,
    N_T_VS_B_3BET,
    N_B_VS_T_JAM,
    N_T_VS_U_OPEN,
    N_B_VS_U_OPEN,
    N_U_VS_B_3BET,
    N_B_VS_U_OPEN_T_JAM,
    N_U_VS_T_3BET_B_FOLD,
    N_U_VS_T_3BET_B_CALL,
    N_T_VS_U_JAM,
    N_B_VS_U_JAM_T_FOLD,
    N_B_VS_U_JAM_T_CALL,
) = range(14)
H_ROOT, H_B_VS_OPEN, H_N_VS_3BET, H_B_VS_JAM = range(4)

# Sloty akcji artefaktu: 0 = fold, 1 = open (w korzeniach) albo call, 2 = jam.
SLOT_FOLD, SLOT_MID, SLOT_JAM = 0, 1, 2

# Korzenie: tam slot środkowy to podbicie 2.2x, w pozostałych węzłach — call.
ROOTS_3MAX = frozenset({N_U_ROOT, N_T_FI})
ROOTS_HU = frozenset({H_ROOT})

# Klucz: (rola decydująca, akcje ról w kolejności U/T/B; None = jeszcze nie grał).
Key3 = tuple[int, str | None, str | None, str | None]
NODES_3MAX: dict[Key3, int] = {
    (0, None, None, None): N_U_ROOT,
    (0, "open", "fold", "jam"): N_U_VS_B_3BET,
    (0, "open", "jam", "fold"): N_U_VS_T_3BET_B_FOLD,
    (0, "open", "jam", "jam"): N_U_VS_T_3BET_B_CALL,
    (1, "fold", None, None): N_T_FI,
    (1, "fold", "open", "jam"): N_T_VS_B_3BET,
    (1, "open", None, None): N_T_VS_U_OPEN,
    (1, "jam", None, None): N_T_VS_U_JAM,
    (2, "fold", "open", None): N_B_VS_T_OPEN,
    (2, "fold", "jam", None): N_B_VS_T_JAM,
    (2, "open", "fold", None): N_B_VS_U_OPEN,
    (2, "open", "jam", None): N_B_VS_U_OPEN_T_JAM,
    (2, "jam", "fold", None): N_B_VS_U_JAM_T_FOLD,
    (2, "jam", "jam", None): N_B_VS_U_JAM_T_CALL,
}

Key2 = tuple[int, str | None, str | None]
NODES_HU: dict[Key2, int] = {
    (0, None, None): H_ROOT,
    (0, "open", "jam"): H_N_VS_3BET,
    (1, "open", None): H_B_VS_OPEN,
    (1, "jam", None): H_B_VS_JAM,
}

# Kolejność areny po ponownym otwarciu licytacji rozjeżdżała się z modelem
# treningu i z regułą „akcja idzie od agresora" (decyzja 28 pkt 2a); rozgrywacz
# jest naprawiony (POKER-54, `spin_arena.speaking_order`), więc oba poniższe
# rozjazdy są w bramce zerami — tablica i liczniki zostają jako niezmiennik,
# bo to one świadczą, że kolejność areny nadal zgadza się z modelem.
# Rozjazd ma DWIE twarze i obie mają osobny licznik:
#
# * ORDER_SWAP — gdy T jamuje na open UTG, `to_act` pyta najpierw UTG, choć
#   trening pyta najpierw BB (węzeł 8). Ten infoset areny nie ma odpowiednika
#   w artefakcie; agent czyta gałąź, w której BB jeszcze nic nie dołożył
#   (węzeł 9), bo tam pula modelu zgadza się z pulą areny w chwili decyzji.
# * ORDER_COLLAPSE — BB pytany PO odpowiedzi UTG na ten sam 3bet. Klucz węzła
#   opisują pierwsze akcje ról, więc druga akcja UTG do niego nie wchodzi:
#   dwa różne infosety areny (UTG spasował / UTG sprawdził) czytają ten sam
#   węzeł 8, a jego pula modelowa jest inna niż pula areny. Wykrywa to
#   niezużyta historia ręki — akcja, której ścieżka drzewa nie konsumuje.
ORDER_SWAP = "order_swap"
ORDER_COLLAPSE = "order_collapse"

NODES_3MAX_OUT_OF_ORDER: dict[Key3, int] = {
    (0, "open", "jam", None): N_U_VS_T_3BET_B_FOLD,
}


def cyclic_hand(hand: int) -> int:
    """Ręka → ręka cyklu punktu stałego horyzontu (decyzja 28 pkt 3).

    Ręka w pierwszym cyklu jest sobie równa; dalsza wraca do warstwy tego
    samego miejsca w cyklu, bo od `CYCLE_BASE` blindy nie rosną, a warstwy
    cyklu są policzone przeciw punktowi stałemu horyzontu.

    Cena przekładu jest ZMIERZONA, nie oszacowana rzędem wielkości (decyzja 28
    pkt 3, KOREKTA F2 audytu POKER-55): niezgodność V między warstwami cyklu
    dla tej samej sytuacji fizycznej wynosi na artefakcie produkcyjnym
    średnio 1,22e−3 i maks 1,67e−2 udziału puli przy trzech żywych
    (6,58e−3 dla stacków ≥ 20 żetonów), a w HU maks 9,98e−4. Odniesienie:
    wpływ całej reguły awaryjnej po tej zmianie jest nieodróżnialny od zera
    w CI (blok POKER-55 pkt 9). Komenda pomiaru w bloku POKER-55 pkt 1.
    """
    if hand < CYCLE_BASE + CYCLE_LENGTH:
        return hand
    return CYCLE_BASE + (hand - CYCLE_BASE) % CYCLE_LENGTH


def quantize_stacks(stacks: tuple[int, int, int], step: int) -> tuple[int, int, int]:
    """Kwantyzacja największych reszt: suma stała, krok siatki, żywy zostaje żywy.

    Reguła treningu (`solve_grid.quantize_stacks`) przepisana do pakietu, bo
    silnik nie importuje `tools`; zgodność obu kopii trzyma test bramki.
    """
    total = sum(stacks)
    if total % step != 0:
        raise ValueError(f"suma żetonów {total} niepodzielna przez krok {step}")
    base = [value // step for value in stacks]
    remainder = total // step - sum(base)
    order = sorted(range(3), key=lambda seat: (-(stacks[seat] % step), seat))
    quantized = base[:]
    for seat in order[:remainder]:
        quantized[seat] += 1
    result = [units * step for units in quantized]
    for seat in range(3):
        while stacks[seat] > 0 and result[seat] == 0:
            donor = max(
                (index for index in range(3) if result[index] > step),
                key=lambda index: (result[index], -index),
            )
            result[donor] -= step
            result[seat] += step
    return (result[0], result[1], result[2])


def role_seats(view: SeatView) -> tuple[int, ...]:
    """Miejsca areny w kolejności ról: (UTG, guzik, BB) albo (guzik, BB) w HU."""
    live = [seat for seat in range(3) if view.stacks[seat] > 0]
    if len(live) < 2:
        raise ValueError(f"ręka bez dwóch żywych miejsc: {view.stacks}")
    if len(live) == 3:
        utg, button, big = roles(view.button)
        return (utg, button, big)
    return (view.button, next(seat for seat in live if seat != view.button))


def label_seats(view: SeatView, layer: int) -> tuple[tuple[int, ...], ...]:
    """Przenumerowania miejsc na etykiety artefaktu: `out[i][etykieta] = miejsce`.

    Trening wiąże role z numerami miejsc (guzik = `warstwa % 3`, w HU guzik =
    `sorted(żywi)[warstwa % 2]`), a arena rotuje guzik po żywych, więc ten sam
    układ sił opisują w obu światach inne numery miejsc. Przenumerowanie jest
    permutacją, na którą model jest równoważny (nagrody i ICM symetryczne),
    i jedynym sposobem, żeby rola areny czytała rozkład swojej roli.

    Role treningu liczą się z numeru CZYTANEJ WARSTWY, nie z numeru ręki areny:
    przy odczycie cyklicznym (ręka ≥ `CYCLE_BASE + CYCLE_LENGTH`) te numery są
    różne, a rozkłady w warstwie opisują role po jej własnej regule. Przy
    trzech żywych obie reguły i tak dają to samo (cykl ma długość 3, więc
    warstwa ≡ ręka mod 3), ale w HU guzik zmienia się co rękę i pomyłka
    posadziłaby guzika areny na etykiecie dużego blinda.

    Przy trzech żywych warunek „role treningu = role areny" wyznacza dokładnie
    jedną permutację (rotację o `guzik − warstwa % 3`). W HU warunek wiąże tylko
    porządek dwóch żywych etykiet, więc etykieta wybitego miejsca zostaje
    wolna: wszystkie trzy warianty opisują tę samą sytuację, ale warstwy rąk
    1–5 niosą wyłącznie stany osiągalne w treningu, więc nie muszą zawierać
    tego wariantu, który akurat wskazał numer miejsca areny. Kolejność jest
    stała (najpierw wariant z etykietą wybitego miejsca areny), a konsument
    bierze pierwszy obecny w warstwie.
    """
    live = [seat for seat in range(3) if view.stacks[seat] > 0]
    if len(live) == 3:
        shift = (view.button - layer % 3) % 3
        return (tuple((label + shift) % 3 for label in range(3)),)
    button, other = role_seats(view)
    dead = next(seat for seat in range(3) if view.stacks[seat] == 0)
    out = []
    for empty in (dead, *(seat for seat in range(3) if seat != dead)):
        low, high = (label for label in range(3) if label != empty)
        seat_of_label = [dead, dead, dead]
        seat_of_label[low if layer % 2 == 0 else high] = button
        seat_of_label[high if layer % 2 == 0 else low] = other
        seat_of_label[empty] = dead
        out.append(tuple(seat_of_label))
    return tuple(out)


def state_keys(view: SeatView, layer: int, step: int) -> tuple[tuple[int, int, int], ...]:
    """Klucze siatki równoważne temu stanowi w tej warstwie — pierwszy kanoniczny."""
    return tuple(
        quantize_stacks(
            (
                view.stacks[seat_of_label[0]],
                view.stacks[seat_of_label[1]],
                view.stacks[seat_of_label[2]],
            ),
            step,
        )
        for seat_of_label in label_seats(view, layer)
    )


def taken_actions(view: SeatView, order: tuple[int, ...]) -> tuple[str | None, ...]:
    """Pierwsza akcja każdej roli w tej ręce; `None` = rola jeszcze nie grała.

    Ścieżkę drzewa wyznaczają pierwsze akcje ról — druga akcja roli jest
    w modelu treningu zawsze terminalna, więc nie ma czego opisywać. Miejsce
    all-in z samego blinda nie ma wpisu w historii, bo nie ma czym zagrać:
    trening wymusza mu wejście maską akcji, więc jego kolejka liczy się jako
    wejście (`jam`). Miejsce wpuszczone za darmo (dołożenie zero) wpis MA —
    rozgrywacz o nie nie pyta, ale zapisuje mu wejście, więc niczego nie
    trzeba doliczać. Wymuszenie dolicza się wyłącznie rolom, których kolejka
    już minęła: przed pierwszą akcją decydenta późniejsze role jeszcze nie
    grały, a przy DRUGIEJ akcji decydenta wymuszenia nie ma w ogóle — druga
    akcja istnieje tylko po otwarciu, otwarcie tylko poza trybem jam/fold,
    a tam każdy żywy stack przekracza 7 bb, więc nikt nie jest all-in z blinda
    (oba warunki pod testem właściwościowym w bramce).
    """
    first: dict[int, str] = {}
    for seat, action in view.actions:
        first.setdefault(seat, action)
    actor = order.index(view.seat)
    out: list[str | None] = []
    for index, seat in enumerate(order):
        if seat in first:
            out.append(first[seat])
        elif index < actor and view.contrib[seat] >= view.stacks[seat]:
            out.append("jam")
        else:
            out.append(None)
    return tuple(out)


def stale_history(view: SeatView) -> bool:
    """Czy w historii ręki jest akcja, której klucz węzła nie konsumuje.

    Klucz opisują PIERWSZE akcje ról, bo w modelu treningu druga akcja roli
    jest terminalna. Rozgrywacz sprzed POKER-54 pytał po jamie BTN najpierw
    UTG, a dopiero potem BB — i wtedy druga akcja UTG zostawała poza kluczem,
    choć w arenie już padła. Naprawiona kolejność takich historii nie
    wytwarza, więc predykat jest tu strażnikiem: gdyby kolejność areny znów
    się rozjechała, kolaps infosetów byłby policzony, a nie przemilczany.
    """
    seats = [seat for seat, _ in view.actions]
    return len(seats) > len(set(seats))


def node_slot(view: SeatView) -> tuple[int, str | None]:
    """(slot węzła artefaktu, przyczyna rozjazdu albo `None` przy zgodności).

    Przyczyna jest jedną z `ORDER_SWAP` / `ORDER_COLLAPSE` — obie opisują tę
    samą usterkę kolejności licytacji areny (decyzja 28 pkt 2a), ale są
    rozłączne: pierwsza pyta wcześniej niż model, druga czyta węzeł modelu
    po odpowiedzi, której ten węzeł nie zna. Na rozgrywaczu po POKER-54 obie
    są nieosiągalne i bramka trzyma je zerami.
    """
    order = role_seats(view)
    actor = order.index(view.seat)
    taken = taken_actions(view, order)
    collapse = ORDER_COLLAPSE if stale_history(view) else None
    if len(order) == 2:
        key2: Key2 = (actor, taken[0], taken[1])
        node = NODES_HU.get(key2)
        if node is None:
            raise ValueError(f"kontekst HU bez slotu w modelu treningu: {key2}")
        return node, collapse
    key3: Key3 = (actor, taken[0], taken[1], taken[2])
    node = NODES_3MAX.get(key3)
    if node is not None:
        return node, collapse
    node = NODES_3MAX_OUT_OF_ORDER.get(key3)
    if node is None:
        raise ValueError(f"kontekst licytacji bez slotu w modelu treningu: {key3}")
    return node, ORDER_SWAP


def jam_fold_slot(view: SeatView) -> int | None:
    """Slot węzła drzewa JAM/FOLD dla tej historii albo `None`, gdy go tam nie ma.

    Kwantyzacja bywa jednostronna: stan artefaktu jest jam/fold, a arena
    z dokładnych stacków gra drzewem głębokim (decyzja 28 pkt 2c). Drzewo
    jam/fold jest drzewem głębokim bez otwarcia, więc tę samą historię opisuje
    w nim ścieżka, w której otwarcie jest jamem — i to jest cała reguła
    przekładu. Ścieżki, których w drzewie jam/fold nie ma, dają `None`: to
    DRUGIE wejście roli, która otworzyła (w jam/fold jest ono terminalne).
    Agent w stanie jam/fold nigdy nie otwiera, więc drugiego wejścia nie ma —
    ale `None` zostaje jawne, bo alternatywą byłby cichy zły węzeł.

    Granica przekładu (F1 audytu POKER-55): bliźniak ma te same AKCJE, ale nie
    tę samą PULĘ — w węźle po jamie model widzi wkład całego stacku agresora,
    a arena tylko jego otwarcie. To ta sama klasa rozjazdu co `ORDER_COLLAPSE`
    (decyzja 28 pkt 2a KOREKTA), w mniejszej skali; dlatego przekład ma własny
    licznik (`mode_flip_translated`) rozłączny od odczytów, w których bliźniak
    jest tym samym węzłem co węzeł areny.
    """
    order = role_seats(view)
    actor = order.index(view.seat)
    taken = tuple(
        "jam" if action == "open" else action for action in taken_actions(view, order)
    )
    if len(order) == 2:
        return NODES_HU.get((actor, taken[0], taken[1]))
    return NODES_3MAX.get((actor, taken[0], taken[1], taken[2]))


class NoLegalMass(BlueprintLookupError):
    """Rozkład artefaktu bez masy na akcjach legalnych w arenie."""


class ClassMissing(BlueprintLookupError):
    """Klasa ręki poza zestawem klas policzonym w biegu artefaktu."""


def passive_action(view: SeatView) -> str:
    """Fallback check-call → fold w zamrożonym drzewie: sprawdź all-in albo pasuj."""
    return "jam" if view.jammed else "fold"


class BlueprintAgent:
    """Miejsce areny grające rozkładami z artefaktu blueprintu.

    Czytnik dostaje otwarty strumień (INV-P7), więc plik otwiera konsument —
    tu: `tools/run_arena.py`. Agent jest stanowy wyłącznie w licznikach; sama
    decyzja jest funkcją widoku, artefaktu i rng-a ręki, więc rotacje bloku
    i replay zostają deterministyczne.
    """

    def __init__(
        self, reader: BlueprintReader, *, grid_step: int, classes: Sequence[int]
    ) -> None:
        self.reader = reader
        self.grid_step = grid_step
        # Bieg artefaktu liczy wybrany zestaw klas preflop (produkcja: wszystkie
        # 169), a kolumna bloku jest pozycją klasy w tym zestawie, nie numerem
        # klasy — mapa jest jedynym miejscem, które o tym wie.
        self.column = {klass: index for index, klass in enumerate(classes)}
        # Warstwa „pełna" to warstwa o największej liczbie stanów: bieg tnie
        # wczesne warstwy osiągalnością, więc dopiero pudło w warstwie pełnej
        # jest sygnałem błędu odwzorowania, a nie granicy artefaktu.
        self.full_layer_states = max(
            layer.n_states for layer in reader.layers if layer.has_policy
        )
        # Ręka z własną warstwą strategii czyta ją wprost; dopiero ręka spoza
        # tego zbioru idzie do warstwy cyklu punktu stałego.
        self.policy_hands = frozenset(
            layer.hand for layer in reader.layers if layer.has_policy
        )
        if len(self.column) != reader.n_classes:
            raise ValueError(
                f"zestaw {len(self.column)} klas nie opisuje {reader.n_classes} kolumn artefaktu"
            )
        self.decisions = 0
        self.from_artifact = 0
        self.cyclic_reads = 0
        self.mode_flip_reads = 0
        self.mode_flip_translated = 0
        self.grid_fallbacks = 0
        self.horizon_fallbacks = 0
        self.state_misses = 0
        self.node_misses = 0
        self.mass_misses = 0
        self.class_misses = 0
        self.full_layer_state_misses = 0
        self.mode_flip_misses = 0
        self.forced_action_misses = 0
        self.mode_mismatches = 0
        self.out_of_order = 0
        self.order_collapse = 0

    def counters(self) -> dict[str, int]:
        return {
            "decisions": self.decisions,
            "from_artifact": self.from_artifact,
            "cyclic_reads": self.cyclic_reads,
            "mode_flip_reads": self.mode_flip_reads,
            "mode_flip_translated": self.mode_flip_translated,
            "grid_fallbacks": self.grid_fallbacks,
            "horizon_fallbacks": self.horizon_fallbacks,
            "state_misses": self.state_misses,
            "node_misses": self.node_misses,
            "mass_misses": self.mass_misses,
            "class_misses": self.class_misses,
            "full_layer_state_misses": self.full_layer_state_misses,
            "mode_flip_misses": self.mode_flip_misses,
            "forced_action_misses": self.forced_action_misses,
            "mode_mismatches": self.mode_mismatches,
            "out_of_order": self.out_of_order,
            "order_collapse": self.order_collapse,
        }

    def act(self, view: SeatView, rng: random.Random) -> str:
        """Decyzja z artefaktu albo fallback — zawsze jeden pobór z rng.

        Stały pobór trzyma strumień losowań ręki taki sam, jak przy `SeatBook`
        na tym miejscu, więc podmiana agenta nie przesuwa decyzji przeciwników
        i porównania na wspólnych seedach zostają porównaniami.
        """
        self.decisions += 1
        try:
            mass = self.action_mass(view)
        except (LayerNotFound, PolicyMissing):
            self.horizon_fallbacks += 1
            rng.random()
            return passive_action(view)
        except ClassMissing:
            self.class_misses += 1
            rng.random()
            return passive_action(view)
        except BlueprintLookupError as miss:
            self.grid_fallbacks += 1
            if isinstance(miss, NodeUnreachable):
                self.node_misses += 1
                # Węzeł spoza maski stanu ma dwie rozłączne przyczyny: przeskok
                # trybu przy kwantyzacji, którego nie uratował węzeł bliźniaczy
                # (POKER-55), albo wejście areny w gałąź za akcją, którą maska
                # treningu wymusza — to drugie znikło razem z pytaniem
                # o darmowy call (POKER-54).
                if self.mode_flipped(view):
                    self.mode_flip_misses += 1
                else:
                    self.forced_action_misses += 1
            elif isinstance(miss, NoLegalMass):
                self.mass_misses += 1
            else:
                self.state_misses += 1
                if self.layer_is_full(self.layer_hand(view.hand)):
                    self.full_layer_state_misses += 1
            rng.random()
            return passive_action(view)
        self.from_artifact += 1
        return sample(mass, rng)

    def layer_hand(self, hand: int) -> int:
        """Numer warstwy, z której czyta ta ręka — wprost albo z cyklu horyzontu.

        Warstwa cyklu wchodzi dopiero tam, gdzie artefakt nie ma własnej
        warstwy strategii; artefakt sięgający dalej czyta się wprost.
        """
        if hand in self.policy_hands:
            return hand
        return cyclic_hand(hand)

    def layer_is_full(self, hand: int) -> bool:
        """Czy warstwa tej ręki niesie pełną siatkę stanów.

        Warstwy wczesne bieg tnie osiągalnością (blok POKER-50), więc stan
        spoza WARSTWY PEŁNEJ to co innego niż stan spoza warstwy przyciętej:
        pierwsze jest błędem odwzorowania, drugie granicą artefaktu.
        """
        for layer in self.reader.layers:
            if layer.hand == hand:
                return layer.n_states >= self.full_layer_states
        return False

    def state_is_jam_fold(self, view: SeatView, layer: int) -> bool:
        """Czy drzewo STANU ARTEFAKTU jest jam/fold (próg liczony po kwantyzacji).

        Wszystkie równoważne klucze są permutacjami tego samego wektora, więc
        próg 7 bb rozstrzyga się na kanonicznym.
        """
        return is_jam_fold_depth(state_keys(view, layer, self.grid_step)[0], view.bb)

    def mode_flipped(self, view: SeatView) -> bool:
        """Czy kwantyzacja przerzuciła stan przez próg jam/fold.

        Arena liczy próg z dokładnych stacków, trening ze skwantowanych, więc
        tuż nad progiem drzewo areny jest głębokie, a drzewo stanu artefaktu —
        jam/fold (i nie ma węzłów po open).
        """
        layer = self.layer_hand(view.hand)
        return self.state_is_jam_fold(view, layer) != view.jamfold

    def state_block(self, view: SeatView, layer: int) -> StateBlock:
        """Blok stanu spod pierwszej równoważnej etykiety obecnej w warstwie."""
        missing: StateNotFound | None = None
        for key in state_keys(view, layer, self.grid_step):
            try:
                return self.reader.state(layer, key)
            except StateNotFound as miss:
                missing = miss
        assert missing is not None, "lista kluczy stanu nigdy nie jest pusta"
        raise missing

    def action_mass(self, view: SeatView) -> dict[str, float]:
        """Rozkład z artefaktu przeniesiony na legalne akcje areny.

        Slot środkowy znaczy „podbij" wyłącznie w korzeniu drzewa GŁĘBOKIEGO;
        w drzewie jam/fold i poza korzeniem znaczy „sprawdź all-in", więc scala
        się ze slotem jamu w jedną akcję areny. Stąd stan jam/fold nigdy nie
        wypuszcza open — także wtedy, gdy arena jest głęboka po przeskoku
        trybu, a agent czyta bliźniaczy węzeł jam/fold (`jam_fold_slot`).
        Rozkład przycina `legal_actions`: przeskok w drugą stronę (stan
        artefaktu głęboki, arena jam/fold) daje open, którego arena nie ma —
        to jest liczone (`mode_mismatches`), a nie przemilczane.

        Liczniki odczytu rosną na końcu, po sprawdzeniu masy: mają znaczyć
        „decyzja zagrana z artefaktu", a nie „próba odczytu" (F3 audytu).
        """
        layer = self.layer_hand(view.hand)
        node, divergence = node_slot(view)
        if divergence == ORDER_SWAP:
            self.out_of_order += 1
        elif divergence == ORDER_COLLAPSE:
            self.order_collapse += 1
        jam_fold_state = self.state_is_jam_fold(view, layer)
        arena_node = node
        twin = jam_fold_slot(view) if jam_fold_state and not view.jamfold else None
        if twin is not None:
            node = twin
        # Kolejność ma znaczenie diagnostyczne: najpierw stan i węzeł (tam żyje
        # odwzorowanie), dopiero potem klasa (tam żyje zakres biegu artefaktu).
        block = self.state_block(view, layer)
        column = self.column.get(view.klass)
        if column is None:
            raise ClassMissing(f"klasa {view.klass} poza zestawem klas artefaktu")
        probs = block.policy(node, column)
        live = sum(1 for seat in range(3) if view.stacks[seat] > 0)
        root = not jam_fold_state and node in (ROOTS_3MAX if live == 3 else ROOTS_HU)
        mass = {"fold": probs[SLOT_FOLD], "jam": probs[SLOT_JAM]}
        if root:
            mass["open"] = probs[SLOT_MID]
        else:
            mass["jam"] += probs[SLOT_MID]
        legal = legal_actions(view)
        if mass.get("open", 0.0) > 0.0 and "open" not in legal:
            self.mode_mismatches += 1
        mass = {action: value for action, value in mass.items() if action in legal}
        if sum(mass.values()) <= 0.0:
            raise NoLegalMass(
                f"rozkład węzła {node} klasy {view.klass} nie ma masy na akcjach {legal}"
            )
        # Liczniki odczytu rosną DOPIERO tutaj: opisują decyzję zagraną
        # z artefaktu, a nie próbę odczytu, więc żadna ścieżka fallbacku ich
        # nie dotyka (F3 audytu POKER-55).
        if layer != view.hand:
            self.cyclic_reads += 1
        if twin is not None:
            self.mode_flip_reads += 1
            if twin != arena_node:
                self.mode_flip_translated += 1
        return mass


def sample(mass: dict[str, float], rng: random.Random) -> str:
    """Losowanie z rozkładu jednym poborem rng — porządek akcji stały."""
    total = sum(mass.values())
    point = rng.random() * total
    seen = 0.0
    chosen = "fold"
    for action in ("fold", "open", "jam"):
        if action not in mass:
            continue
        chosen = action
        seen += mass[action]
        if point < seen:
            return action
    return chosen

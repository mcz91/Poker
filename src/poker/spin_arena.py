"""Spin ROI arena. Hero vs scripted fish. Unit is buy-in, not BB/100.

Jednostką statystyczną jest blok: ten sam seed turnieju rozegrany
w trzech rotacjach cyklicznych (hero kolejno na każdym miejscu) przy tej
samej sekwencji kart. Talia i losowość akcji ręki `i` pochodzą wyłącznie
od pary (seed turnieju, `i`), więc przebieg licytacji jednej rotacji nie
zmienia kart żadnej innej. CI liczone są na blokach (decyzja 26 zakazuje
CI na turniejach i rozdaniach), obok normalnego raportowany jest
bootstrap percentylowy o jawnym seedzie.

Miejsce obsadza `SeatBook` (statyczne częstotliwości per klasa ręki) albo
stanowy `SeatAgent`, który dostaje pełny widok miejsca (`SeatView`) i rng
akcji ręki. Oba źródła decyzji chodzą po tym samym, zamrożonym drzewie
(decyzja 27): zbiór legalnych akcji liczy `legal_actions`, a rozgrywacz
odrzuca akcję spoza niego.

Kolejność głosu jest regułą pokera, nie kolejką ról: akcja idzie na lewo od
tego, kto właśnie zagrał, więc po przebiciu pyta się pierwszego
niedopasowanego gracza na lewo od agresora (`speaking_order`). Gracz, którego
dołożenie do najwyższego wkładu wynosi zero, nie jest pytany — wchodzi do puli
za darmo, bo fold nic by mu nie oszczędził (POKER-54, decyzja 28 pkt 2a i 2b);
nie ma znaczenia, czy stoi przebicie, bo najwyższym wkładem bywa cudzy blind.
Takie wejście jest zawsze OSTATNIĄ akcją ręki (każdy, kto mógłby mówić po nim,
wpłacił mniej, a wpłacił mniej tylko będąc all-in albo już zagrawszy), więc
widać je wyłącznie w obserwatorze `on_action` — nie w widoku kolejnej decyzji.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from poker.cards import Card
from poker.dealing import shuffled_deck
from poker.evaluation import HandValue, evaluate_best
from poker.openfold import WEIGHTS, _hu
from poker.preflop import CLASS_INDEX, classify
from poker.spin import (
    STARTING_CHIPS,
    award_allin,
    blinds_for_hand,
    is_jam_fold_depth,
    open_amount,
    roles,
)

N_HANDS = 169
ZERO = [0.0] * N_HANDS
ONE = [1.0] * N_HANDS
HAND_GUARD = 80
ROTATIONS = 3
BOOTSTRAP_REPLICATIONS = 1000


@dataclass(frozen=True)
class SeatBook:
    open: list[float]
    overjam: list[float]
    vs_open: list[float]
    vs_jam: list[float]
    jf_first: list[float]
    jf_vs_jam: list[float]


@dataclass(frozen=True)
class SeatView:
    """Stan ręki widziany przez jedno miejsce w chwili decyzji.

    `SeatBook` konsumuje trzy flagi kontekstu i klasę ręki, bo nic więcej nie
    umie użyć; agent czytający blueprint potrzebuje zegara (numer ręki),
    wektora stacków i historii licytacji, żeby trafić w warstwę, stan i węzeł
    artefaktu. `stacks` to stan sprzed postawienia blindów, `contrib` —
    wkłady już w puli, `actions` — akcje ręki w kolejności podjęcia
    (miejsce, akcja); miejsce all-in z samego blinda nie ma w nich wpisu, bo
    nie ma czym zagrać, a wejście za darmo ma, choć rozgrywacz o nie nie pyta
    — jest akcją ręki i tak trzyma `actions` pełną historią licytacji, nawet
    jeśli dziś żaden widok już po nim nie powstaje. `bb` to duży blind tej
    ręki — z niego i ze
    stacków liczy się próg jam/fold, więc bez niego agent nie umiałby
    powiedzieć, czy artefakt opisuje ten sam tryb drzewa co arena.
    """

    hand: int
    seat: int
    button: int
    stacks: tuple[int, int, int]
    contrib: tuple[int, int, int]
    actions: tuple[tuple[int, str], ...]
    bb: int
    klass: int
    jamfold: bool
    opened: bool
    jammed: bool


class SeatAgent(Protocol):
    """Stanowy port decyzji: widok miejsca i rng ręki → akcja legalna."""

    def act(self, view: SeatView, rng: random.Random) -> str: ...


Seat = SeatBook | SeatAgent

# Czysta obserwacja licytacji: (widok miejsca w chwili akcji, akcja, czy
# rozgrywacz o nią PYTAŁ) — bez wpływu na przebieg, wzorem `on_deck`. Bez niej
# wejście za darmo jest niewidoczne z zewnątrz: jest zawsze ostatnią akcją
# ręki, więc nie trafia do widoku żadnej następnej decyzji (F4 audytu
# POKER-54). Widok jest stanem SPRZED akcji, więc obserwator odtwarza z niego
# ten sam węzeł modelu, co agent w chwili decyzji.
OnAction = Callable[[SeatView, str, bool], None]


def speaking_order(order: Sequence[int], last_actor: int) -> tuple[int, ...]:
    """Kolejka głosu po `last_actor`: `order` obrócone tak, by zaczynać na jego lewej.

    Jedyne źródło prawdy o kolejności licytacji. `order` to miejsca ręki
    w kolejności ról (UTG, guzik, BB — a po wybiciu guzik, BB), więc obrót
    o pozycję ostatniego grającego daje regułę pokera „akcja idzie w lewo":
    rundę otwiera lewa strona BB (blind jest ostatnim głosem przed pierwszą
    decyzją), a po przebiciu głos ma pierwszy niedopasowany gracz na lewo od
    agresora — nie stała kolejka od UTG (decyzja 28 pkt 2a).
    """
    index = order.index(last_actor)
    return (*order[index + 1 :], *order[: index + 1])


def legal_actions(view: SeatView) -> tuple[str, ...]:
    """Akcje zamrożonego drzewa w tym kontekście — dokładnie zbiór wyjść `pick`.

    Jedno źródło prawdy o legalności: rozgrywacz sprawdza nim decyzję agenta,
    a agent nim przycina rozkład z artefaktu.
    """
    if view.jammed or view.opened or view.jamfold:
        return ("fold", "jam")
    return ("fold", "open", "jam")


def always_jam() -> SeatBook:
    return SeatBook(ZERO, ONE, ONE, ONE, ONE, ONE)


def always_fold() -> SeatBook:
    return SeatBook(ZERO, ZERO, ZERO, ZERO, ZERO, ZERO)


def call_vs_random(thresh: float = 0.50) -> list[float]:
    """Call a 100% jammer when equity vs random ≥ thresh."""
    tot = float(sum(WEIGHTS))
    out = [0.0] * N_HANDS
    for i in range(N_HANDS):
        eq = sum(WEIGHTS[j] * _hu(i, j) for j in range(N_HANDS)) / tot
        out[i] = 1.0 if eq >= thresh else 0.0
    return out


def range_vs_random(thresh: float) -> list[float]:
    return call_vs_random(thresh)


def field_exploit() -> SeatBook:
    """Population exploit for $1: steal wide, 3bet wide, call jams vs random."""
    steal = range_vs_random(0.50)
    premium = range_vs_random(0.62)
    three = range_vs_random(0.53)
    call = range_vs_random(0.50)
    short = range_vs_random(0.48)
    return SeatBook(steal, premium, three, call, short, call)


def dollar_fish() -> SeatBook:
    """$1-ish: opens too wide, under-3bets (would flat), calls jams too wide."""
    open_r = range_vs_random(0.485)
    three = range_vs_random(0.58)
    call = range_vs_random(0.51)
    short = range_vs_random(0.46)
    return SeatBook(open_r, ZERO, three, call, short, call)


def wide_call(p: float = 0.45) -> SeatBook:
    freq = [p] * N_HANDS
    return SeatBook(freq, freq, freq, freq, freq, freq)


def _alive(stacks: list[int]) -> list[int]:
    return [i for i in range(3) if stacks[i] > 0]


def _next_button(stacks: list[int], current: int, first: bool) -> int:
    if first:
        return current
    for k in range(1, 4):
        b = (current + k) % 3
        if stacks[b] > 0:
            return b
    return current


def pick(
    book: SeatBook,
    idx: int,
    *,
    jamfold: bool,
    opened: bool,
    jammed: bool,
    rng: random.Random,
) -> str:
    if jammed:
        freq = book.jf_vs_jam if jamfold else book.vs_jam
        return "jam" if rng.random() < freq[idx] else "fold"
    if opened:
        return "jam" if rng.random() < book.vs_open[idx] else "fold"
    if jamfold:
        return "jam" if rng.random() < book.jf_first[idx] else "fold"
    x = rng.random()
    j = book.overjam[idx]
    o = book.open[idx]
    if x < j:
        return "jam"
    if x < j + o:
        return "open"
    return "fold"


def _hand_seeds(seed: int) -> tuple[tuple[int, int], ...]:
    """(seed talii, seed akcji) ręki `i` — funkcja wyłącznie seeda turnieju.

    Wzorzec `poker.table`: seedy rąk pochodne od seeda meczu. Jeden RNG na
    cały turniej wiązałby karty ręki `i+1` z liczbą losowań akcji ręki `i`,
    więc rotacja miejsc zmieniałaby sekwencję kart.
    """
    rng = random.Random(seed)
    return tuple((rng.getrandbits(64), rng.getrandbits(64)) for _ in range(HAND_GUARD))


def run_spin(
    books: tuple[Seat, Seat, Seat],
    seed: int,
    *,
    on_deck: Callable[[int, tuple[Card, ...]], None] | None = None,
    on_action: OnAction | None = None,
) -> tuple[tuple[int, int, int], str]:
    """Stacki końcowe i powód końca: "bust" (≤1 żywy) albo "guard" (limit rąk).

    `on_deck` to czysta obserwacja talii każdej ręki (indeks, talia) —
    bez wpływu na przebieg gry; z niej test dowodzi identyczności kart
    między rotacjami bloku. `on_action` obserwuje licytację (patrz `OnAction`).
    """
    seeds = _hand_seeds(seed)
    stacks = [STARTING_CHIPS, STARTING_CHIPS, STARTING_CHIPS]
    button = 1
    hand_i = 0
    first = True
    while len(_alive(stacks)) >= 2 and hand_i < HAND_GUARD:
        sb, bb, _ = blinds_for_hand(hand_i)
        button = _next_button(stacks, button, first)
        first = False
        deck_seed, act_seed = seeds[hand_i]
        deck = shuffled_deck(random.Random(deck_seed))
        if on_deck is not None:
            on_deck(hand_i, deck)
        stacks = _play_hand(
            stacks,
            hand_i,
            button,
            sb,
            bb,
            books,
            deck,
            random.Random(act_seed),
            on_action=on_action,
        )
        hand_i += 1
    reason = "bust" if len(_alive(stacks)) <= 1 else "guard"
    return (stacks[0], stacks[1], stacks[2]), reason


def play_spin(
    books: tuple[Seat, Seat, Seat],
    prizes: tuple[float, float, float],
    seed: int,
) -> tuple[float, float, float]:
    stacks, _ = run_spin(books, seed)
    order = sorted(range(3), key=lambda i: (-stacks[i], i))
    money = [0.0, 0.0, 0.0]
    for place, seat in enumerate(order):
        money[seat] = prizes[place]
    return (money[0], money[1], money[2])


def _play_hand(
    stacks: list[int],
    hand: int,
    button: int,
    sb: int,
    bb: int,
    books: tuple[Seat, Seat, Seat],
    deck: Sequence[Card],
    rng: random.Random,
    *,
    on_action: OnAction | None = None,
) -> list[int]:
    live = _alive(stacks)
    if len(live) <= 2:
        # Heads-up po wybiciu: role z żywych miejsc, nie z nominalnego układu 3-max.
        bb_seat = next(s for s in live if s != button)
        order = [button, bb_seat]
    else:
        utg, _, bb_seat = roles(button)
        order = [utg, button, bb_seat]
    contrib = [0, 0, 0]
    folded = [stacks[i] <= 0 for i in range(3)]
    acted = list(folded)
    contrib[button] = min(stacks[button], sb)
    contrib[bb_seat] = min(stacks[bb_seat], bb)
    holes: list[tuple[Card, Card] | None] = [None, None, None]
    n = 0
    for owner in range(3):
        if stacks[owner] > 0:
            holes[owner] = (deck[n], deck[n + 1])
            n += 2
    board = deck[n : n + 5]
    jammed = False
    opened = False
    jamfold = is_jam_fold_depth((stacks[0], stacks[1], stacks[2]), bb)

    # Blindy są ostatnim głosem przed pierwszą decyzją, więc rundę otwiera
    # lewa strona BB; dalej głos idzie na lewo od tego, kto właśnie zagrał.
    speaker = bb_seat

    def to_act() -> int | None:
        remaining = [s for s in range(3) if not folded[s] and stacks[s] > 0]
        if len(remaining) <= 1:
            return None
        raised = jammed or opened
        for candidate in speaking_order(order, speaker):
            if folded[candidate] or stacks[candidate] <= 0:
                continue
            if acted[candidate]:
                continue
            if contrib[candidate] >= stacks[candidate]:
                continue
            if not raised and candidate == bb_seat and len(live) > 2:
                continue
            return candidate
        return None

    steps = 0
    actions: list[tuple[int, str]] = []
    start = (stacks[0], stacks[1], stacks[2])

    def make_view(seat: int, klass: int) -> SeatView:
        return SeatView(
            hand=hand,
            seat=seat,
            button=button,
            stacks=start,
            contrib=(contrib[0], contrib[1], contrib[2]),
            actions=tuple(actions),
            bb=bb,
            klass=klass,
            jamfold=jamfold,
            opened=opened,
            jammed=jammed,
        )

    def klass_of(seat: int) -> int:
        hole = holes[seat]
        assert hole is not None, "rozgrywacz dotyka wyłącznie miejsc z kartami"
        return CLASS_INDEX[classify(hole[0], hole[1])]

    while steps < 12:
        steps += 1
        seat = to_act()
        if seat is None:
            break
        if contrib[seat] >= max(contrib):
            # Nikt nie przebił wkładu tego miejsca: wejście kosztuje zero
            # i dominuje folda, więc rozgrywacz nie pyta (decyzja 28 pkt 2b).
            # Warunek nie pyta o to, CZY stoi przebicie: najwyższym wkładem
            # bywa cudzy blind (all-in z samego blindu), a fold jest wtedy
            # tak samo darmowy — F1 audytu POKER-54. Wpis w historii i głos
            # są tu dziś nieobserwowalne (wejście jest ostatnią akcją ręki),
            # ale zostają, bo to one czynią oba pola prawdziwymi.
            entry = make_view(seat, klass_of(seat)) if on_action is not None else None
            actions.append((seat, "jam"))
            acted[seat] = True
            speaker = seat
            if on_action is not None and entry is not None:
                on_action(entry, "jam", False)
            continue
        idx = klass_of(seat)
        book = books[seat]
        view = make_view(seat, idx) if on_action is not None else None
        if isinstance(book, SeatBook):
            act = pick(
                book,
                idx,
                jamfold=jamfold,
                opened=opened,
                jammed=jammed,
                rng=rng,
            )
        else:
            if view is None:
                view = make_view(seat, idx)
            act = book.act(view, rng)
            if act not in legal_actions(view):
                raise ValueError(
                    f"agent miejsca {seat} zwrócił akcję {act!r} spoza zamrożonego drzewa"
                )
        actions.append((seat, act))
        acted[seat] = True
        speaker = seat
        if on_action is not None and view is not None:
            on_action(view, act, True)
        if act == "fold":
            folded[seat] = True
        elif act == "open":
            contrib[seat] = max(contrib[seat], min(stacks[seat], open_amount(bb)))
            opened = True
        else:
            contrib[seat] = stacks[seat]
            jammed = True
            for s in range(3):
                if folded[s] or stacks[s] <= 0 or s == seat:
                    continue
                if contrib[s] < stacks[s] and contrib[s] < contrib[seat]:
                    acted[s] = False
        remaining = [s for s in range(3) if not folded[s] and stacks[s] > 0]
        if len(remaining) <= 1:
            break

    live_now = [s for s in range(3) if not folded[s] and stacks[s] > 0]
    ranks = [99, 99, 99]
    if len(live_now) == 1:
        ranks[live_now[0]] = 0
    else:
        vals: list[tuple[int, HandValue]] = []
        for s in range(3):
            hole = holes[s]
            if s in live_now and hole is not None:
                vals.append((s, evaluate_best((*hole, *board))))
        top = max((v for _, v in vals), default=None)
        for s, val in vals:
            ranks[s] = 0 if val == top else 1
    awarded = award_allin((contrib[0], contrib[1], contrib[2]), (ranks[0], ranks[1], ranks[2]))
    return [
        stacks[0] - contrib[0] + awarded[0],
        stacks[1] - contrib[1] + awarded[1],
        stacks[2] - contrib[2] + awarded[2],
    ]


def _books_with_hero(hero: Seat, villain: Seat, seat: int) -> tuple[Seat, Seat, Seat]:
    if seat not in (0, 1, 2):
        raise ValueError(f"miejsce poza 3-max: {seat}")
    books = [villain, villain, villain]
    books[seat] = hero
    return (books[0], books[1], books[2])


def play_block(
    hero: Seat,
    villain: Seat,
    prizes: tuple[float, float, float],
    seed: int,
) -> float:
    """Wypłata hero w buy-inach uśredniona po trzech rotacjach jednego seeda."""
    total = 0.0
    for seat in range(ROTATIONS):
        total += play_spin(_books_with_hero(hero, villain, seat), prizes, seed)[seat]
    return total / ROTATIONS


def _percentile(ordered: Sequence[float], q: float) -> float:
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def bootstrap_ci(
    xs: Sequence[float],
    *,
    replications: int = BOOTSTRAP_REPLICATIONS,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentylowy CI średniej: resampling jednostek statystycznych (bloków)."""
    if len(xs) < 2:
        raise ValueError(f"bootstrap wymaga co najmniej 2 obserwacji: {len(xs)}")
    if replications < 1:
        raise ValueError(f"liczba replikacji musi być dodatnia: {replications}")
    rng = random.Random(seed)
    n = len(xs)
    means = sorted(sum(rng.choices(xs, k=n)) / n for _ in range(replications))
    return _percentile(means, alpha / 2.0), _percentile(means, 1.0 - alpha / 2.0)


def _summary(
    xs: Sequence[float],
    *,
    bootstrap_replications: int,
    bootstrap_seed: int,
) -> dict[str, float]:
    n = len(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    sd = var**0.5
    se = sd / n**0.5
    roi = mean - 1.0
    boot_lo, boot_hi = bootstrap_ci(xs, replications=bootstrap_replications, seed=bootstrap_seed)
    return {
        "n": float(n),
        "mean_bi": mean,
        "roi": roi,
        "sd": sd,
        "se": se,
        "ci_lo": roi - 1.96 * se,
        "ci_hi": roi + 1.96 * se,
        "boot_lo": boot_lo - 1.0,
        "boot_hi": boot_hi - 1.0,
    }


def sample_blocks(
    hero: Seat,
    villain: Seat,
    prizes: tuple[float, float, float],
    n: int,
    seed: int = 1,
    *,
    bootstrap_replications: int = BOOTSTRAP_REPLICATIONS,
    bootstrap_seed: int = 0,
) -> dict[str, float]:
    """ROI hero na `n` blokach (seedy seed..seed+n-1); CI normalny i bootstrap."""
    if n < 2:
        raise ValueError("n")
    xs = [play_block(hero, villain, prizes, seed + i) for i in range(n)]
    return _summary(
        xs, bootstrap_replications=bootstrap_replications, bootstrap_seed=bootstrap_seed
    )


def compare_blocks(
    a: tuple[Seat, Seat],
    b: tuple[Seat, Seat],
    prizes: tuple[float, float, float],
    n: int,
    seed: int = 1,
    *,
    bootstrap_replications: int = BOOTSTRAP_REPLICATIONS,
    bootstrap_seed: int = 0,
) -> dict[str, float]:
    """Różnica ROI dwóch zestawów (hero, villain) na wspólnych seedach bloków.

    Oba ramiona grają te same seedy, więc statystyka (CI normalny
    i bootstrap) liczona jest na różnicach sparowanych po bloku.
    """
    if n < 2:
        raise ValueError("n")
    xa = [play_block(a[0], a[1], prizes, seed + i) for i in range(n)]
    xb = [play_block(b[0], b[1], prizes, seed + i) for i in range(n)]
    diffs = [va - vb for va, vb in zip(xa, xb, strict=True)]
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    sd = var**0.5
    se = sd / n**0.5
    boot_lo, boot_hi = bootstrap_ci(
        diffs, replications=bootstrap_replications, seed=bootstrap_seed
    )
    return {
        "n": float(n),
        "roi_a": sum(xa) / n - 1.0,
        "roi_b": sum(xb) / n - 1.0,
        "diff": mean,
        "sd": sd,
        "se": se,
        "ci_lo": mean - 1.96 * se,
        "ci_hi": mean + 1.96 * se,
        "boot_lo": boot_lo,
        "boot_hi": boot_hi,
    }


def sample_seat(
    hero: Seat,
    villain: Seat,
    prizes: tuple[float, float, float],
    n: int,
    seed: int = 1,
    *,
    hero_seat: int = 0,
    bootstrap_replications: int = BOOTSTRAP_REPLICATIONS,
    bootstrap_seed: int = 0,
) -> dict[str, float]:
    """ROI hero na jednym miejscu, turniej po turnieju — diagnostyka.

    To jest estymator sprzed rotacji (obciążenie pozycyjne, pełna
    wariancja); do porównań agentów służą `sample_blocks`/`compare_blocks`.
    """
    if n < 2:
        raise ValueError("n")
    books = _books_with_hero(hero, villain, hero_seat)
    xs = [play_spin(books, prizes, seed + i)[hero_seat] for i in range(n)]
    out = _summary(
        xs, bootstrap_replications=bootstrap_replications, bootstrap_seed=bootstrap_seed
    )
    out["hero_seat"] = float(hero_seat)
    return out

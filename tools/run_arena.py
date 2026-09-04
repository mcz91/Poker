"""Hero book vs fish. Prints ROI in buy-ins; unit = blok trzech rotacji.

Tryby:
- `python tools/run_arena.py [N_BLOKOW] [pay]` — porównania książek na blokach;
- `python tools/run_arena.py blueprint ARTEFAKT.bpk [N_BLOKOW] [pay]` — agent
  grający z artefaktu blueprintu przeciw field_exploit, dollar_fish
  i always_jam; obok ROI z CI wychodzą liczniki fallbacków agenta;
- `python tools/run_arena.py fallback ARTEFAKT.bpk [N_BLOKOW] [pay]` — ile
  z tego ROI robi sama reguła fallbacku: różnica sparowana między agentem
  grającym check-call → fold poza artefaktem a tym samym agentem pasującym
  w każdym takim miejscu (wspólne seedy bloków);
- `python tools/run_arena.py sd [N_BLOKOW] [pay]` — SD na turniej (estymator
  sprzed rotacji, miejsce 0) vs SD na blok na tych samych seedach oraz
  wynikające N dla różnic 5 i 10 pp ROI (moc 80%, alfa 0,05);
- `python tools/run_arena.py seats [N_TURNIEJOW] [pay]` — ROI tego samego
  agenta na każdym z trzech miejsc osobno na wspólnych seedach
  (obciążenie pozycyjne, które rotacja usuwa).
"""

from __future__ import annotations

import json
import random
import sys
from typing import BinaryIO

from poker.blueprint_agent import BlueprintAgent
from poker.blueprint_reader import BlueprintReader
from poker.jamfold import solve as solve_jf
from poker.openfold import _threebet_from_open, threebet_vs_range
from poker.openfold import solve as solve_open
from poker.spin import LEVELS, PAYOUTS, STARTING_CHIPS, is_jam_fold_depth
from poker.spin_arena import (
    SeatBook,
    SeatView,
    always_jam,
    call_vs_random,
    compare_blocks,
    dollar_fish,
    field_exploit,
    play_block,
    play_spin,
    sample_blocks,
    sample_seat,
    wide_call,
)

# Moc 80% i alfa 0,05 (dwustronnie): N = ((z_{0,975} + z_{0,80}) * SD / delta)^2.
Z_ALPHA = 1.96
Z_POWER = 0.8416


def hero_book(pay: str = "3x", iterations: int = 12) -> SeatBook:
    """One book for all depths: 25bb open + 25bb 3bet + 25bb call vs jam.

    Endgame jam/fold uses the 4/8 solve (first level ≤7bb). Cheap and honest.
    """
    prizes = PAYOUTS[pay].prizes
    stacks = (STARTING_CHIPS, STARTING_CHIPS, STARTING_CHIPS)
    deep = solve_open(stacks, prizes, 1, iterations, 1, 2)
    three = _threebet_from_open(
        deep.utg_open, deep.utg_open_pct, stacks, prizes, 1, 1, 2, 0.55
    )
    deep_jf = solve_jf(stacks, prizes, 1, iterations, 1, 2)
    short_sb, short_bb = next(
        (sb, bb) for sb, bb in LEVELS if is_jam_fold_depth(stacks, bb)
    )
    short = solve_jf(stacks, prizes, 1, iterations, short_sb, short_bb)
    return SeatBook(
        open=list(deep.utg_open),
        overjam=list(deep.utg_jam),
        vs_open=list(three.btn_vs_open),
        vs_jam=list(deep_jf.btn_call),
        jf_first=list(short.utg_jam),
        jf_vs_jam=list(short.btn_call),
    )


def exploit_book(pay: str = "3x", iterations: int = 12) -> SeatBook:
    """$1 book: call jams vs random; 3bet a wide fish who folds too much."""
    base = hero_book(pay, iterations)
    vs_jam = call_vs_random(0.50)
    fish = dollar_fish()
    three = threebet_vs_range(
        fish.open,
        (STARTING_CHIPS, STARTING_CHIPS, STARTING_CHIPS),
        PAYOUTS[pay].prizes,
        continue_frac=0.45,
    )
    return SeatBook(
        open=base.open,
        overjam=base.overjam,
        vs_open=list(three.btn_vs_open),
        vs_jam=vs_jam,
        jf_first=base.jf_first,
        jf_vs_jam=vs_jam,
    )


def n_needed(sd: float, delta: float) -> int:
    """Jednostki potrzebne do wykrycia `delta` ROI przy mocy 80% i alfa 0,05."""
    units = ((Z_ALPHA + Z_POWER) * sd / delta) ** 2
    return int(units) + (0 if units == int(units) else 1)


def _sd(xs: list[float]) -> float:
    mean = sum(xs) / len(xs)
    return (sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def sd_reduction(n: int, pay: str) -> dict[str, object]:
    """SD na turniej (miejsce 0, sprzed rotacji) vs SD na blok, wspólne seedy."""
    prizes = PAYOUTS[pay].prizes
    pairs: dict[str, tuple[SeatBook, SeatBook]] = {
        "field_vs_always_jam": (field_exploit(), always_jam()),
        "field_vs_dollar": (field_exploit(), dollar_fish()),
        "tight_vs_always_jam": (hero_book(pay), always_jam()),
    }
    out: dict[str, object] = {"pay": pay, "n_seeds": n, "seed": 21}
    for name, (hero, villain) in pairs.items():
        books = (hero, villain, villain)
        per_tournament = [play_spin(books, prizes, 21 + i)[0] for i in range(n)]
        per_block = [play_block(hero, villain, prizes, 21 + i) for i in range(n)]
        sd_t = _sd(per_tournament)
        sd_b = _sd(per_block)
        out[name] = {
            "sd_tournament": sd_t,
            "sd_block": sd_b,
            "reduction_pct": 100.0 * (1.0 - sd_b / sd_t),
            "n_tournaments_5pp": n_needed(sd_t, 0.05),
            "n_tournaments_10pp": n_needed(sd_t, 0.10),
            "n_blocks_5pp": n_needed(sd_b, 0.05),
            "n_blocks_10pp": n_needed(sd_b, 0.10),
        }
    return out


def seat_bias(n: int, pay: str) -> dict[str, object]:
    """ROI tego samego agenta na każdym miejscu osobno, wspólne seedy."""
    prizes = PAYOUTS[pay].prizes
    pairs: dict[str, tuple[SeatBook, SeatBook]] = {
        "field_vs_always_jam": (field_exploit(), always_jam()),
        "field_vs_dollar": (field_exploit(), dollar_fish()),
    }
    out: dict[str, object] = {"pay": pay, "n_tournaments": n, "seed": 21}
    for name, (hero, villain) in pairs.items():
        per_seat = [
            sample_seat(hero, villain, prizes, n, seed=21, hero_seat=seat)
            for seat in range(3)
        ]
        rois = [hit["roi"] for hit in per_seat]
        out[name] = {
            "roi_seat0": rois[0],
            "roi_seat1": rois[1],
            "roi_seat2": rois[2],
            "se_seat_max": max(hit["se"] for hit in per_seat),
            "spread_pp": 100.0 * (max(rois) - min(rois)),
        }
    return out


def compare_books(n: int, pay: str) -> dict[str, object]:
    hero = hero_book(pay)
    expl = exploit_book(pay)
    field = field_exploit()
    fish = dollar_fish()
    prizes = PAYOUTS[pay].prizes
    return {
        "pay": pay,
        "unit": "blok = 3 rotacje jednego seeda",
        "tight_vs_always_jam": sample_blocks(hero, always_jam(), prizes, n, seed=21),
        "exploit_vs_always_jam": sample_blocks(expl, always_jam(), prizes, n, seed=21),
        "exploit_vs_wide": sample_blocks(expl, wide_call(0.45), prizes, n, seed=22),
        "field_vs_always_jam": sample_blocks(field, always_jam(), prizes, n, seed=21),
        "tight_vs_dollar": sample_blocks(hero, fish, prizes, n, seed=24),
        "field_vs_dollar": sample_blocks(field, fish, prizes, n, seed=24),
        "field_vs_wide": sample_blocks(field, wide_call(0.45), prizes, n, seed=22),
    }


def blueprint_agent(stream: BinaryIO) -> BlueprintAgent:
    """Agent blueprintu z otwartego strumienia artefaktu.

    Otwarcie pliku i JSON metadanych należą do narzędzia: czytnik dostaje
    strumień (INV-P7), a `json` jest w silniku importem zabronionym. Krok
    siatki i zestaw klas biegu czyta się z metadanych, nie z założenia —
    artefakt o innej siatce ma być odrzucony przez odczyt, nie przemilczany.
    """
    return _as_agent(BlueprintAgent, stream)


def _as_agent(kind: type[BlueprintAgent], stream: BinaryIO) -> BlueprintAgent:
    reader = BlueprintReader(stream)
    config = json.loads(reader.meta_bytes())["run_manifest"]["config"]
    return kind(reader, grid_step=config["grid_step"], classes=config["classes"])


class FoldFallbackAgent(BlueprintAgent):
    """Ten sam agent, ale każdy fallback pasuje — druga skrajność reguły.

    Wariant istnieje wyłącznie po to, żeby zmierzyć, ile ROI robi reguła
    fallbacku, a nie strategia z artefaktu; dlatego mieszka w narzędziu
    pomiarowym, a nie w pakiecie.
    """

    def act(self, view: SeatView, rng: random.Random) -> str:
        before = self.from_artifact
        action = super().act(view, rng)
        return action if self.from_artifact != before else "fold"


def fallback_cost(path: str, n: int, pay: str) -> dict[str, object]:
    """Różnica sparowana: check-call → fold vs pasowanie na każdym fallbacku."""
    prizes = PAYOUTS[pay].prizes
    with open(path, "rb") as first, open(path, "rb") as second:
        hero = blueprint_agent(first)
        folding = _as_agent(FoldFallbackAgent, second)
        out: dict[str, object] = {"pay": pay, "artifact": path, "n_blocks": n}
        for name, villain in (
            ("vs_field", field_exploit()),
            ("vs_dollar", dollar_fish()),
            ("vs_always_jam", always_jam()),
        ):
            out[name] = compare_blocks((hero, villain), (folding, villain), prizes, n, seed=21)
        out["fallbacks_total"] = hero.counters()
    return out


def blueprint_arena(path: str, n: int, pay: str) -> dict[str, object]:
    """ROI agenta blueprintu na blokach przeciw trzem przeciwnikom areny."""
    prizes = PAYOUTS[pay].prizes
    with open(path, "rb") as stream:
        hero = blueprint_agent(stream)
        out: dict[str, object] = {
            "pay": pay,
            "artifact": path,
            "unit": "blok = 3 rotacje jednego seeda",
            "config_hash": hero.reader.config_hash,
        }
        field = field_exploit()
        for name, villain in (
            ("blueprint_vs_field", field_exploit()),
            ("blueprint_vs_dollar", dollar_fish()),
            ("blueprint_vs_always_jam", always_jam()),
        ):
            before = hero.counters()
            summary = sample_blocks(hero, villain, prizes, n, seed=21)
            # Ten sam przeciwnik, te same seedy bloków, inny hero: różnica
            # sparowana mówi, czy blueprint jest lepszym hero od field_exploit —
            # a nie tylko, ile wyciąga w oderwaniu (decyzja 26).
            paired = compare_blocks((hero, villain), (field, villain), prizes, n, seed=21)
            after = hero.counters()
            out[name] = {
                **summary,
                "n_blocks_5pp": n_needed(summary["sd"], 0.05),
                "n_blocks_10pp": n_needed(summary["sd"], 0.10),
                "vs_field_exploit_paired": paired,
                "fallbacks": {key: after[key] - before[key] for key in after},
            }
        out["fallbacks_total"] = hero.counters()
    return out


def main() -> None:
    args = sys.argv[1:]
    mode = "compare"
    if args and args[0] in ("sd", "seats", "blueprint", "fallback"):
        mode = args[0]
        args = args[1:]
    if mode in ("blueprint", "fallback"):
        if not args:
            raise SystemExit(f"użycie: run_arena.py {mode} ARTEFAKT.bpk [N_BLOKOW] [pay]")
        path = args[0]
        n = int(args[1]) if len(args) > 1 else 200
        pay = args[2] if len(args) > 2 else "3x"
        run = blueprint_arena if mode == "blueprint" else fallback_cost
        print(json.dumps(run(path, n, pay), indent=2))
        return
    default_n = {"compare": 200, "sd": 320, "seats": 2000}[mode]
    n = int(args[0]) if args else default_n
    pay = args[1] if len(args) > 1 else "3x"
    if mode == "sd":
        out = sd_reduction(n, pay)
    elif mode == "seats":
        out = seat_bias(n, pay)
    else:
        out = compare_books(n, pay)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

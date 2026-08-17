"""Hero book vs fish. Prints ROI in buy-ins."""

from __future__ import annotations

import json
import sys

from poker.arena import SeatBook, always_jam, call_vs_random, dollar_fish, field_exploit, sample, wide_call
from poker.jamfold import solve as solve_jf
from poker.openfold import _threebet_from_open, solve as solve_open, threebet_vs_range
from poker.spin import LEVELS, PAYOUTS, STARTING_CHIPS, is_jam_fold_depth


def hero_book(pay: str = "3x", iterations: int = 12) -> SeatBook:
    """One book for all depths: 25bb open + 25bb 3bet + 25bb call vs jam.

    Endgame jam/fold uses the 4/8 solve (first level ≤7bb). Cheap and honest.
    """
    prizes = PAYOUTS[pay].prizes
    stacks = (STARTING_CHIPS, STARTING_CHIPS, STARTING_CHIPS)
    deep = solve_open(stacks, prizes, 1, iterations, 1, 2)
    three = _threebet_from_open(deep, stacks, prizes, 1, 1, 2, 0.55)
    deep_jf = solve_jf(stacks, prizes, 1, iterations, 1, 2)
    short_sb, short_bb = next(
        (sb, bb) for sb, bb in LEVELS if is_jam_fold_depth(stacks, bb)
    )
    short = solve_jf(stacks, prizes, 1, iterations, short_sb, short_bb)
    return SeatBook(
        open=list(deep["utg_open"]),
        overjam=list(deep["utg_jam"]),
        vs_open=list(three["btn_vs_open"]),
        vs_jam=list(deep_jf["btn_call"]),
        jf_first=list(short["utg_jam"]),
        jf_vs_jam=list(short["btn_call"]),
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
        vs_open=list(three["btn_vs_open"]),
        vs_jam=vs_jam,
        jf_first=base.jf_first,
        jf_vs_jam=vs_jam,
    )


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    pay = sys.argv[2] if len(sys.argv) > 2 else "3x"
    hero = hero_book(pay)
    expl = exploit_book(pay)
    field = field_exploit()
    fish = dollar_fish()
    prizes = PAYOUTS[pay].prizes
    out = {
        "pay": pay,
        "tight_vs_always_jam": sample(hero, always_jam(), prizes, n, seed=21),
        "field_vs_always_jam": sample(field, always_jam(), prizes, n, seed=21),
        "tight_vs_dollar": sample(hero, fish, prizes, n, seed=24),
        "field_vs_dollar": sample(field, fish, prizes, n, seed=24),
        "field_vs_wide": sample(field, wide_call(0.45), prizes, n, seed=22),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

"""Offline first-in open/jam on open-depth clock levels."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from poker.openfold import _threebet_from_open, solve
from poker.spin import JAM_FOLD_BB, LEVELS, PAYOUTS, STARTING_CHIPS, effective_bb

ITERS = 16
STACKS = (STARTING_CHIPS, STARTING_CHIPS, STARTING_CHIPS)


def pack(sigma: tuple[float, ...]) -> list[int]:
    return [int(round(100 * p)) for p in sigma]


def main() -> None:
    out: list[dict[str, object]] = []
    for pay_id in ("3x", "10x"):
        prizes = PAYOUTS[pay_id].prizes
        for sb, bb in LEVELS:
            if effective_bb(STACKS, bb) <= JAM_FOLD_BB:
                continue
            result = solve(STACKS, prizes, button=1, iterations=ITERS, sb=sb, bb_amt=bb)
            tb = _threebet_from_open(
                result.utg_open, result.utg_open_pct, STACKS, prizes, 1, sb, bb, 0.55
            )
            row = {
                "pay": pay_id,
                "sb": sb,
                "bb": bb,
                "utgOpenPct": result.utg_open_pct,
                "utgJamPct": result.utg_jam_pct,
                "btnOpenPct": result.btn_open_pct,
                "btn3betPct": tb.btn_vs_open_pct,
                "bb3betPct": tb.bb_vs_open_pct,
                "utgOpen": pack(result.utg_open),
                "utgJam": pack(result.utg_jam),
                "btnOpen": pack(result.btn_open),
                "btnJam": pack(result.btn_jam),
                "btn3bet": pack(tb.btn_vs_open),
                "bb3bet": pack(tb.bb_vs_open),
            }
            out.append(row)
            print(
                f"{pay_id} {sb}/{bb} open={row['utgOpenPct']:.1f} 3bet={row['btn3betPct']:.1f}",
                file=sys.stderr,
            )
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/dev/stdout")
    dest.write_text(json.dumps({"iters": ITERS, "note": "first-in only", "rows": out}))
    print(dest, file=sys.stderr)


if __name__ == "__main__":
    main()

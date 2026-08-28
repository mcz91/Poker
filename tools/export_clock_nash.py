"""Offline jam/fold Nash on the Spin clock. Writes compact JSON for EXPLO."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from poker.jamfold import solve
from poker.spin import LEVELS, PAYOUTS, STARTING_CHIPS

ITERS = 24
STACKS = (STARTING_CHIPS, STARTING_CHIPS, STARTING_CHIPS)
PAY_IDS = ("3x", "10x")


def pack(sigma: tuple[float, ...]) -> list[int]:
    return [int(round(100 * p)) for p in sigma]


def main() -> None:
    out: list[dict[str, object]] = []
    for pay_id in PAY_IDS:
        prizes = PAYOUTS[pay_id].prizes
        for sb, bb in LEVELS:
            result = solve(STACKS, prizes, button=1, iterations=ITERS, sb=sb, bb_amt=bb)
            row = {
                "pay": pay_id,
                "sb": sb,
                "bb": bb,
                "utg": result.utg_jam_pct,
                "btn": result.btn_call_pct,
                "bb_call": result.bb_call_pct,
                "utgJam": pack(result.utg_jam),
                "btnCall": pack(result.btn_call),
                "bbCall": pack(result.bb_call),
                "btnOpen": pack(result.btn_open),
                "bbVsBtn": pack(result.bb_vs_btn),
            }
            out.append(row)
            print(
                f"{pay_id} {sb}/{bb} utg={row['utg']:.1f} btn={row['btn']:.1f} "
                f"bb={row['bb_call']:.1f}",
                file=sys.stderr,
            )
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/dev/stdout")
    dest.write_text(json.dumps({"iters": ITERS, "stacks": list(STACKS), "rows": out}))
    print(dest, file=sys.stderr)


if __name__ == "__main__":
    main()

"""Offline first-in open/jam on open-depth clock levels.

- `python tools/export_open_nash.py [PLIK]` — wiersze przy N = CURVE_ITERATIONS
  z miarą zbieżności (zysk z best response per punkt decyzji, ułamek sumy
  nagród); etykieta „punkt stały FP modelu" tylko, gdy miara każdego wiersza
  ≤ CONVERGENCE_TOL;
- `python tools/export_open_nash.py --curve` — miara i liczby eksportu na
  CURVE_CHECKPOINTS, najmniejszy punkt kontrolny z miarą w tolerancji na
  wszystkich poziomach i rozrzut każdej liczby eksportu na [N/2, N].
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from poker.openfold import (
    CONVERGENCE_TOL,
    CURVE_CHECKPOINTS,
    CURVE_ITERATIONS,
    DECISION_LABELS,
    OpenFoldSolution,
    _threebet_from_open,
    solve,
    solve_curve,
)
from poker.spin import JAM_FOLD_BB, LEVELS, PAYOUTS, STARTING_CHIPS, effective_bb

STACKS = (STARTING_CHIPS, STARTING_CHIPS, STARTING_CHIPS)
LABEL = "punkt stały FP modelu"
PCT_KEYS = ("utgOpenPct", "utgJamPct", "btnOpenPct", "btn3betPct", "bb3betPct")
RANGE_KEYS = ("utgOpen", "utgJam", "btnOpen", "btnJam", "btn3bet", "bb3bet")


def pack(sigma: tuple[float, ...]) -> list[int]:
    return [int(round(100 * p)) for p in sigma]


def levels() -> list[tuple[str, int, int]]:
    return [
        (pay_id, sb, bb)
        for pay_id in ("3x", "10x")
        for sb, bb in LEVELS
        if effective_bb(STACKS, bb) > JAM_FOLD_BB
    ]


def row(pay_id: str, sb: int, bb: int, result: OpenFoldSolution) -> dict[str, object]:
    prizes = PAYOUTS[pay_id].prizes
    tb = _threebet_from_open(result.utg_open, result.utg_open_pct, STACKS, prizes, 1, sb, bb, 0.55)
    return {
        "pay": pay_id,
        "sb": sb,
        "bb": bb,
        "utgOpenPct": result.utg_open_pct,
        "utgJamPct": result.utg_jam_pct,
        "btnOpenPct": result.btn_open_pct,
        "btn3betPct": tb.btn_vs_open_pct,
        "bb3betPct": tb.bb_vs_open_pct,
        "convergence": result.convergence,
        "brGain": dict(zip(DECISION_LABELS, result.br_gain, strict=True)),
        "utgOpen": pack(result.utg_open),
        "utgJam": pack(result.utg_jam),
        "btnOpen": pack(result.btn_open),
        "btnJam": pack(result.btn_jam),
        "btn3bet": pack(tb.btn_vs_open),
        "bb3bet": pack(tb.bb_vs_open),
    }


def export(dest: Path) -> None:
    out: list[dict[str, object]] = []
    measures: list[float] = []
    for pay_id, sb, bb in levels():
        prizes = PAYOUTS[pay_id].prizes
        result = solve(STACKS, prizes, button=1, iterations=CURVE_ITERATIONS, sb=sb, bb_amt=bb)
        out.append(row(pay_id, sb, bb, result))
        measures.append(result.convergence)
        print(
            f"{pay_id} {sb}/{bb} open={result.utg_open_pct:.1f} "
            f"miara={result.convergence:.2e}",
            file=sys.stderr,
        )
    payload: dict[str, object] = {
        "iters": CURVE_ITERATIONS,
        "tolerance": CONVERGENCE_TOL,
        "note": "first-in only",
        "rows": out,
    }
    if max(measures) <= CONVERGENCE_TOL:
        payload["label"] = LABEL
    dest.write_text(json.dumps(payload))
    print(dest, file=sys.stderr)


def curve() -> None:
    table: dict[tuple[str, int, int], dict[int, dict[str, object]]] = {}
    measure: dict[tuple[str, int, int], dict[int, float]] = {}
    for pay_id, sb, bb in levels():
        prizes = PAYOUTS[pay_id].prizes
        points = solve_curve(STACKS, prizes, CURVE_CHECKPOINTS, button=1, sb=sb, bb_amt=bb)
        table[(pay_id, sb, bb)] = {p.iterations: row(pay_id, sb, bb, p) for p in points}
        measure[(pay_id, sb, bb)] = {p.iterations: p.convergence for p in points}
    print(f"tolerancja miary {CONVERGENCE_TOL:g} sumy nagród; (50, 50, 50), guzik 1")
    for (pay_id, sb, bb), by_n in table.items():
        print(f"== {pay_id} {sb}/{bb}")
        for n, entry in by_n.items():
            nums = " ".join(f"{key}={entry[key]:.1f}" for key in PCT_KEYS)
            print(f"N={n:5d} miara={measure[(pay_id, sb, bb)][n]:.2e} {nums}")
    within = [
        n
        for n in CURVE_CHECKPOINTS
        if all(level[n] <= CONVERGENCE_TOL for level in measure.values())
    ]
    chosen = within[0] if within else CURVE_CHECKPOINTS[-1]
    status = "w tolerancji" if within else "BEZ etykiety równowagi (poza tolerancją)"
    print(
        f"N = {chosen} — najmniejszy punkt kontrolny {status}; "
        f"CURVE_ITERATIONS = {CURVE_ITERATIONS}"
    )
    half = chosen // 2
    if half not in CURVE_CHECKPOINTS:
        return
    print(f"rozrzut na [{half}, {chosen}]: liczby — |Δ| pp; zakresy — max |Δ| pp na klasę (klas ≠)")
    for (pay_id, sb, bb), by_n in table.items():
        lo, hi = by_n[half], by_n[chosen]
        parts = [f"{key} {lo[key]:.1f}/{hi[key]:.1f}" for key in PCT_KEYS]
        for key in RANGE_KEYS:
            a, b = lo[key], hi[key]
            assert isinstance(a, list) and isinstance(b, list)
            diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
            parts.append(f"{key} {max(diffs)} ({sum(1 for d in diffs if d)})")
        print(f"{pay_id} {sb}/{bb}: " + "; ".join(parts))


def main() -> None:
    if sys.argv[1:] == ["--curve"]:
        curve()
        return
    export(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/dev/stdout"))


if __name__ == "__main__":
    main()

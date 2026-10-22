"""Live query: board (3-5 cards) + ranges + pot/stack -> strategy on the current street.

python -m hupf_py.live --board Ks7d2c --pot 2 --stack 14 [--sb-range f] [--bb-range f]
       [--line limp_check] [--tree auto] [--target 0.5] [--threads 2] [--json out.json]

Returns the root node (OOP = BB acts first) and the IP replies to each root action, with
aggregate frequencies, per-class mixed strategies (169) and per-combo strategies (1326).
For repeated queries use `solver.Server` (persistent process) and `query(..., server=srv)`.
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np

from . import cards, ranges, solver
from .pipeline import auto_tree, load_range


def per_class(strategy: np.ndarray, weight: np.ndarray) -> np.ndarray:
    """(actions, 1326) -> (actions, 169) range-weighted mixed strategy per class."""
    num = (strategy * weight) @ cards.CLASS_MATRIX.T
    den = weight @ cards.CLASS_MATRIX.T
    return np.where(den > 0, num / np.maximum(den, 1e-12), np.nan)


def query(
    board: str,
    sb: np.ndarray,
    bb: np.ndarray,
    pot_bb: float,
    stack_bb: float,
    tree: str | dict = "auto",
    target: float = 0.5,
    threads: int = 2,
    max_iter: int = 1000,
    server: solver.Server | None = None,
) -> dict:
    if tree == "auto":
        tree = auto_tree(stack_bb / pot_bb)
    kw = dict(
        board=board,
        pot_bb=pot_bb,
        stack_bb=stack_bb,
        range_oop=bb,
        range_ip=sb,
        tree=tree,
        target_pct=target,
        max_iter=max_iter,
        node_depth=1,
        node_combos=True,
    )
    t = time.time()
    res = server.query(**kw) if server else solver.solve(threads=threads, **kw)
    if not res.get("ok"):
        raise RuntimeError(res.get("error"))
    lat = time.time() - t
    w = {0: np.array(res["players"][0]["weight"]), 1: np.array(res["players"][1]["weight"])}
    nodes = []
    for n in res["nodes"]:
        st = np.array(n["strategy"])
        pc = per_class(st, w[n["player"]])
        nodes.append(
            {
                "path": n["path"],
                "player": "BB(OOP)" if n["player"] == 0 else "SB(IP)",
                "actions": n["actions"],
                "freq": n["freq"],
                "class_strategy": {
                    cards.CLASS_NAMES[i]: [round(float(x), 4) for x in pc[:, i]]
                    for i in range(169)
                    if not np.isnan(pc[0, i])
                },
                "combo_strategy": st,
            }
        )
    return {
        "latency_s": lat,
        "solve_s": res["solve_s"],
        "iters": res["iters"],
        "expl_pct": res["expl_pct"],
        "ev_avg_bb": [x / cards.BB_CHIPS for x in res["ev_avg"]],
        "nodes": nodes,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--pot", type=float, required=True, help="pot at start of this street (bb)")
    ap.add_argument("--stack", type=float, required=True, help="effective remaining stack (bb)")
    ap.add_argument(
        "--line", default="limp_check", help="placeholder ranges if --sb/--bb-range absent"
    )
    ap.add_argument("--sb-range")
    ap.add_argument("--bb-range")
    ap.add_argument("--tree", default="auto", help="auto = by SPR (low1rf <= 4.5 < l1rf)")
    ap.add_argument("--target", type=float, default=0.5)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--json")
    a = ap.parse_args()
    _, sbf, bbf, _, _ = ranges.PLACEHOLDERS[a.line]
    sb = load_range(a.sb_range) if a.sb_range else cards.class_to_combo(sbf())
    bb = load_range(a.bb_range) if a.bb_range else cards.class_to_combo(bbf())
    r = query(a.board, sb, bb, a.pot, a.stack, a.tree, a.target, a.threads)
    print(
        f"latency {r['latency_s']:.2f}s solve {r['solve_s']:.2f}s iters {r['iters']} "
        f"expl {r['expl_pct']:.2f}% pot"
    )
    for n in r["nodes"]:
        fr = ", ".join(f"{a}={100 * f:.1f}%" for a, f in zip(n["actions"], n["freq"], strict=True))
        print(f"[{n['path'] or 'root'}] {n['player']}: {fr}")
    if a.json:
        for n in r["nodes"]:
            n["combo_strategy"] = np.round(n["combo_strategy"], 4).tolist()
        open(a.json, "w").write(json.dumps(r))


if __name__ == "__main__":
    main()

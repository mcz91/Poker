"""Latencja narzędzia: 30 zapytań (8 preflop, 8 flop, 7 turn, 7 river) w jednym procesie
+ 3 wywołania CLI. Kategoria zapytania = ulica pytania; dla flopa rozróżniamy solve na żywo
(pierwsze zapytanie o board/linię) i trafienie w cache.  Turn/river: flop z cache (policzony
wcześniej w tej serii), bieżąca ulica na żywo.  Użycie: python bench_latency.py [wątki]"""

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import spin_gto as G

G._STATE["threads"] = int(sys.argv[1]) if len(sys.argv) > 1 else 4
L15, R15, I15 = "SB limp, BB check", "SB raise 2, BB call", "SB limp, BB iso, SB call"
Q = [
    (15, "", None, "K7o"),
    (15, "", None, "A5s"),
    (15, "SB limp", None, "AJo"),
    (15, "SB limp", None, "72o"),
    (15, "SB raise 2", None, "KTo"),
    (15, "SB limp, BB iso", None, "T9s"),
    (20, "", None, "Q8o"),
    (20, "SB limp", None, "A2s"),
    (15, L15, "Ks7d2c", "AhTd"),
    (15, L15 + "; BB check", "Ks7d2c", "QhJh"),
    (15, L15 + "; BB bet", "Ks7d2c", "9h8h"),
    (15, L15 + "; BB check, SB bet", "Ks7d2c", "Kh5h"),
    (15, R15, "Ks7d2c", "Ah9h"),
    (15, R15 + "; BB check", "Ks7d2c", "AsQd"),
    (15, I15, "Ks7d2c", "AhKd"),
    (15, I15 + "; BB check", "Ks7d2c", "7h6h"),
    (15, L15 + "; BB check, SB check", "Ks7d2c5h", "AhTd"),
    (15, L15 + "; BB check, SB bet, BB call", "Ks7d2c5h", "Kh9h"),
    (15, L15 + "; BB bet, SB call", "Ks7d2c5h", "8h8d"),
    (15, R15 + "; BB check, SB check", "Ks7d2c9s", "Ah9h"),
    (15, R15 + "; BB check, SB bet, BB call", "Ks7d2cAh", "KdQd"),
    (15, I15 + "; BB check, SB check", "Ks7d2c5h", "AhKd"),
    (15, L15 + "; BB check, SB check", "Ks7d2cTh", "QhJd"),
    (15, L15 + "; BB check, SB check; BB check, SB check", "Ks7d2c5h9c", "AhTd"),
    (15, L15 + "; BB check, SB bet, BB call; BB check, SB check", "Ks7d2c5h3d", "Kh9h"),
    (15, L15 + "; BB bet, SB call; BB check, SB check; BB check", "Ks7d2c5h4s", "AhKs"),
    (15, R15 + "; BB check, SB check; BB check, SB bet, BB call", "Ks7d2c9sJd", "Ah9h"),
    (15, R15 + "; BB check, SB bet, BB call; BB check, SB check; BB check", "Ks7d2cAh3c", "AsJs"),
    (15, I15 + "; BB check, SB check; BB check, SB check", "Ks7d2c5hQc", "AhKd"),
    (15, L15 + "; BB check, SB check; BB check, SB check", "Ks7d2cTh6d", "QhJd"),
]
rows = []
for depth, line, board, hand in Q:
    t = time.perf_counter()
    try:
        o = G.query(depth, line, board, hand)
        ok, err = True, ""
    except G.QueryError as e:
        o, ok, err = {}, False, str(e)
    dt = time.perf_counter() - t
    street = o.get("street", "?")
    live = [s for s in o.get("streets", []) if not s["cached"]]
    cat = street if street != "flop" else ("flop-live" if live else "flop-cache")
    rows.append(
        dict(
            cat=cat,
            depth=depth,
            line=line,
            board=board,
            hand=hand,
            ok=ok,
            err=err,
            latency_s=dt,
            streets=o.get("streets"),
            strategy=dict(
                zip(
                    o.get("actions", []),
                    np.round(o.get("hand_strategy", []), 3).tolist(),
                    strict=True,
                )
            ),
            ev=o.get("hand_ev", o.get("hand_ev_street")),
        )
    )
    print(
        f"{cat:<10} {dt * 1000:10.1f} ms  {depth} | {line} | {board} | {hand} -> "
        f"{rows[-1]['strategy']} {err}",
        flush=True,
    )

cli = []
for args in (
    ["--depth", "15", "--hand", "K7o"],
    ["--depth", "15", "--line", "SB limp", "--hand", "AJo"],
    ["--depth", "15", "--line", L15, "--board", "Ks7d2c", "--hand", "AhTd"],
):
    t = time.perf_counter()
    subprocess.run(
        [sys.executable, str(G.TOOL / "spin_gto.py"), *args], check=True, capture_output=True
    )
    cli.append(dict(args=args, wall_s=time.perf_counter() - t))
summary = {}
for cat in ("preflop", "flop-live", "flop-cache", "turn", "river"):
    xs = np.array([r["latency_s"] for r in rows if r["cat"] == cat and r["ok"]])
    if len(xs):
        summary[cat] = dict(
            n=len(xs),
            p50_ms=float(np.percentile(xs, 50) * 1000),
            p95_ms=float(np.percentile(xs, 95) * 1000),
            max_ms=float(xs.max() * 1000),
        )
summary["cli_wall_s"] = [round(c["wall_s"], 3) for c in cli]
summary["errors"] = [r for r in rows if not r["ok"]]
print(json.dumps(summary, indent=1))
Path(G.TOOL / "latency.json").write_text(
    json.dumps(dict(summary=summary, rows=rows, cli=cli), indent=1, default=float)
)

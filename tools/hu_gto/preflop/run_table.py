"""Tabela 1-25 bb co 1 bb dla wariantów liścia + book .npz do lookupu.

Użycie: python run_table.py OUT_DIR [target_expl]
"""

import json
import sys
from pathlib import Path

import hu_preflop as H

COLS = [
    ("root", "SB", ["fold", "limp", "r2", "r2.5", "jam"]),
    ("limp", "L", ["check", "iso", "jam"]),
    ("limp-iso", "LI", ["fold", "call", "jam"]),
    ("r2", "R2", ["fold", "call", "jam"]),
    ("r2.5", "R25", ["fold", "call", "jam"]),
    ("jam", "J", ["call"]),
]
CODE = {
    "fold": "F",
    "limp": "L",
    "r2": "R2",
    "r2.5": "R25",
    "jam": "J",
    "check": "X",
    "iso": "I",
    "call": "C",
}
LEGEND = (
    "# SB:* = SB first-in; L:* = BB vs limp (X check, I iso 3,5 bb, J jam); LI:* = SB vs iso; "
    "R2:* / R25:* = BB vs raise 2x / 2,5x (F, C flat, J 3bet-jam); J:C = BB call vs jam SB"
)


def row(r):
    cells = [f"{r.depth:>3g}"]
    for nid, _, acts in COLS:
        nr = r.nodes.get(nid)
        for a in acts:
            cells.append(f"{100 * nr.freq[a]:6.1f}" if nr and a in nr.freq else "     -")
    vpip = 1 - r.nodes["root"].freq["fold"]
    cells += [
        f"{100 * vpip:5.1f}",
        f"{r.ev_sb:+.3f}",
        f"{r.expl:.1e}",
        f"{r.iters:5d}",
        f"{r.seconds:5.2f}",
    ]
    return " ".join(cells)


def header():
    h = ["  S"]
    for _, pre, acts in COLS:
        h += [f"{pre + ':' + CODE[a]:>6}" for a in acts]
    h += [" VPIP", " EV_SB", "   expl", "iters", "  sec"]
    return " ".join(h)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    target = float(sys.argv[2]) if len(sys.argv) > 2 else 1e-4
    variants = [
        ("jamfold", H.CheckdownLeaf(), H.TreeConfig(mode="jamfold")),
        ("checkdown", H.CheckdownLeaf(), H.TreeConfig()),
        ("eqr105_085", H.ConstEQRLeaf(1.05, 0.85), H.TreeConfig()),
    ]
    for tag, leaf, tree in variants:
        results = []
        lines = [
            f"# wariant {tag}: liść={getattr(leaf, 'name', '')}, drzewo={tree}",
            "# kolumny: % akcji w węźle (ważone kombinacjami * zasięgiem własnym);",
            "# EV_SB bb/rozdanie; expl = (luka BR SB + luka BR BB)/2 bb/rozdanie;",
            f"# cel expl {target:g}; sec = czas solve'u",
            LEGEND,
            header(),
        ]
        for S in range(1, 26):
            r = H.solve(float(S), leaf, tree=tree, iters=20000, target_expl=target)
            results.append(r)
            lines.append(row(r))
            print(tag, lines[-1], flush=True)
        (out / f"table_{tag}.txt").write_text("\n".join(lines) + "\n")
        H.save_book(results, out / f"book_{tag}.npz")
        (out / f"summary_{tag}.json").write_text(
            json.dumps([r.summary() for r in results], indent=1)
        )
        for S in (10, 15, 20):
            r = results[S - 1]
            txt = [f"===== {tag} S={S} bb  EV_SB {r.ev_sb:+.3f}  expl {r.expl:.1e} ====="]
            for nid, nr in r.nodes.items():
                txt.append(H.chart_text(nr, title=f"--- węzeł {nid}"))
            (out / f"charts_{tag}_{S}bb.txt").write_text("\n\n".join(txt) + "\n")
            H.export_leaves(r, out / f"leaves_{tag}_{S}bb.json")


if __name__ == "__main__":
    main()

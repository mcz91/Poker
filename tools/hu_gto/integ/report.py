"""Tabele częstości vs referencje, zbieżność rund, charty 13x13.

Użycie: python report.py [N rundy końcowej]"""

import json
import pickle
import sys

import fp
import numpy as np
from fp import H


def joint_reach(res):
    root = H.build_tree(res.depth, H.TreeConfig(**res.tree), fp.E7, H.CheckdownLeaf())
    out = {}

    def walk(n, rs, rb):
        if n.actor is None:
            return
        out[n.id] = float(rs @ H.W @ rb / H.WTOT)
        sig = res.nodes[n.id].strategy
        for i, c in enumerate(n.children):
            walk(c, rs * sig[:, i], rb) if n.actor == 0 else walk(c, rs, rb * sig[:, i])

    walk(root, np.ones(H.N), np.ones(H.N))
    return out


def change(prev, cur, mp, mc, min_reach=0.01):
    jr = joint_reach(cur)
    jp = joint_reach(prev)
    df = []
    for nid, nr in cur.nodes.items():
        p = prev.nodes.get(nid)
        if p is None or p.actions != nr.actions or max(jr[nid], jp.get(nid, 0)) < min_reach:
            continue
        for a in nr.actions:
            df.append((abs(nr.freq[a] - p.freq[a]) * 100, f"{nid}:{a}"))
    s0, b0 = fp.class_ev(prev, mp)
    s1, b1 = fp.class_ev(cur, mc)
    w = H.NCOMBO / H.NCOMBO.sum()
    ds, db = np.abs(s1 - s0), np.abs(b1 - b0)
    m = max(df)
    return (
        f"max |Δ częstości| {m[0]:5.2f} pp ({m[1]}); |ΔEV klasy| SB max {ds.max():.4f} "
        f"({H.CLASSES[ds.argmax()]}) "
        f"śr. {w @ ds:.4f}; BB max {db.max():.4f} ({H.CLASSES[db.argmax()]}) śr. {w @ db:.4f}; "
        f"ΔEV_SB gry {cur.ev_sb - prev.ev_sb:+.4f}",
        dict(
            max_freq=m[0], at=m[1], sb_max=ds.max(), sb_mean=w @ ds, bb_max=db.max(), bb_mean=w @ db
        ),
    )


def f(res, nid, a):
    nr = res.nodes.get(nid)
    return 100 * nr.freq.get(a, 0.0) if nr else float("nan")


def row(res):
    jr = joint_reach(res)
    r25 = f(res, "root", "r2.5") if "r2.5" in res.nodes["root"].actions else 0
    rs = f(res, "root", "r2") + r25
    cells = dict(
        SB=f"{f(res, 'root', 'fold'):5.1f} {f(res, 'root', 'limp'):5.1f} {rs:5.1f} "
        f"({f(res, 'root', 'r2'):.1f}/{r25:.1f}) {f(res, 'root', 'jam'):5.1f}",
        L=f"{f(res, 'limp', 'check'):5.1f} {f(res, 'limp', 'iso'):5.1f} "
        f"{f(res, 'limp', 'jam'):5.1f}",
        LI=f"{f(res, 'limp-iso', 'fold'):5.1f} {f(res, 'limp-iso', 'call'):5.1f} "
        f"{f(res, 'limp-iso', 'jam'):5.1f}",
        LJ=f"{f(res, 'limp-jam', 'fold'):5.1f} {f(res, 'limp-jam', 'call'):5.1f}",
        R2=f"{f(res, 'r2', 'fold'):5.1f} {f(res, 'r2', 'call'):5.1f} {f(res, 'r2', 'jam'):5.1f}"
        + (" (poza ścieżką)" if jr.get("r2", 0) < 0.01 else ""),
        R25=(
            f"{f(res, 'r2.5', 'fold'):5.1f} {f(res, 'r2.5', 'call'):5.1f} "
            f"{f(res, 'r2.5', 'jam'):5.1f}"
            + (" (poza ścieżką)" if jr.get("r2.5", 0) < 0.01 else "")
        )
        if "r2.5" in res.nodes
        else "-",
        J=f"{f(res, 'jam', 'call'):5.1f}",
    )
    return cells


REFS = {
    10: [
        (
            "GW-AI 10 bb (2025-09-26)",
            "SB 11,9/65,5/0,2/22,4; BB vs limp X 54,0 / iso 29,3 (2,5x 17,2 + 4x 12,1) / J 16,6; "
            "SB(limp) vs iso-jam F 70,3 C 29,7; SB vs iso 2,5: F 39,2 C 47,5 J 13,3",
        ),
        (
            "GTO Gecko 10 bb (2026-09-30)",
            "SB 11,22/62,48/0,01/26,29; BB vs limp (drzewo X/J) X 56,61 J 43,39; BB vs open-jam "
            "call 36,43",
        ),
        ("HRC push/fold 10 bb (2 akcje)", "SB jam 58,29; BB call 37,38"),
    ],
    15: [
        (
            "GW-AI 16 bb",
            "SB 5,2/67,8/25,0/2,0 (VPIP 94,8); BB vs limp X 61,7 / iso 26,9 (3x 14,2 + 5x 12,7) / "
            "J 11,3",
        ),
        ("GW-AI 16 bb, drzewo bez MR", "SB 6,3/89,1/-/4,5"),
        ("HRC push/fold 15 bb", "SB jam 45,66; BB call 28,55"),
    ],
    20: [
        (
            "GW-AI 20 bb",
            "SB 5,2/61,4/33,3/0,1; BB vs limp X 62,7 / iso 28,7 (3x 15,2 + 6x 13,5) / J 8,6; "
            "SB(limp) vs iso-jam F ~82",
        ),
        (
            "GW biblioteka 20 bb (2025-12-01)",
            "SB 4,7/64,0/30,7/0,5; BB vs MR: F 21,0 C 52,2 3bet 13,6 (5x 7,9 + 7x 5,7) J 13,2",
        ),
        ("HRC push/fold 20 bb", "SB jam 40,20; BB call 21,72"),
    ],
}


def main():
    OUT = fp.OUT
    pk = sorted(OUT.glob("round*.pkl"), key=lambda p: int(p.stem[5:]))
    final = int(sys.argv[1]) if len(sys.argv) > 1 else int(pk[-1].stem[5:])
    rounds = [pickle.load(open(OUT / f"round{r}.pkl", "rb")) for r in range(final + 1)]
    lines = [
        "# Częstości preflop (% kombinacji gracza w węźle, ważone zasięgiem własnym; chipEV, bez "
        "ante)",
        "# SB: fold limp raise(2x/2,5x) jam | L = BB vs limp: check iso(3,5bb) jam | LI = SB vs "
        "iso: fold call jam |",
        "# LJ = SB(limp) vs jam BB: fold call | R2/R25 = BB vs 2x/2,5x: fold call 3bet-jam | J = "
        "BB vs open-jam: call",
        f"# rundy: R0 = placeholder ConstEQR 1,05/0,85; R{final} = końcowa",
        "",
    ]
    depths = rounds[-1]["state"]["depths"]
    for d in depths:
        lines.append(f"=== {d:g} bb ===")
        for r, z in enumerate(rounds):
            res = z["res"][d]
            c = row(res)
            lines.append(
                f"R{r}: SB {c['SB']} | L {c['L']} | LI {c['LI']} | LJ {c['LJ']} | R2 {c['R2']} | "
                f"R25 {c['R25']} | J {c['J']} | "
                f"VPIP {100 - f(res, 'root', 'fold'):.1f} | EV_SB {res.ev_sb:+.4f} | expl "
                f"{res.expl:.1e}"
            )
        for name, txt in REFS.get(int(d), []):
            lines.append(f"  ref {name}: {txt}")
        lines.append("")

    # push/fold vs HRC (drzewo jamfold) i pełne drzewo przy <= 10 bb (model liścia z 10 bb,
    # ekstrapolacja)
    hrc = {6: (68.34, 54.45), 8: (61.86, 44.97), 10: (58.29, 37.38)}
    model_final = rounds[-1]["model"]
    lines.append(
        "=== <= 10 bb: push/fold (drzewo jam/fold, macierz eval7) vs HRC; pełne drzewo (liść: "
        "model z 10 bb) ==="
    )
    for S in (6.0, 8.0, 10.0):
        pf = H.solve(
            S,
            H.CheckdownLeaf(),
            tree=H.TreeConfig(mode="jamfold"),
            equity=fp.E7,
            iters=20000,
            target_expl=1e-5,
        )
        leaf = (
            fp.IntegLeaf(
                {
                    k.replace("@10", f"@{S:g}"): v
                    for k, v in getattr(model_final, "a", {}).items()
                    if k.endswith("@10")
                }
            )
            if S != 10
            else model_final
        )
        full = rounds[-1]["res"][10.0] if S == 10 else fp.preflop(S, leaf)
        c = row(full)
        lines.append(
            f"{S:g} bb: jam/fold SB jam {f(pf, 'root', 'jam'):.2f} BB call "
            f"{f(pf, 'jam', 'call'):.2f} | HRC {hrc[int(S)][0]:.2f} / {hrc[int(S)][1]:.2f} | "
            f"pełne drzewo: SB {c['SB']} | L {c['L']} | LJ {c['LJ']} | J {c['J']}"
            + ("" if S == 10 else " (ekstrapolacja liścia z 10 bb)")
        )
    lines.append("  ref GW-AI 8 bb: SB 23,1/32,9/0,0/44,0; BB vs jam call 44,0")
    (OUT / "freq_table.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    cl = [
        "# Zmiana między rundami (węzły z zasięgiem łącznym >= 1%; EV klas w bb od początku "
        "rozdania)"
    ]
    conv = {}
    for r in range(1, final + 1):
        for d in depths:
            txt, dd = change(
                rounds[r - 1]["res"][d],
                rounds[r]["res"][d],
                rounds[r - 1]["model"],
                rounds[r]["model"],
            )
            cl.append(f"R{r - 1}->R{r} {d:g} bb: {txt}")
            conv[f"R{r - 1}->R{r}@{d:g}"] = dd
    (OUT / "convergence.txt").write_text("\n".join(cl) + "\n")
    json.dump(conv, open(OUT / "convergence.json", "w"), indent=1, default=float)
    print("\n".join(cl))

    for d in depths:
        res = rounds[-1]["res"][d]
        jr = joint_reach(res)
        parts = [
            f"# Charty HU Spin {d:g} bb, chipEV, runda końcowa R{final} (punkt stały "
            "preflop<->postflop)",
            "# kody: F fold, L limp, R raise 2x, Q raise 2,5x, J jam, X check, I iso 3,5 bb, C "
            "call; '*' >= 99,5%",
            "# wiersz/kolumna: wyższa ranga; suited nad przekątną, offsuit pod nią",
            "",
        ]
        spec = [
            ("root", None, "SB first-in: akcja dominująca"),
            ("root", "limp", "SB first-in: % limp"),
            ("root", "jam", "SB first-in: % jam"),
        ]
        for a in res.nodes["root"].actions:
            if a.startswith("r"):
                spec.append(("root", a, f"SB first-in: % raise {a[1:]}x"))
        spec += [
            ("limp", None, "BB vs limp: akcja dominująca"),
            ("limp", "iso", "BB vs limp: % iso 3,5 bb"),
            ("limp", "jam", "BB vs limp: % jam"),
            ("limp-iso", None, "SB vs iso 3,5 bb: akcja dominująca"),
        ]
        for rid in ("r2.5", "r2"):
            if rid in res.nodes:
                spec += [
                    (rid, None, f"BB vs raise {rid[1:]}x: akcja dominująca"),
                    (rid, "call", f"BB vs raise {rid[1:]}x: % call"),
                    (rid, "jam", f"BB vs raise {rid[1:]}x: % 3bet-jam"),
                ]
        spec += [("jam", "call", "BB vs open-jam: % call")]
        for nid, act, title in spec:
            tag = f" [zasięg łączny węzła {100 * jr[nid]:.1f}%" + (
                ", POZA ŚCIEŻKĄ: strategia tylko jako groźba]" if jr[nid] < 0.01 else "]"
            )
            parts.append(H.chart_text(res.nodes[nid], act, title=f"--- {title} (węzeł {nid}){tag}"))
            parts.append("")
        (OUT / f"charts_{d:g}bb.txt").write_text("\n".join(parts))
    print("charty:", [str(OUT / f"charts_{d:g}bb.txt") for d in depths])


if __name__ == "__main__":
    main()

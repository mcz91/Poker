"""Tabela rund fictitious play z OUT/state.json (run_fpa.py).  Użycie: python report_fpa.py OUT

Per runda i głębokość: luka BR profilu R̄_r held-out (świeży blok) i w modelu puli, największa
zmiana częstości R̄_r wobec R̄_{r-1}, zmiana iteratu R_{r+1} wobec R_r i R_{r-1} (2-cykl: duża
pierwsza, mała druga), największa |Δ| wobec referencji, naruszenia dominacji, zgodność akcji
najlepszej IN/OOS; na końcu wynik bloku held-out końcowego.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _maxdiff(a: dict, b: dict, mass: dict) -> float:
    best = 0.0
    for nid, fa in a.items():
        fb = b.get(nid)
        if fb is None or list(fa) != list(fb) or mass.get(nid, 0.0) < 0.01:
            continue
        best = max(best, max(abs(x - fb[k]) for k, x in fa.items()))
    return best


def _gap(g: dict) -> str:
    return f"{g['expl']:.4f} ({g['gap_sb']:.3f}/{g['gap_bb']:.3f})"


def _agree(x: dict | None) -> str:
    if not x:
        return "-"
    return "/".join(f"{100 * v:.0f}" for v in x.values())


def rounds_table(state: dict) -> str:
    depths = list(state["rounds"][0]["depths"]) if state["rounds"] else []
    lines = []
    for d in depths:
        lines.append(f"=== {d} bb")
        lines.append(
            "r  luka held-out (SB/BB)   luka w puli            ΔR̄ pp  ΔR it1/it2 pp  "
            "refs max|Δ| pp     dominacja  IN/OOS root/limp/r2 %"
        )
        its = []
        for rnd in state["rounds"]:
            rec = rnd["depths"][d]
            its.append(rec["freq_iterate"])
            ch = rec.get("change")
            d1 = _maxdiff(its[-1], its[-2], rec["mass"]) if len(its) > 1 else float("nan")
            d2 = _maxdiff(its[-1], its[-3], rec["mass"]) if len(its) > 2 else float("nan")
            refs = " ".join(f"{x['node']}:{x['max_abs']:.1f}" for x in rec["refs"]) or "-"
            dom = sum(rec["dominance"].values())
            lines.append(
                f"{rec['r']:<2} {_gap(rec['gap_ho']):<24} {_gap(rec['gap_in']):<22} "
                f"{(ch[0] if ch else float('nan')):6.1f}  {d1:5.1f} / {d2:5.1f}  "
                f"{refs:<18} {dom:<10} {_agree(rec.get('agree_in_oos'))}"
            )
        fin = (state.get("final") or {}).get(d)
        if fin:
            gaps = ", ".join(f"{k} {_gap(v)}" for k, v in fin["gaps"].items())
            lines.append(f"held-out końcowy: {gaps}")
            lines.append(
                f"  IN/OOS {_agree(fin['agree_in_oos'])} ({', '.join(fin['agree_in_oos'])}); "
                f"dominacja {fin['dominance']}"
            )
            for k, b in fin["bias"].items():
                lines.append(
                    f"  bias {k}: SB {b['SB']['bias']:+.3f}±{b['SB']['se']:.3f} "
                    f"BB {b['BB']['bias']:+.3f}±{b['BB']['se']:.3f} bb"
                )
            for x in fin["refs"]:
                lines.append(f"  {x['ref']} {x['node']}: nasze {x['ours']} Δ {x['diff']}")
    return "\n".join(lines)


def main() -> None:
    print(rounds_table(json.loads((Path(sys.argv[1]) / "state.json").read_text())))


if __name__ == "__main__":
    main()

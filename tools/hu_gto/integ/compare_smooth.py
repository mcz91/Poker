"""Model puli surowy vs ściągany empirycznym Bayesem (fpa.shrink), oceniany na bloku held-out
końcowym run_fpa.py.  Użycie: python compare_smooth.py OUT [skale wariancji ...]

Dla każdego wariantu modelu puli M (surowy; EB z wariancją jackknife x skala): równowaga R*(M)
i jej luka BR w modelu held-out, naruszenia dominacji R*(M), zgodność akcji najlepszej M vs
model held-out (na R*(M)). Skala < 1 sprawdza, czy wynik zależy od zawyżenia wariancji
jackknife przy herdingu.  Solve'y postflop bloku held-out są czytane z OUT/cache (bez liczenia).
Wynik: OUT/compare_smooth.json.
"""

from __future__ import annotations

import copy
import json
import pickle
import sys
from pathlib import Path

import fp
import fpa
import run_fpa
from fp import H


def variants(fpd: fpa.FictitiousPlay, scales: list[float]) -> dict:
    out = {}
    for name, smooth, s in [("surowy", False, 1.0)] + [(f"EB x{s:g}", True, s) for s in scales]:
        f = copy.copy(fpd)
        f.smooth = smooth
        f.rounds = [
            {k: fpa.LeafData(x.lf, x.ev, s * x.var) for k, x in P.items()} for P in fpd.rounds
        ]
        out[name] = f.pooled_model()[0]
    return out


def compare(fpd: fpa.FictitiousPlay, ho_model, scales: list[float]) -> dict:
    rep = {}
    for name, m in variants(fpd, scales).items():
        eq = fpd._solve(m)
        gap = H.evaluate_profile(eq, ho_model, equity=fp.E7)
        rep[name] = dict(
            gap_ho={k: float(v) for k, v in gap.items()},
            dominance=run_fpa.dominance(eq),
            agree=fpa.agreement(eq, m, ho_model, ("root", "limp", "r2")),
            root={a: round(100 * v, 1) for a, v in eq.nodes["root"].freq.items()},
        )
    return rep


def main() -> None:
    out_dir = Path(sys.argv[1])
    scales = [float(x) for x in sys.argv[2:]] or [1.0, 0.3, 0.1]
    fp.OUT, fp.CACHE = out_dir, out_dir / "cache"
    state = json.loads((out_dir / "state.json").read_text())
    final = pickle.load(open(out_dir / "fpa_final.pkl", "rb"))
    holdout = [(f, 1.0 / len(state["holdout"])) for f in state["holdout"]]
    report = {}
    for d, fpd in final["fps"].items():
        avg = final["profiles"][d]
        P = {}
        for lf in avg.leaves:
            res = {lab: fp.run_one(kw, 1)[0] for lab, kw in run_fpa.cheap_jobs(lf, holdout)}
            P[fp.leaf_key(lf)], _ = run_fpa.leaf_data(lf, holdout, res)
        rep = compare(fpd, fpd.raw_model(P), scales)
        report[f"{d:g}"] = rep
        for name, r in rep.items():
            g = r["gap_ho"]
            print(
                f"{d:g} bb {name:<8} luka R* w held-out {g['expl']:.4f} (SB {g['gap_sb']:.4f}, "
                f"BB {g['gap_bb']:.4f}); dominacja {sum(r['dominance'].values())}; "
                f"IN/OOS {r['agree']}; root {r['root']}"
            )
    (out_dir / "compare_smooth.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

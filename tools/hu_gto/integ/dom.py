"""Naruszenia dominacji w chartach: ręka XYs/XYo z obiema rangami >= innej ręki tej samej
kategorii (suited/offsuit) kontynuuje (nie pasuje) o ponad 50 pp rzadziej niż ręka słabsza.

Użycie: python dom.py [rundy...]   (domyślnie 3 4; czyta FP_OUT/round<N>.pkl z run_fp.py)
"""

import pickle
import sys

import fp
from fp import H

RK = "AKQJT98765432"


def _ranks(c):
    if len(c) == 2:
        return None
    return RK.index(c[0]), RK.index(c[1]), c[2]


def violations(nr, gap=0.5):
    """Pary 'silniejsza<słabsza' w węźle z akcją fold (NodeResult z hu_preflop)."""
    cont = 1 - nr.strategy[:, nr.actions.index("fold")]
    out = []
    for i, ci in enumerate(H.CLASSES):
        pi = _ranks(ci)
        if not pi:
            continue
        for j, cj in enumerate(H.CLASSES):
            pj = _ranks(cj)
            if not pj or i == j or pi[2] != pj[2]:
                continue
            # niższy indeks rangi = wyższa ranga, więc i dominuje j
            if pi[0] <= pj[0] and pi[1] <= pj[1] and cont[i] < cont[j] - gap:
                out.append(f"{ci}<{cj}")
    return out


def main():
    for rnd in [int(x) for x in sys.argv[1:]] or [3, 4]:
        R = pickle.load(open(fp.OUT / f"round{rnd}.pkl", "rb"))
        for d, res in R["res"].items():
            out = []
            for nid in ("root", "r2"):
                nr = res.nodes[nid]
                viol = violations(nr)
                nf = int((nr.strategy[:, nr.actions.index("fold")] > 0.5).sum())
                out.append(
                    f"{nid}: klas z fold>50% {nf}, naruszeń dominacji {len(viol)} np. {viol[:6]}"
                )
            print(f"R{rnd} {d:g}bb | " + " | ".join(out))


if __name__ == "__main__":
    main()

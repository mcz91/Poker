"""Analizy uzupełniające po pętli (tylko preflop + cache postflop, bez nowych solve'ów).
1) luka przeliczona: profil R_r oceniony w modelu M_{r+1}; M_{r+1} ma liście przeliczone
   solverem postflop na zakresach R_r, więc to luka R_r w grze z liśćmi z prawdziwych solve'ów
   (ten sam estymator),
2) zmiana w tej samej fazie 2-cyklu (R1->R3, R2->R4),
3) jackknife SE EV klas w liściach P3 (12 flopów, ten sam cache) vs różnice EV akcji preflop w R4.
Użycie: python analysis_extra.py  ->  out/analysis_extra.json + stdout"""

import json
import pickle

import fp
import numpy as np
from flopsample import herd
from fp import H
from report import change

R = {r: pickle.load(open(fp.OUT / f"round{r}.pkl", "rb")) for r in range(5)}
depths = R[4]["state"]["depths"]
out = dict(refit_gap={}, same_phase={}, jackknife={}, ev_gaps={})

print("# 1) luka profilu R_r: w modelu własnym M_r i w modelu przeliczonym M_{r+1} (bb/rozdanie)")
for r in range(4):
    for d in depths:
        own = H.evaluate_profile(R[r]["res"][d], R[r]["model"], equity=fp.E7)
        ref = H.evaluate_profile(R[r]["res"][d], R[r + 1]["model"], equity=fp.E7)
        out["refit_gap"][f"R{r}@{d:g}"] = dict(own=own, refit=ref)
        print(
            f"R{r} {d:g} bb: własny expl {own['expl']:.1e} | przeliczony expl {ref['expl']:.4f} "
            f"(SB {ref['gap_sb']:.4f}, BB {ref['gap_bb']:.4f}); EV_SB {own['ev_sb']:+.4f} -> "
            f"{ref['ev_sb']:+.4f}"
        )

print("\n# 2) zmiana w tej samej fazie 2-cyklu")
for a, b in ((1, 3), (2, 4)):
    for d in depths:
        txt, dd = change(R[a]["res"][d], R[b]["res"][d], R[a]["model"], R[b]["model"])
        out["same_phase"][f"R{a}->R{b}@{d:g}"] = dd
        print(f"R{a}->R{b} {d:g} bb: {txt}")

print(
    "\n# 3a) jackknife SE EV klasy w liściu (P3: zakresy R3, flopsmall, 12 flopów herding; bb, "
    "ważone masą klasy)"
)
sample = herd(R[3]["state"]["K2"])
for d in depths:
    for lf in R[3]["res"][d].leaves:
        if not fp.solvable(lf):
            continue
        sb, bb = fp.leaf_ranges(lf)
        res = []
        for f, _ in sample:
            p = fp.cache_path(fp.job_kw(lf["pot"], lf["depth"], sb, bb, f, fp.LOFI_TREE))
            res.append(json.loads(p.read_text()) if p.exists() else None)
        if any(x is None for x in res):
            print(f"  {fp.leaf_key(lf)}: brak w cache, pominięte")
            continue
        w = np.array([x for _, x in sample])
        eqx = fp.eq_vs_range(sb, bb)
        full = fp.aggregate.aggregate(res, w, lf["pot"], eq_exact=eqx)
        loo = []
        for i in range(len(res)):
            wi = w.copy()
            wi[i] = 0.0
            loo.append(fp.aggregate.aggregate(res, wi, lf["pot"], eq_exact=eqx)["ev_bb_ratio"])
        loo = np.array(loo)
        n = len(res)
        se = np.sqrt((n - 1) / n * np.nansum((loo - np.nanmean(loo, 0)) ** 2, 0))
        m = full["mass"] / full["mass"].sum(1, keepdims=True)
        rms = [float(np.sqrt(np.nansum(m[p] * se[p] ** 2))) for p in (0, 1)]
        out["jackknife"][fp.leaf_key(lf)] = dict(
            pot=lf["pot"],
            se_rms_bb=rms,
            se_max_bb=[float(np.nanmax(se[p][m[p] > 1e-3])) for p in (0, 1)],
            se_sb=se[1].tolist(),
            se_bb=se[0].tolist(),
        )
        print(
            f"  {fp.leaf_key(lf):<18} pula {lf['pot']:g}: SE RMS BB {rms[0]:.3f} SB {rms[1]:.3f} "
            "bb; "
            f"max BB {out['jackknife'][fp.leaf_key(lf)]['se_max_bb'][0]:.3f} SB "
            f"{out['jackknife'][fp.leaf_key(lf)]['se_max_bb'][1]:.3f}"
        )


def action_evs(res, model, nid):
    """EV (bb, od początku rozdania) każdej akcji w węźle nid per klasa aktora, przy strategiach
    res."""
    root = H.build_tree(res.depth, H.TreeConfig(**res.tree), fp.E7, model)
    sv = H._Solver(root)
    for n in sv.dec:
        n.S = res.nodes[n.id].strategy.astype(float).copy()
    one = np.ones(H.N)
    path = {"root": [], "limp": ["limp"], "r2": ["r2"]}[nid]
    n, r_sb, r_bb = sv.root, one.copy(), one.copy()
    for a in path:
        i = n.actions.index(a)
        if n.actor == 0:
            r_sb = r_sb * res.nodes[n.id].strategy[:, i]
        else:
            r_bb = r_bb * res.nodes[n.id].strategy[:, i]
        n = n.children[i]
    if n.actor == 0:
        ev = np.array([sv._value(c, 0, r_bb, False) / (H.W @ r_bb) for c in n.children])
        own = r_sb
    else:
        ev = np.array([sv._value(c, 1, r_sb, False) / (H.W.T @ r_sb) for c in n.children])
        own = r_bb
    return n.actions, ev, own


print(
    "\n# 3b) R4 (model M4): różnica EV między najlepszą i drugą akcją; % kombinacji aktora "
    "(ważone zasięgiem) poniżej progu"
)
for d in (15.0, 20.0, 10.0):
    for nid in ("root", "limp", "r2"):
        acts, ev, own = action_evs(R[4]["res"][d], R[4]["model"], nid)
        srt = np.sort(ev, 0)
        gap = srt[-1] - srt[-2]
        w = own * H.NCOMBO
        w = w / w.sum()
        fr = {t: float(w @ (gap < t)) for t in (0.02, 0.05, 0.1)}
        lr = None
        if nid == "root":
            il, ir = acts.index("limp"), acts.index("r2")
            d_lr = np.abs(ev[il] - ev[ir])
            lr = {t: float(w @ (d_lr < t)) for t in (0.02, 0.05, 0.1)}
        out["ev_gaps"][f"{nid}@{d:g}"] = dict(
            actions=acts, frac_gap_below=fr, frac_limp_vs_r2_below=lr, ev=np.round(ev, 4).tolist()
        )
        print(
            f"  {d:g} bb {nid:<5} akcje {acts}: luka<0,02 {100 * fr[0.02]:.0f}%, <0,05 "
            f"{100 * fr[0.05]:.0f}%, <0,1 {100 * fr[0.1]:.0f}%"
            + (
                f" | |EV limp - EV r2| <0,02 {100 * lr[0.02]:.0f}%, <0,05 {100 * lr[0.05]:.0f}%, "
                f"<0,1 {100 * lr[0.1]:.0f}%"
                if lr
                else ""
            )
        )
json.dump(out, open(fp.OUT / "analysis_extra.json", "w"), indent=1, default=float)

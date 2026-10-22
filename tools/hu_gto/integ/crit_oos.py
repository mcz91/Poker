"""Luka held-out: model liścia M4 vs solver postflop na zakresach R4, na flopach z próbki pętli
(IN) i SPOZA niej (OOS).

Dla każdego liścia R4 z zasięgiem >= 2% (głębokość d):
  pred  = EV klas przewidziane przez M4 (model addytywny dopasowany na zakresach R3) przy
          zakresach R4,
  IN    = flopsmall @1% na 12 flopach pętli, zakresy R4 (+ ta sama wygładzona poprawka drzewa co
          w M4),
  OOS   = to samo na 12 innych flopach (flopy 13..24 herdingu; rozłączne z IN).
Następnie luka BR profilu R4 w modelach M5_in / M5_oos / M5_all (liście przeliczone)
i R5 = równowaga M5_*.  Wejście: round3.pkl i round4.pkl z run_fp.py w FP_OUT; wyjście:
FP_OUT/crit_oos.json i crit_oos_<d>.pkl.
Użycie: python crit_oos.py 15 [20]
"""

import json
import os
import pickle
import sys
import time

import fp
import numpy as np
from flopsample import herd
from fp import H

WORKERS = int(os.environ.get("CR_WORKERS", 2))

R4 = pickle.load(open(fp.OUT / "round4.pkl", "rb"))
R3 = pickle.load(open(fp.OUT / "round3.pkl", "rb"))
M4, deltas = R4["model"], R4["deltas"]
IN = herd(12)
in_set = {f for f, _ in IN}
OOS = [(f, 1.0 / 12) for f, _ in herd(24) if f not in in_set]
assert len(OOS) == 12


def pred_ev(model_a, key, lf):
    sb, bb = fp.leaf_ranges(lf)
    a_sb, a_bb = model_a[key]
    R = fp.E7 + a_sb[:, None] - a_bb[None, :]
    ws = H.W * bb[None, :]
    wb = H.W.T * sb[None, :]
    sh_sb = (ws * R).sum(1) / ws.sum(1)
    sh_bb = (wb * (1 - R.T)).sum(1) / wb.sum(1)
    return np.stack([sh_bb, sh_sb]) * lf["pot"]


def wrms(x, m):
    ok = np.isfinite(x) & (m > 0)
    mm = m[ok] / m[ok].sum()
    return float(np.sqrt((mm * x[ok] ** 2).sum()))


def freqs(res):
    out = {}
    for nid in ("root", "limp", "limp-iso", "r2", "r2.5", "jam"):
        if nid in res.nodes:
            out[nid] = {a: round(100 * v, 1) for a, v in res.nodes[nid].freq.items()}
    return out


def maxdiff(a, b, min_mass=0.02):
    best = (0.0, "-")
    for nid, nr in a.nodes.items():
        p = b.nodes.get(nid)
        if (
            p is None
            or p.actions != nr.actions
            or max(fp.node_mass(nr), fp.node_mass(p)) < min_mass
        ):
            continue
        for act in nr.actions:
            d = abs(nr.freq[act] - p.freq[act]) * 100
            if d > best[0]:
                best = (d, f"{nid}:{act}")
    return best


report = {}
for d in [float(x) for x in sys.argv[1:]] or [15.0]:
    t0 = time.time()
    res4 = R4["res"][d]
    todo = [lf for lf in res4.leaves if fp.solvable(lf)]
    jobs = []
    for lf in todo:
        sb, bb = fp.leaf_ranges(lf)
        for f, _ in IN + OOS:
            jobs.append(
                (fp.leaf_key(lf), fp.job_kw(lf["pot"], lf["depth"], sb, bb, f, fp.LOFI_TREE))
            )
    fp.log(
        f"{d:g} bb: liście {[fp.leaf_key(lf) for lf in todo]}, {len(jobs)} jobów, "
        f"OOS={[f for f, _ in OOS]}"
    )
    out = fp.run_jobs(jobs, WORKERS, 1, tag=f"held-out {d:g}bb")
    n = len(IN) + len(OOS)
    rep = dict(leaves={}, flops_in=[f for f, _ in IN], flops_oos=[f for f, _ in OOS])
    a_in, a_oos, a_all = dict(M4.a), dict(M4.a), dict(M4.a)
    for i, lf in enumerate(todo):
        k = fp.leaf_key(lf)
        rs = out[i * n : (i + 1) * n]
        sb, bb = fp.leaf_ranges(lf)
        eqx = fp.eq_vs_range(sb, bb)
        dl = deltas.get(k, 0.0)
        ag_in = fp.aggregate.aggregate(rs[:12], [w for _, w in IN], lf["pot"], eq_exact=eqx)
        ag_oos = fp.aggregate.aggregate(rs[12:], [w for _, w in OOS], lf["pot"], eq_exact=eqx)
        ag_all = fp.aggregate.aggregate(
            rs, [0.5 * w for _, w in IN] + [0.5 * w for _, w in OOS], lf["pot"], eq_exact=eqx
        )
        ev_in, ev_oos, ev_all = (ag["ev_bb_ratio"] + dl for ag in (ag_in, ag_oos, ag_all))
        pr = pred_ev(M4.a, k, lf)
        mass = ag_all["mass"]
        prior = np.stack([H.NCOMBO, H.NCOMBO]).astype(float)
        st = {}
        for name, x in (
            ("pred-IN", pr - ev_in),
            ("pred-OOS", pr - ev_oos),
            ("IN-OOS", ev_in - ev_oos),
        ):
            st[name] = dict(
                rms_mass=[wrms(x[p], mass[p]) for p in (0, 1)],
                rms_prior=[wrms(x[p], prior[p]) for p in (0, 1)],
                bias_mass=[
                    float(np.nansum(mass[p] * x[p]) / mass[p][np.isfinite(x[p])].sum())
                    for p in (0, 1)
                ],
                max=[float(np.nanmax(np.abs(x[p]))) for p in (0, 1)],
            )
        rng = dict(
            in_=ag_in["range_ev_bb"].tolist(),
            oos=ag_oos["range_ev_bb"].tolist(),
            all=ag_all["range_ev_bb"].tolist(),
        )
        worst = {}
        for p, who in ((1, "SB"), (0, "BB")):
            x = np.abs(ev_in[p] - ev_oos[p])
            x = np.where(np.isfinite(x) & (mass[p] > 0), x, -1)
            j = np.argsort(-x)[:6]
            worst[who] = [
                (
                    H.CLASSES[t],
                    round(float(ev_in[p][t]), 3),
                    round(float(ev_oos[p][t]), 3),
                    round(float(pr[p][t]), 3),
                    round(float(lf["range_sb" if p else "range_bb"][t]), 3),
                )
                for t in j
            ]
        rep["leaves"][k] = dict(
            pot=lf["pot"],
            freq_sb=lf["freq_sb"],
            freq_bb=lf["freq_bb"],
            stats=st,
            range_ev=rng,
            worst=worst,
            ev_in=ev_in.tolist(),
            ev_oos=ev_oos.tolist(),
            ev_pred=pr.tolist(),
            mass=mass.tolist(),
        )
        for a, ev in ((a_in, ev_in), (a_oos, ev_oos), (a_all, ev_all)):
            a[k] = H.fit_additive(fp.E7, ev[1] / lf["pot"], ev[0] / lf["pot"], sb, bb)
        fp.log(
            f"  {k}: pred-IN RMS(mass) BB/SB "
            f"{st['pred-IN']['rms_mass'][0]:.3f}/{st['pred-IN']['rms_mass'][1]:.3f}; "
            f"pred-OOS {st['pred-OOS']['rms_mass'][0]:.3f}/{st['pred-OOS']['rms_mass'][1]:.3f}; "
            f"IN-OOS {st['IN-OOS']['rms_mass'][0]:.3f}/{st['IN-OOS']['rms_mass'][1]:.3f} "
            f"(prior {st['IN-OOS']['rms_prior'][0]:.3f}/{st['IN-OOS']['rms_prior'][1]:.3f}); "
            f"EV zakresu SB in {rng['in_'][1]:.3f} oos {rng['oos'][1]:.3f}"
        )
    models = {
        "M4": M4,
        "M5_in": fp.IntegLeaf(a_in),
        "M5_oos": fp.IntegLeaf(a_oos),
        "M5_all": fp.IntegLeaf(a_all),
    }
    rep["gap_R4"] = {}
    for name, m in models.items():
        g = H.evaluate_profile(res4, m, equity=fp.E7)
        rep["gap_R4"][name] = {k: float(v) for k, v in g.items()}
        fp.log(
            f"  luka R4 w {name}: expl {g['expl']:.4f} (SB {g['gap_sb']:.4f}, BB "
            f"{g['gap_bb']:.4f}), EV_SB {g['ev_sb']:+.4f}"
        )
    rep["R5"] = {}
    sols = {}
    for name in ("M5_in", "M5_oos", "M5_all"):
        r5 = fp.preflop(d, models[name])
        sols[name] = r5
        rep["R5"][name] = dict(
            freqs=freqs(r5),
            ev_sb=r5.ev_sb,
            expl_own=r5.expl,
            vs_R4=maxdiff(r5, res4),
            vs_R3=maxdiff(r5, R3["res"][d]),
        )
        fp.log(
            f"  R5[{name}] {freqs(r5)['root']} EV_SB {r5.ev_sb:+.4f}; vs R4 {maxdiff(r5, res4)}, "
            f"vs R3 {maxdiff(r5, R3['res'][d])}"
        )
    rep["R5_in_vs_oos"] = maxdiff(sols["M5_in"], sols["M5_oos"])
    # luka krzyżowa: równowaga modelu IN oceniona w modelu OOS (i odwrotnie) - przeuczenie
    # na próbce flopów
    rep["cross"] = {}
    for a, b in (("M5_in", "M5_oos"), ("M5_oos", "M5_in"), ("M5_in", "M5_all")):
        g = H.evaluate_profile(sols[a], models[b], equity=fp.E7)
        rep["cross"][f"R5[{a}] w {b}"] = {k: float(v) for k, v in g.items()}
        fp.log(
            f"  luka R5[{a}] w {b}: expl {g['expl']:.4f} (SB {g['gap_sb']:.4f}, BB "
            f"{g['gap_bb']:.4f})"
        )
    fp.log(f"  R5 in vs oos: {rep['R5_in_vs_oos']}; czas {time.time() - t0:.0f} s")
    rep["R3_freqs"] = freqs(R3["res"][d])
    rep["R4_freqs"] = freqs(res4)
    report[f"{d:g}"] = rep
    json.dump(report, open(fp.OUT / "crit_oos.json", "w"), indent=1, default=float)
    pickle.dump(
        dict(models={k: v.a for k, v in models.items() if k != "M4"}, sols=sols),
        open(fp.OUT / f"crit_oos_{d:g}.pkl", "wb"),
    )

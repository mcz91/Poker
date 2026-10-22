"""Eksploatowalność: luka BR w modelu + kontrola odchyleń prawdziwymi solve'ami postflop.

Dla odchylenia D (zmiana strategii preflop jednego gracza, rywal bez zmian):
  przewidywany zysk = EV(D | M_final) - EV(eq | M_final)           (model liścia z pętli)
  prawdziwy zysk    = EV(D | M_D) - EV(eq | M_eq)
gdzie M_eq / M_D = model z liśćmi przeliczonymi solverem postflop na zakresach z profilu eq / D
(ten sam estymator co w pętli: flopsmall na K2 flopach, estymator ratio, + ta sama poprawka
drzewa D). Dopasowanie addytywne odtwarza EV klas wobec podanych zakresów dokładnie, więc
EV(.|M_X) = EV z solve'ów.
Różnica przewidywany - prawdziwy = błąd ekstrapolacji modelu liścia na nowe zakresy.

Użycie: python deviations.py out/round3.pkl 15 [20]
"""

import json
import pickle
import sys

import fp
import numpy as np
from flopsample import herd
from fp import H

src = sys.argv[1]
depths = [float(x) for x in sys.argv[2:]] or [15.0]
z = pickle.load(open(src, "rb"))
res_all, model, deltas = z["res"], z["model"], z["deltas"]
K2 = z["state"]["K2"]
sample = herd(K2)


def profile(res, leaf_model, mods=None):
    root = H.build_tree(res.depth, H.TreeConfig(**res.tree), fp.E7, leaf_model)
    sv = H._Solver(root)
    for n in sv.dec:
        n.S = (mods or {}).get(n.id, res.nodes[n.id].strategy).astype(float).copy()
    ex = sv.exploitability()
    _, leaves = H._collect(sv)
    return ex, leaves


def onehot(res, nid, action, mix_from=None):
    nr = res.nodes[nid]
    s = np.zeros_like(nr.strategy)
    if mix_from is None:
        s[:, nr.actions.index(action)] = 1.0
    else:  # przenieś masę akcji mix_from na action
        s = nr.strategy.copy()
        s[:, nr.actions.index(action)] += s[:, nr.actions.index(mix_from)]
        s[:, nr.actions.index(mix_from)] = 0.0
    return s


def real_model(leaves, keys, tag, base):
    """Model = `base` (słownik a) z liśćmi `keys` przeliczonymi solve'ami na zakresach `leaves`."""
    a = dict(base)
    stats = {}
    todo = [
        lf for lf in leaves if fp.leaf_key(lf) in keys and min(lf["freq_sb"], lf["freq_bb"]) > 1e-4
    ]
    jobs = []
    for lf in todo:
        sb, bb = fp.leaf_ranges(lf)
        for f, _ in sample:
            jobs.append(
                (fp.leaf_key(lf), fp.job_kw(lf["pot"], lf["depth"], sb, bb, f, fp.LOFI_TREE))
            )
    out = fp.run_jobs(jobs, 4, 1, tag=tag)
    for i, lf in enumerate(todo):
        k = fp.leaf_key(lf)
        agg = fp.leaf_estimate(lf, sample, None, out[i * len(sample) : (i + 1) * len(sample)])
        ev = agg["ev_bb_ratio"] + deltas.get(k, 0.0)
        sb, bb = fp.leaf_ranges(lf)
        a[k] = H.fit_additive(fp.E7, ev[1] / lf["pot"], ev[0] / lf["pot"], sb, bb)
        stats[k] = dict(
            freq_sb=lf["freq_sb"], freq_bb=lf["freq_bb"], range_ev=agg["range_ev_bb"].tolist()
        )
    m = fp.IntegLeaf(a)
    return m, stats


report = {}
for d in depths:
    res = res_all[d]
    ex_eq, leaves_eq = profile(res, model)
    devs = {
        "SB limp 100%": ("SB", {"root": onehot(res, "root", "limp")}),
        "BB nigdy nie izoluje (iso -> check)": (
            "BB",
            {"limp": onehot(res, "limp", "check", mix_from="iso")},
        ),
    }
    rn = res.nodes["root"]
    big = max((a for a in rn.actions if a.startswith("r")), key=lambda a: rn.freq[a])
    devs[f"SB raise any two ({big})"] = ("SB", {"root": onehot(res, "root", big)})
    prof = {}
    for name, (who, mods) in devs.items():
        ex_d, leaves_d = profile(res, model, mods)
        changed = [
            fp.leaf_key(lf)
            for lf, le in zip(leaves_d, leaves_eq, strict=True)
            if np.abs(np.array(lf["range_sb"]) - le["range_sb"]).max() > 1e-6
            or np.abs(np.array(lf["range_bb"]) - le["range_bb"]).max() > 1e-6
        ]
        prof[name] = (who, mods, ex_d, leaves_d, changed)
    union = sorted({k for p in prof.values() for k in p[4]})
    M_eq, st_eq = real_model(
        res.leaves, union, f"{d:g}bb eq", model.a
    )  # res.leaves: te same zadania co P_r (cache)
    ev_eq_real = profile(res, M_eq)[0]
    rep = dict(
        model_gap=dict(gap_sb=res.gap_sb, gap_bb=res.gap_bb, expl=res.expl),
        eq=dict(
            ev_model=ex_eq["ev_sb"], ev_real=ev_eq_real["ev_sb"], leaves=st_eq, refit_keys=union
        ),
        refit_gap=dict(
            gap_sb=ev_eq_real["gap_sb"], gap_bb=ev_eq_real["gap_bb"], expl=ev_eq_real["expl"]
        ),
        deviations={},
    )
    fp.log(
        f"{d:g}bb: luka BR w modelu {res.expl:.2e} (SB {res.gap_sb:.2e}, BB {res.gap_bb:.2e}); "
        f"EV_SB eq model {ex_eq['ev_sb']:+.4f} vs solve'y na zakresach eq "
        f"{ev_eq_real['ev_sb']:+.4f} (liście {union}); "
        f"luka profilu eq w modelu przeliczonym {ev_eq_real['expl']:.4f} (SB "
        f"{ev_eq_real['gap_sb']:.4f}, BB {ev_eq_real['gap_bb']:.4f})"
    )
    for name, (who, mods, ex_d, leaves_d, changed) in prof.items():
        sign = 1 if who == "SB" else -1
        pred = sign * (ex_d["ev_sb"] - ex_eq["ev_sb"])
        M_d, st_d = real_model(leaves_d, changed, f"{d:g}bb {name}", M_eq.a)
        ev_d_real = profile(res, M_d, mods)[0]
        real = sign * (ev_d_real["ev_sb"] - ev_eq_real["ev_sb"])
        rep["deviations"][name] = dict(
            who=who,
            pred_gain=pred,
            real_gain=real,
            err=pred - real,
            changed_leaves=changed,
            leaves=st_d,
            ev_dev_model=ex_d["ev_sb"],
            ev_dev_real=ev_d_real["ev_sb"],
        )
        fp.log(
            f"  {name}: zysk {who} przewidywany {pred:+.4f}, z solve'ów {real:+.4f}, błąd modelu "
            f"{pred - real:+.4f} bb/rozdanie; liście {changed}"
        )
    report[f"{d:g}"] = rep
    json.dump(report, open(fp.OUT / "deviations.json", "w"), indent=1, default=float)

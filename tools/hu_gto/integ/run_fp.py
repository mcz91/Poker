"""Pętla punktu stałego preflop <-> postflop.  Użycie: python run_fp.py [K2] [K_HI] [depths...]

Runda r: preflop R_r (model liścia M_r) -> liście -> postflop P_r (lofi K2 flopów; w rundzie
HIFI_ROUND też drzewo produkcyjne na K_HI flopach) -> M_{r+1}.  M_0 = ConstEQR 1,05/0,85
(placeholder). Stop: zmiana R_{r-1} -> R_r poniżej progów (1 pp częstości węzła z masą >= 2%,
0,02 bb EV klasy) po rundzie z poprawką drzewa, albo MAX_ROUNDS.  Wszystkie solve'y postflop są
w cache (sha1 zadania), więc ponowne uruchomienie odtwarza wynik bez liczenia.
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
from hupf_py.pipeline import auto_tree

K2 = int(sys.argv[1]) if len(sys.argv) > 1 else 12
KHI = int(sys.argv[2]) if len(sys.argv) > 2 else 4
DEPTHS = [float(x) for x in sys.argv[3:]] or [10.0, 15.0, 20.0]
HIFI_ROUND = int(os.environ.get("FP_HIFI_ROUND", 2))
# rundy postflop P0..P{MAX-1} -> preflop R0..R{MAX}
MAX_ROUNDS = int(os.environ.get("FP_MAX_ROUNDS", 4))
THR_FREQ, THR_EV = 1.0, 0.02

fp.OUT.mkdir(parents=True, exist_ok=True)
lo_sample = herd(K2)
hi_sample = herd(KHI)
fp.log(
    f"START K2={K2} KHI={KHI} depths={DEPTHS} lofi={fp.LOFI_TREE} target={fp.TARGET}% "
    f"hifi_target={fp.HIFI_TARGET}% floor={fp.FLOOR}"
)
fp.log("flopy lofi:", [f for f, _ in lo_sample])
fp.log("flopy hifi:", [f for f, _ in hi_sample])

model = H.ConstEQRLeaf(1.05, 0.85)
deltas, delta_raw, delta_info = {}, {}, {}
state = dict(rounds=[], K2=K2, KHI=KHI, depths=DEPTHS)
prev, prev_model = None, None
t_start = time.time()

for r in range(MAX_ROUNDS + 1):
    t = time.time()
    res = {d: fp.preflop(d, model) for d in DEPTHS}
    rnd = dict(
        r=r,
        model_info=getattr(model, "info", {"all": "ConstEQR 1.05/0.85"}),
        preflop={d: fp.res_to_json(res[d]) for d in DEPTHS},
        preflop_s=time.time() - t,
    )
    for d in DEPTHS:
        x = res[d]
        fr = {
            k: {a: round(100 * v, 1) for a, v in x.nodes[k].freq.items()}
            for k in ("root", "limp")
            if k in x.nodes
        }
        fp.log(
            f"R{r} {d:g}bb EV_SB {x.ev_sb:+.4f} expl {x.expl:.1e} it {x.iters} {x.seconds:.1f}s "
            f"{fr}"
        )
    converged = False
    if prev is not None:
        ch = {d: fp.compare(prev[d], res[d], prev_model, model) for d in DEPTHS}
        rnd["change"] = ch
        for d in DEPTHS:
            c = ch[d]
            fp.log(
                f"  zmiana R{r - 1}->R{r} {d:g}bb: max freq {c['max_freq_pp']:.2f} pp "
                f"({c['max_freq_at']}), "
                f"EV SB max {c['ev_sb_max']:.4f} ({c['ev_sb_at']}) mean {c['ev_sb_mean']:.4f}, "
                f"EV BB max {c['ev_bb_max']:.4f} ({c['ev_bb_at']}) mean {c['ev_bb_mean']:.4f}, "
                f"dEV gry {c['d_ev_game']:+.4f}"
            )
        converged = all(
            c["max_freq_pp"] < THR_FREQ and c["ev_sb_max"] < THR_EV and c["ev_bb_max"] < THR_EV
            for c in ch.values()
        )
    state["rounds"].append(rnd)
    pickle.dump(
        dict(state=state, res=res, model=model, deltas=deltas, delta_raw=delta_raw),
        open(fp.OUT / f"round{r}.pkl", "wb"),
    )
    if (converged and r >= HIFI_ROUND + 2) or r == MAX_ROUNDS:
        fp.log(f"KONIEC po R{r}: converged={converged}")
        break

    leaves = [lf for d in DEPTHS for lf in res[d].leaves]
    todo = [lf for lf in leaves if fp.solvable(lf)]
    skipped = [
        (fp.leaf_key(lf), round(lf["freq_sb"], 3), round(lf["freq_bb"], 3))
        for lf in leaves
        if not fp.solvable(lf)
    ]
    fp.log(
        f"P{r}: liście liczone: {[fp.leaf_key(lf) for lf in todo]}; "
        f"pominięte (zasięg < {fp.MIN_REACH}): {skipped}"
    )
    todo.sort(key=lambda lf: (lf["line"] != "limp_check", -lf["depth"]))
    jobs = []
    for lf in todo:
        sb, bb = fp.leaf_ranges(lf)
        for f, _ in lo_sample:
            jobs.append(
                (fp.leaf_key(lf), fp.job_kw(lf["pot"], lf["depth"], sb, bb, f, fp.LOFI_TREE))
            )
    out = fp.run_jobs(jobs, 4, 1, tag=f"P{r} lofi")
    solved, k = {}, 0
    leaf_stats = {}
    for lf in todo:
        rs = out[k : k + len(lo_sample)]
        k += len(lo_sample)
        agg = fp.leaf_estimate(lf, lo_sample, fp.LOFI_TREE, rs)
        key = fp.leaf_key(lf)
        solved[key] = dict(lf=lf, ev=agg["ev_bb_ratio"], agg=agg)
        leaf_stats[key] = dict(
            range_ev_bb=agg["range_ev_bb"].tolist(),
            range_eq=agg["range_eq"].tolist(),
            solve_s=float(sum(x["solve_s"] for x in rs)),
        )
        fp.log(
            f"  {key}: EV zakresu BB {agg['range_ev_bb'][0]:.3f} SB {agg['range_ev_bb'][1]:.3f} "
            f"(pula {lf['pot']}), "
            f"EQR zakresu BB {agg['range_ev_bb'][0] / lf['pot'] / agg['range_eq'][0]:.3f} "
            f"SB {agg['range_ev_bb'][1] / lf['pot'] / agg['range_eq'][1]:.3f}"
        )
    if r == HIFI_ROUND:
        hjobs = []
        for lf in todo:
            sb, bb = fp.leaf_ranges(lf)
            tree = auto_tree((lf["depth"] - lf["pot"] / 2) / lf["pot"])
            for f, _ in hi_sample:
                hjobs.append(
                    (
                        fp.leaf_key(lf),
                        fp.job_kw(lf["pot"], lf["depth"], sb, bb, f, tree, target=fp.HIFI_TARGET),
                    )
                )
        hout = fp.run_jobs(hjobs, 2, 2, tag=f"P{r} hifi")
        lk = fp.run_jobs(
            [
                (
                    fp.leaf_key(lf),
                    fp.job_kw(lf["pot"], lf["depth"], *fp.leaf_ranges(lf), f, fp.LOFI_TREE),
                )
                for lf in todo
                for f, _ in hi_sample
            ],
            4,
            1,
            tag=f"P{r} lofi@hi",
        )
        k = 0
        for lf in todo:
            key = fp.leaf_key(lf)
            hi = fp.leaf_estimate(lf, hi_sample, None, hout[k : k + len(hi_sample)])
            lo = fp.leaf_estimate(lf, hi_sample, None, lk[k : k + len(hi_sample)])
            k += len(hi_sample)
            raw = hi["ev_bb"] - lo["ev_bb"]
            sm = fp.smooth_delta(raw, hi["eq_exact"], hi["mass"])
            delta_raw[key], deltas[key] = raw, sm
            m = hi["mass"] / hi["mass"].sum(1, keepdims=True)
            rd = hi["range_ev_bb"] - lo["range_ev_bb"]
            delta_info[key] = dict(
                range_delta_bb=rd.tolist(),
                raw_rms=[float(np.sqrt(np.nansum(m[p] * raw[p] ** 2))) for p in (0, 1)],
                resid_rms=[float(np.sqrt(np.nansum(m[p] * (raw[p] - sm[p]) ** 2))) for p in (0, 1)],
                hifi_solve_s=float(sum(x["solve_s"] for x in hout[k - len(hi_sample) : k])),
                tree=auto_tree((lf["depth"] - lf["pot"] / 2) / lf["pot"]),
            )
            fp.log(
                f"  poprawka drzewa {key}: Δ EV zakresu BB {rd[0]:+.3f} SB {rd[1]:+.3f} bb; "
                f"RMS surowa "
                f"{delta_info[key]['raw_rms'][0]:.3f}/{delta_info[key]['raw_rms'][1]:.3f}, "
                f"reszta po wygładzeniu "
                f"{delta_info[key]['resid_rms'][0]:.3f}/{delta_info[key]['resid_rms'][1]:.3f}"
            )
    rnd["postflop"] = dict(leaf_stats=leaf_stats, delta_info=delta_info.copy())
    prev, prev_model = res, model
    model, info = fp.build_model(solved, leaves, deltas)
    model.info = info
    model.solved = solved
    fp.log(f"M{r + 1}: {info}")
    fp.log(f"czas od startu {time.time() - t_start:.0f} s")
    json.dump(state, open(fp.OUT / "state.json", "w"), default=float)

json.dump(state, open(fp.OUT / "state.json", "w"), default=float)
fp.log(f"czas łączny {time.time() - t_start:.0f} s")

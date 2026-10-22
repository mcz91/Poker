"""Fictitious play preflop <-> postflop (fpa.py) na drzewie gw_tree, wznawialny.

python run_fpa.py --depths 15 --rounds 10 [--block 12] [--hifi-round 1] [--hifi-flops 30]
       [--hifi-min-spr 1.5] [--holdout 32] [--workers 4] [--out DIR]

Flopy: blok held-out końcowy (--holdout) i bloki rund (--block; runda --hifi-round ma
--hifi-flops) z flopsample.herd_blocks — wszystkie rozłączne.  Każda runda liczy wszystkie
liście nie-all-in profilu R̄_r tanim drzewem (fp.LOFI_TREE) na swoim bloku.  Runda --hifi-round
liczy też drzewo produkcyjne (pipeline.auto_tree: low1rf/l1rf wg SPR) na całym bloku dla liści
o SPR > --hifi-min-spr; poprawka drzewa D = EV_prod - EV_tanie (wygładzona) wchodzi do modelu
wszystkich rund (także wcześniejszych).  Liście o SPR <= progu: D mierzona na pierwszych
--spr-check-flops flopach bloku, ale nie stosowana (przy SPR <= ~1,5 oba drzewa mają na turnie
i riverze praktycznie tylko check/all-in; liczby trafiają do raportu jako uzasadnienie).
Po ostatniej rundzie: luka R̄_final na bloku held-out (cały, połówki), zgodność akcji najlepszej
IN/OOS, bias modelu, naruszenia dominacji.

Checkpoint: każdy solve postflop w OUT/cache (klucz sha1 zadania), stan po rundzie w
OUT/state.json i OUT/fpa_round<r>.pkl.  Wznowienie = ta sama komenda (także z większym
--rounds): preflop jest deterministyczny, solve'y są czytane z cache, liczy się tylko brakujące.
"""

from __future__ import annotations

import argparse
import json
import pickle
import threading
import time
from pathlib import Path

import fp
import fpa
import numpy as np
from dom import violations
from flopsample import herd_blocks
from fp import H
from hupf_py.pipeline import auto_tree

# Referencje z węzłów o porównywalnym drzewie (web_refs etapu spike; % kombinacji aktora).
# GW-AI: blog.gtowizard.com/isolating_limpers_in_short_stack_hu (2025-09-26), Gecko 10 bb
# (2026-09-30), biblioteka GW „HU SnG 20bb Classic General” (2025-12-01). GW-AI 16 bb
# porównujemy z naszym 15 bb (inna głębokość).
REFS = {
    10: [
        ("GW-AI 10", "root", dict(fold=11.9, limp=65.5, raise_=0.2, jam=22.4)),
        ("Gecko 10", "root", dict(fold=11.22, limp=62.48, raise_=0.01, jam=26.29)),
        ("GW-AI 10", "limp", dict(check=54.0, iso_small=17.2, iso_big=12.1, jam=16.6)),
    ],
    15: [
        ("GW-AI 16", "root", dict(fold=5.2, limp=67.8, raise_=25.0, jam=2.0)),
        ("GW-AI 16", "limp", dict(check=61.7, iso_small=14.2, iso_big=12.7, jam=11.3)),
    ],
    20: [
        ("GW-AI 20", "root", dict(fold=5.2, limp=61.4, raise_=33.3, jam=0.1)),
        ("GW lib 20", "root", dict(fold=4.7, limp=64.0, raise_=30.7, jam=0.5)),
        ("GW-AI 20", "limp", dict(check=62.7, iso_small=15.2, iso_big=13.5, jam=8.6)),
        ("GW lib 20", "r2", dict(fold=21.0, call=52.2, **{"3b": 13.6}, jam=13.2)),
    ],
}


def categories(nid: str, f: dict) -> dict:
    if nid == "root":
        return dict(
            fold=f["fold"],
            limp=f["limp"],
            raise_=sum(v for a, v in f.items() if a.startswith("r")),
            jam=f["jam"],
        )
    if nid == "limp":
        iso = [a for a in f if a.startswith("iso")]
        return dict(check=f["check"], iso_small=f[iso[0]], iso_big=f[iso[-1]], jam=f["jam"])
    return dict(f)


def ref_compare(depth: float, freq: dict) -> list:
    out = []
    for name, nid, ref in REFS.get(int(round(depth)), []):
        ours = categories(nid, freq[nid])
        diff = {k: round(ours[k] - v, 1) for k, v in ref.items()}
        out.append(
            dict(
                ref=name,
                node=nid,
                ours={k: round(ours[k], 1) for k in ref},
                diff=diff,
                max_abs=max(abs(x) for x in diff.values()),
            )
        )
    return out


def dominance(res) -> dict:
    return {
        nid: len(violations(nr))
        for nid, nr in res.nodes.items()
        if "fold" in nr.actions and fpa.joint_mass(res)[nid] >= 0.01
    }


def key_of(lf):
    return fp.leaf_key(lf)


def cheap_jobs(lf, block):
    sb, bb = fp.leaf_ranges(lf)
    return [
        ((key_of(lf), f, "lo"), fp.job_kw(lf["pot"], lf["depth"], sb, bb, f, fp.LOFI_TREE))
        for f, _ in block
    ]


def hifi_jobs(lf, block):
    sb, bb = fp.leaf_ranges(lf)
    tree = auto_tree(lf["spr"])
    return [
        (
            (key_of(lf), f, "hi"),
            fp.job_kw(lf["pot"], lf["depth"], sb, bb, f, tree, target=fp.HIFI_TARGET),
        )
        for f, _ in block
    ]


def cost(item):
    (key, _, kind), kw = item
    base = {"l1rf": 8.0, "low1rf": 3.0}.get(kw["tree"], 1.0)
    return base * (2.0 if key.startswith("limp-check") else 1.0)


# Szczyt pamięci solve'u (GB) przy 15 bb, zmierzony w spike'u (l1rf limp-check do 4,8 GB na
# flopie tęczowym, low1rf do 2,8, flopsmall do 0,56), skalowany głębokością (przy 20 bb: l1rf
# do 5,8, low1rf do 4,8). Budżet: 15 GB RAM minus proces Pythona i system; przy 15 bb mieszczą
# się dwa l1rf i dwa joby tanie naraz.
MEM_GB = {"l1rf": 5.5, "low1rf": 3.5}
MEM_BUDGET_GB = 13.5


def mem_gb(kw: dict) -> float:
    depth = kw["stack_bb"] + kw["pot_bb"] / 2
    return MEM_GB.get(kw["tree"], 0.6) * max(1.0, depth / 15.0)


def run_all(jobs, workers, tag):
    """Joby od najdroższych (lepsze upakowanie na rdzeniach); wolny wątek bierze pierwszy
    oczekujący job mieszczący się w budżecie pamięci. Wynik: {etykieta: wynik}."""
    pending = sorted(jobs, key=cost, reverse=True)
    out: dict = {}
    used = [0.0]
    cv = threading.Condition()
    t0 = time.time()
    n = len(pending)

    def worker():
        while True:
            with cv:
                while True:
                    if not pending:
                        return
                    i = next(
                        (
                            j
                            for j, (_, kw) in enumerate(pending)
                            if used[0] + mem_gb(kw) <= MEM_BUDGET_GB
                        ),
                        None,
                    )
                    if i is not None:
                        lab, kw = pending.pop(i)
                        used[0] += mem_gb(kw)
                        break
                    cv.wait()
            try:
                res, hit = fp.run_one(kw, 1)
            finally:
                with cv:
                    used[0] -= mem_gb(kw)
                    cv.notify_all()
            with cv:
                out[lab] = res
                k = len(out)
            if not hit:
                fp.log(
                    f"  [{tag} {k}/{n}] {lab[0]} {kw['board']} {kw['tree']} "
                    f"solve={res['solve_s']:.1f}s it={res['iters']} expl={res['expl_pct']:.2f}% "
                    f"mem={res['mem_bytes'] / 2**30:.2f}GB"
                )

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if len(out) != n:
        raise RuntimeError(f"{tag}: policzono {len(out)} z {n} jobów")
    fp.log(f"  {tag}: {n} jobów, {time.time() - t0:.0f} s ściennie")
    return out


def leaf_data(lf, block, out):
    results = [out[(key_of(lf), f, "lo")] for f, _ in block]
    ev, var, loo = fpa.leaf_ev(lf, results, [w for _, w in block])
    return fpa.LeafData(lf, ev, var), loo


def summary_gap(g):
    return f"{g['expl']:.4f} (SB {g['gap_sb']:.4f}, BB {g['gap_bb']:.4f})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depths", type=float, nargs="+", default=[15.0])
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--block", type=int, default=12)
    ap.add_argument("--hifi-round", type=int, default=1)
    ap.add_argument("--hifi-flops", type=int, default=30)
    ap.add_argument("--hifi-min-spr", type=float, default=1.5)
    ap.add_argument("--spr-check-flops", type=int, default=4)
    ap.add_argument("--holdout", type=int, default=32)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument(
        "--smooth",
        action="store_true",
        help="model puli ściągany empirycznym Bayesem do regresji po cechach klas (fpa.shrink)",
    )
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "out" / "fpa"))
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    fp.OUT, fp.CACHE = out_dir, out_dir / "cache"
    sizes = [a.holdout] + [a.hifi_flops if r == a.hifi_round else a.block for r in range(a.rounds)]
    blocks = herd_blocks(sizes)
    holdout, train = blocks[0], blocks[1:]
    fp.log(
        f"START run_fpa {vars(a)} lofi={fp.LOFI_TREE} target={fp.TARGET}% "
        f"hifi_target={fp.HIFI_TARGET}% floor={fp.FLOOR}"
    )
    fp.log(f"held-out: {[f for f, _ in holdout]}")
    t0 = time.time()
    fps = {d: fpa.FictitiousPlay(d, H.gw_tree(d), smooth=a.smooth) for d in a.depths}
    state = dict(args=vars(a), holdout=[f for f, _ in holdout], rounds=[], final=None)
    prev_freq = {d: None for d in a.depths}
    for r in range(a.rounds):
        tr = time.time()
        block = train[r]
        profs = {d: fps[d].profile() for d in a.depths}
        jobs = []
        for d in a.depths:
            for lf in profs[d].leaves:
                jobs += cheap_jobs(lf, block)
                if r == a.hifi_round:
                    nb = len(block) if lf["spr"] > a.hifi_min_spr else a.spr_check_flops
                    jobs += hifi_jobs(lf, block[:nb])
        fp.log(f"R{r}: blok {[f for f, _ in block]}, {len(jobs)} jobów")
        out = run_all(jobs, a.workers, f"R{r}")
        rnd = dict(r=r, flops=[f for f, _ in block], depths={})
        for d in a.depths:
            P = {}
            for lf in profs[d].leaves:
                P[key_of(lf)], _ = leaf_data(lf, block, out)
            corr_info = {}
            if r == a.hifi_round:
                for lf in profs[d].leaves:
                    k = key_of(lf)
                    nb = len(block) if lf["spr"] > a.hifi_min_spr else a.spr_check_flops
                    sub = block[:nb]
                    hi = [out[(k, f, "hi")] for f, _ in sub]
                    lo = [out[(k, f, "lo")] for f, _ in sub]
                    w = [x for _, x in sub]
                    D, Dvar = fpa.tree_correction(hi, lo, w)
                    Ds, Dsvar = fpa.smooth_correction(lf, D, Dvar)
                    sb_w, bb_w = fpa.class_weights(lf)
                    m = (bb_w / bb_w.sum(), sb_w / sb_w.sum())
                    corr_info[k] = dict(
                        tree=auto_tree(lf["spr"]),
                        spr=lf["spr"],
                        flops=nb,
                        applied=bool(lf["spr"] > a.hifi_min_spr),
                        range_delta_bb=[float(np.nansum(m[p] * D[p])) for p in (0, 1)],
                        rms_raw_bb=[float(np.sqrt(np.nansum(m[p] * D[p] ** 2))) for p in (0, 1)],
                        rms_smooth_bb=[
                            float(np.sqrt(np.nansum(m[p] * Ds[p] ** 2))) for p in (0, 1)
                        ],
                        se_mean_bb=[float(np.sqrt(np.nansum(m[p] * Dvar[p]))) for p in (0, 1)],
                    )
                    if corr_info[k]["applied"]:
                        fps[d].correction.d[k] = Ds
                        fps[d].correction.var[k] = Dsvar
                    fp.log(f"  D {d:g}bb {k}: {corr_info[k]}")
                fps[d].correction.info = corr_info
            avg_r = profs[d]
            rec = fps[d].add_round(P)
            rec["mass"] = fpa.joint_mass(avg_r)
            rec["dominance"] = dominance(avg_r)
            rec["refs"] = ref_compare(d, rec["freq"])
            rec["change"] = (
                fpa.max_freq_change(rec["freq"], prev_freq[d], rec["mass"])
                if prev_freq[d]
                else None
            )
            rec["correction"] = corr_info
            rec["range_ev"] = {
                k: dict(
                    pot=x.lf["pot"],
                    freq_sb=x.lf["freq_sb"],
                    freq_bb=x.lf["freq_bb"],
                    sb=float(
                        fpa.class_weights(x.lf)[0]
                        @ fps[d].correction.apply(k, x.ev)[1]
                        / fpa.class_weights(x.lf)[0].sum()
                    ),
                )
                for k, x in P.items()
            }
            prev_freq[d] = rec["freq"]
            rnd["depths"][f"{d:g}"] = rec
            fr = {n: {x: round(y, 1) for x, y in rec["freq"][n].items()} for n in ("root", "limp")}
            fp.log(
                f"R̄{r} {d:g}bb: luka held-out {summary_gap(rec['gap_ho'])}; w modelu puli "
                f"{summary_gap(rec['gap_in'])}; zmiana {rec['change']}; IN/OOS "
                f"{rec.get('agree_in_oos')}; dominacja {rec['dominance']}; {fr}; "
                f"refs max|Δ| {[(x['ref'], x['node'], x['max_abs']) for x in rec['refs']]}"
            )
        rnd["seconds"] = time.time() - tr
        state["rounds"].append(rnd)
        json.dump(state, open(out_dir / "state.json", "w"), default=float, indent=1)
        pickle.dump(fps, open(out_dir / f"fpa_round{r}.pkl", "wb"))
        fp.log(f"R{r} gotowe w {rnd['seconds']:.0f} s, od startu {time.time() - t0:.0f} s")

    profs = {d: fps[d].profile() for d in a.depths}
    jobs = [j for d in a.depths for lf in profs[d].leaves for j in cheap_jobs(lf, holdout)]
    fp.log(f"held-out końcowy: {len(jobs)} jobów")
    out = run_all(jobs, a.workers, "HO")
    final = {}
    half = len(holdout) // 2
    for d in a.depths:
        fpd, avg = fps[d], profs[d]
        P, P1, P2, loo = {}, {}, {}, {}
        for lf in avg.leaves:
            k = key_of(lf)
            P[k], loo[k] = leaf_data(lf, holdout, out)
            P1[k], _ = leaf_data(lf, [(f, 1 / half) for f, _ in holdout[:half]], out)
            P2[k], _ = leaf_data(
                lf, [(f, 1 / (len(holdout) - half)) for f, _ in holdout[half:]], out
            )
        ho = fpd.raw_model(P)
        gaps = {
            name: {k: float(v) for k, v in H.evaluate_profile(avg, m, equity=fp.E7).items()}
            for name, m in (
                ("held-out", ho),
                ("held-out 1/2", fpd.raw_model(P1)),
                ("held-out 2/2", fpd.raw_model(P2)),
                ("pula (trening)", fpd.model),
            )
        }
        nids = [n for n in ("root", "limp", "r2", "r2.5") if n in avg.nodes]
        bias = {}
        for lf in avg.leaves:
            k = key_of(lf)
            ev_ho = fpd.correction.apply(k, P[k].ev)
            loo_ho = np.stack([fpd.correction.apply(k, x) for x in loo[k]])
            bias[k] = fpa.bias(fpa.predicted_ev(fpd.model, k, lf), ev_ho, loo_ho, lf)
        final[f"{d:g}"] = dict(
            gaps=gaps,
            agree_in_oos=fpa.agreement(avg, fpd.model, ho, nids),
            bias=bias,
            dominance=dominance(avg),
            freq=fpa.freqs(avg),
            refs=ref_compare(d, fpa.freqs(avg)),
            mass=fpa.joint_mass(avg),
        )
        fp.log(f"KONIEC {d:g}bb: luki {gaps}")
        fp.log(
            f"  IN/OOS {final[f'{d:g}']['agree_in_oos']}; dominacja {final[f'{d:g}']['dominance']}"
        )
        fp.log(f"  bias {bias}")
    state["final"] = final
    json.dump(state, open(out_dir / "state.json", "w"), default=float, indent=1)
    pickle.dump(dict(fps=fps, profiles=profs), open(out_dir / "fpa_final.pkl", "wb"))
    fp.log(f"czas łączny {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()

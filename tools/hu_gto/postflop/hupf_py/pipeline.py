"""HU postflop pipeline: preflop line + depth + ranges -> per-class EV and EQR for both players.

python -m hupf_py.pipeline --line limp_check --stack 15 [--sb-range f] [--bb-range f]
       [--tree auto|<preset>] [--flops 30] [--sampler herd|sys] [--target 1.0] [--threads 2]
       [--out out/lines/x]
       [--eq-ref matrix|full|none] [--lofi-flops 120 [--lofi-tree flopsmall]]

`--eq-ref` gives the population class equity for the ratio estimator EV = EQR_sample * pot * EQ:
`matrix` (default, ms) = repo 169x169 matrix with disjoint-combo weights (vs the exact
1755-flop value: mean |d| 0.09-0.11 pp, max 0.34 pp on limp_check 15 bb), `full` = check-down
jobs on all 1755 flops (~8 min single thread per range pair, cached), `none` = plain estimator.
`--lofi-flops K2` adds `ev_pot_bb_cv` = EV_tree(K) - EV_lofi(K) + EV_lofi(K2) (cheap tree on K2
herding flops; measured on raise2x_call 15 bb: SE of the correction term 0.015-0.019 bb vs plain
0.25-0.28 bb, iid approximation), the recommended per-class estimate for the preflop side.

Ranges: JSON list or .npy of 169 class weights (poker.preflop.ALL_CLASSES order) or 1326
combo weights (b-inary order, see cards.py); default = placeholder for the line.
HU postflop: BB = OOP (player 0), SB/button = IP (player 1).
Output: <out>.json (per class EV/EQR/equity/mass for SB and BB) and <out>.npz (same arrays
plus per-flop raw combo arrays).  EV convention: `ev_pot_bb` = expected share of the
postflop starting pot minus postflop investment (bb); `ev_net_bb` = ev_pot_bb - preflop
contribution, i.e. the hand's chip result for that player from the start of the hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from . import aggregate, cards, flops, ranges, solver

CACHE = solver.ROOT / "out" / "cache"

# Tree choice by SPR, measured against richer trees (2 sizes + 3x raises) on 2 flops each:
# one size + all-in per street is not enough at either SPR - without a non-all-in (3x) flop
# raise the solver over-bets (check-raise missing); with it EV/class deviates ~0.01-0.05 bb.
LOW_SPR_TREE = "low1rf"
LIMPED_TREE = "l1rf"


def auto_tree(spr: float) -> str:
    return LOW_SPR_TREE if spr <= 4.5 else LIMPED_TREE


def load_range(path: str | None) -> np.ndarray | None:
    if path is None:
        return None
    v = (
        np.load(path)
        if path.endswith(".npy")
        else np.array(json.loads(Path(path).read_text()), dtype=float)
    )
    if v.shape == (169,):
        return cards.class_to_combo(v)
    if v.shape == (1326,):
        return v
    raise ValueError(f"range must have 169 or 1326 weights, got {v.shape}")


def solve_cached(threads: int, **kw) -> dict:
    text = solver.job_text(**kw)
    h = hashlib.sha1(text.encode()).hexdigest()[:20]
    p = CACHE / f"{h}.json"
    if p.exists():
        return json.loads(p.read_text())
    res = solver.solve(threads=threads, **kw)
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res))
    return res


def exact_equity(
    range_oop: np.ndarray, range_ip: np.ndarray, pot_bb: float, stack_bb: float, threads: int = 2
) -> np.ndarray:
    """Class equity vs range over all 1755 flops (check-down tree, no solving)."""
    allf = flops.all_flops()
    res = []
    for f, _ in allf:
        res.append(
            solve_cached(
                threads,
                board=f,
                pot_bb=pot_bb,
                stack_bb=stack_bb,
                range_oop=range_oop,
                range_ip=range_ip,
                tree="checkdown",
                target_pct=100.0,
                max_iter=0,
                node_depth=0,
                node_combos=False,
            )
        )
    agg = aggregate.aggregate(res, [w for _, w in allf], pot_bb)
    return agg["eq"]


def run(
    line: str,
    stack: float,
    sb: np.ndarray | None = None,
    bb: np.ndarray | None = None,
    tree: str = "auto",
    n_flops: int = 30,
    u: float = 0.5,
    target: float = 1.0,
    threads: int = 2,
    sampler: str = "herd",
    pot_bb: float | None = None,
    contrib_bb: float | None = None,
    eq_ref: str = "matrix",
    max_iter: int = 600,
    lofi_flops: int = 0,
    lofi_tree: str = "flopsmall",
    log=print,
) -> dict:
    desc, sb_f, bb_f, pot0, contrib0 = ranges.PLACEHOLDERS[line]
    pot_bb = pot0 if pot_bb is None else pot_bb
    contrib = contrib0 if contrib_bb is None else contrib_bb
    sb = cards.class_to_combo(sb_f()) if sb is None else sb
    bb = cards.class_to_combo(bb_f()) if bb is None else bb
    eff = stack - contrib
    spr = eff / pot_bb
    tree = auto_tree(spr) if tree == "auto" else tree
    sample = (
        flops.herding_sample(n_flops) if sampler == "herd" else flops.systematic_sample(n_flops, u)
    )
    results, weights, times = [], [], []
    for i, (f, w) in enumerate(sample):
        t = time.time()
        r = solve_cached(
            threads,
            board=f,
            pot_bb=pot_bb,
            stack_bb=eff,
            range_oop=bb,
            range_ip=sb,
            tree=tree,
            target_pct=target,
            max_iter=max_iter,
            node_depth=1,
            node_combos=True,
        )
        results.append(r)
        weights.append(w)
        times.append(r["solve_s"] + r["build_s"])
        log(
            f"[{i + 1}/{len(sample)}] {f} w={w:.4f} solve={r['solve_s']:.1f}s it={r['iters']} "
            f"expl={r['expl_pct']:.2f}% wall={time.time() - t:.1f}s"
        )
    if eq_ref == "full":
        eqx = exact_equity(bb, sb, pot_bb, eff, threads)
    elif eq_ref == "matrix":
        w_bb, w_sb = cards.combo_to_class_mean(bb), cards.combo_to_class_mean(sb)
        eqx = np.stack([ranges.equity_vs_range(w_bb, w_sb), ranges.equity_vs_range(w_sb, w_bb)])
    else:
        eqx = None
    agg = aggregate.aggregate(results, weights, pot_bb, eq_exact=eqx)
    if lofi_flops:
        # multi-fidelity control variate: EV_cv = EV_tree(K) - EV_lofi(K) + EV_lofi(K_lofi).
        # The per-flop difference between trees varies little across flops, so the K-flop
        # correction term is precise and the sampling error is carried by the cheap K_lofi sample
        # (herding is sequential, so the first K lofi flops are exactly the production flops).
        def lofi(sample_):
            rs = []
            for f, _ in sample_:
                rs.append(
                    solve_cached(
                        threads,
                        board=f,
                        pot_bb=pot_bb,
                        stack_bb=eff,
                        range_oop=bb,
                        range_ip=sb,
                        tree=lofi_tree,
                        target_pct=target,
                        max_iter=max_iter,
                        node_depth=1,
                        node_combos=True,
                    )
                )
            return aggregate.aggregate(rs, [w for _, w in sample_], pot_bb)

        big_sample = (
            flops.herding_sample(lofi_flops)
            if sampler == "herd"
            else flops.systematic_sample(lofi_flops, u)
        )
        lo_k, lo_big = lofi(sample), lofi(big_sample)
        agg["ev_bb_cv"] = agg["ev_bb"] - lo_k["ev_bb"] + lo_big["ev_bb"]
        eq_for_cv = eqx if eqx is not None else lo_big["eq"]
        agg["eqr_cv"] = agg["ev_bb_cv"] / (pot_bb * eq_for_cv)
    # player 0 = BB (OOP), 1 = SB (IP)
    meta = {
        "line": line,
        "desc": desc,
        "stack_bb": stack,
        "pot_bb": pot_bb,
        "eff_bb": eff,
        "spr": spr,
        "contrib_bb": contrib,
        "eq_ref": eq_ref,
        "tree": tree,
        "tree_spec": solver.TREES[tree],
        "target_pct": target,
        "n_flops_draws": n_flops,
        "sampler": sampler,
        "lofi_flops": lofi_flops,
        "lofi_tree": lofi_tree,
        "flops": [[f, w] for f, w in sample],
        "solve_s_total": float(np.sum(times)),
        "threads": threads,
        "players": {"0": "BB (OOP)", "1": "SB (IP)"},
    }
    return {"meta": meta, "agg": agg, "results": results, "weights": weights}


def write_outputs(out: Path, run_res: dict) -> None:
    meta, agg = run_res["meta"], run_res["agg"]
    out.parent.mkdir(parents=True, exist_ok=True)
    contrib = meta["contrib_bb"]
    classes = []
    for i, name in enumerate(cards.CLASS_NAMES):
        row = {"class": name}
        for p, who in ((1, "sb"), (0, "bb")):
            if agg["mass"][p, i] > 0:
                row[who] = {
                    "ev_pot_bb": round(float(agg["ev_bb"][p, i]), 5),
                    "ev_net_bb": round(float(agg["ev_bb"][p, i] - contrib), 5),
                    "eq": round(float(agg["eq"][p, i]), 5),
                    "eqr": round(float(agg["eqr"][p, i]), 5),
                    "mass": float(agg["mass"][p, i]),
                }
                if "ev_bb_cv" in agg:
                    row[who]["ev_pot_bb_cv"] = round(float(agg["ev_bb_cv"][p, i]), 5)
                    row[who]["eqr_cv"] = round(float(agg["eqr_cv"][p, i]), 5)
                if "ev_bb_ratio" in agg:
                    row[who]["ev_pot_bb_ratio"] = round(float(agg["ev_bb_ratio"][p, i]), 5)
                    row[who]["eq_exact"] = round(float(agg["eq_exact"][p, i]), 5)
        classes.append(row)
    summary = {
        "sb_range_ev_pot_bb": float(agg["range_ev_bb"][1]),
        "bb_range_ev_pot_bb": float(agg["range_ev_bb"][0]),
        "sb_range_eq": float(agg["range_eq"][1]),
        "bb_range_eq": float(agg["range_eq"][0]),
    }
    out.with_suffix(".json").write_text(
        json.dumps({"meta": meta, "summary": summary, "classes": classes}, indent=1)
    )
    res = run_res["results"]
    raw = {k: np.stack([aggregate.per_flop_arrays(r)[k] for r in res]) for k in ("nw", "ev", "eq")}
    np.savez_compressed(
        out.with_suffix(".npz"),
        class_names=np.array(cards.CLASS_NAMES),
        mass=agg["mass"],
        ev_pot_bb=agg["ev_bb"],
        eq=agg["eq"],
        eqr=agg["eqr"],
        ev_net_bb=agg["ev_bb"] - contrib,
        flops=np.array([f for f, _ in meta["flops"]]),
        flop_weights=np.array(run_res["weights"]),
        combo_nw=raw["nw"],
        combo_ev_chips=raw["ev"],
        combo_eq=raw["eq"],
        **(
            {"ev_pot_bb_ratio": agg["ev_bb_ratio"], "eq_exact": agg["eq_exact"]}
            if "ev_bb_ratio" in agg
            else {}
        ),
        **({"ev_pot_bb_cv": agg["ev_bb_cv"], "eqr_cv": agg["eqr_cv"]} if "ev_bb_cv" in agg else {}),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--line", default="limp_check", choices=sorted(ranges.PLACEHOLDERS))
    ap.add_argument(
        "--stack", type=float, default=15.0, help="effective stack at start of hand (bb)"
    )
    ap.add_argument("--sb-range")
    ap.add_argument("--bb-range")
    ap.add_argument("--pot-bb", type=float)
    ap.add_argument("--contrib-bb", type=float)
    ap.add_argument("--tree", default="auto")
    ap.add_argument("--flops", type=int, default=30)
    ap.add_argument(
        "--sampler",
        default="herd",
        choices=["herd", "sys"],
        help="herd = deterministic feature-balanced sample (default); "
        "sys = texture-sorted systematic PPS",
    )
    ap.add_argument(
        "--u", type=float, default=0.5, help="start of the systematic sample (sampler=sys)"
    )
    ap.add_argument("--target", type=float, default=1.0, help="exploitability target, %% of pot")
    ap.add_argument("--max-iter", type=int, default=600)
    ap.add_argument(
        "--lofi-flops",
        type=int,
        default=0,
        help="K_lofi > K: add the multi-fidelity estimator (cheap tree on K_lofi flops)",
    )
    ap.add_argument("--lofi-tree", default="flopsmall")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--eq-ref", default="matrix", choices=["matrix", "full", "none"])
    ap.add_argument(
        "--exact-eq", dest="eq_ref", action="store_const", const="full", help="= --eq-ref full"
    )
    ap.add_argument("--out")
    a = ap.parse_args()
    r = run(
        a.line,
        a.stack,
        load_range(a.sb_range),
        load_range(a.bb_range),
        a.tree,
        a.flops,
        a.u,
        a.target,
        a.threads,
        a.sampler,
        a.pot_bb,
        a.contrib_bb,
        a.eq_ref,
        a.max_iter,
        a.lofi_flops,
        a.lofi_tree,
    )
    out = (
        Path(a.out)
        if a.out
        else solver.ROOT
        / "out"
        / "lines"
        / f"{a.line}_{a.stack:g}bb_{r['meta']['tree']}_k{a.flops}_{a.sampler}"
    )
    write_outputs(out, r)
    print(
        json.dumps(
            {
                "out": str(out),
                "solve_s_total": r["meta"]["solve_s_total"],
                "tree": r["meta"]["tree"],
                "spr": r["meta"]["spr"],
                "sb_range_ev": float(r["agg"]["range_ev_bb"][1]),
                "bb_range_ev": float(r["agg"]["range_ev_bb"][0]),
            }
        )
    )


if __name__ == "__main__":
    main()

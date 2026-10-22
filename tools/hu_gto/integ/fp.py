"""Integracja preflop (hu_preflop) <-> postflop (hupf / b-inary) dla HU Spina, chipEV.

Model liścia w rundzie r+1 = model addytywny R = E + a_sb[h] - a_bb[v] (H.fit_additive)
dopasowany do udziałów per klasa z solvera postflop na zakresach z rundy r.
Udział per klasa = (EV_lofi_ratio(K2) + D) / pula, gdzie
  EV_lofi_ratio(K2) = estymator ratio z taniego drzewa 'flopsmall' na K2 flopach (herding),
  D = poprawka drzewa EV_hifi(K_hi) - EV_lofi(K_hi) (drzewo produkcyjne auto: low1rf/l1rf),
      liczona raz, na zakresach jednej rundy, wygładzona kwadratowo po equity klasy.
Liście z zasięgiem < MIN_REACH (odsetek kombinacji gracza) nie są liczone: dostają a_* pożyczone
z policzonego liścia tej samej linii o najbliższym SPR, a gdy takiego nie ma - ConstEQRLeaf.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HU = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(HU / "preflop"), str(HU / "postflop"), str(Path(__file__).resolve().parent)]

import hu_preflop as H  # noqa: E402
from hupf_py import aggregate, cards, solver  # noqa: E402

assert H.CLASSES == cards.CLASS_NAMES
E7 = H.load_equity("eval7")
OUT = Path(os.environ.get("FP_OUT", Path(__file__).resolve().parent / "out"))
CACHE = OUT / "cache"
# Waga zasięgu klas spoza zakresu: solver liczy dla nich (prawie) BR, a preflop potrzebuje ich
# wartości do regretów.
FLOOR = 0.005
MIN_REACH = 0.02
LOFI_TREE = "flopsmall"
TARGET = float(os.environ.get("FP_TARGET", 1.0))  # % puli
MAX_ITER = 600
# % puli; drzewo produkcyjne liczy tylko poprawkę drzewa, więc wystarcza luźniejszy cel.
HIFI_TARGET = float(os.environ.get("FP_HIFI_TARGET", 2.0))
_lock = threading.Lock()


def log(*a):
    msg = " ".join(str(x) for x in a)
    with _lock:
        print(time.strftime("%H:%M:%S"), msg, flush=True)
        with open(OUT / "run.log", "a") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def leaf_ranges(lf, floor=FLOOR):
    return (
        np.maximum(np.asarray(lf["range_sb"], float), floor),
        np.maximum(np.asarray(lf["range_bb"], float), floor),
    )


def job_kw(
    pot,
    depth,
    sb169,
    bb169,
    board,
    tree,
    target=TARGET,
    max_iter=MAX_ITER,
    node_depth=0,
    combos=False,
):
    return dict(
        board=board,
        pot_bb=pot,
        stack_bb=depth - pot / 2,
        range_oop=cards.class_to_combo(bb169),
        range_ip=cards.class_to_combo(sb169),
        tree=tree,
        target_pct=target,
        max_iter=max_iter,
        node_depth=node_depth,
        node_combos=combos,
        max_mem_gb=9.0,
    )


def cache_path(kw):
    return CACHE / (hashlib.sha1(solver.job_text(**kw).encode()).hexdigest()[:20] + ".json")


def run_one(kw, threads):
    p = cache_path(kw)
    if p.exists():
        return json.loads(p.read_text()), True
    t = time.time()
    res = solver.solve(threads=threads, **kw)
    res["wall_s"] = time.time() - t
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res))
    return res, False


def run_jobs(jobs, workers, threads, tag=""):
    """jobs: lista (etykieta, kw). Zwraca listę wyników w tej samej kolejności."""
    t0 = time.time()
    done = [0]

    def one(item):
        lab, kw = item
        res, hit = run_one(kw, threads)
        with _lock:
            done[0] += 1
        if not hit:
            log(
                f"  [{tag} {done[0]}/{len(jobs)}] {lab} {kw['board']} {kw['tree']} "
                f"solve={res['solve_s']:.1f}s it={res['iters']} expl={res['expl_pct']:.2f}% "
                f"mem={res['mem_bytes'] / 2**30:.2f}GB"
            )
        return res

    with ThreadPoolExecutor(workers) as ex:
        out = list(ex.map(one, jobs))
    log(f"  {tag}: {len(jobs)} jobów, {time.time() - t0:.0f} s ściennie")
    return out


def eq_vs_range(sb, bb, E=E7):
    """Equity all-in per klasa wobec zakresu rywala (card removal przez W): [2, 169],
    0 = BB, 1 = SB."""
    eq_sb = (H.W * E) @ bb / (H.W @ bb)
    eq_bb = (H.W * (1 - E)).T @ sb / (H.W.T @ sb)
    return np.stack([eq_bb, eq_sb])


def leaf_estimate(lf, sample, tree, results):
    sb, bb = leaf_ranges(lf)
    eqx = eq_vs_range(sb, bb)
    return aggregate.aggregate(results, [w for _, w in sample], lf["pot"], eq_exact=eqx)


class IntegLeaf:
    """R = E + a_sb[h] - a_bb[v] per liść (klucz node@depth); brak klucza -> fallback."""

    def __init__(self, a: dict, fallback=None, name="integ"):
        self.a = a
        self.fallback = fallback or H.ConstEQRLeaf()
        self.name = name

    def share(self, line, E):
        k = f"{line.node}@{line.depth:g}"
        if k in self.a:
            a_sb, a_bb = self.a[k]
            return E + a_sb[:, None] - a_bb[None, :]
        return self.fallback.share(line, E)


def smooth_delta(delta, eq, mass):
    """Wygładzenie poprawki drzewa: WLS delta ~ 1 + eq + eq^2 per gracz (waga = masa klasy)."""
    out = np.zeros_like(delta)
    for p in range(2):
        m = np.isfinite(delta[p]) & (mass[p] > 0)
        X = np.stack([np.ones(m.sum()), eq[p][m], eq[p][m] ** 2], 1)
        w = np.sqrt(mass[p][m])
        beta = np.linalg.lstsq(X * w[:, None], delta[p][m] * w, rcond=None)[0]
        Xa = np.stack([np.ones(169), eq[p], eq[p] ** 2], 1)
        out[p] = Xa @ beta
    return out


def build_model(solved: dict, all_leaves: list, deltas: dict, use_delta=True):
    """solved: key -> dict(lf, ev [2,169] (bb, ratio)), deltas: key -> [2,169] (bb)."""
    a = {}
    info = {}
    for k, s in solved.items():
        lf = s["lf"]
        ev = s["ev"].copy()
        if use_delta and k in deltas:
            ev = ev + deltas[k]
        sb, bb = leaf_ranges(lf)
        share_sb, share_bb = ev[1] / lf["pot"], ev[0] / lf["pot"]
        a[k] = H.fit_additive(E7, share_sb, share_bb, sb, bb)
        info[k] = "solved" + ("+delta" if use_delta and k in deltas else "")
    for lf in all_leaves:
        k = f"{lf['node']}@{lf['depth']:g}"
        if k in a:
            continue
        donors = [s["lf"] for s in solved.values() if s["lf"]["line"] == lf["line"]]
        if donors:
            d = min(donors, key=lambda x: abs(x["spr"] - lf["spr"]))
            a[k] = a[f"{d['node']}@{d['depth']:g}"]
            info[k] = f"borrowed:{d['node']}@{d['depth']:g}"
        else:
            info[k] = "fallback:ConstEQR"
    return IntegLeaf(a), info


def preflop(depth, leaf_model, target=2e-5):
    return H.solve(
        float(depth), leaf_model, equity=E7, iters=30000, target_expl=target, check_every=100
    )


def class_ev(res, leaf_model):
    """EV per klasa (bb) w profilu res przy modelu liścia: (ev_sb[169], ev_bb[169])."""
    root = H.build_tree(res.depth, H.TreeConfig(**res.tree), E7, leaf_model)
    sv = H._Solver(root)
    for n in sv.dec:
        n.S = res.nodes[n.id].strategy.copy()
    one = np.ones(H.N)
    v_sb = sv._value(sv.root, 0, one, False) / H.W.sum(1)
    v_bb = sv._value(sv.root, 1, one, False) / H.W.sum(0)
    return v_sb, v_bb


def node_mass(nr):
    return float((nr.reach * H.NCOMBO).sum() / H.NCOMBO.sum())


def compare(prev, cur, model_prev, model_cur, min_mass=0.02):
    """Zmiana między rundami: częstości węzłów (pp, węzły z masą aktora >= min_mass)
    i EV klas (bb)."""
    df = []
    for nid, nr in cur.nodes.items():
        p = prev.nodes.get(nid)
        if p is None or p.actions != nr.actions or max(node_mass(nr), node_mass(p)) < min_mass:
            continue
        for a in nr.actions:
            df.append((abs(nr.freq[a] - p.freq[a]) * 100, f"{nid}:{a}"))
    s0, b0 = class_ev(prev, model_prev)
    s1, b1 = class_ev(cur, model_cur)
    w = H.NCOMBO / H.NCOMBO.sum()
    d_sb, d_bb = np.abs(s1 - s0), np.abs(b1 - b0)
    mx = max(df) if df else (0.0, "-")
    return dict(
        max_freq_pp=mx[0],
        max_freq_at=mx[1],
        ev_sb_max=float(d_sb.max()),
        ev_sb_at=H.CLASSES[int(d_sb.argmax())],
        ev_sb_mean=float(w @ d_sb),
        ev_bb_max=float(d_bb.max()),
        ev_bb_at=H.CLASSES[int(d_bb.argmax())],
        ev_bb_mean=float(w @ d_bb),
        d_ev_game=float(cur.ev_sb - prev.ev_sb),
    )


def solvable(lf):
    return min(lf["freq_sb"], lf["freq_bb"]) >= MIN_REACH


def leaf_key(lf):
    return f"{lf['node']}@{lf['depth']:g}"


def res_to_json(r):
    return dict(
        depth=r.depth,
        ev_sb=r.ev_sb,
        gap_sb=r.gap_sb,
        gap_bb=r.gap_bb,
        expl=r.expl,
        iters=r.iters,
        seconds=r.seconds,
        tree=r.tree,
        nodes={
            k: dict(
                actor=v.actor,
                actions=v.actions,
                freq=v.freq,
                mass=node_mass(v),
                strategy=np.round(v.strategy, 5).tolist(),
                reach=np.round(v.reach, 5).tolist(),
            )
            for k, v in r.nodes.items()
        },
        leaves=r.leaves,
    )

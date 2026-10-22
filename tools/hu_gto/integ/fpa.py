"""Fictitious play preflop <-> postflop: następca pętli run_fp.py, która kręci się w 2-cyklu.

Runda r (R̄_r = profil uśredniony, start R̄_0 = R_0 = równowaga modelu startowego):
  P_r     = EV klas z solve'ów postflop liści R̄_r na ŚWIEŻYM bloku flopów F_r (rozłącznym z
            blokami wcześniejszymi), z poprawką drzewa D,
  g_r     = luka BR R̄_r w modelu dopasowanym tylko do P_r. To luka held-out: żaden model, z którego
            powstał R̄_r, nie widział flopów F_r. Wartości klas są wartościami wobec ustalonej
            strategii postflop rywala na zakresach R̄_r, więc to luka w sensie BR (rywal stały
            preflop i postflop), bez eksploatacji samego postflopu (solve'y mają lukę <= cel %
            puli),
  M̄_r     = średnia modeli addytywnych a^k (k <= r) z wagami w_k = k + 1 [FP na modelach liścia],
            opcjonalnie (smooth=True) ściągnięta empirycznym Bayesem do regresji po cechach klas,
  R_{r+1} = równowaga preflop w M̄_r,  R̄_{r+1} = średnia R_0..R_{r+1} z wagami k + 1 w sensie
            realizacji [FP na profilach].
Dlaczego obie średnie: równowaga modelu addytywnego jest „bang-bang”, więc R_{r+1} przeskakuje
między fazami (to jest 2-cykl run_fp.py); średnia profili wygasza przeskoki, a średnia modeli
z blokami świeżych flopów zmniejsza szum próbki jak w aproksymacji stochastycznej (model po r
rundach widzi wszystkie bloki). Wagi liniowe zamiast 1/(r+1): stan przejściowy z modelu
startowego wygasa jak 1/r^2, nie 1/r (jak uśrednianie w CFR+/DCFR).
Domyślnie smooth=False: na danych krytyka (R4 15 bb, 12 flopów pętli + 12 spoza) ściąganie EB
z wariancją jackknife pogorszyło lukę równowagi modelu IN w modelu OOS z 0,049 do 0,060 bb/rękę
(szum próbki flopów jest głównie wspólny dla wielu klas, więc regresja po cechach go nie usuwa,
a dokłada obciążenie); ten szum zmniejsza dopiero pula bloków.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import fp
import numpy as np
from fp import H
from hupf_py import aggregate
from hupf_py.cards import BB_CHIPS


def _class_features() -> np.ndarray:
    eq_rand = (H.W * fp.E7).sum(1) / H.W.sum(1)
    rows = []
    for i, c in enumerate(H.CLASSES):
        r1, r2 = 12 - H.RANKS.index(c[0]), 12 - H.RANKS.index(c[1])
        pair = float(len(c) == 2)
        s = float(c.endswith("s"))
        gap = 0.0 if pair else float(r1 - r2)
        e = eq_rand[i]
        rows.append(
            [
                1.0,
                e,
                e * e,
                e**3,
                pair,
                pair * r1,
                pair * r1 * r1 / 12,
                s,
                s * gap,
                float(gap == 1),
                float(gap >= 4),
                r1,
                r2,
                r1 * r2 / 12,
                float(r2 >= 8),
                s * float(r1 == 12),
                (1 - pair) * float(r2 <= 3),
            ]
        )
    X = np.array(rows)
    sd = X[:, 1:].std(0)
    X[:, 1:] = (X[:, 1:] - X[:, 1:].mean(0)) / np.where(sd > 0, sd, 1.0)
    return X


FEATURES = _class_features()


def shrink(
    a: np.ndarray, var: np.ndarray, w: np.ndarray, X: np.ndarray = FEATURES, iters: int = 6
) -> tuple[np.ndarray, dict]:
    """Empiryczny Bayes (Efron–Morris): a_h -> s_h + lam_h (a_h - s_h), s = X beta (WLS po cechach
    klasy), lam_h = tau2 / (tau2 + var_h), tau2 = wariancja prawdziwej reszty a - s (metoda
    momentów, wagi w). Klasy z var = inf albo NaN dostają s_h. Dlaczego nie samo s (smooth.py):
    cechy nie opisują wszystkiego (np. blokery), a klasa z małym szumem ma zostać przy swoim a."""
    ok = np.isfinite(a) & np.isfinite(var) & (w > 0)
    a0 = np.where(ok, a, 0.0)
    v = np.where(ok, np.maximum(var, 0.0), np.inf)
    wn = np.where(ok, w, 0.0) / max(float(np.where(ok, w, 0.0).sum()), 1e-300)
    tau2 = float(wn @ (a0 - wn @ a0) ** 2)
    s = np.zeros_like(a0)
    for _ in range(iters):
        prec = np.where(ok, wn / (tau2 + v + 1e-12), 0.0)
        A = X.T @ (X * prec[:, None]) + 1e-9 * np.eye(X.shape[1])
        beta = np.linalg.solve(A, X.T @ (prec * a0))
        s = X @ beta
        tau2 = max(0.0, float(wn @ np.where(ok, (a0 - s) ** 2 - np.where(ok, v, 0.0), 0.0)))
    lam = np.where(ok, tau2 / (tau2 + v + 1e-300), 0.0)
    out = s + lam * (a0 - s)
    return out, dict(tau2=tau2, lam_mean=float(wn @ lam))


def flop_class_sums(results: list[dict]) -> np.ndarray:
    """(K, 3, 2, 169) sumy klasowe per flop (aggregate.class_sums)."""
    return np.stack([aggregate.class_sums(r) for r in results])


def _ratio(S: np.ndarray, eqx: np.ndarray) -> np.ndarray:
    _, evs, eqs = S
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(eqs > 0, evs / eqs, np.nan) / BB_CHIPS * eqx


def _plain(S: np.ndarray) -> np.ndarray:
    mass, evs, _ = S
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(mass > 0, evs / mass, np.nan) / BB_CHIPS


def _jk_var(loo: np.ndarray) -> np.ndarray:
    k = len(loo)
    with np.errstate(invalid="ignore"):
        return (k - 1) / k * ((loo - loo.mean(0)) ** 2).sum(0)


def jackknife(cs: np.ndarray, weights, est) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Estymator `est(sumy)` na flopach z wagami, jego wariancja jackknife (pomijanie flopu;
    przybliżenie iid, dla herdingu raczej zawyżone) i wartości z pominięciem flopu (K, ...)."""
    w = np.asarray(weights, float)[:, None, None, None]
    S = (w * cs).sum(0)
    full = est(S)
    if len(cs) < 2:
        return full, np.full_like(full, np.inf), full[None]
    loo = np.stack([est(S - w[i] * cs[i]) for i in range(len(cs))])
    return full, _jk_var(loo), loo


def leaf_ev(lf: dict, results: list[dict], weights):
    """EV klas (bb, [2,169], 0 = BB) estymatorem ratio (EQR z próbki x equity z populacji),
    wariancja jackknife i wartości z pominięciem flopu."""
    sb, bb = fp.leaf_ranges(lf)
    eqx = fp.eq_vs_range(sb, bb)
    return jackknife(flop_class_sums(results), weights, lambda S: _ratio(S, eqx))


def tree_correction(hi: list[dict], lo: list[dict], weights) -> tuple[np.ndarray, np.ndarray]:
    """Poprawka drzewa D = EV_produkcyjne - EV_tanie na tych samych flopach (para, więc
    estymator zwykły) i jej wariancja jackknife."""
    chi, clo = flop_class_sums(hi), flop_class_sums(lo)
    w = np.asarray(weights, float)[:, None, None, None]

    def est(idx):
        return _plain((w[idx] * chi[idx]).sum(0)) - _plain((w[idx] * clo[idx]).sum(0))

    k = len(chi)
    full = est(np.arange(k))
    if k < 2:
        return full, np.full_like(full, np.inf)
    return full, _jk_var(np.stack([est(np.delete(np.arange(k), i)) for i in range(k)]))


def fit_leaf(lf: dict, ev: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    sb, bb = fp.leaf_ranges(lf)
    return H.fit_additive(fp.E7, ev[1] / lf["pot"], ev[0] / lf["pot"], sb, bb)


def class_weights(lf: dict) -> tuple[np.ndarray, np.ndarray]:
    sb, bb = fp.leaf_ranges(lf)
    return sb * H.NCOMBO, bb * H.NCOMBO


@dataclass
class LeafData:
    """Dane jednej rundy dla jednego liścia: EV klas (bb, [2,169]) i ich wariancja."""

    lf: dict
    ev: np.ndarray
    var: np.ndarray


@dataclass
class Correction:
    """Poprawka drzewa per liść (bb, [2,169]) po wygładzeniu i jej wariancja."""

    d: dict = field(default_factory=dict)
    var: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)

    def apply(self, key: str, ev: np.ndarray) -> np.ndarray:
        return ev + self.d[key] if key in self.d else ev

    def variance(self, key: str) -> np.ndarray | float:
        return self.var.get(key, 0.0)


def smooth_correction(lf: dict, d: np.ndarray, var: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Wygładzenie poprawki drzewa tym samym empirycznym Bayesem co model (po cechach klas);
    wariancja wyniku ~ lam^2 var (część gładka ma wariancję dużo mniejszą, pomijaną)."""
    w = class_weights(lf)
    out, out_var = np.zeros_like(d), np.zeros_like(var)
    for p, wp in ((0, w[1]), (1, w[0])):
        sm, info = shrink(d[p], var[p], wp)
        lam = info["tau2"] / (info["tau2"] + np.where(np.isfinite(var[p]), var[p], np.inf))
        fin = np.isfinite(var[p])
        out[p], out_var[p] = sm, np.where(fin, lam**2 * np.where(fin, var[p], 0.0), 0.0)
    return out, out_var


def round_weights(n: int, averaging: str) -> np.ndarray:
    if averaging == "last":
        w = np.zeros(n)
        w[-1] = 1.0
        return w
    if averaging == "uniform":
        return np.ones(n)
    if averaging == "linear":
        return np.arange(1, n + 1, dtype=float)
    raise ValueError(averaging)


class FictitiousPlay:
    """Stan FP dla jednej głębokości. `profile()` -> R̄_r do policzenia postflopu, `add_round(P)`
    przyjmuje {klucz liścia: LeafData} na liściach R̄_r i robi krok. averaging='last' to stara
    iteracja punktu stałego (bez uśredniania; do porównań)."""

    def __init__(
        self,
        depth: float,
        tree: H.TreeConfig,
        start=None,
        averaging: str = "linear",
        smooth: bool = False,
        target: float = 2e-5,
    ):
        self.depth, self.tree = float(depth), tree
        self.averaging, self.smooth, self.target = averaging, smooth, target
        self.start = start or H.ConstEQRLeaf()
        self.correction = Correction()
        self.rounds: list[dict] = []  # {klucz: LeafData}
        self.iterates = [self._solve(self.start)]
        self.model = None

    def _solve(self, model):
        return H.solve(
            self.depth,
            model,
            tree=self.tree,
            equity=fp.E7,
            iters=30000,
            target_expl=self.target,
            check_every=100,
        )

    def profile(self):
        if self.averaging == "last":
            return self.iterates[-1]
        w = round_weights(len(self.iterates), self.averaging)
        return H.average_profiles(self.iterates, list(w))

    def raw_model(self, P: dict) -> fp.IntegLeaf:
        a = {}
        for k, x in P.items():
            a[k] = fit_leaf(x.lf, self.correction.apply(k, x.ev))
        return fp.IntegLeaf(a, fallback=self.start)

    def pooled_model(self) -> tuple[fp.IntegLeaf, dict]:
        """M̄: średnia ważona a^k po rundach (z bieżącą poprawką drzewa), opcjonalnie wygładzona."""
        w = round_weights(len(self.rounds), self.averaging)
        keys = set().union(*self.rounds)
        a, info = {}, {}
        for k in sorted(keys):
            acc_sb = acc_bb = 0.0
            v_sb = v_bb = 0.0
            tot = 0.0
            last = None
            for wr, P in zip(w, self.rounds, strict=True):
                if k not in P or wr == 0:
                    continue
                s, b = fit_leaf(P[k].lf, self.correction.apply(k, P[k].ev))
                pot2 = P[k].lf["pot"] ** 2
                acc_sb, acc_bb = acc_sb + wr * s, acc_bb + wr * b
                v_sb, v_bb = v_sb + wr**2 * P[k].var[1] / pot2, v_bb + wr**2 * P[k].var[0] / pot2
                tot += wr
                last = P[k].lf
            assert last is not None
            # poprawka drzewa jest wspólna dla rund, więc jej wariancja nie maleje z uśrednianiem
            vd = np.asarray(self.correction.variance(k)) / last["pot"] ** 2
            a_sb, a_bb = acc_sb / tot, acc_bb / tot
            v_sb = v_sb / tot**2 + (vd[1] if vd.ndim else vd)
            v_bb = v_bb / tot**2 + (vd[0] if vd.ndim else vd)
            if self.smooth:
                w_sb, w_bb = class_weights(last)
                a_sb, i_sb = shrink(a_sb, v_sb, w_sb)
                a_bb, i_bb = shrink(a_bb, v_bb, w_bb)
                info[k] = dict(sb=i_sb, bb=i_bb)
            a[k] = (a_sb, a_bb)
        return fp.IntegLeaf(a, fallback=self.start), info

    def add_round(self, P: dict) -> dict:
        avg = self.profile()
        raw = self.raw_model(P)
        prev_model = self.model
        gap_ho = H.evaluate_profile(avg, raw, equity=fp.E7)
        self.rounds.append(P)
        self.model, smooth_info = self.pooled_model()
        gap_in = H.evaluate_profile(avg, self.model, equity=fp.E7)
        it = self._solve(self.model)
        self.iterates.append(it)
        rec = dict(
            r=len(self.rounds) - 1,
            gap_ho={k: float(v) for k, v in gap_ho.items()},
            gap_in={k: float(v) for k, v in gap_in.items()},
            freq=freqs(avg),
            freq_iterate=freqs(it),
            smooth=smooth_info,
        )
        if prev_model is not None:
            rec["agree_in_oos"] = agreement(avg, prev_model, raw)
        return rec


def freqs(res) -> dict:
    return {nid: {a: 100 * v for a, v in nr.freq.items()} for nid, nr in res.nodes.items()}


def max_freq_change(a: dict, b: dict, mass_a=None) -> tuple[float, str]:
    best = (0.0, "-")
    for nid, fa in a.items():
        fb = b.get(nid)
        if fb is None or list(fa) != list(fb) or (mass_a is not None and mass_a.get(nid, 1) < 0.01):
            continue
        for act, x in fa.items():
            d = abs(x - fb[act])
            if d > best[0]:
                best = (d, f"{nid}:{act}")
    return best


def joint_mass(res) -> dict:
    """Prawdopodobieństwo dojścia do węzła (wspólne, z card removal)."""
    root = H.build_tree(res.depth, H.TreeConfig(**res.tree), fp.E7, H.CheckdownLeaf())
    out = {}

    def walk(n, rs, rb):
        if n.actor is None:
            return
        out[n.id] = float(rs @ H.W @ rb / H.WTOT)
        sig = res.nodes[n.id].strategy
        for i, c in enumerate(n.children):
            if n.actor == 0:
                walk(c, rs * sig[:, i], rb)
            else:
                walk(c, rs, rb * sig[:, i])

    walk(root, np.ones(H.N), np.ones(H.N))
    return out


def action_evs(res, model, nid: str):
    """EV akcji per klasa aktora w węźle `nid` profilu `res` przy modelu liścia (bb na kombinację
    aktora, wobec zasięgu rywala w węźle) i zasięg własny aktora."""
    root = H.build_tree(res.depth, H.TreeConfig(**res.tree), fp.E7, model)
    sv = H._Solver(root)
    for n in sv.dec:
        n.S = res.nodes[n.id].strategy.copy()
    one = np.ones(H.N)

    def find(n, r_sb, r_bb):
        if n.id == nid:
            return n, r_sb, r_bb
        if n.actor is None:
            return None
        sig = res.nodes[n.id].strategy
        for i, c in enumerate(n.children):
            got = (
                find(c, r_sb * sig[:, i], r_bb) if n.actor == 0 else find(c, r_sb, r_bb * sig[:, i])
            )
            if got:
                return got
        return None

    n, r_sb, r_bb = find(sv.root, one, one)
    if n.actor == 0:
        ev = np.array([sv._value(c, 0, r_bb, False) / (H.W @ r_bb) for c in n.children])
        return n.actions, ev, r_sb
    ev = np.array([sv._value(c, 1, r_sb, False) / (H.W.T @ r_sb) for c in n.children])
    return n.actions, ev, r_bb


def agreement(res, model_a, model_b, nids=("root", "limp", "r2")) -> dict:
    """Zgodność akcji najlepszej per klasa w profilu `res` między dwoma modelami liścia (ważona
    zasięgiem aktora x kombinacje) — miara krytyka (post_oos.py)."""
    out = {}
    for nid in nids:
        if nid not in res.nodes:
            continue
        _, ev_a, own = action_evs(res, model_a, nid)
        _, ev_b, _ = action_evs(res, model_b, nid)
        w = own * H.NCOMBO
        if w.sum() <= 0:
            continue
        out[nid] = float((w @ (ev_a.argmax(0) == ev_b.argmax(0))) / w.sum())
    return out


def predicted_ev(model: fp.IntegLeaf, key: str, lf: dict) -> np.ndarray:
    """EV klas (bb, [2,169]) przewidziane przez model addytywny przy zakresach liścia."""
    sb, bb = fp.leaf_ranges(lf)
    a_sb, a_bb = model.a[key]
    s_sb, s_bb = H.shares_vs_range(fp.E7 + a_sb[:, None] - a_bb[None, :], sb, bb)
    return np.stack([s_bb, s_sb]) * lf["pot"]


def bias(pred: np.ndarray, ev: np.ndarray, loo: np.ndarray, lf: dict) -> dict:
    """Średnia ważona zasięgiem (pred - ev) per gracz (bb), jej SE jackknife po flopach `ev`
    (loo = EV z pominięciem flopu) i RMS różnicy per klasa."""
    w = class_weights(lf)
    out = {}
    for p, who, wp in ((1, "SB", w[0]), (0, "BB", w[1])):
        ok = np.isfinite(ev[p]) & np.isfinite(pred[p]) & np.all(np.isfinite(loo[:, p]), 0)
        m = wp[ok] / wp[ok].sum()
        means = loo[:, p][:, ok] @ m
        out[who] = dict(
            bias=float(m @ (pred[p][ok] - ev[p][ok])),
            se=float(np.sqrt(_jk_var(means))) if len(loo) > 1 else float("inf"),
            rms=float(np.sqrt(m @ (pred[p][ok] - ev[p][ok]) ** 2)),
        )
    return out

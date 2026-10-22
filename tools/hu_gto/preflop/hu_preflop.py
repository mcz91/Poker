"""Solver preflop HU (SB = button vs BB) dla fazy heads-up Spina, chipEV (WTA).

Gra: 169 klas rąk z card removal na poziomie kombinacji. Waga pary klas
W[h, v] = liczba rozłącznych par kombinacji; przy strategiach niezależnych od
kolorów (a każda strategia na klasach taka jest) to abstrakcja bezstratna.
Wszystkie wartości w bb, z perspektywy SB, jako zmiana stacku w rozdaniu.

Drzewo (domyślne, `TreeConfig`):
  SB first-in : fold / limp / raise 2x / raise 2,5x (gdy S > 12) / jam
  BB vs limp  : check [liść limp_check] / iso do `iso_size` / jam
  SB vs iso   : fold / call [liść iso_call] / jam;   BB vs jam SB: fold / call
  SB vs jam BB: fold / call
  BB vs raise : fold / call [liść raise_call] / 3bet-jam (+ mały 3bet przy S >= small_3bet_min)
  SB vs 3bet-jam: fold / call;  SB vs mały 3bet: fold / call [liść 3bet_call] / 4bet-jam
  BB vs jam   : fold / call
Rozmiar >= stacku jest usuwany (byłby jamem).

Liście nie-all-in (`Line`) wycenia `LeafModel.share(line, E) -> R[h, v]`:
udział SB w puli, a EV_SB = pot * R - pot / 2. BB dostaje 1 - R, więc suma
zerowa jest zachowana z konstrukcji, niezależnie od modelu.

Algorytm: wektorowy DCFR (alpha 1,5, beta 0, gamma 2) z naprzemiennymi
aktualizacjami albo CFR+; luka best response liczona dokładnie na tym samym drzewie.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

HERE = Path(__file__).resolve().parent
RANKS = "AKQJT98765432"


def _classes() -> list[str]:
    out = []
    for a, hi in enumerate(RANKS):
        for lo in RANKS[a:]:
            if hi == lo:
                out.append(hi + lo)
            else:
                out += [hi + lo + "s", hi + lo + "o"]
    return out


CLASSES = _classes()
N = len(CLASSES)
INDEX = {c: i for i, c in enumerate(CLASSES)}


def _combos(cls: str) -> list[tuple[int, int]]:
    hi, lo = 4 * RANKS.index(cls[0]), 4 * RANKS.index(cls[1])
    if len(cls) == 2:
        return [(hi + a, lo + b) for a in range(4) for b in range(a + 1, 4)]
    if cls[2] == "s":
        return [(hi + s, lo + s) for s in range(4)]
    return [(hi + a, lo + b) for a in range(4) for b in range(4) if a != b]


def _weights() -> tuple[np.ndarray, np.ndarray]:
    owner, rows = [], []
    for i, c in enumerate(CLASSES):
        for x, y in _combos(c):
            m = np.zeros(52)
            m[x] = m[y] = 1
            rows.append(m)
            owner.append(i)
    M = np.array(rows)
    disjoint = (M @ M.T == 0).astype(float)
    P = np.zeros((N, len(owner)))
    P[owner, np.arange(len(owner))] = 1
    return P @ disjoint @ P.T, P.sum(1)


W, NCOMBO = _weights()
WTOT = W.sum()


def load_equity(source: str = "eval7") -> np.ndarray:
    """'eval7' = equity_eval7_1M.npy (MC 1e6 prób/parę, SE ~0,05 pp); 'repo' = poker.preflop_equity
    (MC 2048 prób/parę, SE ~1,1 pp); inna wartość = ścieżka do .npy 169x169."""
    if source == "eval7":
        return np.load(HERE / "equity_eval7_1M.npy")
    if source == "repo":
        from poker.preflop_equity_data import HALF_POT_UNITS, TRIALS_PER_PAIR

        return np.array(HALF_POT_UNITS, float).reshape(N, N) / (2 * TRIALS_PER_PAIR)
    return np.load(source)


@dataclass(frozen=True)
class Line:
    """Pula nie-all-in na flopie. SB jest IP (HU: button działa ostatni postflop)."""

    name: str  # limp_check | iso_call | raise_call | 3bet_call
    node: str  # identyfikator historii preflop prowadzącej do liścia
    depth: float  # stack efektywny S (bb) na starcie rozdania
    pot: float  # pula na flopie (bb)
    aggressor: str  # 'none' | 'SB' | 'BB' — ostatni agresor preflop

    @property
    def behind(self) -> float:
        return self.depth - self.pot / 2

    @property
    def spr(self) -> float:
        return self.behind / self.pot


class LeafModel(Protocol):
    def share(self, line: Line, E: np.ndarray) -> np.ndarray:
        """Macierz 169x169: oczekiwany udział SB w puli `line.pot` (h = SB, v = BB).
        Może wychodzić poza [0, 1] (postflop przegrywa/wygrywa też stack za pulą)."""
        ...


class CheckdownLeaf:
    """EQR = 1: pula rozgrywana do showdownu bez licytacji."""

    name = "checkdown"

    def share(self, line: Line, E: np.ndarray) -> np.ndarray:
        return E


@dataclass
class ConstEQRLeaf:
    """Stały EQR per pozycja (PLACEHOLDER, nie pomiar).

    Naiwne R = EQR * equity nie jest sumą zerową (1,05 e + 0,85 (1 - e) != 1),
    więc udziały są normalizowane parami: R = q_ip e / (q_ip e + q_oop (1 - e)).
    Przy e = 0,5 IP dostaje 0,553 puli (efektywne EQR 1,105 / 0,895).
    `spr_full` > 0 włącza liniowe wygaszanie do EQR = 1 przy SPR -> 0 (opcja, domyślnie wyłączona).
    """

    eqr_ip: float = 1.05
    eqr_oop: float = 0.85
    spr_full: float = 0.0

    @property
    def name(self) -> str:
        return f"eqr{self.eqr_ip:g}/{self.eqr_oop:g}" + (
            f"/taper{self.spr_full:g}" if self.spr_full else ""
        )

    def share(self, line: Line, E: np.ndarray) -> np.ndarray:
        k = 1.0 if self.spr_full <= 0 else min(1.0, line.spr / self.spr_full)
        qi = 1 + (self.eqr_ip - 1) * k
        qo = 1 + (self.eqr_oop - 1) * k
        return proportional_share(E, np.full(N, qi), np.full(N, qo))


def proportional_share(E: np.ndarray, q_sb: np.ndarray, q_bb: np.ndarray) -> np.ndarray:
    a = q_sb[:, None] * E
    b = q_bb[None, :] * (1 - E)
    s = a + b
    return np.where(s > 0, a / np.where(s > 0, s, 1), 0.5)


@dataclass
class ClassEQRLeaf:
    """EQR per klasa i linia (np. z solvera postflop): table[line.name] = (q_sb[169], q_bb[169]).
    Zero-sum przez tę samą normalizację co ConstEQRLeaf. Linia spoza tabeli -> fallback."""

    table: dict
    fallback: object = field(default_factory=lambda: ConstEQRLeaf())
    name: str = "class-eqr"

    def share(self, line: Line, E: np.ndarray) -> np.ndarray:
        key = _table_key(self.table, line)
        if key is None:
            return self.fallback.share(line, E)
        q_sb, q_bb = self.table[key]
        return proportional_share(E, np.asarray(q_sb, float), np.asarray(q_bb, float))


@dataclass
class ClassEVLeaf:
    """EV per klasa wobec zakresu (wynik solvera postflop) -> model addytywny
    R[h, v] = E[h, v] + a_sb[h] - a_bb[v]  (zero-sum: R_BB = 1 - R).

    table[key] = dict(share_sb[169], share_bb[169], range_sb[169], range_bb[169]),
    gdzie share_X[c] = EV_postflop(c) / pot — oczekiwany udział w puli klasy c wobec
    zakresu rywala (EV liczone od puli na flopie, jak w solverach postflop),
    range_X = wagi zasięgu klas w liściu (prawdopodobieństwo dojścia, bez mnożenia przez liczbę
    kombinacji). Klucz (pierwszy pasujący): f"{line.node}@{depth:g}", line.node,
    f"{line.name}@{depth:g}", line.name.
    a_* dopasowane metodą najmniejszych kwadratów z card removal (`fit_additive`), z normalizacją
    sum_v range_bb a_bb = 0. Klasa z udziałem NaN albo bez zasięgu rywala: a = 0.
    """

    table: dict
    fallback: object = field(default_factory=lambda: CheckdownLeaf())
    name: str = "class-ev"
    _cache: dict = field(default_factory=dict, repr=False)

    def share(self, line: Line, E: np.ndarray) -> np.ndarray:
        key = _table_key(self.table, line)
        if key is None:
            return self.fallback.share(line, E)
        ck = (key, id(E))
        if ck not in self._cache:
            d = self.table[key]
            a_sb, a_bb = fit_additive(
                E,
                *(
                    np.asarray(d[k], float)
                    for k in ("share_sb", "share_bb", "range_sb", "range_bb")
                ),
            )
            self._cache[ck] = E + a_sb[:, None] - a_bb[None, :]
        return self._cache[ck]


def _table_key(table: dict, line: Line):
    for k in (f"{line.node}@{line.depth:g}", line.node, f"{line.name}@{line.depth:g}", line.name):
        if k in table:
            return k
    return None


def fit_additive(E, share_sb, share_bb, range_sb, range_bb, floor: float = 1e-3):
    """Dopasowanie a_sb, a_bb modelu R = E + a_sb[h] - a_bb[v] do udziałów per klasa wobec zakresu.

    Klasa z udziałem NaN jest pomijana (a = 0). Wagi równań: max(zasięg, floor) * kombinacje, więc
    klasy spoza zakresu (wartość BR podana przez solver postflop) też są dopasowane, ale słabiej.
    """
    ws = W * range_bb[None, :]  # SB klasa h: rozkład rąk BB
    wb = W.T * range_sb[None, :]  # BB klasa v: rozkład rąk SB
    act_s = np.isfinite(share_sb) & (ws.sum(1) > 0)
    act_b = np.isfinite(share_bb) & (wb.sum(1) > 0)
    ps = ws[act_s] / ws[act_s].sum(1, keepdims=True)
    pb = wb[act_b] / wb[act_b].sum(1, keepdims=True)
    es = (ps * E[act_s]).sum(1)
    eb = (pb * (1 - E.T[act_b])).sum(1)
    ns, nb = act_s.sum(), act_b.sum()
    # niewiadome x = [a_sb(act_s), a_bb(act_b)]
    A1 = np.zeros((ns, ns + nb))
    A1[np.arange(ns), np.arange(ns)] = 1
    A1[:, ns:] = -ps[:, act_b]
    A2 = np.zeros((nb, ns + nb))
    A2[np.arange(nb), ns + np.arange(nb)] = 1
    A2[:, :ns] = -pb[:, act_s]
    wts = np.sqrt(
        np.concatenate(
            [
                np.maximum(range_sb[act_s], floor) * NCOMBO[act_s],
                np.maximum(range_bb[act_b], floor) * NCOMBO[act_b],
            ]
        )
    )
    wts = wts / wts.max()
    norm = np.zeros((1, ns + nb))
    norm[0, ns:] = range_bb[act_b] * NCOMBO[act_b]
    norm /= max(norm.sum(), 1e-12)
    A = np.vstack([A1 * wts[:ns, None], A2 * wts[ns:, None], norm])
    b = np.concatenate(
        [(share_sb[act_s] - es) * wts[:ns], (share_bb[act_b] - eb) * wts[ns:], [0.0]]
    )
    x = np.linalg.lstsq(A, b, rcond=None)[0]
    a_sb = np.zeros(N)
    a_bb = np.zeros(N)
    a_sb[act_s] = x[:ns]
    a_bb[act_b] = x[ns:]
    return a_sb, a_bb


def shares_vs_range(R: np.ndarray, range_sb: np.ndarray, range_bb: np.ndarray):
    """Udziały per klasa wobec zakresu rywala z macierzy par R (z card removal) — to, co
    zwróciłby idealny solver postflop, gdyby prawdziwą grą był model R. Używane w testach."""
    ws = W * range_bb[None, :]
    wb = W * range_sb[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        s_sb = (ws * R).sum(1) / ws.sum(1)
        s_bb = (wb * (1 - R)).sum(0) / wb.sum(0)
    return s_sb, s_bb


@dataclass
class TreeConfig:
    mode: str = "full"  # full | jamfold | open_jam (fold / open / jam)
    raise_small: float = 2.0
    raise_big: float | None = 2.5  # drugi rozmiar przy S > big_min
    big_min: float = 12.0
    limp: bool = True
    iso_size: float = 3.5  # iso do X bb (bezwzględnie)
    bb_flat: bool = True
    small_3bet_min: float | None = None  # np. 20.0 -> mały 3bet przy S >= 20
    small_3bet_mult: float = 2.5  # 3bet do mult * rozmiar raise'a
    open_size: float = 2.0  # tylko mode=open_jam

    def raise_sizes(self, S: float) -> list[float]:
        if self.mode == "open_jam":
            return [self.open_size] if self.open_size < S else []
        out = [self.raise_small]
        if self.raise_big and S > self.big_min:
            out.append(self.raise_big)
        return [r for r in out if r < S]


@dataclass
class Node:
    id: str
    actor: int | None  # 0 = SB, 1 = BB, None = liść
    actions: list[str] = field(default_factory=list)
    children: list[Node] = field(default_factory=list)
    U: np.ndarray | None = None  # liść: zmiana stacku SB per para (h, v)
    line: Line | None = None
    kind: str = ""  # liść: fold_sb | fold_bb | allin | postflop


def _cid(parent: str, a: str) -> str:
    return a if parent == "root" else f"{parent}-{a}"


def build_tree(S: float, cfg: TreeConfig, E: np.ndarray, leaf: LeafModel) -> Node:
    allin = S * (2 * E - 1)

    def fold(nid, who, c_sb, c_bb):
        U = np.full((N, N), -c_sb if who == 0 else c_bb)
        return Node(nid, None, U=U, kind="fold_sb" if who == 0 else "fold_bb")

    def showdown(nid):
        return Node(nid, None, U=allin, kind="allin")

    def flop(nid, name, c, aggressor):
        line = Line(name, nid, S, 2 * c, aggressor)
        return Node(nid, None, U=line.pot * leaf.share(line, E) - c, line=line, kind="postflop")

    def facing_jam(nid, who, c_sb, c_bb):  # `who` decyduje fold/call wobec all-in rywala
        n = Node(nid, who, ["fold", "call"])
        n.children = [fold(_cid(nid, "fold"), who, c_sb, c_bb), showdown(_cid(nid, "call"))]
        return n

    root = Node("root", 0)
    if S <= 1.0:  # BB all-in z blindu
        root.actions = ["fold", "call"]
        root.children = [fold("fold", 0, min(0.5, S), S), showdown("call")]
        return root

    def add(node, a, child):
        node.actions.append(a)
        node.children.append(child)

    add(root, "fold", fold("fold", 0, 0.5, 1.0))
    if cfg.mode == "full" and cfg.limp:
        L = Node("limp", 1)
        add(L, "check", flop("limp-check", "limp_check", 1.0, "none"))
        X = cfg.iso_size
        if X < S:
            iso = Node("limp-iso", 0)
            add(iso, "fold", fold("limp-iso-fold", 0, 1.0, X))
            add(iso, "call", flop("limp-iso-call", "iso_call", X, "BB"))
            add(iso, "jam", facing_jam("limp-iso-jam", 1, S, X))
            add(L, "iso", iso)
        add(L, "jam", facing_jam("limp-jam", 0, 1.0, S))
        add(root, "limp", L)
    if cfg.mode in ("full", "open_jam"):
        for r in cfg.raise_sizes(S):
            rid = f"r{r:g}"
            B = Node(rid, 1)
            add(B, "fold", fold(_cid(rid, "fold"), 1, r, 1.0))
            if cfg.bb_flat:
                add(B, "call", flop(_cid(rid, "call"), "raise_call", r, "SB"))
            if cfg.small_3bet_min is not None and S >= cfg.small_3bet_min:
                t = cfg.small_3bet_mult * r
                if t < S:
                    tid = _cid(rid, "3b")
                    T = Node(tid, 0)
                    add(T, "fold", fold(_cid(tid, "fold"), 0, r, t))
                    add(T, "call", flop(_cid(tid, "call"), "3bet_call", t, "BB"))
                    add(T, "jam", facing_jam(_cid(tid, "jam"), 1, S, t))
                    add(B, "3b", T)
            add(B, "jam", facing_jam(_cid(rid, "jam"), 0, r, S))
            add(root, rid, B)
    add(root, "jam", facing_jam("jam", 1, S, 1.0))
    return root


def iter_nodes(node: Node):
    yield node
    for c in node.children:
        yield from iter_nodes(c)


class _Solver:
    def __init__(self, root: Node, algo: str = "dcfr"):
        self.root = root
        self.algo = algo
        self.dec = [n for n in iter_nodes(root) if n.actor is not None]
        for n in iter_nodes(root):
            if n.actor is None:
                n.M = W * n.U  # SB: v = M @ reach_bb;  BB: v = -(M.T @ reach_sb)
                n.MT = np.ascontiguousarray(-n.M.T)
            else:
                k = len(n.actions)
                n.R = np.zeros((N, k))
                n.S = np.zeros((N, k))
        self.t = 0

    @staticmethod
    def _strat(R):
        p = np.maximum(R, 0.0)
        s = p.sum(1, keepdims=True)
        return np.where(s > 0, p / np.where(s > 0, s, 1.0), 1.0 / R.shape[1])

    def _cfr(self, n: Node, p: int, r_opp: np.ndarray, r_own: np.ndarray) -> np.ndarray:
        if n.actor is None:
            return n.M @ r_opp if p == 0 else n.MT @ r_opp
        sig = self._strat(n.R)
        if n.actor == p:
            V = np.stack(
                [self._cfr(c, p, r_opp, r_own * sig[:, a]) for a, c in enumerate(n.children)], 1
            )
            v = (sig * V).sum(1)
            n.R += V - v[:, None]
            t = self.t
            if self.algo == "dcfr":
                ta = t**1.5
                n.R *= np.where(n.R > 0, ta / (ta + 1), 0.5)
                n.S = n.S * (t / (t + 1)) ** 2 + r_own[:, None] * sig
            else:  # cfr+
                np.maximum(n.R, 0, out=n.R)
                n.S += t * r_own[:, None] * sig
            return v
        return sum(self._cfr(c, p, r_opp * sig[:, a], r_own) for a, c in enumerate(n.children))

    def iterate(self, k: int):
        one = np.ones(N)
        for _ in range(k):
            self.t += 1
            for p in (0, 1):
                self._cfr(self.root, p, one, one)

    @staticmethod
    def avg(n: Node) -> np.ndarray:
        s = n.S.sum(1, keepdims=True)
        return np.where(s > 0, n.S / np.where(s > 0, s, 1.0), 1.0 / n.S.shape[1])

    def _value(self, n, p, r_opp, br: bool):
        if n.actor is None:
            return n.M @ r_opp if p == 0 else n.MT @ r_opp
        sig = self.avg(n)
        if n.actor == p:
            V = np.stack([self._value(c, p, r_opp, br) for c in n.children], 1)
            return V.max(1) if br else (sig * V).sum(1)
        return sum(self._value(c, p, r_opp * sig[:, a], br) for a, c in enumerate(n.children))

    def exploitability(self):
        one = np.ones(N)
        ev_sb = self._value(self.root, 0, one, False).sum() / WTOT
        br_sb = self._value(self.root, 0, one, True).sum() / WTOT
        br_bb = self._value(self.root, 1, one, True).sum() / WTOT
        return dict(
            ev_sb=ev_sb,
            gap_sb=br_sb - ev_sb,
            gap_bb=br_bb + ev_sb,
            expl=(br_sb - ev_sb + br_bb + ev_sb) / 2,
        )


@dataclass
class NodeResult:
    actor: str
    actions: list[str]
    strategy: np.ndarray  # 169 x A
    reach: np.ndarray  # zasięg własny klasy aktora (prawdopodobieństwo dojścia)
    freq: dict  # częstości akcji ważone kombinacjami * zasięgiem własnym


@dataclass
class SolveResult:
    depth: float
    leaf: str
    tree: dict
    nodes: dict  # id -> NodeResult
    leaves: list  # liście postflop z zakresami (do zasilenia solvera postflop)
    ev_sb: float  # bb/rozdanie
    gap_sb: float  # zysk BR SB ponad EV profilu (bb/rozdanie)
    gap_bb: float
    expl: float  # (gap_sb + gap_bb) / 2
    iters: int
    seconds: float
    history: list = field(default_factory=list)

    def summary(self) -> dict:
        out = dict(
            depth=self.depth,
            ev_sb=self.ev_sb,
            gap_sb=self.gap_sb,
            gap_bb=self.gap_bb,
            iters=self.iters,
            seconds=self.seconds,
        )
        for nid, nr in self.nodes.items():
            for a, f in nr.freq.items():
                out[f"{nid}:{a}"] = f
        return out


def solve(
    depth_bb: float,
    leaf_model: LeafModel | None = None,
    *,
    tree: TreeConfig | None = None,
    equity: np.ndarray | str = "eval7",
    algo: str = "dcfr",
    iters: int = 2000,
    target_expl: float | None = 1e-4,
    check_every: int = 100,
) -> SolveResult:
    """Rozwiązuje HU preflop dla stacku efektywnego `depth_bb`.

    Zatrzymanie: `iters` iteracji albo wcześniej, gdy expl = (gap_SB + gap_BB)/2 < target_expl
    (bb/rozdanie).
    """
    leaf_model = leaf_model or CheckdownLeaf()
    tree = tree or TreeConfig()
    E = load_equity(equity) if isinstance(equity, str) else equity
    t0 = time.perf_counter()
    root = build_tree(depth_bb, tree, E, leaf_model)
    sv = _Solver(root, algo)
    hist = []
    done = 0
    ex = None
    while done < iters:
        k = min(check_every, iters - done)
        sv.iterate(k)
        done += k
        if target_expl is not None or done >= iters:
            ex = sv.exploitability()
            hist.append((done, time.perf_counter() - t0, ex["expl"]))
            if target_expl is not None and ex["expl"] < target_expl:
                break
    seconds = time.perf_counter() - t0
    nodes, leaves = _collect(sv)
    return SolveResult(
        depth_bb,
        getattr(leaf_model, "name", type(leaf_model).__name__),
        asdict(tree),
        nodes,
        leaves,
        ex["ev_sb"],
        ex["gap_sb"],
        ex["gap_bb"],
        ex["expl"],
        done,
        seconds,
        hist,
    )


def evaluate_profile(
    result: SolveResult, leaf_model: LeafModel | None = None, *, equity: np.ndarray | str = "eval7"
) -> dict:
    """Luka BR strategii `result` w (być może innej) grze: inny model liścia albo inna macierz
    equity. Drzewo jak w `result.tree`. Zwraca ev_sb, gap_sb, gap_bb, expl (bb/rozdanie)."""
    E = load_equity(equity) if isinstance(equity, str) else equity
    root = build_tree(result.depth, TreeConfig(**result.tree), E, leaf_model or CheckdownLeaf())
    sv = _Solver(root)
    for n in sv.dec:
        n.S = result.nodes[n.id].strategy.copy()
    return sv.exploitability()


def export_leaves(result: SolveResult, path: str | Path):
    """JSON z liśćmi postflop i zakresami (wejście dla solvera postflop)."""
    Path(path).write_text(
        json.dumps(
            dict(depth=result.depth, classes=CLASSES, leaves=result.leaves), ensure_ascii=False
        )
    )


def fixed_point(
    depth_bb: float,
    postflop: Callable[[dict], dict],
    *,
    rounds: int = 4,
    start: LeafModel | None = None,
    damping: float = 0.0,
    **solve_kw,
) -> list[SolveResult]:
    """Pętla preflop <-> postflop. `postflop(leaf)` dostaje element `SolveResult.leaves`
    (line, node, depth, pot, behind, spr, aggressor, range_sb, range_bb) i zwraca
    dict(share_sb=[169], share_bb=[169]) = EV_postflop/pot per klasa wobec zakresu rywala
    (NaN dla klas, których nie policzono). Kolejne rundy używają ClassEVLeaf; `damping` miesza
    udziały z poprzednią rundą."""
    leaf = start or ConstEQRLeaf()
    table: dict = {}
    out = []
    for _ in range(rounds):
        res = solve(depth_bb, leaf, **solve_kw)
        out.append(res)
        new = {}
        for lf in res.leaves:
            d = postflop(lf)
            key = f"{lf['node']}@{lf['depth']:g}"
            s_sb, s_bb = np.asarray(d["share_sb"], float), np.asarray(d["share_bb"], float)
            if damping and key in table:
                s_sb = damping * table[key]["share_sb"] + (1 - damping) * s_sb
                s_bb = damping * table[key]["share_bb"] + (1 - damping) * s_bb
            new[key] = dict(
                share_sb=s_sb,
                share_bb=s_bb,
                range_sb=np.asarray(lf["range_sb"]),
                range_bb=np.asarray(lf["range_bb"]),
            )
        table = new
        leaf = ClassEVLeaf(table, fallback=start or ConstEQRLeaf())
    return out


def _collect(sv: _Solver):
    nodes, leaves = {}, []

    def walk(n: Node, r_sb, r_bb):
        if n.actor is None:
            if n.kind == "postflop":
                ln = n.line
                leaves.append(
                    dict(
                        line=ln.name,
                        node=ln.node,
                        depth=ln.depth,
                        pot=ln.pot,
                        behind=ln.behind,
                        spr=ln.spr,
                        aggressor=ln.aggressor,
                        range_sb=r_sb.tolist(),
                        range_bb=r_bb.tolist(),
                        freq_sb=float((r_sb * NCOMBO).sum() / NCOMBO.sum()),
                        freq_bb=float((r_bb * NCOMBO).sum() / NCOMBO.sum()),
                    )
                )
            return
        sig = sv.avg(n)
        own = r_sb if n.actor == 0 else r_bb
        w = own * NCOMBO
        tot = w.sum()
        freq = {
            a: float((w * sig[:, i]).sum() / tot) if tot > 0 else 0.0
            for i, a in enumerate(n.actions)
        }
        nodes[n.id] = NodeResult(
            "SB" if n.actor == 0 else "BB", list(n.actions), sig, own.copy(), freq
        )
        for i, c in enumerate(n.children):
            if n.actor == 0:
                walk(c, r_sb * sig[:, i], r_bb)
            else:
                walk(c, r_sb, r_bb * sig[:, i])

    walk(sv.root, np.ones(N), np.ones(N))
    return nodes, leaves


def grid_index(i: int, j: int) -> int:
    """Komórka (wiersz i, kolumna j): nad przekątną suited, pod offsuit, przekątna pary."""
    if i == j:
        return INDEX[RANKS[i] * 2]
    if i < j:
        return INDEX[RANKS[i] + RANKS[j] + "s"]
    return INDEX[RANKS[j] + RANKS[i] + "o"]


ACTION_CODE = {
    "fold": "F",
    "limp": "L",
    "check": "X",
    "call": "C",
    "iso": "I",
    "jam": "J",
    "3b": "T",
}


def _code(a: str) -> str:
    if a.startswith("r"):
        return "R" if a == "r2" else "Q"
    return ACTION_CODE.get(a, a[:1].upper())


def chart_text(nr: NodeResult, action: str | None = None, title: str = "") -> str:
    """action=None: w komórce kod akcji dominującej + jej % (np. 'J100', 'L64');
    action='jam': procent tej akcji w każdej komórce."""
    lines = [title] if title else []
    if action is None:
        legend = ", ".join(f"{_code(a)}={a}" for a in nr.actions)
        lines.append(f"[{nr.actor}] dominująca akcja i jej % ({legend})")
    else:
        lines.append(f"[{nr.actor}] % akcji '{action}'")
    lines.append("     " + " ".join(f"{r:>4}" for r in RANKS))
    k = nr.actions.index(action) if action else None
    for i in range(13):
        row = []
        for j in range(13):
            s = nr.strategy[grid_index(i, j)]
            if k is not None:
                row.append(f"{100 * s[k]:4.0f}")
            else:
                a = int(np.argmax(s))
                row.append(
                    f"{_code(nr.actions[a])}{min(99, round(100 * s[a])):>3d}"
                    if s[a] < 0.995
                    else f"{_code(nr.actions[a])}  *"
                )
        lines.append(f"{RANKS[i]:>4} " + " ".join(row))
    lines.append(
        "     ('*' = >=99,5%; kolumna wyższa ranga = suited nad przekątną, offsuit pod nią)"
    )
    lines.append("     częstości: " + ", ".join(f"{a} {100 * f:.1f}%" for a, f in nr.freq.items()))
    return "\n".join(lines)


def save_book(results: list[SolveResult], path: str | Path):
    """Zapis strategii wielu głębokości do .npz + manifest JSON (lookup w µs)."""
    arrays, meta = {}, {"classes": CLASSES, "depths": {}}
    for r in results:
        d = f"{r.depth:g}"
        meta["depths"][d] = dict(
            leaf=r.leaf,
            ev_sb=r.ev_sb,
            gap_sb=r.gap_sb,
            gap_bb=r.gap_bb,
            iters=r.iters,
            seconds=r.seconds,
            tree=r.tree,
            nodes={nid: nr.actions for nid, nr in r.nodes.items()},
        )
        for nid, nr in r.nodes.items():
            arrays[f"{d}|{nid}"] = nr.strategy.astype(np.float32)
    np.savez_compressed(str(path), **arrays)
    Path(str(path) + ".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))


class Book:
    """Lookup: Book(path).get(depth, node, hand) -> {akcja: p}. Głębokość spoza siatki:
    interpolacja liniowa między sąsiednimi głębokościami, jeśli mają ten sam zestaw akcji,
    inaczej najbliższa."""

    def __init__(self, path: str | Path):
        z = np.load(str(path))
        self.meta = json.loads(Path(str(path) + ".json").read_text())
        self.depths = sorted(float(d) for d in self.meta["depths"])
        self.tab = {}
        for key in z.files:
            d, nid = key.split("|", 1)
            self.tab[(float(d), nid)] = (self.meta["depths"][d]["nodes"][nid], z[key])

    def get(self, depth: float, node: str, hand: str) -> dict:
        h = INDEX[hand]
        ds = self.depths
        if depth <= ds[0] or depth >= ds[-1] or depth in ds:
            d = min(ds, key=lambda x: abs(x - depth))
            acts, arr = self.tab[(d, node)]
            return dict(zip(acts, arr[h].tolist(), strict=True))
        lo = max(x for x in ds if x < depth)
        hi = min(x for x in ds if x > depth)
        a_lo, s_lo = self.tab.get((lo, node), (None, None))
        a_hi, s_hi = self.tab.get((hi, node), (None, None))
        if a_lo is not None and a_lo == a_hi:
            w = (depth - lo) / (hi - lo)
            return dict(zip(a_lo, ((1 - w) * s_lo[h] + w * s_hi[h]).tolist(), strict=True))
        d = lo if (depth - lo) <= (hi - depth) else hi
        acts, arr = self.tab[(d, node)]
        return dict(zip(acts, arr[h].tolist(), strict=True))


def _main():
    import argparse

    ap = argparse.ArgumentParser(description="HU preflop solve + chart 13x13")
    ap.add_argument("depth", type=float)
    ap.add_argument("--leaf", default="eqr", choices=["checkdown", "eqr", "jamfold"])
    ap.add_argument("--eqr", nargs=2, type=float, default=(1.05, 0.85), metavar=("IP", "OOP"))
    ap.add_argument("--node", default=None, help="id węzła (domyślnie wszystkie)")
    ap.add_argument("--action", default=None, help="chart procentowy jednej akcji")
    ap.add_argument("--equity", default="eval7")
    ap.add_argument("--target", type=float, default=1e-4)
    a = ap.parse_args()
    leaf = ConstEQRLeaf(*a.eqr) if a.leaf == "eqr" else CheckdownLeaf()
    tree = TreeConfig(mode="jamfold") if a.leaf == "jamfold" else TreeConfig()
    r = solve(a.depth, leaf, tree=tree, equity=a.equity, iters=20000, target_expl=a.target)
    print(
        f"S={r.depth:g} bb  liść={r.leaf}  EV_SB {r.ev_sb:+.4f} bb  "
        f"luka SB {r.gap_sb:.1e} BB {r.gap_bb:.1e}  {r.iters} it  {r.seconds:.2f} s"
    )
    for nid, nr in r.nodes.items():
        if a.node in (None, nid):
            print("\n" + chart_text(nr, a.action, title=f"--- węzeł {nid}"))


if __name__ == "__main__":
    _main()

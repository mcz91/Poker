#!/usr/bin/env python
"""spin_gto: strategia bliska GTO dla fazy HU Spina (SB = button vs BB), chipEV, bez ante.
Narzędzie do nauki i analizy offline.

  python spin_gto.py --depth 15 --line "SB limp" --hand K7o
  python spin_gto.py --depth 15 --line "SB limp, BB check" --board Ks7d2c --hand AhTd
  python spin_gto.py --depth 15 --line "SB limp, BB check; BB check, SB bet 1, BB call"
      --board Ks7d2c5h --hand AhTd

--line: akcje preflop rozdzielone przecinkami, ulice postflop po ';' (flop; turn; river).
  preflop: SB fold|limp|raise 2|raise 2.5|jam, BB check|iso|jam|fold|call,
           SB vs iso: fold|call|jam ...
  postflop: '<SB|BB> check|bet X|raise X|call|fold|allin' (X w bb, albo 'X%' puli, albo bez kwoty).
--board: 3/4/5 kart = pytanie o flop/turn/river. Bez --board pytanie dotyczy węzła preflop.
--hand: ręka gracza, który ma ruch (np. AhTd albo klasa ATo dla preflop).

Preflop: strategia z booka punktu stałego (data/book.npz), EV akcji z modelu liścia (ms).
Postflop: zakresy z liścia preflop -> solve b-inary na żywo (cache w tool/cache,
klucz = sha1 zadania);
turn/river: zakresy zawężone przez strategię z solve'u poprzedniej ulicy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

TOOL = Path(__file__).resolve().parent
HU = TOOL.parent
sys.path[:0] = [str(HU / "preflop"), str(HU / "postflop")]

import hu_preflop as H  # noqa: E402
from hupf_py import cards, solver  # noqa: E402
from hupf_py.pipeline import auto_tree  # noqa: E402

DATA = TOOL / "data"
CACHE = TOOL / "cache"
# Jak w pętli punktu stałego: każda klasa ma strategię (prawie BR), także spoza zakresu.
FLOOR = 0.005
TARGETS = {3: 2.0, 4: 1.0, 5: 0.5}  # % puli: flop / turn / river
NODE_DEPTH = {3: 3, 4: 3, 5: 2}
LEAF_NODES = {"limp-check", "limp-iso-call", "r2-call", "r2.5-call"}
_STATE: dict = {}


class QueryError(Exception):
    pass


def equity() -> np.ndarray:
    if "E" not in _STATE:
        _STATE["E"] = H.load_equity("eval7")
    return _STATE["E"]


def data():
    if "meta" not in _STATE:
        if not (DATA / "meta.json").is_file():
            raise QueryError(
                f"brak danych narzędzia w {DATA}: to artefakt pętli, nie część repo; "
                "wygeneruj je przez integ/run_fp.py i integ/export_tool_data.py (README)"
            )
        meta = json.loads((DATA / "meta.json").read_text())
        z = np.load(DATA / "leaf_model.npz")
        a = {}
        for k in z.files:
            key, side = k.rsplit("|", 1)
            a.setdefault(key, [None, None])[0 if side == "sb" else 1] = z[k]
        _STATE.update(
            meta=meta,
            book=H.Book(DATA / "book.npz"),
            a={k: tuple(v) for k, v in a.items()},
            E=equity(),
            leaves={},
            solves={},
        )
    return _STATE


class Leaf:
    """Ten sam model co w pętli (integ/fp.IntegLeaf): R = E + a_sb[h] - a_bb[v],
    fallback ConstEQR."""

    def __init__(self, a, depth_map=None):
        self.a, self.depth_map, self.fb = a, depth_map or {}, H.ConstEQRLeaf()

    def share(self, line, E):
        d = self.depth_map.get(line.depth, line.depth)
        k = f"{line.node}@{d:g}"
        if k in self.a:
            a_sb, a_bb = self.a[k]
            return E + a_sb[:, None] - a_bb[None, :]
        return self.fb.share(line, E)


def preflop_result(depth: float):
    """SolveResult-like (nodes, leaves) dla głębokości: z booka (siatka) albo solve na żywo
    (inne S)."""
    st = data()
    grid = [float(d) for d in st["meta"]["depths"]]
    if depth in st["solves"]:
        return st["solves"][depth]
    if depth in grid:
        leaves = json.loads((DATA / f"leaves_{depth:g}.json").read_text())["leaves"]
        out = dict(depth=depth, leaves=leaves, live=False, leaf=Leaf(st["a"]))
    else:
        near = min(grid, key=lambda g: abs(g - depth))
        leaf = Leaf(st["a"], {depth: near})
        r = H.solve(depth, leaf, equity=st["E"], iters=30000, target_expl=2e-5)
        out = dict(depth=depth, leaves=r.leaves, live=True, near=near, leaf=leaf, res=r)
    st["solves"][depth] = out
    return out


def strategy_at(depth, node, cls):
    pr = preflop_result(depth)
    if pr["live"]:
        nr = pr["res"].nodes[node]
        return dict(zip(nr.actions, nr.strategy[H.INDEX[cls]].tolist(), strict=True))
    return data()["book"].get(depth, node, cls)


def node_strategies(depth):
    pr = preflop_result(depth)
    if pr["live"]:
        return {k: v.strategy for k, v in pr["res"].nodes.items()}
    bk = data()["book"]
    return {nid: arr for (d, nid), (_, arr) in bk.tab.items() if d == depth}


def preflop_action_ev(depth, node_id, cls):
    """EV (bb, zmiana stacku od początku rozdania) każdej akcji klasy `cls` w węźle,
    przy strategiach z booka."""
    st = data()
    pr = preflop_result(depth)
    root = H.build_tree(depth, H.TreeConfig(), st["E"], pr["leaf"])
    sv = H._Solver(root)
    strat = node_strategies(depth)
    for n in sv.dec:
        n.S = strat[n.id].astype(float)
    one = np.ones(H.N)

    def find(n, r_sb, r_bb):
        if n.id == node_id:
            return n, r_sb, r_bb
        if n.actor is None:
            return None
        sig = sv.avg(n)
        for i, c in enumerate(n.children):
            got = (
                find(c, r_sb * sig[:, i], r_bb) if n.actor == 0 else find(c, r_sb, r_bb * sig[:, i])
            )
            if got:
                return got
        return None

    n, r_sb, r_bb = find(sv.root, one, one)
    h = H.INDEX[cls]
    if n.actor == 0:
        den = (H.W @ r_bb)[h]
        vals = [sv._value(c, 0, r_bb, False)[h] / den for c in n.children]
    else:
        den = (H.W.T @ r_sb)[h]
        vals = [sv._value(c, 1, r_sb, False)[h] / den for c in n.children]
    reach_opp = float(den / H.W.sum(1)[h])
    return dict(zip(n.actions, [float(v) for v in vals], strict=True)), reach_opp


PRE_SYN = {
    "fold": "fold",
    "limp": "limp",
    "complete": "limp",
    "check": "check",
    "call": "call",
    "iso": "iso",
    "jam": "jam",
    "allin": "jam",
    "all-in": "jam",
    "shove": "jam",
    "push": "jam",
    "3bet": "jam",
    "minraise": "r2",
    "mr": "r2",
}


def parse_pre_token(tok, node_actions):
    m = re.match(r"^(SB|BB)\s+(.+)$", tok.strip(), re.I)
    if not m:
        raise QueryError(f"akcja preflop '{tok}': oczekiwano 'SB ...' albo 'BB ...'")
    who, act = m.group(1).upper(), m.group(2).strip().lower()
    num = re.search(r"(\d+(?:[.,]\d+)?)", act)
    if act.startswith(("raise", "open", "r")) and num and "iso" not in act:
        a = f"r{float(num.group(1).replace(',', '.')):g}"
    elif act.startswith("raise") and "r2" in node_actions:
        a = "r2"
    elif act.startswith("raise") and "iso" in node_actions:
        a = "iso"
    elif act == "call" and "limp" in node_actions:
        a = "limp"
    else:
        a = PRE_SYN.get(act.split()[0], act.split()[0])
    if a not in node_actions:
        raise QueryError(f"'{tok}': akcji '{a}' nie ma w węźle (dostępne: {node_actions})")
    return who, a


def walk_preflop(depth, tokens):
    n = H.build_tree(depth, H.TreeConfig(), equity(), H.CheckdownLeaf())
    for tok in tokens:
        if n.actor is None:
            raise QueryError(f"'{tok}': rozdanie preflop już się skończyło ({n.id})")
        who, a = parse_pre_token(tok, n.actions)
        if who != ("SB" if n.actor == 0 else "BB"):
            raise QueryError(f"'{tok}': teraz decyduje {'SB' if n.actor == 0 else 'BB'}")
        n = n.children[n.actions.index(a)]
    return n


POST_RE = re.compile(
    r"^(SB|BB)\s+(check|bet|raise|call|fold|allin|all-in|jam|shove)\s*([\d.,]+%?)?\s*(bb)?$", re.I
)


def parse_post(tok):
    m = POST_RE.match(tok.strip())
    if not m:
        raise QueryError(
            f"akcja postflop '{tok}': oczekiwano np. 'BB check', 'SB bet 1', 'BB raise 3', 'SB "
            "call'"
        )
    kind = m.group(2).lower()
    kind = "allin" if kind in ("all-in", "jam", "shove") else kind
    return m.group(1).upper(), kind, m.group(3)


def act_kind(name):
    m = re.match(r"(\w+)(?:\((\d+)\))?", name)
    return m.group(1).lower(), int(m.group(2)) if m.group(2) else None


def match_action(actions, kind, amount, pot_now):
    """Akcja drzewa najbliższa akcji użytkownika (kwota w bb albo % puli)."""
    kinds = [act_kind(a) for a in actions]
    if kind in ("check", "call", "fold", "allin"):
        for i, (k, _) in enumerate(kinds):
            if k == kind:
                return i
        raise QueryError(f"akcji '{kind}' nie ma w węźle (dostępne: {actions})")
    cand = [i for i, (k, _) in enumerate(kinds) if k in ("bet", "raise", "allin")]
    if not cand:
        raise QueryError(f"w węźle nie ma betu/raise'u (dostępne: {actions})")
    if amount is None:
        non_allin = [i for i in cand if kinds[i][0] != "allin"]
        return (non_allin or cand)[0]
    chips = (
        float(amount[:-1]) / 100 * pot_now
        if amount.endswith("%")
        else float(amount.replace(",", ".")) * cards.BB_CHIPS
    )
    return min(cand, key=lambda i: abs(kinds[i][1] - chips))


def fmt_action(name):
    k, amt = act_kind(name)
    return f"{k} {amt / cards.BB_CHIPS:g}" if amt is not None else k


def solve_street(board, pot, stack, sb, bb, tree, target):
    kw = dict(
        board=board,
        pot_bb=pot,
        stack_bb=stack,
        range_oop=bb,
        range_ip=sb,
        tree=tree,
        target_pct=target,
        max_iter=1000,
        node_depth=NODE_DEPTH[len(board) // 2],
        node_combos=True,
        max_mem_gb=9.0,
    )
    p = CACHE / (hashlib.sha1(solver.job_text(**kw).encode()).hexdigest()[:20] + ".json")
    t = time.perf_counter()
    if p.exists():
        res = json.loads(p.read_text())
        return res, True, time.perf_counter() - t
    srv = _STATE.get("server")
    res = srv.query(**kw) if srv else solver.solve(threads=_STATE.get("threads", 4), **kw)
    if not res.get("ok"):
        raise QueryError(res.get("error"))
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res))
    return res, False, time.perf_counter() - t


def postflop(depth, leaf, streets, board, hand, targets):
    pr = preflop_result(depth)
    lf = next(x for x in pr["leaves"] if x["node"] == leaf)
    sb = cards.class_to_combo(np.maximum(lf["range_sb"], FLOOR))
    bb = cards.class_to_combo(np.maximum(lf["range_bb"], FLOOR))
    pot, stack = lf["pot"], depth - lf["pot"] / 2
    tree = auto_tree(stack / pot)
    nb = len(board) // 2
    if len(streets) > nb - 2:
        raise QueryError(f"linia ma {len(streets)} ulic postflop, a board {nb} kart")
    while len(streets) < nb - 2:
        streets.append([])
    info = dict(leaf=leaf, tree=tree, freq_sb=lf["freq_sb"], freq_bb=lf["freq_bb"], streets=[])
    for si, toks in enumerate(streets):
        b = board[: 2 * (3 + si)]
        last = si == len(streets) - 1
        res, hit, dt = solve_street(b, pot, stack, sb, bb, tree, targets[3 + si])
        info["streets"].append(
            dict(
                board=b,
                pot=pot,
                stack=stack,
                cached=hit,
                seconds=dt,
                solve_s=res["solve_s"],
                iters=res["iters"],
                expl_pct=res["expl_pct"],
            )
        )
        nodes = {n["path"]: n for n in res["nodes"]}
        path, pot_now, closed = [], pot * cards.BB_CHIPS, None
        for ti, tok in enumerate(toks):
            key = ",".join(map(str, path))
            if key not in nodes:
                raise QueryError(f"'{tok}': węzeł poza eksportem solve'u (za długa linia na ulicy)")
            n = nodes[key]
            who, kind, amount = parse_post(tok)
            actor = "BB" if n["player"] == 0 else "SB"
            if who != actor:
                raise QueryError(f"'{tok}': teraz decyduje {actor}")
            i = match_action(n["actions"], kind, amount, pot_now + sum(n["bets"]))
            st = np.array(n["strategy"][i])
            if n["player"] == 0:
                bb = bb * st
            else:
                sb = sb * st
            path.append(i)
            k_ = act_kind(n["actions"][i])[0]
            if k_ == "fold":
                raise QueryError("fold kończy rozdanie")
            if k_ == "call" or (k_ == "check" and len(path) >= 2):
                if ti != len(toks) - 1:
                    raise QueryError(f"akcje po zamknięciu ulicy: {toks[ti + 1 :]}")
                closed = n["bets"]
        if sb.sum() <= 0 or bb.sum() <= 0:
            raise QueryError("zakres zerowy po tej linii (solver nie gra jej żadną ręką)")
        if not last:
            if closed is None:
                raise QueryError(
                    f"ulica {si + 1} postflop nie jest zamknięta (oczekiwano check-check albo call)"
                )
            called = max(closed)
            pot, stack = pot + 2 * called / cards.BB_CHIPS, stack - called / cards.BB_CHIPS
            sb, bb = np.where(sb < 1e-5, 0.0, sb), np.where(bb < 1e-5, 0.0, bb)
            if stack <= 1e-9:
                raise QueryError("all-in: dalej nie ma decyzji")
            continue
        if closed is not None:
            raise QueryError("ulica zamknięta: dodaj kartę następnej ulicy do --board")
        if last:
            key = ",".join(map(str, path))
            if key not in nodes:
                raise QueryError("węzeł nie jest decyzją (koniec ulicy) albo poza eksportem")
            n = nodes[key]
            actor = "BB" if n["player"] == 0 else "SB"
            c1, c2 = cards.card_id(hand[:2]), cards.card_id(hand[2:4])
            if {c1, c2} & set(cards.board_ids(b)):
                raise QueryError(f"ręka {hand} koliduje z boardem {b}")
            ci = cards.pair_index(c1, c2)
            w = np.array(res["players"][n["player"]]["weight"])
            strat = np.array(n["strategy"])
            evs = np.array(n["action_ev"]) / cards.BB_CHIPS
            reach = (bb if n["player"] == 0 else sb)[ci]
            if reach <= 0:
                raise QueryError(
                    f"{hand}: ręka nie dochodzi do tego węzła ({actor} nie gra jej tą linią)"
                )
            cls = cards.COMBO_CLASS
            mask = cls == cls[ci]
            wr = (bb if n["player"] == 0 else sb) * cards.board_mask(b)
            cls_mix = (strat[:, mask] * wr[mask]).sum(1) / max(wr[mask].sum(), 1e-12)
            ev_hand = float((strat[:, ci] * evs[:, ci]).sum())
            info.update(
                street=["flop", "turn", "river"][si],
                actor=actor,
                actions=[fmt_action(a) for a in n["actions"]],
                hand_strategy=strat[:, ci].tolist(),
                hand_action_ev=evs[:, ci].tolist(),
                class_strategy=cls_mix.tolist(),
                range_freq=n["freq"],
                hand_ev_street=ev_hand,
                hand_ev_net=ev_hand - pot / 2,
                pot_now=(pot_now + sum(n["bets"])) / cards.BB_CHIPS,
                hand_reach=float(reach),
                hand_weight_solver=float(w[ci]),
                hero_class=H.CLASSES[cls[ci]],
            )
    return info


def norm_class(hand: str) -> str:
    hand = hand.strip()
    if re.fullmatch(r"[2-9TJQKA][cdhs][2-9TJQKA][cdhs]", hand, re.I):
        r1, s1, r2, s2 = hand[0].upper(), hand[1], hand[2].upper(), hand[3]
        hi, lo = sorted([r1, r2], key=H.RANKS.index)
        return hi + lo if hi == lo else hi + lo + ("s" if s1 == s2 else "o")
    hand = hand[:2].upper() + hand[2:].lower()
    if hand in H.INDEX:
        return hand
    if len(hand) == 2 and hand[0] != hand[1]:
        raise QueryError(f"'{hand}': podaj s/o (np. {hand}s)")
    hi, lo = sorted(hand[:2], key=H.RANKS.index)
    c = hi + lo + hand[2:]
    if c in H.INDEX:
        return c
    raise QueryError(f"nieznana ręka '{hand}'")


def query(depth: float, line: str, board: str | None, hand: str, targets=None) -> dict:
    t0 = time.perf_counter()
    targets = {**TARGETS, **(targets or {})}
    segs = [s for s in re.split(r"[;|]", line or "")]
    pre = [t for t in segs[0].split(",") if t.strip()] if segs else []
    streets = [[t for t in s.split(",") if t.strip()] for s in segs[1:]]
    node = walk_preflop(depth, pre)
    board = (board or "").replace(" ", "")
    out = dict(depth=depth, line=line, board=board or None, hand=hand)
    if not board:
        if streets:
            raise QueryError("akcje postflop bez --board")
        if node.actor is None:
            raise QueryError(
                f"linia kończy się poza decyzją preflop ({node.id}: {node.kind}); podaj --board "
                "dla postflopu"
            )
        cls = norm_class(hand)
        strat = strategy_at(depth, node.id, cls)
        evs, reach_opp = preflop_action_ev(depth, node.id, cls)
        pr = preflop_result(depth)
        out.update(
            street="preflop",
            node=node.id,
            actor="SB" if node.actor == 0 else "BB",
            hero_class=cls,
            actions=list(strat),
            hand_strategy=list(strat.values()),
            hand_action_ev=[evs[a] for a in strat],
            hand_ev=float(sum(strat[a] * evs[a] for a in strat)),
            opp_reach=reach_opp,
            preflop_live=pr["live"],
            near=pr.get("near"),
        )
    else:
        if node.id not in LEAF_NODES:
            raise QueryError(
                f"linia preflop kończy się w '{node.id}', a nie w puli postflop "
                f"{sorted(LEAF_NODES)}"
            )
        if len(board) not in (6, 8, 10):
            raise QueryError("board: 3, 4 albo 5 kart")
        if not re.fullmatch(r"[2-9TJQKA][cdhs][2-9TJQKA][cdhs]", hand, re.I):
            raise QueryError("postflop: podaj konkretną rękę, np. AhTd")
        hand = hand[0].upper() + hand[1].lower() + hand[2].upper() + hand[3].lower()
        board = "".join(board[i].upper() + board[i + 1].lower() for i in range(0, len(board), 2))
        out.update(postflop(depth, node.id, streets, board, hand, targets))
    out["latency_s"] = time.perf_counter() - t0
    return out


def render(o: dict) -> str:
    L = [
        f"HU Spin chipEV | {o['depth']:g} bb | linia: {o['line'] or '(SB first-in)'} | "
        f"{('board ' + o['board'] + ' | ') if o.get('board') else ''}ręka {o['actor']}: "
        f"{o['hand']} ({o['hero_class']})"
    ]
    if o["street"] == "preflop":
        L.append(
            f"preflop, węzeł '{o['node']}'"
            + (
                f" (solve na żywo, model liścia z {o['near']:g} bb)"
                if o.get("preflop_live")
                else " (book punktu stałego)"
            )
        )
        L.append(f"  {'akcja':<8}{'ręka':>7}{'EV akcji (bb)':>15}")
        for a, p, e in zip(o["actions"], o["hand_strategy"], o["hand_action_ev"], strict=True):
            L.append(f"  {a:<8}{100 * p:>6.1f}%{e:>+15.3f}")
        L.append(f"EV ręki w węźle: {o['hand_ev']:+.3f} bb (zmiana stacku od początku rozdania)")
    else:
        L.append(
            f"liść {o['leaf']} (zakresy: SB {100 * o['freq_sb']:.0f}% / BB "
            f"{100 * o['freq_bb']:.0f}% kombinacji), drzewo {o['tree']}"
        )
        for x in o["streets"]:
            L.append(
                f"  {len(x['board']) // 2} karty {x['board']}: pula {x['pot']:.2f} bb, stack "
                f"{x['stack']:.2f} bb, "
                f"{'cache' if x['cached'] else 'solve na żywo'} {x['seconds']:.2f} s (solver "
                f"{x['solve_s']:.1f} s, "
                f"{x['iters']} it., expl {x['expl_pct']:.2f}% puli)"
            )
        L.append(f"{o['street']}: decyduje {o['actor']}, pula teraz {o['pot_now']:.2f} bb")
        L.append(f"  {'akcja':<10}{'ręka':>7}{'klasa':>7}{'zakres':>8}{'EV akcji (bb)':>15}")
        for a, p, c, f, e in zip(
            o["actions"],
            o["hand_strategy"],
            o["class_strategy"],
            o["range_freq"],
            o["hand_action_ev"],
            strict=True,
        ):
            L.append(f"  {a:<10}{100 * p:>6.1f}%{100 * c:>6.1f}%{100 * f:>7.1f}%{e:>+15.3f}")
        L.append(
            f"EV ręki: {o['hand_ev_street']:+.3f} bb (udział w puli z początku ulicy minus dalsze "
            "wpłaty), "
            f"netto od początku rozdania {o['hand_ev_net']:+.3f} bb"
        )
        if o["hand_reach"] < 0.05:
            L.append(
                f"UWAGA: ręka ma zasięg {o['hand_reach']:.3f} (poza zakresem tej linii): strategia "
                "~ best response."
            )
    L.append(f"czas zapytania {1000 * o['latency_s']:.1f} ms")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--depth",
        type=float,
        required=True,
        help="stack efektywny w bb (siatka: book; inne: solve preflop ~1-3 s)",
    )
    ap.add_argument(
        "--line", default="", help="np. 'SB limp, BB check; BB check, SB bet 1, BB call'"
    )
    ap.add_argument("--board", default=None)
    ap.add_argument("--hand", required=True)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument(
        "--target",
        type=float,
        default=None,
        help="cel zbieżności postflop (% puli) dla bieżącej ulicy",
    )
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    _STATE["threads"] = a.threads
    tg = {}
    if a.target is not None and a.board:
        tg = {len(a.board.replace(" ", "")) // 2: a.target}
    try:
        o = query(a.depth, a.line, a.board, a.hand, tg)
    except QueryError as e:
        print(f"błąd: {e}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(o, default=float) if a.json else render(o))


if __name__ == "__main__":
    main()

"""Herding (jak hupf_py.flops.herding_sample), ale z cechą 'sparowany' (para lub trips) zamiast
one-hot trips/para/brak i z wagą bloku parowania 3: przy K = 4 i 12 oryginał nie daje żadnego
flopu sparowanego (populacja 17%), przy K = 16 jeden, a one-hot z trips i wagą 3 wymusza flop
trips (populacja 0,24%) w pierwszej dwunastce.

Import po `fp` (fp dokłada tools/hu_gto/postflop do sys.path dla hupf_py)."""

import numpy as np
from hupf_py import flops
from hupf_py.cards import RANKS


def feats(f):
    rs = [RANKS.index(f[i]) for i in (0, 2, 4)]
    ranks = sorted(set(rs))
    nsuit = len({f[1], f[3], f[5]})
    pres = np.zeros(13)
    pres[ranks] = 1.0
    high = np.zeros(13)
    high[max(rs)] = 1.0
    co = np.outer(pres, pres)[np.triu_indices(13, 1)]
    return np.concatenate([pres, high, [nsuit == 1, nsuit == 2, nsuit == 3], [len(ranks) < 3], co])


def _scaled(bw):
    fl, mult = flops.canonical_flops()
    names = [flops.flop_str(f) for f in fl]
    X = np.array([feats(n) for n in names])
    mu = (X * mult[:, None]).sum(0) / mult.sum()
    scale = (
        1.0
        / np.sqrt(np.maximum(mu * (1 - mu), 1e-4))
        * np.repeat(np.asarray(bw), (13, 13, 3, 1, 78))
    )
    return names, X * scale, mu * scale


def herd_blocks(sizes, bw=(1.0, 1.0, 1.0, 3.0, 1.0)):
    """Rozłączne bloki flopów: każdy blok to osobny herding do średniej cech CAŁEJ populacji, bez
    flopów z bloków wcześniejszych (wagi 1/rozmiar). Dlaczego bez powtórzeń: zwykły herding
    powtarza flopy tęczowe (400 wyborów = 326 różnych flopów), a blok ma być held-out wobec
    poprzednich. Bloki są deterministyczne i nie zależą od liczby bloków dalszych."""
    names, Xs, mus = _scaled(bw)
    used = np.zeros(len(names), bool)
    out = []
    for k in sizes:
        w = mus.copy()
        block = []
        for _ in range(k):
            j = int(np.argmax(np.where(used, -np.inf, Xs @ w)))
            used[j] = True
            w += mus - Xs[j]
            block.append((names[j], 1.0 / k))
        out.append(block)
    return out


def herd(k, bw=(1.0, 1.0, 1.0, 3.0, 1.0)):
    names, Xs, mus = _scaled(bw)
    w = mus.copy()
    picks = {}
    for _ in range(k):
        j = int(np.argmax(Xs @ w))
        w += mus - Xs[j]
        picks[names[j]] = picks.get(names[j], 0.0) + 1.0 / k
    return list(picks.items())

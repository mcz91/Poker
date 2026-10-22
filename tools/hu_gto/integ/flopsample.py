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


def herd(k, bw=(1.0, 1.0, 1.0, 3.0, 1.0)):
    fl, mult = flops.canonical_flops()
    names = [flops.flop_str(f) for f in fl]
    X = np.array([feats(n) for n in names])
    mu = (X * mult[:, None]).sum(0) / mult.sum()
    scale = (
        1.0
        / np.sqrt(np.maximum(mu * (1 - mu), 1e-4))
        * np.repeat(np.asarray(bw), (13, 13, 3, 1, 78))
    )
    Xs, mus = X * scale, mu * scale
    w = mus.copy()
    picks = {}
    for _ in range(k):
        j = int(np.argmax(Xs @ w))
        w += mus - Xs[j]
        picks[names[j]] = picks.get(names[j], 0.0) + 1.0 / k
    return list(picks.items())

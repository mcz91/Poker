"""Macierz equity all-in preflop 169x169 przez eval7 Monte Carlo.

E[i, j] = udział puli klasy i przeciw klasie j (wygrana + pół splitu), uśredniony
po rozłącznych parach kombinacji. Wystarczy jedna reprezentatywna kombinacja
klasy i: zbiór kombinacji klasy j jest niezmienniczy względem permutacji kolorów,
więc każda kombinacja klasy i daje to samo equity i tę samą liczbę rozłącznych par.
Liczony górny trójkąt; E[j, i] = 1 - E[i, j] (dokładnie, bo split liczony po połowie),
przekątna 0,5 z symetrii.

Użycie: python gen_equity.py ITERS WORKERS OUT.npy

Ziarna nie ma: eval7 0.1.11 seeduje swój xorshift czasem przy imporcie w każdym procesie
puli, więc dwa przebiegi dają macierze różne w granicach błędu MC, nie bitowo równe.
"""

import sys
import time
from multiprocessing import Pool

import eval7
import numpy as np

RANKS = "AKQJT98765432"


def classes():
    out = []
    for a, hi in enumerate(RANKS):
        for lo in RANKS[a:]:
            if hi == lo:
                out.append(hi + lo)
            else:
                out.append(hi + lo + "s")
                out.append(hi + lo + "o")
    return out


CLASSES = classes()


def representative(cls):
    if len(cls) == 2:
        return [eval7.Card(cls[0] + "c"), eval7.Card(cls[1] + "d")]
    if cls[2] == "s":
        return [eval7.Card(cls[0] + "c"), eval7.Card(cls[1] + "c")]
    return [eval7.Card(cls[0] + "c"), eval7.Card(cls[1] + "d")]


def row(args):
    i, iters = args
    hero = representative(CLASSES[i])
    out = np.full(len(CLASSES), np.nan)
    for j in range(i + 1, len(CLASSES)):
        out[j] = eval7.py_hand_vs_range_monte_carlo(hero, eval7.HandRange(CLASSES[j]), [], iters)
    return i, out


def main():
    iters = int(sys.argv[1])
    workers = int(sys.argv[2])
    path = sys.argv[3]
    n = len(CLASSES)
    E = np.full((n, n), 0.5)
    t0 = time.time()
    with Pool(workers) as pool:
        for i, out in pool.imap_unordered(row, [(i, iters) for i in range(n)]):
            E[i, i + 1 :] = out[i + 1 :]
            E[i + 1 :, i] = 1.0 - out[i + 1 :]
    np.save(path, E)
    print(f"iters/pair={iters} workers={workers} time={time.time() - t0:.1f}s -> {path}")


if __name__ == "__main__":
    main()

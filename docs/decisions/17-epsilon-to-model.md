# 17 — ε≈0 nie znaczy, że umiemy grać

POKER-36 porównał 0.0006 BI do Ganzfrieda. To było za dużo.

Self-ε mierzy Nash **tego** drzewa (bez blockerów, 3-way z pary).
Dwie implementacje mogą mieć ε≈0 i inne zakresy: Python + macierz
UTG ≈14%, live vs-field UTG ≈27%. Oba „Nash”. Żadne nie jest
pokerem na 25 bb (tam jest open 2.2x).

Mianownik: always-jam w tym samym modelu wycieka ≈0.18 BI.
16 iteracji jest ~300× ciaśniejsze od always-jam **w modelu**,
nie względem HRC/ICMIZER i nie względem field $1.

Lab pokazuje live % i offline % obok siebie. Odznaka: self-ε · this
model. `strategy_table` nietknięty.

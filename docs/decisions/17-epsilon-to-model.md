# 17 — ε≈0 nie znaczy, że umiemy grać

POKER-36 porównał 0.0006 BI do Ganzfrieda. To było za dużo.

Self-ε mierzy Nash **tego** drzewa (bez blockerów, 3-way z pary).
Dwie implementacje mogą mieć ε≈0 i inne zakresy: Python + macierz
UTG ≈14%, live vs-field UTG ≈27%. Oba „Nash”. Żadne nie jest
pokerem na 25 bb (tam jest open 2.2x).

**KOREKTA (POKER-84):** „3-way z pary” — zwycięzca 3-way z iloczynu
equity par znormalizowanego, drugie miejsce z equity pary pozostałych
dwóch (side pot wygrywa lepsza ręka spośród uprawnionych); ε liczy
funkcja wartości per ręka decydenta, ta sama co best response
(decyzja 16, KOREKTA (POKER-84)).

Mianownik: always-jam w tym samym modelu wycieka ≈0.18 BI.
16 iteracji jest ~300× ciaśniejsze od always-jam **w modelu**,
nie względem HRC/ICMIZER i nie względem field $1.

**KOREKTA (POKER-84):** po zmianie funkcji ε (decyzja 16) always-jam
wycieka 0,147 BI (0,14671; przed POKER-84 0,16818), a 16 iteracji
jest 237× ciaśniejsze (236,7×; przed 263,7×). Komenda: `python -c
"from poker.jamfold import N_HANDS, N_NODES, _exploitability,
_payoffs, solve; from poker.spin import PAYOUTS; p =
PAYOUTS['3x'].prizes; junk = max(_exploitability([[1.0] * N_HANDS
for _ in range(N_NODES)], _payoffs((50, 50, 50), p, 1, 1, 2))); nash
= solve((50, 50, 50), p, button=1, iterations=16).exploitability;
print(junk, junk / nash)"`.

Lab pokazuje live % i offline % obok siebie. Odznaka: self-ε · this
model. `strategy_table` nietknięty.

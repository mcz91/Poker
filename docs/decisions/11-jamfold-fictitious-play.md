# 11 — Jam/fold 3-max: fictitious play, jeden stan

POKER-30 dał $EV. Operator kazał iść w Spin dalej, nie wracać do HU.

## Decyzja

1. **Gra wewnętrzna Ganzfried & Sandholm (AAMAS 2008):** Nash
   jam/fold na jednym wektorze stacków. Payoff = ICM (WTA jako
   szczególny przypadek). Bez value iteration po turnieju — to
   następny kontrakt.
2. **Solver: fictitious play z wagą liniową t.** To ta sama idea
   uśredniania co Linear CFR (POKER-29), nie nowy wynalazek.
   Brown 1951 / papier Ganzfrieda na grze wewnętrznej.
3. **Equity HU z macierzy POKER-12.** 3-way: iloczyn parami,
   znormalizowany. Blockery wyłączone (jawne).
4. **Nie otwiera INV-P5.** Drzewo to jam/fold, nie NL. `HeadsUpHand`
   i `strategy_table.py` nietknięte.
5. **HRC/ICMIZER** nadal tylko sędzia offline.

## Skutek

`poker.jamfold.solve` na 25 bb WTA daje UTG ≈16% jam, call 7–8%;
10× zaciska call. Lab EXPLO pokazuje te zakresy na żywo.

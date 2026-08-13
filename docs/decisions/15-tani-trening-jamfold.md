# 15 — Tani trening pod $1 to offline jam/fold, nie więcej cash-MCCFR

Boty przy stole nie grały „naszej” strategii. Grały 16 iteracji
fictitious play w przeglądarce (macierz vs-field) albo próg equity
0.58. Artefakt `strategy_table` to HU cash Linear MCCFR: **−329 BB/100**
vs `rule` (20 par, decyzja 07/09). To jest przegrywająca strategia
w złej grze.

Metryka, którą obraliśmy (decyzja 04/07): **BB/100** na lustrzanych
rozdańiach HU. Do Spina $1 jest zła jednostka. Spin liczy się w
**ROI / $EV turnieju** i w exploitability drzewa jam/fold (BI).

## Decyzja

1. **Nie trenujemy dalej cash-MCCFR**, dopóki krzywa POKER-27 nie
   pokaże, że skala kupuje jakość. Decyzja 09 pkt 4 już to przewidziała:
   płaska krzywa → powrót do push/fold, nie większy artefakt.
2. **Tani trening = fictitious play offline** na zegarze Spin
   (Ganzfried & Sandholm, AAMAS 2008): prawdziwa macierz POKER-12,
   24 iteracje z wagą t, stany = poziomy blindów × 3×/10×.
   Koszt: minuty CPU, nie GPU. Artefakt ~35 kB, nie `strategy_table`.
3. **Bar $1.** Jam/fold Nash na zegarze wystarcza, żeby nie być rybą
   od ~12 bb w dół (większość Spina). 25 bb z otwarciem 2.2x to osobny,
   droższy plaster. Nie twierdzimy, że to crusher $1.
4. **Metryka Spina:** (a) exploitability vs BR na drzewie jam/fold
   w BI; (b) ROI vs skryptowany fish. Nie BB/100 z cash HU.
5. **`strategy_table.py` nietknięty.**

## Źródła

- Ganzfried & Sandholm, AAMAS 2008 — jam/fold 3-max, FP + VI, ε≈0.001
  po ~100 iteracjach wewnętrznych; exploitability < 0.05% puli.
- Ganzfried & Sandholm, IJCAI 2009 — rozszerzenie na gry stochastyczne.
- Decyzja 09 pkt 4; decyzja 04 (odrzucony push/fold — tu wraca jako
  solver, nie jako ML).

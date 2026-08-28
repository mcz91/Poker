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

## Pomiar eskalacji blindów (POKER-45)

Po naprawie rozliczeń żetonów (POKER-45) jam UTG przy stackach 50
rośnie z blindami monotonicznie przez cały zegar (%, 3×, 12 iteracji;
komenda: `python -c "from poker.jamfold import solve; from poker.spin
import LEVELS, PAYOUTS; print([solve((50,50,50), PAYOUTS['3x'].prizes,
button=1, iterations=12, sb=sb, bb_amt=bb).utg_jam_pct for sb, bb in
LEVELS])"`):

1/2 14.1 → 2/4 27.3 → 3/6 35.2 → 4/8 37.5 → 5/10 38.7 → 8/16 40.0
→ 10/20 40.6.

Odwrócenie monotoniczności na 8/16 i 10/20 raportowane w audycie
2026-08-28 (30.3 → 23.8 → 20.1) odtwarza się wyłącznie na kodzie
sprzed naprawy `_allin_two` — było artefaktem gubienia żetonów blindów,
nie własnością modelu; monotoniczność przybija test
`test_wyzszy_blind_szerzej_jamuje_caly_zegar`.

Model pozostaje jednokrokowy (bez wartości przyszłych rąk): wiersze
eksportu 8/16 i 10/20 (BB call 88.9% / 100.0% przy 12 iteracjach) to
polityka pojedynczej ręki przy 2.5–3 bb efektywnych — pełną
wiarygodność da dopiero zewnętrzna pętla VI (plan decyzji 18).

## Źródła

- Ganzfried & Sandholm, AAMAS 2008 — jam/fold 3-max, FP + VI, ε≈0.001
  po ~100 iteracjach wewnętrznych; exploitability < 0.05% puli.
- Ganzfried & Sandholm, IJCAI 2009 — rozszerzenie na gry stochastyczne.
- Decyzja 09 pkt 4; decyzja 04 (odrzucony push/fold — tu wraca jako
  solver, nie jako ML).

# 12 — Jeden backup zewnętrzny, nie pełna siatka

POKER-31 dał Nash jam/fold na jednym stanie z terminalem ICM.
Zewnętrzna pętla Ganzfrieda (AAMAS 2008) to value iteration po
wektorach stacków. Pełna siatka 3-max (sumy 150) to ~90 stanów ×
koszt fictitious play — za drogo na bramkę i na lab.

## Decyzja

1. **Pierwszy iterate:** V¹(s) = E[ICM(s′) | Nash w s]. To jeden
   backup. Cash-out to V⁰ = ICM(s).
2. **Na WTA V¹ = V⁰** (żetony są martyngałem, pula liniowa) — z
   błędem fictitious play. Na 10× przy nierównych stackach V¹ ≠ ICM.

   **KOREKTA (POKER-84):** pod WTA V¹ ≠ V⁰, a różnica nie jest błędem
   fictitious play. Wypłata WTA jest liniowa w żetonach, więc
   V¹_i − V⁰_i = Σnagród·E[Δżetonów_i]/Σstacków z dokładnością
   maszynową: to chip-EV pozycji w jednej ręce przy stałym guziku,
   które nie maleje ze zbieżnością. (70, 50, 30), 3×, guzik 1:
   V¹ − V⁰ = (+5,609e−3; −4,951e−3; −6,587e−4) BI przy 16 iteracjach
   i (+5,373e−3; −4,818e−3; −5,557e−4) przy 64, gdy exploitability
   spada 3,961e−4 → 2,847e−5 (13,9×). Komenda: `python -c "from
   poker.jamfold import solve; from poker.spin import PAYOUTS; rs =
   [solve((70, 50, 30), PAYOUTS['3x'].prizes, button=1, iterations=n)
   for n in (16, 64)]; print([([v - c for v, c in zip(r.values,
   r.icm)], r.exploitability) for r in rs])"`. Tożsamość i te pasma
   przybija test `test_wta_v1_minus_v0_to_chip_ev_pozycji`.
3. **Nie ruszamy pełnej siatki ani drugiego iterate** (Nash w każdym
   następcy). To osobny kontrakt, gdy operator chce zegar blindów
   albo głębsze V.
4. **INV-P5 i strategy_table nietknięte.**

## Skutek

Lab pokazuje cash-out vs after-one-hand. 3×: tożsamość. 10× Short
8 bb: krótki stack zyskuje na zagraniu ręki (~+0.05 BI).

**KOREKTA (POKER-84):** „3×: tożsamość” — nieprawda (pkt 2, KOREKTA):
(50, 50, 50), 3×, guzik 1, 16 iteracji daje V¹ − V⁰ = (+4,821e−3;
−9,374e−3; +4,553e−3) BI, bitowo tak samo jak przed POKER-84; komenda:
`python -c "from poker.jamfold import solve; from poker.spin import
PAYOUTS; r = solve((50, 50, 50), PAYOUTS['3x'].prizes, button=1,
iterations=16); print([v - c for v, c in zip(r.values, r.icm)])"`.
Zamiast „~+0.05 BI” — zmierzone +0,0366 (+0,036650): V¹ − V⁰ UTG
(miejsce 0) dla (16, 50, 84), 10×, guzik 1, 16 iteracji; komenda:
`python -c "from poker.jamfold import solve; from poker.spin import
PAYOUTS; r = solve((16, 50, 84), PAYOUTS['10x'].prizes, button=1,
iterations=16); print(r.values[0] - r.icm[0])"`. Wartość jest bitowo
ta sama co przed POKER-84: w tym stanie 3-way nie tworzy side potu,
a values liczy łączna wycena zakres–zakres.

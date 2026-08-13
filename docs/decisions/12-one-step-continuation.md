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
3. **Nie ruszamy pełnej siatki ani drugiego iterate** (Nash w każdym
   następcy). To osobny kontrakt, gdy operator chce zegar blindów
   albo głębsze V.
4. **INV-P5 i strategy_table nietknięte.**

## Skutek

Lab pokazuje cash-out vs after-one-hand. 3×: tożsamość. 10× Short
8 bb: krótki stack zyskuje na zagraniu ręki (~+0.05 BI).

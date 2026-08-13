# 13 — Zegar Spin: głębokość, nie eskalacja w trakcie

Spin na Stars startuje 25 bb i ściska się, bo rosną blindy.
W naszym modelu blinds zostają 1/2, a żetony maleją: 50 → 12.
ICM na równych stackach się nie zmienia; zmienia się stosunek
stack/bb, więc Nash jam/fold.

## Decyzja

1. **DEPTHS** = 25 / 15 / 10 / 6 bb, zawsze equal. To nie jest
   zegar ręka-po-ręce (brak licznika rąk, brak ante).
2. **Krótki stack jams szerzej.** Invariant pod testem: UTG 6 bb
   > UTG 25 bb o ≥5 pp na WTA.
3. **Krzywa w labie** liczy te cztery stany osobno. Nie rusza
   INV-P5 ani `strategy_table`.

## Skutek

Widać, po co Spin jest jam/fold: im płycej, tym więcej rąk idzie
all-in. 10× nadal zaciska call względem WTA.

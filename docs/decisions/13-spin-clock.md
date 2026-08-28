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

## Pomiar (POKER-45, po naprawie rozliczeń żetonów)

Krzywa 3× WTA, button=1, 12 iteracji; komenda:
`python -c "from poker.jamfold import jam_vs_depth; from poker.spin
import PAYOUTS; print(jam_vs_depth(PAYOUTS['3x'].prizes, button=1,
iterations=12))"`.

| bb eff | UTG jam % | BTN call % | BB call % |
|---|---|---|---|
| 25 | 14.1 | 9.0 | 10.0 |
| 15 | 24.0 | 11.7 | 14.1 |
| 10 | 32.2 | 16.2 | 21.6 |
| 6 | 37.9 | 23.9 | 33.9 |

Wcześniejsza krzywa 14/23/29/31 była liczona na kodzie gubiącym żetony
blindów w stanach terminalnych (`_allin_two` przed POKER-45).

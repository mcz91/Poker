# 14 — Eskalacja w trakcie, stół jam/fold

POKER-33 pokazał głębokość jako osobne stany. Spin na stole wymaga
zegara: blinds rosną, żetony zostają.

## Decyzja

1. **3 ręce na poziom.** `LEVELS` = 1/2 → 2/4 → 3/6 → 4/8 → 5/10 →
   8/16 → 10/20. To nie jest zegar Stars co do minuty — to pierwszy
   grywalny squeeze.
2. **`post_blinds(..., sb, bb)`** z domyślnymi 1/2. Istniejące testy
   25 bb bez zmian.
3. **Stół to jam/fold 3-max.** Nie otwieramy INV-P5. Showdown na
   prawdziwej planszy 5 kart. Boty biorą Nash z fictitious play na
   bieżącym poziomie, albo vs-field gdy ktoś odpadł (HU).
4. **`strategy_table.py` nietknięty.**

## Skutek

Pakiet ma zegar. Lab EXPLO ma /play: siadasz, jam/fold, blinds idą
w górę. To MVP, nie pełny Spin z limpem i 3-betem.

# 19 — Push/fold dopiero przy 6–7 bb

Operator: jam/fold od 12 bb był błędem. Próg produktu: **≤ 7 bb**
efektywnych (`min(żywe stacki) / bb`).

Powyżej: open 2.2x / jam / fold. Vs open: jam lub fold (bez flata).
To zamyka drzewo bez flopu. Na 1/2 i 2/4 i 3/6 stół jest w trybie
open. Na 4/8 (6.25 bb przy 50 chipach) — jam/fold.

`JAM_FOLD_BB = 7` w `poker.spin` i EXPLO. `strategy_table` nietknięty.
INV-P5 nietknięte.

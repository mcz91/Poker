# 21 — Ciasny 3bet: spot, nie drzewo

3bet Nash drzewa bez flata jest bezużyteczny (35–100%). Polityka:

UTG open zamrożony z POKER-40. UTG kontynuuje **górnymi 55%** tego
openu. BTN/BB: jam jeśli +EV, inaczej fold.

Na 3× 25 bb: BTN 3bet = **10.4%** combo. Zakres wygenerowany z kodu
(POKER-45): pary AA–44, AKs/AKo, AQs/AQo, AJs/AJo, ATs/ATo, A9s, KQs.
10× = 7.2% (AA–77, AKs/AKo, AQs/AQo, AJs/AJo). AA jams, 72o folds.
Komenda (iteracje jak w testach: 12 dla 3×, 10 dla 10×):
`python -c "from poker.openfold import threebet; from poker.spin import
PAYOUTS; hit = threebet((50,50,50), PAYOUTS['3x'].prizes, button=1,
iterations=12); print(hit.btn_vs_open_pct)"` — lista rąk to indeksy
`hit.btn_vs_open[i] > 0.5` w `ALL_CLASSES`. Poprzednio publikowane
„9.4% (TT+, ATs+, AQo+, KQs)" nie odpowiadało kodowi.

W Play zawsze bierzemy wykres 25 bb — nie 8 bb (tam spot daje 100%).

`strategy_table` nietknięty.

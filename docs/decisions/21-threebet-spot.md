# 21 — Ciasny 3bet: spot, nie drzewo

3bet punktu stałego FP modelu (miara = 8,46e−4 sumy nagród na 3× 25 bb
przy N = 128; do POKER-73 nazywany tu „Nash”) drzewa bez flata jest
bezużyteczny (35–100%). Polityka:

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

**KOREKTA (POKER-73):** liczby wyżej policzono modelem, w którym overcall
BB wyceniano showdownem bez udziału BB, a fold BTN — equity ręki
spasowanego (finding B6 audytu 2026-09-26), przy FP uciętym na 12 i 10
iteracjach bez miary zbieżności (I-25). Liczba iteracji to teraz
N = 128 dla obu wypłat — najmniejszy punkt kontrolny krzywej 8…1024
z miarą ≤ 1e−3 sumy nagród na wszystkich poziomach eksportu
(`python tools/export_open_nash.py --curve`, 137,6 s). Wartości przy
N = 128, obok rozrzut na punktach kontrolnych [64, 128]:

- 3bet drzewa (BTN vs open): 3× 6,4 / 44,6 / 53,8% przy 25 / 12,5 /
  8,3 bb (64: 10,0 / 45,1 / 54,4%), 10× 1,2 / 5,5 / 20,4% (64: 2,5 / 8,4 /
  20,6%); miara 8,46e−4 / 8,75e−5 / 1,85e−4 (3×) i 5,12e−4 / 5,61e−4 /
  6,14e−5 (10×). Teza „bezużyteczny (35–100%)” **nie trzyma się** przy 25 bb:
  drzewo 3betuje tam 6,4% (3×) i 1,2% (10×), ciaśniej niż spot; szeroki
  3bet drzewa zostaje na 3× przy 12,5 i 8,3 bb (spot: 40,6 i 98,2%).
  Zmiana polityki spotu należy do architekta, poza POKER-73. Komenda
  i czas — KOREKTA (POKER-73) decyzji 20.
- open zamrożony to open UTG z modelu po POKER-73 przy N = 128: 3× 25 bb
  **28,9%** (64: 29,7%), 10× **30,4%** (64: 23,7%) — nie open POKER-40.
- 3× 25 bb: BTN 3bet **10,41%** (64: 10,41%) — ta sama lista rąk: AA–44,
  AKs/AKo, AQs/AQo, AJs/AJo, ATs/ATo, A9s, KQs.
- 10× 25 bb: BTN 3bet **7,54%** (64: 5,88%) — AA–77, AKs/AKo, AQs/AQo,
  AJs/AJo, ATs (przy 64: AA–88, AKs/AKo, AQs/AQo, AJs). Przed POKER-73:
  7,24%.
- AA jamuje, 72o pasuje — na obu wypłatach przy 64 i 128.
- „tam spot daje 100%” (8,3 bb, 3/6): przy 128 i przy 64 spot daje 98,2%
  na 3× i 11,6% na 10× (`--curve`, kolumna btn3betPct).

Komenda (czas ścienny: 3,2 s na 3×, 2,3 s na 10×; przy `iterations=64`
1,6 s i 1,2 s): `python -c "from poker.openfold import threebet; from
poker.preflop import ALL_CLASSES; from poker.spin import PAYOUTS; hit =
threebet((50,50,50), PAYOUTS['3x'].prizes, button=1, iterations=128);
print(hit.btn_vs_open_pct, hit.aa_jams, hit.junk_folds,
hit.utg_open_pct); print([ALL_CLASSES[i] for i in
range(len(ALL_CLASSES)) if hit.btn_vs_open[i] > 0.5])"` (10×:
`PAYOUTS['10x']`).

W Play zawsze bierzemy wykres 25 bb — nie 8 bb (tam spot daje 100%).

`strategy_table` nietknięty.

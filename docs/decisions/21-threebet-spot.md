# 21 — Ciasny 3bet: spot, nie drzewo

3bet punktu stałego FP modelu (miara = 4,80e−4 sumy nagród na 3× 25 bb
przy N = 512; do POKER-73 nazywany tu „Nash”) drzewa bez flata jest
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
N = 512 dla obu wypłat — najmniejszy punkt kontrolny krzywej 8…1024, od
którego miara jest ≤ 1e−3 sumy nagród na wszystkich poziomach eksportu we
wszystkich dalszych punktach (`python tools/export_open_nash.py --curve`,
140,5 s; reguła i dołek krzywej przy 128 — KOREKTA (POKER-73) decyzji 20).
Wartości przy N = 512, obok rozrzut na punktach kontrolnych [256, 512]:

- 3bet drzewa (BTN vs open): 3× 2,2 / 44,5 / 53,6% przy 25 / 12,5 /
  8,3 bb (256: 4,1 / 44,5 / 53,6%), 10× 0,5 / 2,0 / 20,8% (256: 0,6 / 3,7 /
  20,7%); miara 4,80e−4 / 3,41e−4 / 6,62e−5 (3×) i 1,20e−4 / 3,45e−4 /
  5,11e−6 (10×). Teza „bezużyteczny (35–100%)” **nie trzyma się** przy 25 bb:
  drzewo 3betuje tam 2,2% (3×) i 0,5% (10×), ciaśniej niż spot; szeroki
  3bet drzewa zostaje na 3× przy 12,5 i 8,3 bb (spot: 40,6 i 98,2%).
  Zmiana polityki spotu należy do architekta, poza POKER-73. Komenda
  i czas — KOREKTA (POKER-73) decyzji 20.
- open zamrożony to open UTG z modelu po POKER-73 przy N = 512: 3× 25 bb
  **33,9%** (256: 32,9%), 10× **32,7%** (256: 29,3%) — nie open POKER-40.
- 3× 25 bb: BTN 3bet **13,27%** (256: 12,07%) — lista rąk szersza niż
  wyżej: pary AA–33, AKs/AKo, AQs/AQo, AJs/AJo, ATs/ATo, A9s/A9o, A8s,
  KQs/KQo, KJs (przy 256: bez KQo i KJs). Przed POKER-73: 10,41% z listą
  wyżej.
- 10× 25 bb: BTN 3bet **8,90%** (256: 7,54%) — AA–66, AKs/AKo, AQs/AQo,
  AJs/AJo, ATs/ATo (przy 256: AA–77, AKs/AKo, AQs/AQo, AJs/AJo, ATs).
  Przed POKER-73: 7,24%.
- AA jamuje, 72o pasuje — na obu wypłatach przy 256 i 512.
- „tam spot daje 100%” (8,3 bb, 3/6): przy 512 i przy 256 spot daje 98,2%
  na 3× i 11,6% na 10× (`--curve`, kolumna btn3betPct).

Komenda (czas ścienny: 12,3 s na 3×, 10,1 s na 10×; przy `iterations=256`
5,9 s i 4,5 s): `python -c "from poker.openfold import threebet; from
poker.preflop import ALL_CLASSES; from poker.spin import PAYOUTS; hit =
threebet((50,50,50), PAYOUTS['3x'].prizes, button=1, iterations=512);
print(hit.btn_vs_open_pct, hit.aa_jams, hit.junk_folds,
hit.utg_open_pct); print([ALL_CLASSES[i] for i in
range(len(ALL_CLASSES)) if hit.btn_vs_open[i] > 0.5])"` (10×:
`PAYOUTS['10x']`).

**KOREKTA (architekt, 2026-09-27) do KOREKTY POKER-73:** „nie trzyma
się” dotyczy BTN. BB w drzewie bez flata przy 3× 25 bb 3betuje wobec
openu UTG **41,5%**, BB w spocie 14,0% (komendy — adnotacja architekta
w decyzji 20) — dla BB 3bet drzewa jest szerszy niż spotu także przy
25 bb, więc teza „drzewo bezużyteczne dla 3betu” trzyma się na BB.
Polityka spotu bez zmian.

W Play zawsze bierzemy wykres 25 bb — nie 8 bb (tam spot daje 100%).

`strategy_table` nietknięty.

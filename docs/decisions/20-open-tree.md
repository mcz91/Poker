# 20 — Drzewo open 2.2x, first-in

Powyżej 7 bb first-in to fold / open 2.2x / jam. Fictitious play,
macierz POKER-12, bez flata.

Na 3× 25 bb: UTG open ≈ 23%, overjam ≈ 1%. To jest produkt.

3bet w tym drzewie bez flata wychodzi za szeroki (artefakt: jedyna
kara to shove). Nie eksportujemy go. Vs open bot 3betuje ciasno
(vs-field), nie 3betem punktu stałego FP modelu (miara = 4,80e−4 sumy
nagród na 3× 25 bb przy N = 512; do POKER-73 nazywany tu „Nash 3bet”).

**KOREKTA (POKER-73):** liczby wyżej pochodziły z modelu, w którym overcall
BB wyceniano showdownem bez udziału BB, a fold BTN — equity ręki
spasowanego (finding B6 audytu 2026-09-26), i z FP uciętego na 16
iteracjach bez miary zbieżności (I-25). Po poprawce eksport liczy
N = 512 — najmniejszy punkt kontrolny krzywej 8…1024, od którego miara
zbieżności (zysk z best response per punkt decyzji, w ułamku sumy nagród)
jest ≤ 1e−3 na wszystkich sześciu poziomach eksportu we wszystkich
dalszych punktach kontrolnych. Miara FP nie maleje monotonicznie: przy
N = 128 wszystkie poziomy są w tolerancji, ale przy 256 3× 12,5 bb ma
1,26e−3, więc pierwszy punkt w tolerancji był dołkiem krzywej. Wartości
przy N = 512, obok rozrzut na punktach kontrolnych [256, 512]:

- 3× 25 bb: UTG open **33,9%** (256: 32,9%), overjam **0,0%** (256: 0,0%);
  miara 4,80e−4. Wcześniej na krzywej open 29,7 / 28,9% (64 / 128), dalej
  32,5% (1024) — miara w tolerancji nie oznacza liczby stojącej w miejscu.
- 3bet drzewa (BTN vs open): 3× 25 bb **2,2%** (256: 4,1%), 12,5 bb
  44,5% (44,5%), 8,3 bb 53,6% (53,6%); 10× 0,5% (0,6%), 2,0% (3,7%),
  20,8% (20,7%). Teza „3bet w tym drzewie wychodzi za szeroki” **nie
  trzyma się przy 25 bb** (2,2% wobec 13,3% ciasnego spotu z decyzji 21);
  przy 12,5 i 8,3 bb drzewo 3betuje na 3× szeroko (44,5 i 53,6%), ale spot
  daje tam 40,6 i 98,2%. „Nie eksportujemy go” — nadal prawda: eksport
  niesie 3bet spotu, nie drzewa.

Komendy (czas ścienny na maszynie pomiaru, 4 rdzenie współdzielone):
`python tools/export_open_nash.py PLIK` — eksport przy N = 512 z miarą
w każdym wierszu (67,1 s); `python tools/export_open_nash.py --curve` —
krzywa 8…1024, N wybrane regułą wyżej i rozrzut na [256, 512] (140,5 s);
3bet drzewa: `python -c "from poker.openfold import solve_curve; from
poker.spin import PAYOUTS; print([(r.iterations, r.btn_vs_open_pct,
r.convergence) for r in solve_curve((50,50,50), PAYOUTS['3x'].prizes,
(256, 512), button=1, sb=1, bb_amt=2)])"` (13,1 s; inne poziomy:
`sb=2, bb_amt=4` i `sb=3, bb_amt=6`, wypłata `'10x'` — 9,3–12,2 s).

**KOREKTA (architekt, 2026-09-27) do KOREKTY POKER-73:** teza „3bet
w tym drzewie wychodzi za szeroki” dotyczy drzewa, a KOREKTA wyżej
sprawdziła ją tylko na BTN. BB w drzewie przy 3× 25 bb 3betuje wobec
openu UTG **41,5%** (`solve((50,50,50), PAYOUTS['3x'].prizes, button=1,
iterations=512).bb_vs_open_pct`, 25 s razem z komendą spotu), a BB
w spocie 14,0% (`threebet(…, iterations=512).bb_vs_open_pct`) — dla BB
teza trzyma się także przy 25 bb; „nie trzyma się” wyżej dotyczy BTN.
Rozstrzygnięcie („nie eksportujemy go”, 3bet ze spotu) bez zmian.

`strategy_table` nietknięty. INV-P5 nietknięte.

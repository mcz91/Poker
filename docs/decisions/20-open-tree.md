# 20 — Drzewo open 2.2x, first-in

Powyżej 7 bb first-in to fold / open 2.2x / jam. Fictitious play,
macierz POKER-12, bez flata.

Na 3× 25 bb: UTG open ≈ 23%, overjam ≈ 1%. To jest produkt.

3bet w tym drzewie bez flata wychodzi za szeroki (artefakt: jedyna
kara to shove). Nie eksportujemy go. Vs open bot 3betuje ciasno
(vs-field), nie 3betem punktu stałego FP modelu (miara = 8,46e−4 sumy
nagród na 3× 25 bb przy N = 128; do POKER-73 nazywany tu „Nash 3bet”).

**KOREKTA (POKER-73):** liczby wyżej pochodziły z modelu, w którym overcall
BB wyceniano showdownem bez udziału BB, a fold BTN — equity ręki
spasowanego (finding B6 audytu 2026-09-26), i z FP uciętego na 16
iteracjach bez miary zbieżności (I-25). Po poprawce eksport liczy
N = 128 — najmniejszy punkt kontrolny krzywej 8…1024, na którym miara
zbieżności (zysk z best response per punkt decyzji, w ułamku sumy nagród)
jest ≤ 1e−3 na wszystkich sześciu poziomach eksportu. Wartości przy
N = 128, obok rozrzut na punktach kontrolnych [64, 128]:

- 3× 25 bb: UTG open **28,9%** (64: 29,7%), overjam **0,1%** (64: 0,3%);
  miara 8,46e−4. Dalej na krzywej open 32,9 / 33,9 / 32,5% (256 / 512 /
  1024) — miara w tolerancji nie oznacza liczby stojącej w miejscu.
- 3bet drzewa (BTN vs open): 3× 25 bb **6,4%** (64: 10,0%), 12,5 bb
  44,6% (45,1%), 8,3 bb 53,8% (54,4%); 10× 1,2% (2,5%), 5,5% (8,4%),
  20,4% (20,6%). Teza „3bet w tym drzewie wychodzi za szeroki” **nie
  trzyma się przy 25 bb** (6,4% wobec 10,4% ciasnego spotu z decyzji 21);
  przy 12,5 i 8,3 bb drzewo 3betuje na 3× szeroko (44,6 i 53,8%), ale spot
  daje tam 40,6 i 98,2%. „Nie eksportujemy go” — nadal prawda: eksport
  niesie 3bet spotu, nie drzewa.

Komendy (czas ścienny na maszynie pomiaru):
`python tools/export_open_nash.py PLIK` — eksport przy N = 128 z miarą
w każdym wierszu (16,6 s); `python tools/export_open_nash.py --curve` —
krzywa 8…1024 i rozrzut na [64, 128] (137,6 s); 3bet drzewa:
`python -c "from poker.openfold import solve_curve; from poker.spin
import PAYOUTS; print([(r.iterations, r.btn_vs_open_pct, r.convergence)
for r in solve_curve((50,50,50), PAYOUTS['3x'].prizes, (64, 128),
button=1, sb=1, bb_amt=2)])"` (3,2 s; inne poziomy: `sb=2, bb_amt=4`
i `sb=3, bb_amt=6`, wypłata `'10x'`).

`strategy_table` nietknięty. INV-P5 nietknięte.

# 22 — Arena ROI: tight GTO przegrywa z maniakiem

320 bloków, 3× WTA, hero vs dwóch fishy. Jednostka: blok trzech rotacji
cyklicznych jednego seeda — hero gra każde miejsce raz przy tej samej
sekwencji kart (POKER-48; wcześniejszy pomiar sadzał hero zawsze na
miejscu 0). Pomiar POKER-48:
`python tools/run_arena.py 320 3x` (seedy deterministyczne w narzędziu,
solve 12 iteracji — do POKER-73 dla openfold i jamfold, od POKER-73
openfold 512, patrz KOREKTA niżej; obok CI normalnego bootstrap
percentylowy, 1000 replikacji, seed 0).

| Książka | vs always-jam | 95% CI | bootstrap |
|---|---|---|---|
| Ciasny call (Nash 25 bb ~7%) | **−40.0% ROI** | −48.5 do −31.5 | −47.8 do −31.3 |
| Exploit: call vs random ≥50% (~48%) | **+18.4% ROI** | +10.0 do +26.9 | +10.6 do +26.6 |

**KOREKTA (POKER-71):** do POKER-71 arena dzieliła side pot 3-way po
równo między przegranych puli głównej (finding B3 audytu 2026-09-26).
Po poprawce rozliczenia `python tools/run_arena.py 320 3x` daje dla
ciasnego calla **−39.7% ROI**, CI −48.2 do −31.2, bootstrap −47.5 do
−30.9 (kod sprzed poprawki: −40.0%, CI −48.4 do −31.6, bootstrap −48.1
do −31.6); wiersz exploit jest bit w bit ten sam. Werdykt bez zmian.

**KOREKTA (POKER-73):** obie książki biorą open i overjam z openfold, a ciasna
także 3bet spotu z openu openfold; openfold wyceniał overcall BB showdownem
bez udziału BB i grał FP ucięte na 12 iteracjach bez miary zbieżności
(findingi B6 i I-25 audytu 2026-09-26). Po poprawce openfold liczy przy
N = 512 (najmniejszy punkt kontrolny krzywej 8…1024, od którego miara jest
≤ 1e−3 sumy nagród na wszystkich poziomach eksportu we wszystkich dalszych
punktach — KOREKTA (POKER-73) decyzji 20; call jamu nadal jamfold przy 12
iteracjach — zmiana w sprincie B).
`python tools/run_arena.py 320 3x --openfold-iters 512` (44,0 s) daje:

| Książka | vs always-jam | 95% CI | bootstrap | rozrzut [256, 512] |
|---|---|---|---|---|
| Ciasny call | **−44.4% ROI** | −52.7 do −36.1 | −52.2 do −35.6 | −43.4 / −44.4 |
| Exploit: call vs random ≥50% | **+19.1% ROI** | +10.8 do +27.3 | +11.3 do +27.5 | +19.4 / +19.1 |

(N = 256: `--openfold-iters 256`, 32,1 s; kod sprzed POKER-73: −39.7%
i +18.4% jak wyżej). Zmiana należy wyłącznie do książek openfold: open
i overjam obu książek oraz 3bet ciasnej (spot z openu openfold: 13,27%
zamiast 10,41%, lista rąk — KOREKTA (POKER-73) decyzji 21); call jamu
(jamfold) i 3bet exploitu są bit w bit te same co przed POKER-73. Werdykt
bez zmian — ciasny call przegrywa całym przedziałem, exploit wygrywa
całym przedziałem.

Bar $1 zaczyna się od bicia skryptowanego fisha. Ciasny „GTO”
tego nie robi — folduje za dużo. Play na głębokim stole woła jam
wykresem exploit, nie 7%.

To nie jest field $1. To always-jam.

`strategy_table` nietknięty.

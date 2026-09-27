# 22 — Arena ROI: tight GTO przegrywa z maniakiem

320 bloków, 3× WTA, hero vs dwóch fishy. Jednostka: blok trzech rotacji
cyklicznych jednego seeda — hero gra każde miejsce raz przy tej samej
sekwencji kart (POKER-48; wcześniejszy pomiar sadzał hero zawsze na
miejscu 0). Pomiar POKER-48:
`python tools/run_arena.py 320 3x` (seedy deterministyczne w narzędziu,
solve 12 iteracji — do POKER-73 dla openfold i jamfold, od POKER-73
openfold 128, patrz KOREKTA niżej; obok CI normalnego bootstrap
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

**KOREKTA (POKER-73):** obie książki biorą open i overjam z openfold, który
wyceniał overcall BB showdownem bez udziału BB i grał FP ucięte na 12
iteracjach bez miary zbieżności (findingi B6 i I-25 audytu 2026-09-26).
Po poprawce open i overjam liczy openfold przy N = 128 (najmniejszy punkt
kontrolny krzywej 8…1024 z miarą ≤ 1e−3 sumy nagród; call jamu nadal
jamfold przy 12 iteracjach — zmiana w sprincie B).
`python tools/run_arena.py 320 3x --openfold-iters 128` (28,7 s) daje:

| Książka | vs always-jam | 95% CI | bootstrap | rozrzut [64, 128] |
|---|---|---|---|---|
| Ciasny call | **−41.9% ROI** | −50.2 do −33.5 | −50.0 do −33.1 | −41.6 / −41.9 |
| Exploit: call vs random ≥50% | **+19.1% ROI** | +10.4 do +27.7 | +11.2 do +27.5 | +17.5 / +19.1 |

(N = 64: `--openfold-iters 64`, 25,5 s; kod sprzed POKER-73: −39.7%
i +18.4% jak wyżej). Zmiana należy wyłącznie do openu i overjamu książek:
call jamu (jamfold) i 3bet ciasnej książki są bit w bit te same co przed
POKER-73. Werdykt bez zmian — ciasny call przegrywa całym przedziałem,
exploit wygrywa całym przedziałem.

Bar $1 zaczyna się od bicia skryptowanego fisha. Ciasny „GTO”
tego nie robi — folduje za dużo. Play na głębokim stole woła jam
wykresem exploit, nie 7%.

To nie jest field $1. To always-jam.

`strategy_table` nietknięty.

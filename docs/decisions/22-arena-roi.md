# 22 — Arena ROI: tight GTO przegrywa z maniakiem

320 bloków, 3× WTA, hero vs dwóch fishy. Jednostka: blok trzech rotacji
cyklicznych jednego seeda — hero gra każde miejsce raz przy tej samej
sekwencji kart (POKER-48; wcześniejszy pomiar sadzał hero zawsze na
miejscu 0). Pomiar POKER-48:
`python tools/run_arena.py 320 3x` (seedy deterministyczne w narzędziu,
solve 12 iteracji; obok CI normalnego bootstrap percentylowy,
1000 replikacji, seed 0).

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

Bar $1 zaczyna się od bicia skryptowanego fisha. Ciasny „GTO”
tego nie robi — folduje za dużo. Play na głębokim stole woła jam
wykresem exploit, nie 7%.

To nie jest field $1. To always-jam.

`strategy_table` nietknięty.

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

Bar $1 zaczyna się od bicia skryptowanego fisha. Ciasny „GTO”
tego nie robi — folduje za dużo. Play na głębokim stole woła jam
wykresem exploit, nie 7%.

To nie jest field $1. To always-jam.

`strategy_table` nietknięty.

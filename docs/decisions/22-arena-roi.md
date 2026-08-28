# 22 — Arena ROI: tight GTO przegrywa z maniakiem

360 Spins, 3× WTA, hero seat 0 vs dwóch fishy. Pomiar POKER-45 po
naprawie martwej ręki HU (POKER-44) i rozliczeń żetonów (POKER-45):
`python tools/run_arena.py 360 3x` (seedy deterministyczne w narzędziu,
solve 12 iteracji).

| Książka | vs always-jam | 95% CI |
|---|---|---|
| Ciasny call (Nash 25 bb ~7%) | **−46.7% ROI** | −58.5 do −34.8 |
| Exploit: call vs random ≥50% (~48%) | **+18.3% ROI** | +3.2 do +33.5 |

Bar $1 zaczyna się od bicia skryptowanego fisha. Ciasny „GTO”
tego nie robi — folduje za dużo. Play na głębokim stole woła jam
wykresem exploit, nie 7%.

To nie jest field $1. To always-jam.

`strategy_table` nietknięty.

# 18 — Plan rozbudowy: Spin $1, nie większy cash-MCCFR

> Uwaga ([decyzja 24](24-audyt-i-scalenie-linii-spin.md)): ten dokument
> został przepisany w miejscu w commicie 42aae23; pierwotna treść
> (z sekcją Źródła) jest w historii pod commitem a437d34. Od decyzji 24
> dokument decyzji unieważnia się odesłaniem w nowej decyzji, nie edycją.

Cel produktu: bot, który **nie jest rybą na $1 Spin** (3-max NLH).
Nie crusher. Nie HU cash. `strategy_table` i INV-P5 zostają.

Push/fold jest **endgame**: dopiero przy **≤ 7 bb** efektywnych.
Wyżej (25 → 8 bb) drzewo to fold / open 2.2x / jam; vs open:
fold / 3bet-jam. Bez flata, bez flopu — zamknięte, preflop.

| Tor | Kiedy | Jednostka |
|---|---|---|
| B · open 2.2x | > 7 bb | ROI / $EV |
| A · jam/fold | ≤ 7 bb | ε transfer + ROI vs fish |

POKER-27 tylko jeśli operator wraca do cash HU.

## Kolejność

1. **Próg 7 bb na stole.** Play nie zmusza do shove na 25 bb.
2. **Jedna polityka jam/fold** na ≤7 bb (macierz, nie vs-field).
3. **Nierówne stacki** — eff bb = min(żywe) / bb.
4. **Nash drzewa 2.2x** (FP jak jam/fold, nadal preflop).
5. **VI Ganzfrieda** na jam/fold endgame + kontynuacje z 2.2x.
6. **Arena ROI** vs fish. Bar $1.
7. **Flop** tylko jeśli po (4)+(6) widać wyciek na SPR.

## Świadomie nie robimy

- Jam/fold jako modelu 12–25 bb.
- Regeneracji `strategy_table`.
- PokerKit / N=3 w `HeadsUpHand`.
- Twierdzenia „bijemy field $1” przed areną ROI.

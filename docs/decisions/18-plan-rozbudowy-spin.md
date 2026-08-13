# 18 — Plan rozbudowy: Spin $1, nie większy cash-MCCFR

Cel produktu: bot, który **nie jest rybą na $1 Spin** (3-max NLH).
Nie crusher. Nie HU cash. `strategy_table` i INV-P5 zostają.

Dwa tory. Nie mieszać ich metryk.

| Tor | Jednostka | Kupuje | Nie kupuje |
|---|---|---|---|
| A · jam/fold | ε transfer + ROI vs fish | fazę od ~12 bb | pierwsze ręce 25 bb |
| B · 25 bb | ROI / $EV turnieju | open 2.2x / fold / 3bet-jam | flop |

POKER-27 (krzywa HU MCCFR) tylko jeśli operator wraca do cash HU.

## Co już jest (i czego nie udawać)

- Zegar, ICM/WTA, stół /play, offline FP na równych stackach.
- Self-ε ≈ 0 w modelu ≠ Nash pokera (decyzja 17).
- Live vs-field UTG ~27% ≠ macierz UTG ~17%.
- Cash MCCFR: −329 BB/100 vs `rule`. Zamrożone.

## Kolejność (A zanim B, C tylko po pomiarze)

1. **Jedna polityka.** Play i lab czytają ten sam artefakt
   (Python + macierz). Live vs-field przestaje być źródłem decyzji.
   Tanio. Przywraca wiarygodność.
2. **ε transfer.** BR w modelu macierzy przeciw polityce lab/Play.
   Mianownik: always-jam 0.18 BI. Koniec porównań do Ganzfrieda.
3. **Nierówne stacki.** Kubły chipów (nie tylko 50/50/50 × poziom).
   Bez tego bot po pierwszym shovie zgaduje.
4. **Zewnętrzna pętla Ganzfrieda.** V już jest jednokrokowe
   (POKER-32). Value iteration po stanach stacków = prawdziwy
   jam/fold turniejowy (AAMAS 2008). Godziny CPU, nie GPU.
5. **Arena ROI.** Duplikat Spina vs skryptowany fish (za szeroki
   call, always-jam). Metryka (b) z decyzji 15. Bar: ROI > fish
   na ≥ N turniejach z CI. Nie BB/100.
6. **Drzewo 25 bb: fold / open 2.2x / jam; call / fold / 3bet-jam.**
   To wyciek $1 na starcie. Nadal preflop. Nadal stdlib.
7. **Flop (tor C).** Tylko jeśli po (5)+(6) ROI vs fish stoi w miejscu
   i wyciek widać na SPR po minraise. Abstrakcja + MCCFR HU najpierw,
   3-max później. Droższe niż wszystko powyżej razem.

## Świadomie nie robimy

- Regeneracji `strategy_table` i skali c2 bez krzywej 09.
- PokerKit / AGPL / silnika N=3 w `HeadsUpHand`.
- Twierdzenia „bijemy field $1” przed areną ROI.
- Postflopu „bo tak się robi GTO”.

## Źródła (te same co przy wyborze metody)

- Ganzfried & Sandholm, AAMAS 2008 / IJCAI 2009 — FP + VI, nie ML.
- Decyzje 09, 15, 17.

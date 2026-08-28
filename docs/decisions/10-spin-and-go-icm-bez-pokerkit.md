# 10 — Spin & Go: własny ICM, bez PokerKit

Operator wskazał format Spin & Go (3-max, krótki stack) jako pierwszy
przed cashem 50–100 bb. Integracja gotowca tylko gdy jest serio
kosztowna i dobra.

## Decyzja

1. **Pakiet produktu zostaje bez zależności.** `pyproject.toml`
   `dependencies = []`. PokerKit (MIT) jest dobrym symulatorem 3-max
   i side potów, ale:
   - nie liczy równowagi ani ICM;
   - wpięcie do `src/poker` łamie stdlib-only (INV, decyzja 06);
   - konstytucja §9 wymaga powodu i planu usunięcia — tu powodu nie ma:
     Harville to kilkadziesiąt linii, rozliczenie all-in jam/fold też.
2. **ICM jest własny** (`poker.icm`): Malmuth–Harville, WTA jako
   szczególny przypadek nagród `(pula, 0, …, 0)`. Źródło: Malmuth 1987;
   tożsamość WTA = udział żetonów.
3. **Spin jest warstwą wypłat i jam/fold**, nie nową maszyną licytacji.
   `HeadsUpHand` i `play_match` zostają przy N=2 (INV-P5). Side pot
   istnieje wyłącznie w `award_allin` dla all-inów, nie w drzewie betów.
4. **PokerKit, TexasSolver, postflop-solver, slumbot2019, OpenSpiel
   jako silnik — nie wchodzą do produktu.** OpenSpiel DCFR zostaje
   lekturą wzoru. HRC / ICMIZER — wyrocznia offline (golden file),
   bez API w serwisie.
5. **Start 25 bb** (`STARTING_CHIPS = 50`, `big_blind = 2`) — klasyczny
   Spin Stars (500 żetonów, 10/20). 2× i 3× = WTA; 10× = 80/20 jako
   pierwszy nie-WTA. Zegar blindów i Nash 3-max (Ganzfried & Sandholm,
   AAMAS 2008) — osobny kontrakt.

## Skutek

POKER-30 dostarcza matematykę $EV. Nie otwiera multiway NL. Następny
krok po pomiarze: jam/fold 3-max albo powrót do POKER-28/27 (HU skala).

# Stan bieżący produktu Poker

Wersja pakietu: 0.1.0 · ostatnie zamknięte zadanie: POKER-4
(ujednolicenie bramki po audycie POKER-1).

## Co istnieje

- pakiet `poker` w układzie src-layout (`src/poker/`), typowany strict
  (marker `py.typed`), wyłącznie standard library;
- `poker.cards` — 52 niemutowalne karty (13 rang × 4 kolory), pełna
  talia `FULL_DECK`; karta spoza zbioru jest błędem;
- `poker.evaluation` — klasyfikacja 5-kartowego układu do jednej z 9
  kategorii, porządek zupełny z kickerami (`HandValue`), wybór
  najlepszego układu z 5–7 kart;
- `poker.events` — niemutowalne, typowane zdarzenia cyklu rozdania
  (start z konfiguracją i seedem, blindy, karty własne, flop/turn/river,
  akcja, showdown, przyznanie puli, koniec); każde zdarzenie deklaruje
  widoczność (`Public` / `PrivateToSeat`) — filtrowanie widoku to
  krok 5;
- `poker.history` — append-only historia rozdania, zamykana zdarzeniem
  końca; API bez mutacji i usuwania;
- `poker.projection` — stan stołu (stacki, pula, board, karty per
  miejsce, faza) jako czysta projekcja sekwencji zdarzeń; replay
  i prefiksy pokryte testami, suma żetonów stała w każdym prefiksie;
- `poker.dealing` — talia i rozdanie kart deterministyczne
  z wstrzykniętego, seedowanego RNG; miejsca jako kolekcja (testy N=2
  i N=3);
- bramka repozytorium: ruff, mypy strict, pytest — komendy wylicza
  [`README.md`](../README.md); goła `mypy` typuje `src` i `tests`
  (konfiguracja `files`), a rozjazd bramki z kontraktami czerwieni
  test zgodności `tests/test_repo_gate.py`.

## Czego nie ma

Maszyny licytacji (legalność akcji, min-raise, side poty), widoku
agenta z testem przecieku, stołu, pętli meczu, agentów, CLI,
serializacji i persystencji historii. Sekwencję budowy definiuje
[`PROMPT_POKER_ARCHITEKT.md`](../PROMPT_POKER_ARCHITEKT.md) (punkt 5).

## Następny krok

Krok 4 sekwencji budowy: maszyna licytacji heads-up — TaskSpec
specyfikuje architekt po scaleniu POKER-3 i POKER-4.

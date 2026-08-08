# Stan bieżący produktu Poker

Wersja pakietu: 0.1.0 · ostatnie zamknięte zadanie: POKER-2 (karty
i ewaluator rąk).

## Co istnieje

- pakiet `poker` w układzie src-layout (`src/poker/`), typowany strict
  (marker `py.typed`), wyłącznie standard library;
- `poker.cards` — 52 niemutowalne karty (13 rang × 4 kolory), pełna
  talia `FULL_DECK`; karta spoza zbioru jest błędem;
- `poker.evaluation` — klasyfikacja 5-kartowego układu do jednej z 9
  kategorii, porządek zupełny z kickerami (`HandValue`), wybór
  najlepszego układu z 5–7 kart; koło A-5, remisy i niezależność od
  kolejności kart pokryte testami;
- bramka repozytorium: ruff, mypy strict, pytest — komendy wylicza
  [`README.md`](../README.md).

## Czego nie ma

Talii jako obiektu gry (tasowanie, RNG), zdarzeń rozdania, maszyny
licytacji, kontraktu agenta, stołu ani CLI. Sekwencję budowy definiuje
[`PROMPT_POKER_ARCHITEKT.md`](../PROMPT_POKER_ARCHITEKT.md) (punkt 5).

## Następny krok

POKER-3 — zdarzenia rozdania i projekcja stanu; specyfikuje architekt
po zieleni bramki POKER-2.

# Stan bieżący produktu Poker

Wersja pakietu: 0.1.0 · ostatnie zamknięte zadanie: POKER-1 (szkielet).

## Co istnieje

- pakiet `poker` w układzie src-layout (`src/poker/`), typowany strict
  (marker `py.typed`), bez logiki gry;
- bramka repozytorium: ruff, mypy strict, pytest — komendy wylicza
  [`README.md`](../README.md);
- test szkieletu: zgodność wersji pakietu z metadanymi dystrybucji.

## Czego nie ma

Żadnej logiki gry: kart, ewaluatora rąk, zdarzeń rozdania, maszyny
licytacji, kontraktu agenta, stołu ani CLI. Sekwencję budowy definiuje
[`PROMPT_POKER_ARCHITEKT.md`](../PROMPT_POKER_ARCHITEKT.md) (punkt 5).

## Następny krok

POKER-2 — karty i ewaluator rąk; specyfikuje architekt po zieleni
bramki POKER-1.

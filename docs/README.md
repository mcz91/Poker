# Indeks dokumentacji produktu Poker

- [`CURRENT_STATE.md`](CURRENT_STATE.md) — stan bieżący, bramka,
  następny krok.

## Dokumenty decyzji

1. [`01-trzy-produkty-jeden-rdzen.md`](decisions/01-trzy-produkty-jeden-rdzen.md)
   — trzy produkty docelowe (pokerroom, trener, bot), jeden wspólny
   rdzeń, zakaz pustych szkieletów produktów;
2. [`02-jezyk-rdzenia-python.md`](decisions/02-jezyk-rdzenia-python.md)
   — język rdzenia: Python ≥3.12, toolchain wspólny z Foundry.

## TaskSpeki

Kontrakty zadań żyją w [`taskspecs/`](taskspecs/) według
`schemas/task-spec.schema.json` z `mcz91/foundry`:

- [`POKER-1.json`](taskspecs/POKER-1.json) — szkielet i pełna bramka
  (zamknięty, commit `5a74ab9`);
- [`POKER-2.json`](taskspecs/POKER-2.json) — karty i ewaluator rąk
  (zamknięty, commit `bd3473c`);
- [`POKER-3.json`](taskspecs/POKER-3.json) — zdarzenia rozdania
  i projekcja stanu (zamknięty na gałęzi kodera, czeka na scalenie);
- [`POKER-4.json`](taskspecs/POKER-4.json) — ujednolicenie bramki po
  audycie POKER-1 (zamknięty na gałęzi kodera, czeka na scalenie).

## Operator

Prompty ról żyją w korzeniu repozytorium:
[`PROMPT_POKER_ARCHITEKT.md`](../PROMPT_POKER_ARCHITEKT.md),
[`PROMPT_POKER_KODER.md`](../PROMPT_POKER_KODER.md),
[`PROMPT_POKER_AUDYTOR.md`](../PROMPT_POKER_AUDYTOR.md).

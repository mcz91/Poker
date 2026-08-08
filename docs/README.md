# Indeks dokumentacji produktu Poker

- [`CURRENT_STATE.md`](CURRENT_STATE.md) — stan bieżący, bramka,
  następny krok.

## Dokumenty decyzji

1. [`01-trzy-produkty-jeden-rdzen.md`](decisions/01-trzy-produkty-jeden-rdzen.md)
   — trzy produkty docelowe (pokerroom, trener, bot), jeden wspólny
   rdzeń, zakaz pustych szkieletów produktów;
2. [`02-jezyk-rdzenia-python.md`](decisions/02-jezyk-rdzenia-python.md)
   — język rdzenia: Python ≥3.12, toolchain wspólny z Foundry;
3. [`03-kierunek-bot-interfejs-czlowieka.md`](decisions/03-kierunek-bot-interfejs-czlowieka.md)
   — kierunek bot etapami: interfejs człowieka (a), baseline GTO (b),
   warstwa eksploatacyjna (c).

## TaskSpeki

Kontrakty zadań żyją w [`taskspecs/`](taskspecs/) według
`schemas/task-spec.schema.json` z `mcz91/foundry`:

- [`POKER-1.json`](taskspecs/POKER-1.json) — szkielet i pełna bramka
  (zamknięty, commit `5a74ab9`);
- [`POKER-2.json`](taskspecs/POKER-2.json) — karty i ewaluator rąk
  (zamknięty, commit `bd3473c`);
- [`POKER-3.json`](taskspecs/POKER-3.json) — zdarzenia rozdania
  i projekcja stanu (zamknięty, commit `68df34e`);
- [`POKER-4.json`](taskspecs/POKER-4.json) — ujednolicenie bramki po
  audycie POKER-1 (zamknięty, commit `bd6dd56`);
- [`POKER-5.json`](taskspecs/POKER-5.json) — maszyna licytacji heads-up
  z rozliczeniem rozdania (zamknięty, commit `fa6a25c`);
- [`POKER-6.json`](taskspecs/POKER-6.json) — kontrakt agenta i widok
  gracza z testem przecieku (zamknięty, commit `8e7d9e6`);
- [`POKER-7.json`](taskspecs/POKER-7.json) — stół i pętla meczu
  (zamknięty, commit `462576d`; domknięcie audytu `4a01775`);
- [`POKER-8.json`](taskspecs/POKER-8.json) — pierwszy agent regułowy
  (zamknięty, commit `95d004a`; audyt w toku);
- [`POKER-9.json`](taskspecs/POKER-9.json) — CLI i eksport historii
  (zamknięty, commit `b6f7035`; audyt w toku);
- [`POKER-10.json`](taskspecs/POKER-10.json) — interfejs człowiek vs
  bot w terminalu (zatwierdzony, u kodera).

## Operator

Prompty ról żyją w korzeniu repozytorium:
[`PROMPT_POKER_ARCHITEKT.md`](../PROMPT_POKER_ARCHITEKT.md),
[`PROMPT_POKER_KODER.md`](../PROMPT_POKER_KODER.md),
[`PROMPT_POKER_AUDYTOR.md`](../PROMPT_POKER_AUDYTOR.md).

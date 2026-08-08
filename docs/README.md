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
   — kierunek bot etapami: interfejs człowieka (a), baseline (b),
   warstwa eksploatacyjna (c);
4. [`04-reguly-dzis-ml-docelowo.md`](decisions/04-reguly-dzis-ml-docelowo.md)
   — etap (b) drogą operatora: proste reguły dziś, silnik GTO/explo
   na ML docelowo; podetapy equity → arena → dane self-play → ML;
5. [`05-b4-plastrami-dane-baseline-zaleznosci.md`](decisions/05-b4-plastrami-dane-baseline-zaleznosci.md)
   — podetap b4 plastrami (zbiór przykładów → baseline stdlib →
   zależności po pomiarze), granica informacyjna danych treningowych,
   bezstanowość agentów w rozgrywce (zamyka wątek audytu POKER-13).

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
  bot w terminalu (zamknięty, commit `b1da201`; audyt: 1 finding
  informacyjny → POKER-11);
- [`POKER-11.json`](taskspecs/POKER-11.json) — showdown na żywo
  w trybie człowieka (zamknięty, commit `80899ce`; audyt w toku);
- [`POKER-12.json`](taskspecs/POKER-12.json) — equity preflop 169
  klas rąk jako dane (zamknięty, commit `f166f41`; audyt w toku);
- [`POKER-13.json`](taskspecs/POKER-13.json) — arena porównawcza
  agentów: BB/100 na lustrzanych rozdaniach (zamknięty, commit
  `5f5302b`; audyt: CZYSTY);
- [`POKER-14.json`](taskspecs/POKER-14.json) — korpus self-play:
  masowa generacja historii w formacie eksportu (zamknięty, commit
  `5a75ef8`; audyt: CZYSTY);
- [`POKER-15.json`](taskspecs/POKER-15.json) — zbiór przykładów
  decyzyjnych z korpusu, plaster b4.1 decyzji 05 (zatwierdzony,
  u kodera).

## Operator

Prompty ról żyją w korzeniu repozytorium:
[`PROMPT_POKER_ARCHITEKT.md`](../PROMPT_POKER_ARCHITEKT.md),
[`PROMPT_POKER_KODER.md`](../PROMPT_POKER_KODER.md),
[`PROMPT_POKER_AUDYTOR.md`](../PROMPT_POKER_AUDYTOR.md).

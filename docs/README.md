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
   bezstanowość agentów w rozgrywce (zamyka wątek audytu POKER-13);
6. [`06-b43-zaleznosci-w-narzedziach-droga-gto-explo.md`](decisions/06-b43-zaleznosci-w-narzedziach-droga-gto-explo.md)
   — b4.3: zależności ML wyłącznie w narzędziach, inferencja
   w stdlib, plastry c1 (MLP-klon) → c2 (self-play) → c3 (explo),
   dwustopniowe dowody odtwarzalności na skalę;
7. [`07-c2-mccfr-na-abstrakcji-strategia-mieszana.md`](decisions/07-c2-mccfr-na-abstrakcji-strategia-mieszana.md)
   — c2: seedowany MCCFR w self-play na wersjonowanej abstrakcji,
   artefakt strategii z pochodzeniem, mieszanie akcji bez stanu
   (deterministyczna funkcja seeda i widoku); plastry c2a→c2c;
8. [`08-pokerroom-krok1-stoly-heads-up-w-lan.md`](decisions/08-pokerroom-krok1-stoly-heads-up-w-lan.md)
   — otwarcie gałęzi pokerroom na zamówienie operatora: serwer wielu
   stołów heads-up w LAN (adapter, mono-repo), separacja informacji
   na granicy procesu; multiway = osobna kwalifikacja silnika.

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
  decyzyjnych z korpusu, plaster b4.1 decyzji 05 (zamknięty, commit
  `cb2298d`; audyt: CZYSTY);
- [`POKER-16.json`](taskspecs/POKER-16.json) — baseline behavior
  clone, plaster b4.2 decyzji 05 (zamknięty, commit `eea6b81`;
  audyt: F1 ISTOTNY — odtwarzalność wag z samego repo → POKER-17);
- [`POKER-17.json`](taskspecs/POKER-17.json) — przepis pochodzenia
  wag w artefakcie i test pochodzenia (zamknięty, commit `469f2db`;
  audyt: CZYSTY — F1 audytu POKER-15/16 domknięty z dowodem
  mechanicznym);
- [`POKER-18.json`](taskspecs/POKER-18.json) — sufit baseline'u
  stdlib: cechy v2 (equity, siła układu), korpus 100 meczów, pomiar
  w arenie (zamknięty, commit `cd645ed`; audyt: 1 finding
  informacyjny — niedoliczony dowód czerwieni, bez obowiązku
  działania);
- [`POKER-19.json`](taskspecs/POKER-19.json) — MLP-klon, plaster c1
  decyzji 06: trening numpy w tools/, inferencja stdlib, trzeci
  punkt pomiarowy (zamknięty, commit `0dfa48b`; audyt: F1 ISTOTNY —
  sprzeczność kryterium czasu bramki w kontrakcie, uznana przez
  architekta → POKER-20; F2 informacyjny — nieprzypięty numpy
  → POKER-20);
- [`POKER-20.json`](taskspecs/POKER-20.json) — porządek dowodów po
  c1: dwustopniowy dowód dla klona liniowego, przypięcie numpy
  (zamknięty, commit `72305b1`; audyt: CZYSTY — F1 i F2 audytu
  POKER-19 domknięte z dowodem);
- [`POKER-21.json`](taskspecs/POKER-21.json) — pokerroom krok 1:
  serwer stołów heads-up w LAN, klient terminalowy, przeciek
  protokołu pod testem (zamknięty, commit `c9231e3`; audyt:
  1 finding informacyjny — przewidywalny kod stołu → wątek na
  najbliższy kontrakt sieciowy).

## Operator

Prompty ról żyją w korzeniu repozytorium:
[`PROMPT_POKER_ARCHITEKT.md`](../PROMPT_POKER_ARCHITEKT.md),
[`PROMPT_POKER_KODER.md`](../PROMPT_POKER_KODER.md),
[`PROMPT_POKER_AUDYTOR.md`](../PROMPT_POKER_AUDYTOR.md).

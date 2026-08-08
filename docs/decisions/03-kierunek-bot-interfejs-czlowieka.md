# Decyzja 03 — Kierunek: bot; pierwszy krok: interfejs człowiek vs bot

Status: obowiązuje · 2026-08-08 · decyzja operatora na rekomendację
architekta

## Kontekst

Sekwencja budowy horyzontu bieżącego jest ukończona (POKER-1…9).
Operator wybrał kierunek rozwoju: gałąź **bot** z decyzji
[`01`](01-trzy-produkty-jeden-rdzen.md), zaczynając od prostego
interfejsu do grania człowieka z istniejącym agentem regułowym.

## Decyzja

1. Gałąź bot otwiera się **etapami, każdy własną kwalifikacją**:
   - (a) interfejs człowiek vs bot w terminalu — natychmiast
     (POKER-10);
   - (b) baseline równowagowy (aproksymacja GTO) — osobna
     kwalifikacja, gdy operator zamówi;
   - (c) warstwa eksploatacyjna na eksportowanych historiach — po
     etapie (b), bo zysk z eksploatacji mierzy się względem baseline'u.
2. Człowiek wchodzi **portem Agent przez adapter** (INV-P4) — silnik
   nie wie, że decyduje człowiek; całe I/O w adapterze (INV-P1, P7).
3. Terminal renderuje **wyłącznie z `PlayerView`** miejsca człowieka
   (INV-P3): karty bota i seed niewidoczne żadnym kanałem aż do
   showdownu — ta sama dyscyplina przecieku co dla agentów.

## Którą gałąź (pokerroom / trener / GTO-ML) ta decyzja zamyka albo czyni droższą?

Żadnej nie zamyka. Bot: otwiera wprost — to jego pierwszy etap.
Trener: tanieje — interfejs człowieka to przyszły kanał replay
i practice, a dyscyplina widoku (INV-P3) jest wspólna. Pokerroom:
neutralny — interfejs jest lokalny, sieć i wiele stołów pozostają za
granicą adapterów; dowód: kierunek importów strzeżony
`tests/test_architecture.py`, silnik pozostaje nietknięty. Ryzyko:
pokusa wbudowania prezentacji w silnik — mitygacja jak wyżej, test
architektury czerwieni każdy import w złą stronę.

## Konsekwencje na przyszłość

Agent eksploatacyjny (etap c) będzie potrzebował pamięci między
rozdaniami (model przeciwnika) — to świadome rozszerzenie kontraktu
INV-P4, wymagające nowej wersji tej decyzji, nie cichej zmiany.

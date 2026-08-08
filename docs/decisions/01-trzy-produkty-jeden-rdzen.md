# Decyzja 01 — Trzy produkty docelowe, jeden rdzeń

Status: obowiązuje · 2026-08-08 · źródło celu: operator

## Kontekst

Operator zamówił szkielet repozytorium „pod 3 produkty": pokerroom,
oprogramowanie treningowe (trener) i bot autonomiczny. Dotychczas były
to gałęzie przyszłe z promptu architekta — od tej decyzji są
potwierdzonym celem produktowym. Żaden z trzech produktów nie jest
jednak specyfikowany dziś: funkcja bez odbiorcy w horyzoncie bieżącym
pozostaje odłożona.

## Decyzja

1. **Wspólnym fundamentem trzech produktów jest jeden czysty rdzeń**:
   deterministyczny silnik heads-up NLHE, append-only historia zdarzeń
   i kontrakt agenta (niezmienniki INV-P1…P8 z
   [`PROMPT_POKER_ARCHITEKT.md`](../../PROMPT_POKER_ARCHITEKT.md)).
   Szkielet POKER-1 buduje wyłącznie rdzeń.
2. **Zakaz pustych szkieletów produktów.** Katalogi, pakiety ani kod
   pokerroomu, trenera czy bota nie powstają, dopóki dany produkt nie
   wejdzie własną kwalifikacją „czy budować" i własnymi TaskSpekami.
   Otwartość drzwi gwarantują granice, nie placeholdery:
   - INV-P2 (historia zdarzeń jest prawdą) → trener (replay), bot
     (dane treningowe), pokerroom (audyt);
   - INV-P4 (jeden port agenta) → bot autonomiczny i człowiek przez
     adapter wchodzą tym samym kontraktem co agent regułowy;
   - INV-P5 (miejsca są kolekcją N) → pokerroom (multiway);
   - INV-P7 (krawędzie są adapterami) → UI, sieć i eksporty każdego
     produktu zależą od silnika, nigdy odwrotnie.
3. **Struktura repozytorium:** jedno repozytorium, jeden pakiet `poker`
   jako rdzeń. Rozstrzygnięcie mono- vs multi-repo dla produktów jest
   odroczone do pierwszej kwalifikacji produktu — dziś nic go nie
   wymusza, a czysty kontrakt rdzenia czyni oba warianty wykonalnymi.

## Którą gałąź ta decyzja zamyka albo czyni droższą?

Żadnej — i to nie deklaracja: każdy z niezmienników wyżej mapuje się na
co najmniej jedną gałąź, a rdzeń jako wspólna zależność czyni wszystkie
trzy tańszymi (jedna implementacja reguł gry zamiast trzech). Ryzyko:
pokusa dublowania logiki gry w produktach; mitygacja — produkty
konsumują silnik wyłącznie przez jego kontrakty, co egzekwują testy
przecieku i przyszłe testy kontraktowe.

## Konsekwencje dla POKER-1

Zakres POKER-1 bez zmian merytorycznych; do `non_goals` wchodzi jawny
zakaz szkieletów produktów (punkt 2 tej decyzji).

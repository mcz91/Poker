# Decyzja 05 — Podetap b4 plastrami: dane decyzyjne, baseline stdlib, zależności po pomiarze

Status: obowiązuje · 2026-08-08 · decyzja architekta na zamówienie
operatora (wejście w podetap b4 decyzji
[`04`](04-reguly-dzis-ml-docelowo.md) po zamknięciu b3)

## Decyzja

1. Podetap b4 („ML właściwe") wchodzi plastrami, każdy własnym
   kontraktem i pełną bramką:
   - **(b4.1)** — POKER-15: zbiór przykładów decyzyjnych z korpusu
     self-play — dla każdej decyzji agenta cechy wyprowadzone
     wyłącznie z widoku miejsca decydującego oraz etykieta (podjęta
     akcja); typowany, wersjonowany, deterministyczny plik zbioru;
   - **(b4.2)** — baseline behavior cloning w standard library:
     prosty model trenowany offline narzędziem w repo,
     deterministyczna inferencja agentem portem `Agent` w rejestrze
     CLI, wynik zmierzony w arenie przeciw agentom regułowym;
     kryterium plastra jest pomiar, nie „lepszość";
   - **(b4.3)** — kwalifikacja pierwszych zależności ML (np. numpy /
     torch) **wyłącznie** gdy pomiary b4.2 wykażą sufit standard
     library; wraz z nią decyzja o formacie modelu w repo — reguła 9
     konstytucji (powód + plan usunięcia) i osobny dokument decyzji.
2. **Granica informacyjna danych treningowych** (rozszerzenie INV-P3
   na trening): przykład koduje wyłącznie informacje z widoku miejsca
   decydującego w chwili decyzji. Karty przeciwnika przed showdownem,
   seedy i zdarzenia `EngineOnly` nie wchodzą do cech ani etykiet —
   żadnym kanałem. Test przecieku danych jest obowiązkowy w każdym
   plastrze dotykającym zbioru; model nauczony na przecieku jest
   bezwartościowy przy stole, bo dostaje tam tylko widok.
3. Rozstrzygnięcie wątku z audytu POKER-13: **agenci produktu są
   bezstanowi w rozgrywce** — uczenie odbywa się wyłącznie offline,
   poza pętlą gry (decyzja 04, INV-P8); inferencja jest czystą
   funkcją widoku (INV-P4). Lustro areny pozostaje ważne bez zmian.
   Agent uczący się w trakcie serii wymagałby nowej decyzji operatora
   i zmiany kontraktu areny (świeże instancje na przebieg) — dziś
   poza horyzontem.

## Uzasadnienie

- dane przed modelem: błędy w danych treningowych są najdroższe
  i najtrudniejsze do wykrycia po fakcie — zbiór dostaje własny
  kontrakt, audyt i test przecieku, zanim powstanie pierwszy model;
- baseline w stdlib przed zależnościami: mierzalny punkt odniesienia
  w arenie pozwala uczciwie ocenić, co kupuje każda przyszła
  zależność (mitygacja ryzyka z decyzji 04); zerowy koszt wejścia
  i pełna zgodność z decyzją 02 (standard library first);
- plik zbioru zamiast treningu „z korpusu w locie": operator może
  obejrzeć dane, a trener (analiza decyzji) dostaje gotowy artefakt.

## Którą gałąź (pokerroom / trener / GTO-ML) ta decyzja zamyka albo czyni droższą?

Żadnej nie zamyka:

- **GTO-ML**: otwiera wprost — to jego droga; ryzykiem jest sufit
  jakości baseline'u stdlib, ale to koszt jednego plastra, nie
  architektury: port `Agent` i zbiór przykładów są niezależne od
  wyboru biblioteki w b4.3;
- **trener**: tanieje — zbiór przykładów decyzyjnych (widok →
  decyzja) to dokładnie substrat analizy decyzji i podpowiedzi;
- **pokerroom**: neutralna — wszystko dzieje się w danych
  i narzędziach za portem `Agent`; silnik nietknięty. Granica
  informacyjna (pkt 2) wręcz tanieje pokerroomowi: te same reguły
  widoczności obowiązują dane, więc przyszły audyt rozdań ludzkich
  nie wymaga nowych zasad.

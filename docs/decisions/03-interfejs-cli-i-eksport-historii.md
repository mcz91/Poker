# Decyzja 03 — Interfejs uruchomieniowy: eksport historii i CLI

Status: obowiązuje · 2026-08-08 · decyzja architekta na zamówienie
operatora (projekt kroku 8 sekwencji budowy)

## Decyzja

Krok 8 sekwencji („CLI i eksport historii") realizują dwa kontrakty,
scalane sekwencyjnie po zieleni POKER-8:

1. **POKER-9 — eksport historii.** Adapter serializacji pełnej historii
   meczu do formatu v1 (niżej) z parserem odtwarzającym zdarzenia bez
   strat (round-trip).
2. **POKER-10 — CLI.** Adapter uruchomieniowy `python -m poker`:
   deterministyczny mecz dwóch nazwanych agentów, wynik na stdout,
   eksport przez `--export`.

Format eksportu jest kontraktem danych — przeżyje CLI i jest wejściem
przyszłych gałęzi; dlatego ma własny kontrakt i osobny audyt, przed CLI.

### Format eksportu v1

- JSON Lines: UTF-8, LF, jeden obiekt JSON na linię, klucze w stałym
  porządku; ten sam mecz daje plik identyczny bajtowo — bez znaczników
  czasu (silnik nie ma zegara, INV-P1; adapter go nie dodaje);
- linia 1 — nagłówek: `format` (`"poker-match-history"`), `version`
  (`1`) oraz wyłącznie dane niewyprowadzalne ze zdarzeń: konfiguracja
  meczu (w tym limit rozdań) i seed meczu;
- każda następna linia — jedno zdarzenie rozdania (POKER-3) w kolejności
  wystąpienia, z polem typu; granice rozdań wyznaczają same zdarzenia
  (`HandStarted`…`HandEnded`) — bez powielania indeksów;
- zakaz danych wyprowadzalnych (widoczność zdarzeń, projekcje stanów,
  wynik meczu): kopia mogłaby rozjechać się z prawdą zdarzeń (INV-P2,
  reguła 1 konstytucji); konsument liczy projekcje sam;
- karty w notacji standardowej: ranga `2…9 T J Q K A` + kolor `c d h s`,
  np. `"As"`, `"Td"`;
- pełny eksport zawiera zdarzenia `EngineOnly` (seed rozdania) i karty
  prywatne obu miejsc: to artefakt operatora (audyt, replay, dane) —
  INV-P3 ogranicza kanał agenta, nie operatora; widok per-miejsce
  uzyskuje się kompozycją `visible_events` z tym samym serializatorem,
  bez osobnej funkcji w v1;
- ewolucja: zmiana łamiąca podnosi `version`; parser odrzuca jawnym
  błędem wersję, której nie zna.

### CLI v1

- wejście: blindy, stacki, button startowy, limit rozdań — parametry
  wywołania z udokumentowanymi domyślnymi (INV-P6) — oraz seed
  **wymagany jawnie**: CLI nie ma własnego źródła losowości ani zegara,
  determinizm jest widoczny w wywołaniu;
- agenci wybierani po nazwie z rejestru żyjącego w CLI; silnik nazw nie
  zna; v1 rejestruje agenta regułowego z POKER-8 (domyślny na obu
  miejscach) — człowiek i przyszłe modele wchodzą tym samym portem
  `Agent` przez adaptery (INV-P4, INV-P7);
- wyjście: deterministyczne podsumowanie meczu na stdout (stacki
  końcowe, liczba rozdań, powód zakończenia); `--export ŚCIEŻKA`
  zapisuje pełną historię w formacie v1; błąd wejścia → stderr
  i kod ≠ 0;
- moduł eksportu, `poker.cli` i `poker.__main__` są adapterami: żaden
  moduł silnika ich nie importuje (INV-P7) — pod testem importów.

## Uzasadnienie

- dwa kontrakty zamiast jednego: jeden problem, jedno kryterium, jeden
  rollback (konstytucja, reguła 10); błędy formatu danych są najdroższe
  do naprawy po fakcie, więc format dostaje własny audyt przed CLI;
- JSON Lines ze standard library: zero nowych zależności (decyzja 02),
  zapis i odczyt strumieniowy, naturalny format datasetów ML;
- round-trip jako kryterium bezstratności: jedyny testowalny dowód, że
  eksport niczego nie gubi i nie kłamie;
- seed wymagany jawnie: „losowy" domyślny seed wymagałby źródła
  losowości w adapterze i ukrywałby determinizm zamiast go eksponować.

## Którą gałąź (pokerroom / trener / GTO-ML) ta decyzja zamyka albo czyni droższą?

Żadnej nie zamyka; uzasadnienie per gałąź:

- **trener**: tanieje — bezstratny, wersjonowany eksport z round-trip
  to jego wejście replay; ryzykiem jest ubóstwo v1 (metadane, których
  dziś nikt nie zamówił) — ograniczone do kosztu inkrementu wersji;
- **GTO-ML**: tanieje — deterministyczne historie w JSON Lines to
  gotowy format danych treningowych;
- **pokerroom**: neutralna — zdarzenia i ich serializacja są
  N-miejscowe; heads-upowe są wyłącznie nagłówek meczu i CLI, czyli
  adapter i parametryzacja `MatchConfig`, nie rozgałęzienie rdzenia;
  przyszły pokerroom definiuje własny nagłówek i transport, rdzeń
  formatu zdarzeń współdzieli.

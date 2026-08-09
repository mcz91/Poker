# Stan bieżący produktu Poker

Wersja pakietu: 0.1.0 · ostatnie zamknięte zadanie: POKER-18
(sufit baseline'u stdlib: cechy v2, większy korpus, pomiar).

## Co istnieje

- pakiet `poker` w układzie src-layout (`src/poker/`), typowany strict
  (marker `py.typed`), wyłącznie standard library;
- `poker.cards` — 52 niemutowalne karty (13 rang × 4 kolory), pełna
  talia `FULL_DECK`; karta spoza zbioru jest błędem;
- `poker.evaluation` — klasyfikacja 5-kartowego układu do jednej z 9
  kategorii, porządek zupełny z kickerami (`HandValue`), wybór
  najlepszego układu z 5–7 kart;
- `poker.events` — niemutowalne, typowane zdarzenia cyklu rozdania
  (start z konfiguracją, seed talii, blindy, karty własne,
  flop/turn/river, akcja, showdown, zwrot nadpłaty, przyznanie puli,
  koniec); każde zdarzenie deklaruje widoczność (`Public` /
  `PrivateToSeat` / `EngineOnly`); seed żyje wyłącznie w `DeckSeeded`
  (EngineOnly) — poza zasięgiem widoku każdego miejsca;
- `poker.history` — append-only historia rozdania, zamykana zdarzeniem
  końca; API bez mutacji i usuwania;
- `poker.projection` — stan stołu (stacki, pula, board, karty per
  miejsce, faza) jako czysta projekcja sekwencji zdarzeń; replay
  i prefiksy pokryte testami, suma żetonów stała w każdym prefiksie;
- `poker.dealing` — talia i rozdanie kart deterministyczne
  z wstrzykniętego, seedowanego RNG; miejsca jako kolekcja (testy N=2
  i N=3);
- `poker.betting` — maszyna licytacji heads-up (`HeadsUpHand`):
  wskazuje miejsce na ruchu i granice legalnych akcji na każdej ulicy,
  odrzuca akcje nielegalne bez śladu w historii, egzekwuje min-raise
  (krótki all-in nie otwiera licytacji ponownie), zwraca nadpłatę
  all-ina (`UncalledBetReturned`), rozstrzyga fold bez showdownu
  i showdown ewaluatorem z kolejnością pokazywania kart; split
  z deterministyczną regułą niepodzielnej reszty (`split_pot`,
  kolejno od miejsca po lewej buttona). Uproszczenie jawne (INV-P5):
  `HeadsUpHand` wymaga dokładnie N=2 — multiway (w tym side poty)
  wymaga decyzji architekta; zdarzenia i `split_pot` pozostają
  N-miejscowe;
- `poker.views` — filtr widoczności zdarzeń i niemutowalny
  `PlayerView`: budowany wyłącznie ze zdarzeń widocznych z danego
  miejsca (własne karty, board, jawne akcje i blindy, stacki, pula,
  faza, miejsce na ruchu, granice legalnych akcji, karty jawne po
  showdownie); test przecieku sprawdza pola, repr i pełną
  serializację — karty przeciwnika i seed nieosiągalne przed
  odkryciem (zamyka OBJECTION audytu POKER-3);
- `poker.agent` — kontrakt agenta (INV-P4): protokół `Agent.decide
  (widok) -> Decision`, silnik przyjmuje dowolny obiekt spełniający
  protokół (`apply_decision`); decyzja nie może zmutować widoku ani
  historii — pod testem; pełne rozdanie rozgrywane przez dwóch
  deterministycznych agentów testowych wyłącznie na widokach;
- `poker.table` — stół i pętla meczu (`play_match`): konfiguracja
  (blindy, stacki startowe, button startowy, limit rozdań) to
  parametry (INV-P6); button rotuje, stacki przechodzą między
  rozdaniami; seedy rozdań pochodzą deterministycznie z seeda meczu;
  koniec przez bust (stack dokładnie 0) albo limit rozdań; wynik
  obserwowalny (stacki, liczba rozdań, powód) wraz z pełną sekwencją
  niemutowalnych historii rozdań; opcjonalna czysta obserwacja meczu
  rozdanie po rozdaniu (`on_hand` — callback z historią zakończonego
  rozdania, bez I/O w silniku i bez zmiany zachowania istniejących
  wywołań — pod testem); suma żetonów stała przez cały mecz
  — pod testami. Uproszczenie jawne (INV-P5): `play_match` wymaga
  dokładnie 2 miejsc — multiway to gałąź pokerroom;
- `poker.rule_agent` — agent regułowy (`RuleAgent`): czysta,
  deterministyczna funkcja widoku w decyzję, bez pamięci, I/O
  i losowości; reguły czytelne (siła ręki przez ewaluator, koszt
  sprawdzenia względem puli, granice legalnych akcji z widoku);
  progi (`RuleAgentThresholds`) są parametrem konstrukcji
  z udokumentowanym domyślnym zestawem (podbija od dwóch par, gra
  o wartość od pary, sprawdza tanio 2:1); moduł importuje wyłącznie
  widok, decyzję i ewaluator — bez silnika, historii i stołu;
- `poker.preflop` — 169 kanonicznych klas preflop (13 par, 78 suited,
  78 offsuit): mapowanie dowolnych dwóch kart do klasy (`classify`)
  i kombinacje klasy (`class_combos`: pary 6, suited 4, offsuit 12,
  suma 1326 — pod testami); importuje wyłącznie karty;
- `poker.preflop_equity` + `poker.preflop_equity_data` — macierz
  equity all-in heads-up klasa vs klasa (udział oczekiwany puli:
  wygrana + połowa splitu) jako wygenerowany moduł danych (bez I/O
  przy odczycie, INV-P1) z metadanymi metody (metoda, seed, liczba
  prób); czysta funkcja `equity(a, b)`; spójność pod testami:
  e(a,b)+e(b,a)=1 i e(a,a)=0.5 dokładnie (jednostki pół-puli
  o mianowniku będącym potęgą dwójki, przekątna i lustro
  z konstrukcji), AA najwyższa średnia przeciw polu, AA vs KK
  i AA vs losowa ręka w przedziałach odniesienia;
- `poker.preflop_sim` — deterministyczna symulacja Monte Carlo pary
  klas (RNG wstrzyknięty, seed pary pochodny od seeda macierzy);
  używana przez generator `tools/generate_preflop_equity.py`
  (komenda udokumentowana w [`README.md`](../README.md)) i test
  reprodukcji podzbioru macierzy; granice importów rodziny preflop
  (wyłącznie karty i ewaluator) strzeże test architektury;
- `poker.encoding` — rdzeń enkodowania przykładów decyzyjnych
  (b4.1, bez I/O, INV-P1): z historii rozdania dla każdej akcji
  agenta (blindy nie są decyzjami) przykład z prefiksu zdarzeń
  widocznych z miejsca decydującego bezpośrednio przed akcją
  (widoczność jak w `poker.views`): 23 cechy liczbowe v2
  (`FEATURE_NAMES` — pozycja, blindy, stacki, pula, faza, karty
  własne, board oraz od POKER-18: `hole_equity_mille` — equity
  all-in klasy kart własnych przeciw polu z macierzy preflop,
  w promilach, i `hand_category` — kategoria układu z ewaluatora na
  kartach własnych i boardzie, 0 przed flopem) i etykieta (typ
  akcji, kwota); jawne pole wersji zbioru (`DATASET_VERSION` = 2);
  granica informacyjna decyzji 05 pod testem przecieku (karty
  przeciwnika i seed nie wpływają na przykłady żadnym kanałem);
  importuje wyłącznie zdarzenia, karty, projekcję, widoczność,
  ewaluator i equity preflop — pod testem architektury;
- `poker.clone_training` + `poker.clone_weights` + `poker.clone_agent`
  — baseline behavior cloning (b4.2): deterministyczny trening
  offline w czystym stdlib (wieloklasowa regresja logistyczna na typ
  akcji, pełny batch bez losowości, standaryzacja cech w modelu)
  narzędziem `tools/train_behavior_clone.py --from-corpus` —
  łańcuch korpus → zbiór → trening w całości z manifestu korpusu
  (hiperparametry z udokumentowanymi domyślnymi, INV-P6); wagi jako
  wygenerowany moduł danych z kompletnym przepisem pochodzenia
  (stałe `CORPUS_*`: agenci, liczba meczów, seed, konfiguracja
  meczu; wersja zbioru, hiperparametry, liczba przykładów; bez I/O
  przy odczycie, INV-P1); test pochodzenia odtwarza pełny łańcuch
  wyłącznie z metadanych artefaktu i porównuje moduł bajt w bajt
  z utrwalonym, a sekwencję regeneracji dokumentuje
  [`README.md`](../README.md) (domknięcie F1 audytu POKER-15/16);
  reprodukcja treningu bajt w bajt pod testem; agent `clone`
  (rejestr CLI) — czysta
  deterministyczna inferencja portem Agent (INV-P4, INV-P8), cechy
  z widoku tą samą definicją co zbiór (`view_features`, zgodność
  trening↔gra pod testem), kwoty v1 minimum legalnym,
  deterministyczny fallback check→call→fold — nigdy decyzji
  nielegalnej (test właściwościowy na wielu seedach); importy agenta
  ograniczone do widoku, decyzji, cech i wag — pod testem
  architektury; pomiary w arenie (kryterium plastra to pomiar,
  nie kierunek wyniku — decyzja 05), serie 20 par × 100 rozdań,
  seed 7: **POKER-18 (cechy v2, korpus 100 meczów):** clone vs rule
  −281.30 BB/100, std 482.64, CI95 [−492.82, −69.77]; clone vs
  rule-aggressive −171.43 BB/100, std 535.73, CI95 [−406.22, 63.36];
  poprzedni punkt odniesienia **b4.2 (cechy v1, korpus 30 meczów):**
  clone vs rule −316.25 BB/100, CI95 [−534.35, −98.16];
- `poker.arena` — arena porównawcza agentów (rdzeń bez I/O, INV-P1):
  seria par meczów przez `play_match` na lustrzanych rozdaniach
  (duplicate — ten sam seed meczu dwukrotnie z zamianą miejsc, obie
  strony grają te same karty; identyczność kart pod testem), wynik
  pary sumą obu przebiegów; konfiguracja serii (blindy, stacki,
  button, limit rozdań, liczba par) to parametry (INV-P6), seedy par
  pochodne od seeda serii jawnym kontraktem (`series_pair_seeds`);
  raport: BB/100 agenta A, odchylenie standardowe po parach i 95%
  przedział ufności — pod testami znanych relacji (zawsze-fold
  przegrywa z regułowym całym przedziałem; agent przeciw samemu
  sobie: lustro znosi wynik do dokładnie zera) i determinizmu;
  importuje wyłącznie stół, kontrakt agenta i zdarzenia — pod testem
  architektury;
- `poker.adapters` — adaptery (INV-P7): `cli` rozgrywa mecz
  z terminala (`python -m poker.adapters.cli`, argumenty
  z udokumentowanymi domyślnymi w [`README.md`](../README.md), kod
  wyjścia 0/2) oraz serię areny flagą `--series` (raport BB/100 na
  stdout, deterministyczny dla seeda; wyklucza `--human`
  i `--export`), `export` — pełna historia meczu (łącznie ze
  zdarzeniami EngineOnly — kanał operatora) w typowanym,
  wersjonowanym JSON, a `human` — człowiek przy stole portem Agent
  (INV-P4): `cli --human MIEJSCE` gra mecz człowiek vs agent, render
  przed decyzją wyłącznie z `PlayerView` miejsca człowieka (INV-P3,
  sygnaturę renderera strzeże test architektury), wejście walidowane
  z ponownym pytaniem bez śladu w historii, koniec strumienia wejścia
  przerywa mecz niezerowym kodem; rozstrzygnięcie każdego rozdania
  (fold/showdown) renderowane na żywo natychmiast po jego końcu —
  przed pierwszą decyzją następnego rozdania (obserwacja `on_hand`
  stołu), obok zbiorczego przebiegu po meczu; karty bota i seed
  nieobecne w wyjściu terminala do showdownu, także w wyjściu na
  żywo — pod testem przecieku i testem kolejności; round-trip
  i determinizm eksportu bajt w bajt oraz odtwarzalność meczu przy
  identycznym wejściu człowieka pod testami; `registry` — rejestr
  nazwanych agentów CLI (rule, rule-aggressive), a `corpus` — korpus
  self-play (podetap b3, `cli --corpus KATALOG --matches N`): mecze
  na seedach pochodnych od seeda korpusu (`corpus_match_seeds` —
  jawny kontrakt jak w arenie), każdy mecz osobnym plikiem
  w formacie eksportu POKER-9 (format_version bez zmian), obok
  manifest z własną wersją i danymi niewyprowadzalnymi z plików;
  round-trip (`read_corpus`), determinizm bajt w bajt, niezależność
  zawartości od `--jobs` i odmowa zapisu do niepustego katalogu —
  pod testami; `dataset` — plik zbioru przykładów decyzyjnych
  (b4.1, `cli --dataset PLIK --from-corpus KATALOG`): ekstrakcja
  korpusu rdzeniem `poker.encoding` do jednego typowanego JSON
  z jawną wersją zbioru; round-trip, determinizm bajt w bajt,
  odmowa nadpisania istniejącego pliku i czytelne błędy manifestu —
  pod testami; kierunek importów od
  adapterów do silnika strzeże `tests/test_architecture.py`;
- bramka repozytorium: ruff, mypy strict, pytest — komendy wylicza
  [`README.md`](../README.md); goła `mypy` typuje `src` i `tests`
  (konfiguracja `files`), a rozjazd bramki z kontraktami czerwieni
  test zgodności `tests/test_repo_gate.py`.

## Czego nie ma

Persystencji poza plikiem eksportu, side potów multiway, struktur
turniejowych, UI/sieci/wielu stołów (pokerroom), replayu i analizy
(trener), agentów ML (bot) — gałęzie przyszłe z decyzji 01 pozostają
otwarte i niezamówione. Sandbox niezaufanych agentów to osobna
decyzja, gdy pojawi się agent spoza repozytorium.

## Następny krok

Etap (b) kierunku bot drogą operatora
([decyzja 04](README.md#dokumenty-decyzji)): proste reguły dziś,
silnik GTO/explo na ML docelowo. Podetapy b1–b3 (equity, arena,
korpus self-play) scalone; b4 wchodzi plastrami
([decyzja 05](README.md#dokumenty-decyzji)): POKER-15 (zbiór
przykładów, b4.1) i POKER-16 (baseline behavior clone, b4.2)
scalone po audycie; POKER-17 (przepis pochodzenia wag) scalony
z audytem CZYSTYM — droga b4.1–b4.2 jest kompletna i w pełni
odtwarzalna z samego repozytorium. Operator wybrał drogę pomiaru
sufitu stdlib przed b4.3: POKER-18 — cechy v2 (equity preflop,
siła układu), korpus 100 meczów, pomiar w arenie
([`docs/taskspecs/POKER-18.json`](taskspecs/POKER-18.json)) —
scalony po audycie, pomiary udokumentowane przy opisie agenta clone
wyżej. Materiał pomiarowy pod b4.3 jest kompletny: kwalifikacja
pierwszych zależności ML u operatora, na rekomendację architekta;
ulepszenia agentów wyłącznie z pomiarem w arenie (decyzja 04,
pkt 2).

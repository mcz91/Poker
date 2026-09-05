# Stan bieżący produktu Poker

Wersja pakietu: 0.1.0 · ostatnie zamknięte zadanie: POKER-50 (bieg
produkcyjny blueprintu: siatka 2 żetonów pełnego zegara pod budżetami
z POKER-47/49 — ex-post ε maks 4,720e−4 poniżej punktu odniesienia
5e−4, opcja sufitu 1536 nieuruchomiona; koszt regeneracji artefaktu
76,6 rdzenio-h; artefakt poza repozytorium, w repo artefakt kontrolny
łańcucha i bezpiecznik kosztu pod testami); POKER-48 (arena
Spin liczy na blokach trzech rotacji: hero gra każde miejsce raz przy
tej samej sekwencji kart, ramiona porównań na wspólnych seedach,
CI na blokach z bootstrapem; redukcja SD i obciążenie pozycyjne
zmierzone); POKER-49 (kotwice
orientacji osi puli 2-way, horyzont zbieżny do tolerancji zamiast do
sufitu cykli, CFR+ ważony własnym reachem, ślepota metryki na warunek
brzegowy skwantyfikowana, `tools/blueprint` pod `mypy --strict`; pakiet
`poker` nietknięty); POKER-47 (krzywa
ex-post ε vs budżet iteracji PI-FP zmierzona, budżet solvera wybrany
z pomiaru, pilot powtórzony); POKER-46 (pilot
blueprintu po DAG-u zegara w `tools/blueprint/` — koszt, ex-post ε
i różnica względem ICM zmierzone);
POKER-45 (rozliczenia żetonów Spin/jamfold wierne — suma stała, wkłady
legalne — i liczby linii Spin wymienione na zmierzone); POKER-29
(Linear CFR) zamknięty; POKER-24 (skala) częściowo — patrz
„Następny krok".

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
  przy odczycie, INV-P1); dowód pochodzenia dwustopniowy (decyzja 06,
  od POKER-20): w bramce deterministyczna reprodukcja małego łańcucha
  kontrolnego z metadanych artefaktu (seed korpusu różnicuje wagi),
  pełna regeneracja produkcyjna sekwencją z [`README.md`](../README.md)
  poza bramką, weryfikowana bajt w bajt w raporcie zadania
  zmieniającego artefakt (domknięcie F1 audytów POKER-15/16 i 19);
  agent `clone` (rejestr CLI) — czysta
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
- `poker.mlp_agent` + `poker.mlp_weights` +
  `tools/train_mlp_clone.py` — MLP-klon (c1, decyzja 06): trening
  sieci (warstwy gęste, architektura i hiperparametry parametrami
  z udokumentowanymi domyślnymi: 23→16→5, relu, lr 0.05, 300 epok,
  seed 0) narzędziem z numpy — zależność wyłącznie w `tools/`
  i extras `train` (pakiet produktu bez numpy — pod testem
  architektury); trening deterministyczny (seedowana inicjalizacja
  PCG64, pełny batch) z dwustopniowym dowodem odtwarzalności:
  reprodukcja małego łańcucha kontrolnego bajt w bajt w bramce,
  pełna regeneracja artefaktu komendami z [`README.md`](../README.md);
  wagi jako wygenerowany moduł z kompletnym przepisem pochodzenia
  (wzorzec POKER-17); agent `mlp-clone` (rejestr CLI) — inferencja
  czystym stdlib (forward pass na `math.sumprod`), cechy v2 wspólną
  definicją, kwoty i fallback regułą v1 (współdzielona
  `decision_for_action`), nigdy decyzji nielegalnej (test
  właściwościowy); **pomiary c1** (serie 20 par × 100 rozdań,
  seed 7): mlp-clone vs rule −347.62 BB/100, std 522.16, CI95
  [−576.47, −118.77]; vs rule-aggressive −354.76, std 690.80, CI95
  [−657.52, −52.01]; vs clone +33.81, std 727.96, CI95 [−285.23,
  352.86] — nieliniowość przy tych danych nie przesuwa sufitu
  klonowania (CI vs clone obejmuje zero);
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
- `poker.abstraction` — wersjonowana abstrakcja gry pod trenera
  równowagi (c2a, decyzja 07; czysty stdlib, bez I/O, INV-P1; jawne
  `ABSTRACTION_VERSION` — zmiana definicji wymaga podbicia): kubełki
  preflop ze 169 klas szeregowanych equity przeciw polu (grupowanie
  parametrem, kubełek 0 najsłabszy), kubełki postflop z kategorii
  ewaluatora (liczby kubełków per ulica parametrami, INV-P6); akcje
  abstrakcyjne (fold, check-call, bet half/pot z rejestru rozmiarów,
  all-in — zbiór parametrem) mapowane w obie strony: `decision_for`
  przycina kwoty do granic `legal_actions`, typ niedostępny ma
  deterministyczny fallback check-call — test właściwościowy na
  widokach realnych rozdań wielu seedów gra wyłącznie decyzjami
  przyjmowanymi przez maszynę licytacji; infoset deterministyczny
  wyłącznie z informacji widocznych (ulica, kubełek, pozycja,
  znormalizowany przebieg licytacji f/k/c + b/r z sufiksem H/P/A
  względem puli sprzed akcji) — przeciek pod testem (karty
  przeciwnika po showdownie i seed nie zmieniają infosetu; para
  seedów o tej samej klasie kart daje ten sam infoset), złote
  przypadki przybite z wersją; importy ograniczone (bez licytacji,
  historii, stołu i adapterów) i nikt nie importuje abstrakcji
  w tym plastrze — pod testem architektury;
- `poker.strategy_agent` + `poker.strategy_table` +
  `tools/train_mccfr.py` — strategia przybliżonej równowagi (c2b,
  decyzja 07): trener MCCFR (external sampling) w self-play na
  abstrakcji c2a, w całości seedowany (seedy rozdań i losowania przy
  węzłach przeciwnika z jednego seeda głównego; węzeł drzewa to
  seed rozdania + prefiks akcji odgrywany publicznym API licytacji)
  — czysty stdlib, numpy niepotrzebny; artefakt `strategy_table` to
  wygenerowany moduł danych (infoset → wagi akcji sumujące się
  dokładnie do `DENOMINATOR`) z kompletnym przepisem pochodzenia
  (wersja abstrakcji, seed, iteracje, kubełki, rozmiary zakładów,
  konfiguracja rozdania); dowód dwustopniowy (decyzja 06 pkt 3):
  reprodukcja małego biegu kontrolnego bajt w bajt w bramce (seed
  różnicujący), pełna regeneracja komendą z [`README.md`](../README.md)
  poza bramką; od POKER-24 trening ma deterministyczne wznowienia
  (`--checkpoint`, `--checkpoint-every`, `--resume`): losowość iteracji
  zależy wyłącznie od pary (seed, numer), więc bieg przerwany
  i wznowiony daje artefakt identyczny z ciągłym o tej samej łącznej
  liczbie iteracji — pod testami; od POKER-29 uśrednianie strategii
  jest liniowe (Linear CFR: waga iteracji t; `--averaging linear`
  domyślnie, `uniform` zostawia poprzednie sumowanie) — artefakt
  produkcyjny `strategy_table.py` nie był regenerowany; trawersacja
  schodzi w dół mutując
  rozdanie w miejscu tam, gdzie stan rodzica nie jest już potrzebny
  (100 iteracji: 13.7 s → 9.1 s); agent `mccfr` (rejestr CLI, gra też przez serwer LAN)
  — inferencja stdlib: widok → infoset → rozkład → akcja losowana
  **bez stanu** deterministyczną funkcją seeda konstrukcji i widoku
  (blake2b — wbudowany `hash()` jest solony per proces), więc replay
  i lustro areny działają bez zmian (INV-P4); kwoty i legalność przez
  odwzorowanie c2a, fallback check-call→fold dla infosetu spoza
  artefaktu — nigdy decyzji nielegalnej (test właściwościowy);
  **pomiary** artefaktu obecnego w repo (1000 iteracji, seed 7,
  20 971 infosetów; serie 20 par × 100 rozdań, seed 7 — zmierzone
  przez architekta na commicie scalającym POKER-24/25): mccfr vs
  rule −328.92 BB/100, std 779.13, CI95 [−670.39, 12.55]; vs
  rule-aggressive −504.32, std 754.30, CI95 [−834.90, −173.73];
  vs clone +15.66, std 1081.49, CI95 [−458.33, 489.64]; vs mlp-clone
  +208.73, std 984.86, CI95 [−222.90, 640.36]. Oczekiwanie decyzji 07
  pkt 6 (wynik vs rule istotnie lepszy od klonów) **nieosiągnięte**:
  punkt vs rule jest gorszy od klona liniowego (−328.92 wobec
  −281.30), a przy odchyleniu ~800–1100 BB/100 na parę 20 par nie
  rozdziela różnic tego rzędu — rozstrzygnięcie wymaga pomiaru
  o większej mocy i krzywej jakość-vs-skala
  ([decyzja 09](decisions/09-skala-mccfr-krzywa-przed-forma.md),
  POKER-27). Poprzednia wersja tego bloku opisywała artefakt sprzed
  regeneracji w POKER-24 (20 607 infosetów) — liczby wymieniono po
  reprodukcji;
- `poker.icm` + `poker.spin` — matematyka $EV turnieju 3-max (POKER-30,
  decyzja 10): ICM Malmuth–Harville (stdlib, bez importów silnika),
  WTA jako szczególny przypadek nagród `(pula, 0, …, 0)`, premia
  żetonowa (chipEV − ICM); Spin: start 25 bb (`STARTING_CHIPS=50`,
  bb=2), wypłaty 2×/3× WTA i 10× 80/20, role 3-max (button=SB),
  rozliczenie all-in z side potem i zwrotem nadpłaty, EV shove UTG
  (fold / obie fold / jeden caller z zadanym equity). **Nie otwiera
  INV-P5** — `HeadsUpHand` i `play_match` zostają przy N=2. PokerKit
  i obce solvery nie są zależnością (decyzja 10).
- `poker.jamfold` — Nash jam/fold 3-max na jednym stanie stacków
  (POKER-31, decyzja 11): fictitious play z wagą liniową t (gra
  wewnętrzna Ganzfried & Sandholm, AAMAS 2008). Equity HU z macierzy
  preflop; 3-way z pary znormalizowanej; bez blockerów. Na 25 bb WTA
  UTG jams 16.4% combo, BTN/BB call 7.3/8.3% (solve 20 iteracji,
  POKER-45); 10× 80/20 zaciska call.
  `strategy_table.py` nietknięty. Od POKER-32 `solve` zwraca też
  `values` (E[ICM po ręce] pod Nash) i `icm` (cash-out): na WTA
  przybliżona tożsamość, na 10× przy nierównych stackach V ≠ ICM.
  Od POKER-33 `DEPTHS` 25/15/10/6 bb i `jam_vs_depth`: na WTA
  UTG 14.1% → 37.9% (krótszy stack, szerszy jam; 12 iteracji,
  zmierzone po naprawie rozliczeń POKER-45 —
  [decyzja 13](decisions/13-spin-clock.md)). Od POKER-34 zegar
  w trakcie: `blinds_for_hand`, 3 ręce na poziom, `post_blinds(sb, bb)`.
- `tools/blueprint/` — **pilot blueprintu po DAG-u zegara** (POKER-46,
  [decyzja 25](decisions/25-blueprint-po-dagu-zegara-pifp-cfrplus.md));
  zależności extras `train` (numpy), pakiet `poker` nietknięty.
  `rollout_tensor.py` — deterministyczny (seedowany) tensor
  rozstrzygnięć all-in preflop: dla multizbioru trzech klas rozkład 13
  słabych porządków, Monte Carlo na prawdziwych kartach (card removal
  w losowaniu; wagi rozdania dokładne z kombinatoryki, nie z prób),
  osobny tensor par dla endgame'u HU; backend `table` (jednorazowa
  tablica wartości wszystkich C(52,5)) albo `direct` (`evaluate_five`
  wprost). `solve_grid.py` — backward induction po warstwach
  (ręka × wektor stacków), horyzont punktem stałym ostatniego poziomu
  iterowanym od ICM; gra etapowa 14 węzłów (fold / open 2.2x / jam,
  maska jam/fold ≤ 7 bb wg `poker.spin`), PI-FP z restartami przy
  trzech żywych i CFR+ w endgame HU; pula 2-way przy trzech żywych
  zawsze pełnym wektorem ICM trzech graczy; zapis atomowy warstw
  z manifestem, wznowienie bajt w bajt i wynik niezależny od liczby
  procesów (jobs 1 vs 2 vs 4) — pod testami. Trzy kryteria stopu mają
  ten sam kształt: tolerancja wiąże, sufit zabezpiecza — PI-FP (sufit 384,
  tolerancja 5e−5 z pomiaru POKER-47), CFR+ w endgame'ach HU i horyzont
  (POKER-49; tolerancja CFR+ równa tolerancji PI-FP, bo dług obu sumuje
  się w tym samym DAG-u). Średnia CFR+ jest
  ważona własnym prawdopodobieństwem dojścia — na tej średniej stoi
  gwarancja zbieżności, na której powołuje się decyzja 25 pkt 2 (pod
  testem odtwarzającym wagę z ciągu profili). Horyzont raportuje deltę
  każdego cyklu i flagę `converged`, więc „zbiegł" i „skończył się
  budżet" są rozróżnialne w artefakcie. `build_parser` bierze domyślne
  wartości CLI wprost z `GridConfig`, więc jedno i drugie nie może się
  rozjechać (pod testem). `--perturb`/`--boundary-from` liczą blueprint
  na jawnie zaburzonym warunku brzegowym (zerosumowo per stan,
  deterministycznie), a `boundary_sensitivity.py` zestawia taki bieg
  z biegiem odniesienia — ex-post ε zamraża ogon dla obu stron, więc
  bez tego pomiaru błąd horyzontu jest dla metryki niewidzialny.
  `expost.py` — ex-post best response po całym
  DAG-u (Ganzfried Alg. 6), raport V vs ICM per warstwa z
  wyszczególnieniem krótkiego BB, sanity jam/fold obok
  `poker.jamfold.solve`. `eps_curve.py` (POKER-47) — krzywa ε ex-post
  gry etapowej po sufitach iteracji na próbce stanów jednego trybu
  (najgorsze ex-post z biegu plus losowanie o jawnym seedzie; w trybach
  `hu-*` mierzy CFR+, a nie PI-FP — solverem drabinki jest ten, którym
  bieg dany tryb rozwiązuje),
  rozkład ε ex-post po DAG-u na część etapową i odziedziczoną oraz
  odczyt budżetu potrzebnego do zadanego progu. Pomiar wyłącza
  tolerancję biegu (`NO_TOLERANCE`), bo inaczej PI-FP kończy na niej,
  a nie na sufcie; jeden bieg obsługuje całą drabinkę przez bierny hak
  obserwatora w `_fp_solve` (hak nie zmienia profilu — pod testem,
  a punkt drabinki równa się co do bitu profilowi z osobnego biegu
  `_fp_solve` z tym sufitem — też pod testem). Od POKER-50 bieg ma
  **bezpiecznik kosztu** (po ≥3 policzonych warstwach ekstrapolacja
  kosztu całości ze zmierzonego tempa per tryb — tryb niezmierzony
  liczy się priorem POKER-49 przeskalowanym kalibracją maszyny; limit
  domyślnie 140 rdzenio-h, przekroczenie przerywa bieg z raportem
  tempa; limit nie wchodzi do hasha konfiguracji, a przerwanie
  i wznowienie jest bajt w bajt — pod testem), postęp per warstwa
  (czas, stany, tryby — w manifeście i na stdout; czasy nigdy
  w plikach warstw), manifest pochodzenia (wersje, model CPU, seed
  i próby tensora) oraz raport ex-post z kryterium blokującym 1e−3,
  punktem odniesienia 5e−4 i rozkładem ε per warstwa.
  `control_chain.py` przybija parametry produkcji (15 000 / 60 000 /
  seed 50 / krok 2) i utrzymuje **artefakt kontrolny łańcucha**
  w `tools/blueprint/control/` (24 KB, jedyny artefakt blueprintu
  w repo — decyzja 25 pkt 6): regeneracja tensora kontrolnego,
  łańcuch solver→ex-post na kroku 2 pokrywający wszystkie cztery
  tryby i reprodukcja podzbioru tensora produkcyjnego — wszystko pod
  testami bramki, więc zmiana kodu przesuwająca wynik zapala bramkę
  zamiast po cichu unieważnić artefakt produkcyjny. Testy
  `tests/test_blueprint_pilot.py`, w tym
  **kotwice orientacji osi**: AA wygrywa dokładnie na tej osi, na
  której ją posadzono — osobno w tensorze, w `load_tensors` (wszystkie
  sześć kolejności trójki, więc także 3-cykle), w tensorze wypłat
  liścia showdownu 3-way oraz (POKER-49) w tablicach `wt2_fold` puli
  2-way przy trzech żywych: wszystkie trzy pary osi, wszystkie sześć
  kolejności klas, jednocześnie w tensorze i u konsumenta (trzy liście
  2-way, po jednym na parę). Do tego kotwica wypłat liścia 2-way (suma
  żetonów stała, foldujący traci dokładnie swój wkład, najsilniejszy
  bierze pulę) i związanie equity `wt2_fold` z `poker.preflop_equity`
  progiem wyprowadzonym z liczb prób obu artefaktów. Kotwice powstały
  po błędzie, który przeżył pierwszy bieg pilota: tabela permutacji
  zdarzeń była zbudowana w odwrotną stronę, a że transpozycje są
  inwolucjami, psuła wyłącznie trójki klas o trzech różnych indeksach
  ustawione 3-cyklem; ta sama klasa błędu w `wt2_fold` przeżyła 343
  testy do POKER-49. Cały katalog wchodzi pod `mypy --strict`
  (`files = ["src", "tests", "tools/blueprint"]` w pyproject, wraz
  z asercją w `tests/test_repo_gate.py` — oba pliki zmieniają się
  razem, bo ten test istnieje po to, by łapać ich dryf).
- `poker.blueprint_reader` + `tools/blueprint/pack_blueprint.py` —
  **wersjonowany format binarny artefaktu blueprintu (`.bpk`) i jego
  czytnik** (POKER-51): zapis po stronie narzędzi (numpy), odczyt po
  stronie produktu w czystym stdlib (`struct`, `zlib`) — bez numpy
  i bez I/O, czytnik dostaje otwarty strumień binarny, nie ścieżkę
  (INV-P7; z tego samego powodu blok metadanych wraca jako bajty,
  bo `json` jest w silniku importem zabronionym). Dostęp swobodny:
  jeden stan to wyszukiwanie binarne klucza plus jeden blok zlib tego
  stanu, jedna wartość V to `seek` i osiem bajtów — bez ładowania
  i dekompresji całości. Węzeł spoza maski osiągalności podnosi
  `NodeUnreachable`, stan spoza siatki `StateNotFound`, warstwa
  brzegowa (samo V) `PolicyMissing` — nigdy cichy rozkład zerowy,
  bo to jest kontrakt fallbacku agenta z POKER-52. Konwerter jest
  deterministyczny (ten sam artefakt wejściowy → bajt w bajt ten sam
  plik) i sprawdza sha256 pakowanych plików wobec manifestu biegu.
  Specyfikacja bajtowa, liczby i komendy: blok POKER-51 niżej.
- `poker.blueprint_agent` — **jedyny konsument czytnika w pakiecie**
  (POKER-52): miejsce areny Spin grające rozkładami z artefaktu.
  Decyzja powstaje wyłącznie z widocznego stanu (`SeatView`: numer ręki,
  stacki, guzik, historia licytacji, klasa własnej ręki) i artefaktu:
  numer ręki wskazuje warstwę — a ręka za jej zegarem warstwę cyklu
  punktu stałego (POKER-55) — stacki po przenumerowaniu miejsc
  i kwantyzacji krokiem siatki dają stan, kontekst licytacji — slot węzła
  (przy przeskoku trybu jam/fold: bliźniaczy węzeł drzewa jam/fold);
  losowanie z odczytanego rozkładu idzie rng-iem akcji ręki, więc
  rotacje bloku i replay zostają deterministyczne. Fallback jest jawny
  i policzalny (cztery rozłączne liczniki przyczyn plus liczniki
  diagnostyczne rozjazdu areny z modelem — po POKER-54/55 zerami
  blokująco na artefakcie bramki są `out_of_order`, `order_collapse`,
  `forced_action_misses`, `mode_flip_misses` i `horizon_fallbacks`),
  a plik otwiera narzędzie, nie agent (INV-P7).
  Po POKER-55 fallback zostaje wyłącznie granicą artefaktu i dotyka
  0,850% decyzji pomiaru produkcyjnego. Liczby, liczniki i granice
  odwzorowania: bloki POKER-52, POKER-54 i POKER-55 niżej.
- LAN (pokerroom krok 1, decyzja 08): `poker.adapters.protocol` —
  typowane, wersjonowane JSON Lines (jawne pole `v`, nieznana wersja
  odrzucana po obu stronach); `poker.adapters.lan_server`
  (`TableServer`, CLI `--serve`) — jeden proces prowadzi wiele
  niezależnych stołów heads-up (kod stołu, człowiek vs człowiek albo
  vs agent z rejestru; konfiguracja meczu parametrami tworzenia
  stołu, INV-P6); człowiek zdalny wchodzi portem Agent przez most
  protokołu do istniejącego `HumanAgent` (walidacja wejścia i render
  wyłącznie z widoku miejsca — INV-P3 egzekwowane na granicy procesu,
  pod testem pełnego strumienia bajtów klienta: karty przeciwnika
  i seedy nieobecne przed showdownem); rozłączenie gracza kończy
  wyłącznie jego stół komunikatem dla przeciwnika — pod testem;
  opcjonalny eksport historii zakończonych stołów istniejącym
  formatem (round-trip pod testem); kod stołu od POKER-25 jest losowy
  (8 znaków z 31-znakowego alfabetu bez znaków mylących, ~39,6 bita)
  z seedowanego RNG adaptera — `--serve-seed` daje odtwarzalną
  sekwencję, pominięty nieodtwarzalną; kolizja kodu nie nadpisuje
  cudzego stołu, a błędny kod nie zdradza liczby ani kodów
  istniejących stołów — pod testami (domknięcie F1 audytu POKER-21);
  `poker.adapters.lan_client`
  (CLI `--connect`, `--join`, `--opponent`) — klient terminalowy;
  testy sterują serwerem i klientami w procesie (gniazda lokalne,
  porty efemeryczne, bez podprocesów i zegara ściennego); kierunek
  importów pod rozszerzonym testem architektury; silnik, licytacja,
  widoki i agenci nietknięci;
- bramka repozytorium: ruff, mypy strict, pytest — komendy wylicza
  [`README.md`](../README.md); goła `mypy` typuje `src` i `tests`
  (konfiguracja `files`), a rozjazd bramki z kontraktami czerwieni
  test zgodności `tests/test_repo_gate.py`.

## Czego nie ma

Persystencji poza plikiem eksportu, side potów w maszynie licytacji
(INV-P5, N=2 — `award_allin` w `poker.spin` liczy je tylko dla
all-inów jam/fold), zegara blindów, pełnego 3-max NL, value iteration
po stanach turnieju (zewnętrzna pętla Ganzfrieda), UI poza LAN.
ICM/WTA od POKER-30, jam/fold Nash na jednym stanie od POKER-31,
jeden backup continuation od POKER-32, zegar głębokości 25–6 bb
od POKER-33. Pełna siatka stanów istnieje wyłącznie jako artefakty
`tools/blueprint/` poza repozytorium (pilot kroku 5, POKER-46/47/49,
i bieg produkcyjny kroku 2, POKER-50) — w pakiecie `poker` jej nie ma
i żaden agent z niej nie korzysta. Od POKER-51 pakiet ma **czytnik**
tego artefaktu (`poker.blueprint_reader`), a od POKER-52 **agenta**,
który z niego gra w arenie Spin (`poker.blueprint_agent`, rejestr
`tools/run_arena.py blueprint`) — ale samego artefaktu w repozytorium
nadal nie ma (do repo wchodzi wyłącznie artefakt kontrolny łańcucha;
bramka buduje własny mini-artefakt solverem i konwerterem; dystrybucja
pełnego pliku to osobna decyzja operatora). Agenta blueprintu nie ma
w rejestrze LAN ani w `poker.adapters.registry` — gra wyłącznie w
arenie Spin (rejestr LAN jest poza kontraktem POKER-52).
Sandbox niezaufanych agentów to osobna decyzja, gdy pojawi się agent
spoza repozytorium.

## Następny krok

Etap (b) kierunku bot drogą operatora
([decyzja 04](README.md#dokumenty-decyzji)); b4 plastrami
([decyzja 05](README.md#dokumenty-decyzji)), b4.3 i droga do GTO+explo
([decyzje 06](README.md#dokumenty-decyzji) i 07). Podetapy b1–b3
i plastry c1, c2a, c2b scalone; pokerroom krok 1 (LAN,
[decyzja 08](README.md#dokumenty-decyzji)) scalony.

**POKER-24 (c2c, skala) zamknięty częściowo; sprzeciw kodera uznany**
([decyzja 09](README.md#dokumenty-decyzji)). Dostarczone, zielone
i zweryfikowane niezależnie: deterministyczne wznowienia z checkpointu
(bieg przerwany = bieg ciągły bajt w bajt, także na głębokim drzewie)
oraz przyspieszenie iteracji 1,52×. Kryterium artefaktu ≥50 000
iteracji **wycofane** jako sprzeczne z kryterium kosztu bramki z tego
samego kontraktu. Liczby po weryfikacji architekta (korygują
oszacowanie kodera): wykładnik wzrostu infosetów nie jest stały —
0,65 do ~2000 iteracji, dalej ~0,45, więc 50 000 iteracji daje
**110–145 tys. infosetów** (~18–22 MB), a nie 268 tys.; twardy sufit
przestrzeni infosetów przy abstrakcji c2a to 317 048. Taki artefakt
podnosi bramkę z 22,7 s do 56,7 s (ciepła), przy czym dominuje
`pytest` (pięciokrotny `ast.parse` wygenerowanego modułu w testach
architektury), nie `mypy`; sama memoizacja tego parsowania zbija
dzisiejszą bramkę do 16,1 s, ale przy artefakcie na skali nie
wystarcza. Artefakt w repozytorium pozostaje na 1000 iteracjach,
przetrenowany nowym trenerem (regeneracja bajt w bajt zweryfikowana).

**POKER-29 (Linear CFR) zamknięty.** Domyślne uśrednianie strategii
to waga t; `--averaging uniform` zostawia poprzednie sumowanie.
Artefakt produkcyjny nietknięty — następna regeneracja (POKER-27)
mierzy już Linear MCCFR.

**POKER-30 (ICM + Spin 3-max) zamknięty.** Własny Harville i wypłaty
2×/3×/10×; INV-P5 nietknięte; PokerKit odrzucony (decyzja 10).

**POKER-31 (jam/fold 3-max) zamknięty.** Fictitious play na jednym
stanie; AA jams / 72o folds; 10× zaciska call. INV-P5 nietknięte.

**POKER-32 (one-step continuation) zamknięty.** V¹ = E[ICM(s′)] pod
Nash. WTA ≈ ICM; 10× Short 8 bb rozjeżdża się.

**POKER-33 (zegar głębokości) zamknięty.** DEPTHS 25/15/10/6 bb.

**POKER-34 (eskalacja + MVP) zamknięty.** Zegar 1/2 → 10/20 co 3 ręce.
Stół jam/fold jest w EXPLO (/play), nie w HeadsUpHand.

**POKER-35 (tani trening jam/fold) zamknięty.** `solve` zna blinds.
Offline Nash na zegarze; 10× zaciska call. To nie jest crusher $1
i nie jest cash-MCCFR. `strategy_table` nietknięty.

**POKER-36 (exploitability jam/fold) zamknięty.** ε vs BR w BI.
16 iteracji na 3× 25 bb: ≈ 0.0006 w modelu. Always-jam ≈ 0.18.
Live vs-field UTG ~27% ≠ offline macierz ~17%. Self-ε ≠ jakość
w pokerze (decyzja 17).

**Próg 7 bb (decyzja 19).** Push/fold tylko ≤ 7 bb eff. Wyżej open
2.2x, bez flata. `JAM_FOLD_BB` w `poker.spin`.

**POKER-40 (open 2.2x first-in) zamknięty.** UTG open ≈ 23% / jam ≈ 1%
na 3× 25 bb. 3bet z drzewa bez flata nie jest polityką.

**POKER-41 (ciasny 3bet) zamknięty.** Spot vs zamrożony open, continue
55%: BTN 10.4% na 3× 25 bb (12 iteracji; zakres z kodu —
[decyzja 21](decisions/21-threebet-spot.md)). Nie 35% z no-flat Nash.

**POKER-42 (arena ROI) zamknięty.** Pomiar POKER-48
(`python tools/run_arena.py 320 3x`, jednostka: blok trzech rotacji):
tight vs always-jam −40.0% ROI (CI −48.5..−31.5).
Exploit call vs random: +18.4%, CI (+10.0, +26.9) > 0. Play woła jam
na głębokim stole exploitem.
**Adnotacja POKER-54:** te liczby zmierzył rozgrywacz sprzed naprawy
kolejności i wymuszonego wejścia za darmo. Na tych samych seedach po
naprawie: „exploit call vs random" **+18,4%** — na tych 320 seedach wynik
wyszedł co do bitu ten sam (żaden blok się nie zmienił); tight vs
always-jam **−40,0%**, czyli ta sama liczba (6 bloków innych, różnica
sparowana 0,00 pp, CI −1,50..+1,50). Werdykty bez zmian — pomiar, tabela
i komendy w bloku POKER-54.

**POKER-43 (field exploit) zamknięty.** Bez flata ciasny 3bet przegrywa
z szerokim openem. Field book: open 48% / 3bet 39% / call 48%.
Pomiar POKER-48 (`python tools/run_arena.py 320 3x`, jednostka: blok
trzech rotacji): vs always-jam +15.9% (CI +7.6..+24.3) — rozstrzygnięte
całym przedziałem; vs $1-ish fish −2.5% (CI −8.9..+3.9) — CI obejmuje
zero, oczekiwanie „bije $1-ish fisha" **nieosiągnięte** na 320 blokach
([decyzja 23](decisions/23-field-exploit.md)).
**Adnotacja POKER-54:** liczby z rozgrywacza sprzed naprawy. Na tych
samych seedach po naprawie: vs always-jam **+15,9%** co do bitu ta sama
liczba (żaden blok się nie zmienił), vs $1-ish fish **−2,8%** (różnica
sparowana −0,31 pp, CI −1,68..+1,06). Oba werdykty trzymają się tak samo,
w tym „bije $1-ish fisha" nadal nieosiągnięte — blok POKER-54.

**POKER-44 (arena HU przywrócona, spin_arena wydzielona) zamknięty.**
`poker.arena` (HU, duplicate) wraca z main; arena ROI Spin żyje w
`poker.spin_arena`; talia z `poker.dealing` (INV-P1 — wynik niezależny
od PYTHONHASHSEED); martwa ręka HU po wybiciu naprawiona; `solve`
utypowane.

**POKER-45 (rozliczenia żetonów + uczciwe liczby) zamknięty.**
Gałąź fold `utg_shove_ev` nie gubi blindów (pod WTA fold == udział
żetonowy); `_allin_two` liczy wkłady od pełnych stacków sprzed blindów;
`_three_way` każe wołającym wstawić min(stack, shove); niezmiennik sumy
żetonów stanów terminalnych pod testami (`_terminal_states`, ręka
areny); `effective_bb` odrzuca bb ≤ 0 i pusty stół. Liczby decyzji
13/15/21/22/23 wymienione na zmierzone; odwrócenie monotoniczności
jamu na 8/16 i 10/20 z audytu było artefaktem gubienia blindów — po
naprawie jam rośnie monotonicznie przez cały zegar
([decyzja 15](decisions/15-tani-trening-jamfold.md)).

**Linia Spin scalona do `main` po audycie i naprawach**
([decyzja 24](decisions/24-audyt-i-scalenie-linii-spin.md)).

**POKER-46 (pilot blueprintu po DAG-u zegara) zamknięty.** Wszystkie
liczby zmierzone na 4 rdzeniach, numpy 2.5.2, venv z extras `train`;
`PILOT` to katalog artefaktów poza repozytorium (tensor 16 MB, warstwy
6 MB — patrz decyzja 25 pkt 6). Komendy odtwarzające:

```
A  OMP_NUM_THREADS=1 python tools/blueprint/rollout_tensor.py \
       --out PILOT/tensor --trials 2000 --hu-trials 8000 --seed 7 --jobs 4
B  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
   python tools/blueprint/solve_grid.py --tensor PILOT/tensor \
       --out PILOT/grid5 --grid-step 5 --jobs 4
C  python tools/blueprint/expost.py expost --out PILOT/grid5 --jobs 4
D  python tools/blueprint/expost.py icm --out PILOT/grid5
E  python tools/blueprint/expost.py sanity --tensor PILOT/tensor
```

1. **Tensor (A).** Tablica wartości C(52,5): 25,59 s. Trójki:
   1 163,9 s przy 4 procesach dla 818 805 multizbiorów (325 z nich
   nierozdawalnych, waga 0) × 2 000 prób → **2,84 µs/próbę rdzenia**.
   Pary HU: 49,19 s dla 14 365 par × 8 000 prób (1,71 µs/próbę — dwie
   ręce zamiast trzech). Backend `direct` (`evaluate_five` na 21
   podzbiorach) to ~550 µs/próbę, czyli 190× drożej: **tablica wartości
   z `poker.evaluation` wystarcza, numba/GPU nie są potrzebne.**
   Ekstrapolacja produkcyjnych 15 000 prób/multizbiór: 8 729 s przy
   4 procesach ≈ **9,7 rdzenio-godziny**.
2. **Solver (B).** Cały bieg 3 408,1 s (56,8 min). Horyzont (punkt
   stały ostatniego poziomu): 987,1 s, **3 cykle**, delta 0,00188
   (4 437 solve'ów, 0,890 rdzenio-s/stan). 21 warstw: 8 654 stany
   w 2 417,9 s → **0,279 s/stan przy 4 procesach, 1,118
   rdzenio-s/stan**. Mieszanka trybów warstw: `deep` 253, `jamfold`
   6 798, `hu-deep` 397, `hu-jamfold` 1 206. Koszt pojedynczego stanu
   zmierzony osobno (jobs=1, mediana z 10 stanów na tryb): `deep`
   3,99 s, `jamfold` 0,87 s, `hu-deep` 0,066 s, `hu-jamfold` 0,037 s —
   suma po tej mieszance to 0,807 rdzenio-s/stan, czyli narzut forka
   i zbiórki cykli dokłada ~1,39× do kosztu w biegu równoległym.
   Iteracje: PI-FP mediana **16**, maksimum 24 (sufit `--fp-iters`);
   97,1% z 7 051 stanów 3-osobowych kończy z ε wewnętrznym ≤ 1e−3
   (`--fp-tol`), reszta wyczerpuje sufit iteracji. CFR+
   w HU stałe 128 iteracji. ε wewnętrzne (self-ε, **nie** jakość —
   decyzja 17): FP mediana 4,4e−4, maks 3,6e−3; CFR+ mediana 4,0e−6.
3. **Ex-post best response (C).** 883 s dla 8 654 stanów. W jednostkach
   puli (pula = 1): **ε max 0,00848, mediana 0,00092**, min −7e−8
   (szum f32). Punkt odniesienia decyzji 25 to 0,05% puli — mediana
   jest 1,8× wyżej, a maksimum **17× wyżej**. Dziesięć najgorszych
   stanów to wyłącznie ręce 0–3 przy ~25 bb, czyli tryb `deep`
   (14 węzłów, pełne drzewo z openem): tam 24 iteracje PI-FP nie
   wystarczają. Stany jam/fold i HU są o rząd wielkości lepsze.
   **Wyjaśnienie „bo 24 iteracje" okazało się błędne — patrz blok
   POKER-47 niżej; te liczby zastąpił bieg pod nowym budżetem.**
4. **V vs ICM (D).** Max |V − ICM| na warstwę rośnie z zegarem: 0,0031
   (ręka 0) → 0,0785 (ręka 20); średnia 0,0031 → 0,0214. Stany
   krótkiego BB (< 5 bb bieżącego poziomu): 4 327 stanów, max **0,0785**,
   średnia 0,0200. Największe rozjazdy mają kształt „jeden gracz na 5
   żetonach, dwaj z resztą" (np. ręka 15, stan 125/20/5). To ~2,6×
   więcej niż 3% puli, które Ganzfried mierzył jako błąd ICM —
   **ICM jako wartość „po ręce" jest w naszym reżimie jeszcze gorszy,
   niż zakładała decyzja 25.**
5. **Sanity vs `poker.jamfold` (E).** Równe stacki 50/50/50 przy 1/2
   (25 bb), drzewo jam/fold wymuszone, kontynuacja dokładnym ICM po
   ręce — ten sam model co `poker.jamfold`, inna maszyneria equity.
   UTG jam 15,29% vs 15,26% (zgodność klas 0,953); BTN call 4,60% vs
   3,94% (0,982); BB call vs UTG 5,24% vs 4,49% (0,988); BTN first-in
   jam 39,86% vs 39,42% (0,905); BB call vs BTN 11,02% vs 10,51%
   (0,988). Rozjazdy to wyłącznie ręce na krawędzi zakresu. Modele
   equity są zgodne bez obciążenia: kontrola na próbce 30 par (equity
   wołającego z `wt2_fold[(1, 2)]` zmarginalizowanego po klasie
   foldującego, obok `poker.preflop_equity.equity`) daje średnią
   różnicę +0,0004 i największą 0,027. Różnicę pojedynczych klas
   tłumaczy precyzja tensora: przy 2 000 prób na multizbiór błąd
   standardowy zdarzeń jednej trójki to ~1,1 punktu procentowego —
   tyle, ile dzieli sąsiednie klasy przy progu obojętności. Zgodność
   klas rośnie więc z liczbą prób, nie ze zmianą modelu; to pierwszy
   parametr do podniesienia w biegu produkcyjnym (punkt 1).
6. **DAG vs model jednej ręki.** Ten sam stan 50/50/50 czytany z warstw
   biegu B (`layer_NN.npz`, pole `sigma`, węzły `N_U_ROOT` /
   `N_T_VS_U_JAM` / `N_B_VS_U_JAM_T_FOLD`, klasy ważone
   `poker.jamfold.WEIGHTS`) obok `poker.jamfold.solve(stacks, prizes,
   button=hand % 3, iterations=80, sb, bb_amt)` z blindami tej samej
   warstwy; porównywane wyłącznie warstwy w trybie `jamfold`, bo przy
   pełnym drzewie open odbiera część zakresu jamowi. BB call vs jam
   UTG: ręka 9 (6,2 bb) 14,5% vs 16,0%; ręka 12 (5,0 bb) 27,2% vs
   20,4%; ręka 20 (2,5 bb) **71,5% vs 52,4%**. Kierunek jest zgodny
   z Ganzfriedem, ale nie monotoniczny w jedną stronę: przy głębszych
   stackach DAG bywa ciaśniejszy, a przy 2–3 bb jest wyraźnie szerszy,
   bo w DAG-u fold płaci przyszłe blindy, których ICM „po ręce" nie
   widzi. To ten sam mechanizm, który daje punkt 4.
7. **Ekstrapolacja siatki 2-żetonowej.** `grid_states(150, 2)` = 2 923
   stany; warstwy osiągalne 49 765 + horyzont 26 307 (2 923 × 3 ręce ×
   3 cykle) = **76 072 solve'y**. Przy 1,118 rdzenio-s/stan to **23,6
   rdzenio-godziny**, po korekcie na mieszankę trybów siatki 2
   (`deep` 1 198, `jamfold` 68 859, `hu-deep` 932, `hu-jamfold` 5 083)
   **24,9 rdzenio-godziny** — z tensorem 9,7 rdzenio-h razem ~35.
   Oszacowanie decyzji 25 (48,6 tys. solve'ów, ~108 rdzenio-godzin)
   było **za wysokie ~4,4× w koszcie i za niskie 1,6× w liczbie
   stanów**; budżet klasy Colab wystarcza z zapasem. **Ta ekstrapolacja
   dotyczyła budżetu 24/1e−3, który nie trzymał jakości; obowiązują
   liczby z bloku POKER-49 (~82 rdzenio-h po medianach kosztu, do ~114
   przy maksimach) i zapasu już nie ma.**

Wniosek pilota do rozstrzygnięcia przez architekta: koszt nie jest
przeszkodą, a jakość jest — ε ex-post w węzłach `deep` (0,85% puli)
jest 17× powyżej punktu odniesienia decyzji 25 i to tam, nie w koszcie,
leży kontrakt produkcyjny (więcej iteracji PI-FP albo inny solver dla
pełnego drzewa 14-węzłowego). **Rozstrzygnięte w POKER-47: wystarczył
budżet iteracji i tolerancji, inny solver nie był potrzebny, ale koszt
przestał być darmowy.**

**Rozstrzygnięcie architekta (weryfikacja niezależna 2026-08-29).**
Czerwień testu kotwicznego na kodzie sprzed poprawki odtworzona
(worktree na `b1b494b` + nowy plik testów: dwa testy konsumenta
czerwone, test tensora zielony — zgodnie z raportem); bramka, zakres
i raporty commitów sprawdzone; ε, delta ICM i sanity odczytane
z zapisanych artefaktów. Pilot **zdany**: kierunek decyzji 25
potwierdzony, bo błąd ICM „po ręce" (7,9% puli) jest 2,6× większy niż
u Ganzfrieda — model turniejowy kupuje realną przewagę, a nie
kosmetykę. Koszt schodzi z drogi (~35 rdzenio-h wobec ~108
oszacowanych; oszacowanie decyzji 25 było błędne w obie strony —
zapisane, nie zamiecione). Jakość jest jedynym wąskim gardłem
i **nie unieważnia decyzji 25**: mediana ε (0,092% puli) mieści się
w regule odczytu, a maksimum dotyczy trybu `deep` — 253 z 8 654
stanów pilota, ~1,6% siatki produkcyjnej. To ograniczony defekt
budżetu iteracji, nie porażka metody, więc następny krok jest wąski
(POKER-47), a bieg produkcyjny czeka za nim. Zgodnie z PUŁAPKĄ
o kryteriach ilościowych POKER-47 najpierw **mierzy krzywą
ε-vs-iteracje**, a dopiero z niej bierze próg — nie odwrotnie.

**POKER-47 (krzywa ε-vs-iteracje i budżet PI-FP) zamknięty; wariant (i)
kontraktu.** Liczby zmierzone na 4 rdzeniach, numpy 2.5.2, venv z extras
`train`; `PILOT/grid5` to artefakty pilota POKER-46, `PILOT/grid5n` —
bieg powtórzony pod nowym budżetem. Komendy (wszystkie z
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`):

```
F  python tools/blueprint/eps_curve.py decompose --out PILOT/grid5 \
       --worst 10 --jobs 4
G  python tools/blueprint/eps_curve.py curve --out PILOT/grid5 \
       --ladder 24,48,96,192,384,768,1536,2000 \
       --worst 10 --extra 10 --seed 47 --jobs 4
H  python tools/blueprint/eps_curve.py curve --out PILOT/grid5 --mode jamfold \
       --ladder 24,48,96,192,384,768,1536,2000 \
       --worst 10 --extra 10 --seed 47 --jobs 4 --report eps_curve_jamfold.json
I  python tools/blueprint/eps_curve.py curve --out PILOT/grid5 \
       --ladder 24,48,96,192,384,768,1536,2000 \
       --worst 3 --extra 0 --seed 47 --dense 64 --jobs 3 --report eps_curve_dense.json
J  python tools/blueprint/eps_curve.py budget --report PILOT/grid5/eps_curve.json
K  python tools/blueprint/solve_grid.py --tensor PILOT/tensor \
       --out PILOT/grid5n --grid-step 5 --jobs 4
L  python tools/blueprint/expost.py expost --out PILOT/grid5n --jobs 4
M  python tools/blueprint/expost.py icm --out PILOT/grid5n
```

1. **Diagnoza była błędna, a pomiar ją poprawił (F).** Wniosek POKER-46
   „dziesięć najgorszych stanów to `deep`, więc brakuje iteracji"
   opisywał korelację, nie przyczynę. Rozkład ε ex-post na część
   **etapową** (best response przy zamrożonej kontynuacji V tej samej
   warstwy) i **odziedziczoną** (to, co best responder dobiera sobie
   w warstwach późniejszych) daje dla dziesięciu najgorszych stanów
   medianę udziału odziedziczonego **76,2%**, a dla najgorszego stanu
   całego pilota — startowego 50/50/50 w ręce 0 — ε ex-post 0,00848
   przy ε etapowym **0,00021**, czyli **97,5% długu jest spoza tego
   stanu**. ε ex-post rośnie z trendem w stronę początku zegara
   (ręka 20: 0,00099 → ręka 0: 0,00848), ale **nie monotonicznie** —
   audyt 2026-08-29 wskazał trzy lokalne inwersje w
   `eps_decomposition.json` (ręka 1 < 2, 10 < 11, 12 < 13); warstwy 9–20 nie mają ani
   jednego stanu `deep` i każdy ich stan kończy PI-FP **na
   tolerancji**, nie na sufcie. ε ex-post jednej warstwy to więc suma
   długów wszystkich warstw za nią, a nie własność stanu. Uwaga
   pochodna: ε ex-post stanu startowego (odwiedzanego z
   prawdopodobieństwem 1) **jest** eksploatowalnością całego blueprintu
   ważoną częstością odwiedzin — indukcja wsteczna BR waży sobie stany
   sama; osobne Σ P(s)·ε(s) po ε ex-post liczyłoby ten sam dług
   wielokrotnie. Maksimum po stanach i liczba ważona odwiedzinami to
   tutaj ta sama liczba: 0,00848.
2. **Progiem wiążącym była tolerancja, nie sufit (F).** ε etapowe biegu
   POKER-46 po trybach: `deep` maks 3,56e−3, mediana 1,60e−3 (203 z 253
   stanów powyżej tolerancji, 239 z 253 na sufcie 24 iteracji);
   `jamfold` maks 1,00e−3 — **równo tolerancja `--fp-tol`, na której
   bieg się zatrzymywał** — mediana 4,24e−4, ani jeden stan powyżej
   tolerancji; `hu-deep` 7,1e−5 / 1,9e−5;
   `hu-jamfold` 8,9e−6 / 3,1e−6 (CFR+, 128 iteracji — bez zarzutu).
   6 798 stanów `jamfold` to 79% siatki i występują w **każdej**
   warstwie, więc to one dyktowały tempo narastania długu. Podnoszenie
   samego `--fp-iters` nic by nie dało: PI-FP kończył na tolerancji
   średnio po 16 iteracjach.
3. **Krzywa ε-vs-iteracje, tryb `deep` (G, J).** Próbka 20 stanów:
   dziesięć najgorszych ex-post z POKER-46 plus dziesięć losowych
   (seed 47). Tolerancja w pomiarze wyłączona, więc sufit jest jedynym
   ogranicznikiem; koszt to rdzenio-sekundy obu restartów.

   | sufit | ε maks | ε mediana | rdzenio-s/stan |
   |------:|-------:|----------:|---------------:|
   |    24 | 3,56e−3 | 1,57e−3 |   4,94 |
   |    48 | 1,45e−3 | 8,62e−4 |   9,46 |
   |    96 | 6,81e−4 | 3,18e−4 |  18,51 |
   |   192 | 3,00e−4 | 1,06e−4 |  36,51 |
   |   384 | 1,30e−4 | 3,51e−5 |  72,69 |
   |   768 | 5,11e−5 | 1,12e−5 | 145,54 |
   |  1536 | 1,36e−5 | 3,91e−6 | 292,92 |
   |  2000 | 8,97e−6 | 2,37e−6 | 382,44 |

   Nachylenie log ε vs log t: **−1,35** na całej drabince (odcinkami
   −1,09…−1,91). To szybciej niż O(1/√t) z literatury PI-FP; koszt
   rośnie liniowo z sufitem (4,94 s na 24 iteracje → 382 s na 2 000).
   Sufit potrzebny do progu (J): 1e−3 → mediana 48, maks 96; 1e−4 →
   288 / 768; 5e−5 → 384 / 1536; 1e−5 → 1536 / 2000.
4. **Krzywa `jamfold` (H).** Ten sam pomiar dla trybu, który dominuje
   siatkę: 24 iteracje dają ε maks 3,17e−4 i medianę 1,14e−4 (koszt
   2,23 rdzenio-s), 48 → 8,20e−5 / 2,85e−5 (4,26 s), 96 → 2,07e−5 /
   7,49e−6 (8,32 s), 384 → 1,30e−6 / 4,96e−7 (32,66 s). Nachylenie
   **−2,00** aż do 768 iteracji, potem krzywa siada na podłodze
   arytmetyki f32 (~1,7e−7) i przestaje spadać — to podłoga
   numeryczna, nie plateau algorytmu. Wniosek: samo obniżenie
   tolerancji poprawia `jamfold` **3,7× przy sufcie, którego nikt nie
   podniósł** (mediana 4,24e−4 przy zatrzymaniu na tolerancji po 16
   iteracjach wobec 1,14e−4 po pełnych 24) — a przy 96 iteracjach
   jest 57× lepiej.
5. **Sufit czy oscylacja? Sufit (I).** Przebieg ε po każdej z pierwszych
   64 iteracji dla trzech najgorszych stanów `deep`. Stan startowy
   50/50/50 (ręka 0): 9,1e−3 (1 iteracja) → 8,6e−4 (8) → 1,8e−4 (16) →
   6,5e−5 (24) → 1,2e−5 (48) → 6,2e−6 (64) → 3,3e−8 (2 000) —
   monotonicznie, bez piły. Najwolniejszy stan (ręka 1, 50/50/50):
   2,3e−3 (24) → 5,4e−5 (384) → 2,0e−6 (2 000), z drobnym garbem
   1,1e−3 → 1,3e−3 między 32 a 40 iteracją. Trzy testy odróżniające
   wolną zbieżność od cyklu fictitious play wypadają zgodnie: (a)
   nachylenie log-log −1,60, nigdzie nie płaskie; (b) długości runów
   identycznego best response są krótkie na początku (jedynki) i długie
   dopiero na końcu, gdy ε spadło do ~1e−8 — czyli best response
   zastyga **po** zbieżności, a nie geometrycznie rosnącymi cyklami jak
   w kontrprzykładzie Shapleya; (c) ε ostatniej iteracji jest równe ε
   najlepszej napotkanej (stosunek 1,00 w drabince gęstej, maks 1,08 na
   próbce 20 stanów, przy czym te 8% to podłoga f32 rzędu 1e−8).
   Dlatego **nie** wprowadzono wyboru argmin po napotkanych iteracjach:
   przy tej krzywej to czysty no-op, a kod na wszelki wypadek jest
   kodem bez uzasadnienia.
6. **Wybrany budżet: sufit 384 iteracji, tolerancja 5e−5** — domyślny
   w `GridConfig` i w CLI solvera. Uzasadnienie z krzywej, nie
   z założenia: dług DAG-u jest sumą ε etapowych ~21 warstw, więc żeby
   ε ex-post maks zeszło z 0,00848 poniżej 0,001 (2× punktu odniesienia
   decyzji 25, którym pozostaje 0,05% puli), typowe ε etapowe musi
   spaść ~9×; tolerancja 5e−5 wobec 1e−3 daje zapas 20×, a sufit 384
   jest miejscem, w którym mediana `deep` tę tolerancję osiąga
   (a `jamfold` osiąga ją już przy 48–96).
7. **Powtórzony pilot (K, L, M) — kryterium wariantu (i) spełnione.**
   *(Liczby biegu `grid5n`; zastąpione przez pilota POKER-49 pod
   domkniętym brzegiem i nowym CFR+ — blok niżej, pkt 5.)*
   Cały bieg 11 587,3 s (3,22 h) wobec 3 408,1 s poprzednio (**3,40×**).
   Horyzont 2 342,0 s, 3 cykle, delta 0,00209. 21 warstw: 8 654 stany
   w 9 242,1 s → **1,068 s/stan przy 4 procesach, 4,272
   rdzenio-s/stan** (poprzednio 0,279 / 1,118). Mediana iteracji PI-FP:
   `jamfold` 40, `deep` 360; 111 z 253 stanów `deep` kończy na sufcie
   384. ε etapowe po trybach: `deep` maks 1,64e−4, mediana 4,94e−5
   (było 3,56e−3 / 1,60e−3); `jamfold` maks 5,00e−5, mediana 4,17e−5
   (było 1,00e−3 / 4,24e−4). **Ex-post ε (L): maks 0,000432, mediana
   0,0000838, min −4,6e−8** (było 0,00848 / 0,00092) — maksimum 19,6×
   niżej, mediana 11,0× niżej, w 916 s. Rozbicie po trybach: `deep`
   maks 4,322e−4 (mediana 2,422e−4), `jamfold` 2,696e−4 (1,080e−4),
   `hu-deep` 2,175e−4, `hu-jamfold` 4,791e−5 (te dwie liczby są w obu
   biegach identyczne **co do bitu** — patrz niżej). **Żaden z 8 654 stanów
   nie przekracza 0,001 puli** (poprzednio 253 z 253 stanów `deep`
   i 4 514 z 6 798 `jamfold` przekraczało), a maksimum 0,043% puli jest
   **poniżej punktu odniesienia decyzji 25** (0,05%) — nie tylko poniżej
   podwojonego progu z kontraktu. Na stanach HU V i ε ex-post są w obu
   biegach identyczne co do bitu (20 z 20 warstw mających stany HU,
   największa różnica ε dokładnie 0) i tak ma być: po odpadnięciu gracza
   gra nie wraca do trzech żywych, więc pod-DAG HU (CFR+, 128 iteracji
   nietknięte) liczy się identycznie — to niezależna kontrola, że zmiana
   budżetu dotknęła wyłącznie solvera 3-osobowego. Różnica V vs ICM (M)
   zmieniła się nieznacznie na maksimum krótkiego BB: 4 327 stanów, maks
   **0,0788** (było 0,0785), średnia 0,0200, najgorszy nadal ręka 15,
   stan 125/20/5. Wcześniejsze zdanie, że „zmienić nie mogła, bo to
   własność modelu, nie dokładności solvera", było **fałszywe** (audyt
   2026-08-29): V zależy od dokładności solvera, więc |V − ICM| też —
   na warstwie 0 `max_abs_delta` urosło z 0,003116 na 0,005017, o 61%.
8. **Ekstrapolacja siatki 2-żetonowej.** *(Zastąpiona przez blok
   POKER-49 pkt 6: mediany kosztu spadły, doszedł rozrzut i pełny
   koszt zbieżnego horyzontu.)* Koszt stanu pod
   budżetem produkcyjnym (`cost`, jobs=1, mediana z 10 stanów na tryb,
   seed 47): `deep` **38,56** rdzenio-s (było 3,99), `jamfold` **2,10**
   (0,87), `hu-deep` 0,056, `hu-jamfold` 0,027 (CFR+ nietknięty).
   Ta mieszanka na siatce 5 daje 2,780 rdzenio-s/stan wobec 4,272
   zmierzonych w biegu, czyli narzut forka, zbiórki cykli i rywalizacji
   o pamięć to **1,537×** (POKER-46: 1,39×). Siatka 2-żetonowa to nadal
   76 072 solve'y (2 923 stany; warstwy 49 765 + horyzont 26 307)
   o mieszance `deep` 1 198, `jamfold` 68 859, `hu-deep` 932,
   `hu-jamfold` 5 083 → 190 708 rdzenio-s czystego solvera, po narzucie
   **81,4 rdzenio-godziny**; z tensorem 15 000 prób (9,7 rdzenio-h,
   POKER-46) razem **~91 rdzenio-godzin** wobec ~35 przy starym
   budżecie. Jakość kosztuje więc 2,6× całości i **zjada cały zapas
   względem ~108 rdzenio-godzin z decyzji 25** — budżet klasy Colab
   nadal wystarcza, ale bez marginesu, więc każde dalsze zaostrzenie
   tolerancji wymaga decyzji o koszcie.

   ```
   N  python tools/blueprint/eps_curve.py cost --out PILOT/grid5n \
          --per-mode 10 --seed 47 --jobs 1
   ```

9. **Wybór solvera — odpowiedź na korektę decyzji 25 pkt 2.** Korekta
   zostawiła rozstrzygnięcie „PI-FP czy CFR+ w trybie `deep`" pomiarowi
   POKER-47. Pomiar mówi: PI-FP **wystarcza do jakości** — schodzi
   w `deep` poniżej punktu odniesienia (0,05% puli) bez plateau
   i bez oscylacji, nachyleniem −1,35 w log-log, a w `jamfold` −2,00.
   Argument „przełącz na CFR+, bo eksploatowalność nie schodzi" nie ma
   tu podstawy faktycznej, bo schodzi. Otwarta zostaje **cena**, nie
   jakość: stan `deep` kosztuje 38,56 rdzenio-s wobec 2,10 dla
   `jamfold` (18×) i to on zjadł zapas budżetu produkcyjnego. Czy CFR+
   osiąga w `deep` to samo ε taniej, wymaga zmierzenia jego krzywej —
   tego kontrakt POKER-47 nie robił (non_goal) i żadnej alternatywy nie
   wdrożono; `eps_curve.py` mierzył wtedy wyłącznie PI-FP (od POKER-49
   mierzy też CFR+ w trybach `hu-*` — blok niżej).

Świadomie zostawione: 39 stanów `hu-deep` ma ε etapowe powyżej nowej
tolerancji (maks 7,1e−5), bo CFR+ chodzi na stałych 128 iteracjach —
nietknięty, skoro jego wkład w ex-post ε jest o rząd wielkości mniejszy
niż solvera 3-osobowego. Horyzont nadal kończy się na sufcie trzech
cykli z deltą 0,00209 > `--tail-tol`; to błąd warunku brzegowego, a nie
solvera, i w ex-post ε się nie pojawia (ogon jest zamrożony dla obu
stron) — osobna sprawa do kwalifikacji. **Oba punkty podjęte
w POKER-49 (blok niżej): CFR+ dostał średnią ważoną reachem i stop na
tolerancji, horyzont — tolerancję zamiast sufitu.**

**Rozstrzygnięcie architekta (weryfikacja niezależna 2026-08-29).**
Bramka, zakres i raporty commitów sprawdzone; czerwień ośmiu nowych
testów odtworzona na worktree z `d7239e5`; ε odczytane z artefaktu
`grid5c` (maks 4,3216e−4, mediana 8,376e−5 na tych samych 8 654
stanach). Zadanie **zdane**, a jego wynik koryguje werdykt architekta
z POKER-46: rozpoznanie „24 iteracje PI-FP nie wystarczają w trybie
`deep`" **było błędne**. Progiem wiążącym była tolerancja zbieżności
1e−3, na której kończył `jamfold` (79% siatki), a 76,2% ex-post ε
stanu to dług odziedziczony z warstw za nim — dla stanu startowego
97,5%. Diagnoza koder-vs-architekt rozstrzygnięta pomiarem na korzyść
kodera; utrwalone w PUŁAPKACH.

Uznaję też sprzeciw kodera wobec punktu 4 mojego uzupełnienia do
kontraktu (ε ważone częstością odwiedzin): przy indukcji wstecznej
best response waży stany sam, więc ε ex-post stanu startowego **jest**
eksploatowalnością całego blueprintu, a osobne Σ P(s)·ε(s) liczyłoby
ten sam dług wielokrotnie. Mój model tej metryki był błędny.

Jakość przestaje być wąskim gardłem: maksimum 0,043% puli jest poniżej
samego punktu odniesienia decyzji 25 (0,05%), nie tylko podwojonego
progu kontraktu. Wąskim gardłem staje się **koszt** (91 rdzenio-godzin
wobec ~108 z decyzji 25 — zapas zniknął) oraz **warunek brzegowy
horyzontu**: delta 0,00209 jest 4,8× większa od naszego zmierzonego
ε, a ex-post ε jej nie widzi, bo ogon jest zamrożony dla obu stron.
Nie płacimy 91 rdzenio-godzin za bieg produkcyjny stojący na
niezbieżnym warunku brzegowym — dlatego przed produkcją wchodzi
**POKER-49** (domknięcie horyzontu i endgame'ów HU), a przed nim
audyt linii blueprintu świeżym kontekstem.

**POKER-55 (agent wierny artefaktowi: tryb jam/fold przy przeskoku progu,
cykliczny odczyt horyzontu; PONOWNY pomiar BF/BG/BH) DOSTARCZONY.**
Realizacja [decyzji 28](decisions/28-adjudykacja-objection-poker52-rozjazdy-areny.md)
pkt 2c i 3. Agent przestał wołać regułę awaryjną tam, gdzie artefakt ma
odpowiedź: fallback został wyłącznie granicą artefaktu. Zmiana siedzi w
`poker.blueprint_agent` (drzewo gry, rozgrywacz, format i czytnik nietknięte),
a liczby niżej są ponownym pomiarem tych samych komend co w POKER-52, na tym
samym artefakcie produkcyjnym, tych samych seedach i N — po naprawach
POKER-54 (przyrząd) i POKER-55 (agent).

1. **Horyzont: ręka za zegarem warstw czyta warstwę cyklu punktu stałego.**
   Od ręki `CYCLE_BASE` = 18 blindy stoją na ostatnim poziomie (10/20), więc
   ręce ≥ 21 żyją w tym samym stacjonarnym cyklu 3 rąk co warstwy 18–20 i
   czytają warstwę `18 + (ręka − 18) mod 3` (21→18, 22→19, 23→20, 24→18).
   Warunek zweryfikował architekt (decyzja 28 pkt 3), a bramka trzyma go jako
   niezmiennik: `blinds_for_hand` jest stała od 18 do `HAND_GUARD` i różna
   w ręce 17 — ósmy poziom zegara albo inna długość poziomu czerwieni test,
   a nie milczy w agencie. **Role liczą się z numeru CZYTANEJ WARSTWY**, nie
   z numeru ręki areny: przy trzech żywych to bez różnicy (cykl ma 3 ręce,
   więc warstwa ≡ ręka mod 3), ale w HU guzik treningu to `sorted(żywi)[ręka
   % 2]` i `21 % 2 ≠ 18 % 2` — pomyłka posadziłaby guzika areny na etykiecie
   dużego blinda, a **żaden licznik by tego nie pokazał**, bo stan i węzeł
   istnieją. Kotwica: dla rąk 21–29 przenumerowanie sadza role warstwy na
   rolach areny, a w HU numer ręki i numer warstwy dają jawnie różne klucze.
2. **Przeskok trybu: rozkład jam/fold jest legalnym podzbiorem, nie brakiem.**
   Gdy kwantyzacja zepchnie stan pod próg 7 bb, drzewo stanu w artefakcie jest
   jam/fold, choć arena z dokładnych stacków oferuje drzewo głębokie. Agent
   czyta wtedy **bliźniaczy węzeł drzewa jam/fold** — tę samą historię, w
   której otwarcie jest jamem (`jam_fold_slot`): 2→4, 5→11, 6→12, 8→13 w
   3-max i 1→3 w HU, a węzły bez otwarcia są sobie bliźniakami. Reguła jest
   sprawdzana **chodzeniem po drzewie jam/fold gry etapowej treningu**, nie
   przynależnością do tablicy (PUŁAPKA POKER-46). Bliźniaka nie ma dokładnie
   dla drugiego wejścia roli, która otworzyła — w drzewie jam/fold odpowiedź
   na jam jest terminalna; agent w stanie jam/fold nigdy nie otwiera, więc do
   tych infosetów nie dochodzi, a `None` zostaje jawne zamiast cichego złego
   węzła. Slot środkowy znaczy „podbij" tylko w korzeniu drzewa GŁĘBOKIEGO,
   więc stan jam/fold **nigdy nie wypuszcza open**, choćby arena go dawała.
3. **Fallback tylko dla granicy artefaktu; zera są niepuste na TEJ SAMEJ
   próbce.** Na artefakcie bramki (4 przeciwników × 80 seedów, 5 770 decyzji)
   `horizon_fallbacks` = 0 i `mode_flip_misses` = 0 blokująco, przy
   `cyclic_reads` = 6 i `mode_flip_reads` = 10. Kontrola eksperymentu (lekcja
   F3 audytu POKER-54): ten sam bieg z wyłączoną regułą cyklu zapala horyzont
   **109 razy**, a z wyłączonym węzłem bliźniaczym zapala `mode_flip_misses`
   **3 razy**. Z artefaktu bramki wychodzi tylko sześć odczytów cyklicznych,
   bo mini-artefakt zna 4 klasy ze 169 i reszta kończy się na `class_misses`;
   na artefakcie produkcyjnym cały ten ruch jest odczytem.
4. **Ponowny pomiar (BF/BG/BH) — komendy i koszt.** Te same komendy co
   w POKER-52, `PROD` to katalog artefaktu produkcyjnego poza repozytorium;
   trzy procesy równolegle, ≈10 min zegara ściennego na komplet trzech
   (BH ≈7 min, BF i BG ≈10 min każdy; 4 rdzenie,
   Intel Xeon @ 2.80GHz, Python 3.13.12, venv bramki bez extras `train`):

   ```
   BF python tools/run_arena.py blueprint PROD/blueprint.bpk 10000 3x
   BG python tools/run_arena.py blueprint PROD/blueprint.bpk 10000 10x
   BH python tools/run_arena.py fallback  PROD/blueprint.bpk 10000 3x
   ```

   Mianownik BF/BG jest ten sam co w POKER-52 (bieg przepuszcza te same
   rozdania dwa razy): **1 563 234 wpisy na 781 617 różnych decyzji** —
   mniej niż 1 582 048 przed, bo wierniejszy agent gra inne decyzje i
   turnieje kończą się inaczej. Liczniki BG są identyczne co do sztuki
   z BF (nagrody wchodzą dopiero do punktacji — pod testem).

5. **Liczniki przed i po (BF, oba przebiegi razem).** Odsetki od mianownika
   danego biegu:

   | licznik | POKER-52 (przed) | po 54+55 | udział po |
   |---|---:|---:|---:|
   | `decisions` | 1 582 048 | 1 563 234 | 100% |
   | `from_artifact` | 1 545 678 | 1 549 946 | **99,150%** |
   | `cyclic_reads` | — | 10 596 | 0,678% |
   | `mode_flip_reads` | — | 4 502 | 0,288% |
   | `horizon_fallbacks` | 21 354 | **0** | 0% |
   | `grid_fallbacks` | 15 016 | 13 288 | **0,850%** |
   | `state_misses` (warstwy 1–4) | 12 826 | 13 194 | 0,844% |
   | `node_misses` | 2 190 | 94 | 0,006% |
   | `mode_flip_misses` | 1 098 | **0** | 0% |
   | `forced_action_misses` | 1 092 (wtedy `node_misses` − `mode_flip_misses`) | 94 | 0,006% |
   | `out_of_order` | 21 348 | **0** | 0% |
   | `order_collapse` | 19 458 | **0** | 0% |
   | `mass_misses` / `class_misses` / `full_layer_state_misses` / `mode_mismatches` | 0 | 0 | 0% |

   Liczby bezwzględne nie są sparowane (wierniejszy agent gra inne rozdania),
   niezależne od tego są odsetki. Sumaryczny udział fallbacku: **2,299% →
   0,850% decyzji**, w całości granica artefaktu. Rozjazdy areny z modelem,
   które POKER-54 naprawił w rozgrywaczu, są zerami także na artefakcie
   produkcyjnym.
6. **`forced_action_misses` = 94 to NIE jest pytanie o darmowy call —
   to trzecia twarz kwantyzacji.** POKER-54 zerował ten licznik na artefakcie
   bramki (krok siatki 50 nie schodzi do wysokości blindu) i tam zero jest
   prawdziwe; na siatce produkcyjnej (krok 2) zostaje 94 wpisy (0,006%),
   wszystkie tego samego wzorca — sprawdzone na próbce 156 904 decyzji, gdzie
   wypadło ich 10 z 10: **węzeł 12** (BB wobec jamu UTG po foldzie guzika),
   którego stan artefaktu nie ma, bo po kwantyzacji guzik jest all-in z
   samego blindu (`min(s_t, s_u) ≤ sb_posted`) i model wymusza mu wejście,
   a arena z dokładnego stacku pyta go i pozwala spasować (guzik ma 5 żetonów
   przy blindach 4/8, siatka 2 żetonów daje 4; albo 3 przy 2/4 → 2). Reguły
   podzbioru tu nie ma: „guzik spasował" i „guzik sprawdził" to dwa różne
   infosety o różnych pulach, więc agent uczciwie woła fallback. Naprawa
   należałaby do drzew (kwantyzacja vs maski wymuszeń), nie do agenta —
   dane do decyzji, nie decyzja.
7. **Siła po naprawach (BF, 3x WTA, N = 10 000 bloków, seedy 21…10020).**
   ROI hero w buy-inach, jednostka: blok trzech rotacji; CI normalne i
   bootstrap percentylowy (1 000 replikacji, seed 0). Kolumna „przed" to
   liczby POKER-52 (rozgrywacz sprzed POKER-54 i agent sprzed POKER-55) —
   **nie jest to różnica sparowana przed/po**, więc z zestawienia nie wolno
   czytać „agent urósł o tyle a tyle"; przedziały obu pomiarów zachodzą na
   siebie.

   | przeciwnik | ROI przed | ROI po | CI po | bootstrap po | różnica sparowana wobec `field_exploit` (CI) |
   |---|---:|---:|---|---|---|
   | `field_exploit` | +3,42% | **+5,20%** | +3,74..+6,66 | +3,70..+6,74 | **+5,20 pp** (+3,74..+6,66) |
   | `dollar_fish` | +3,92% | **+6,36%** | +4,90..+7,82 | +4,78..+7,75 | **+5,62 pp** (+3,89..+7,35) |
   | `always_jam` | +8,93% | **+8,23%** | +6,45..+10,01 | +6,51..+10,04 | **−11,65 pp** (−13,52..−9,78) |

   Kierunek rozstrzygnięć jest ten sam co w POKER-52: przeciw obu polom
   „ludzkim" ROI i różnica sparowana są dodatnie całym przedziałem, a przeciw
   `always_jam` `field_exploit` zarabia więcej całym przedziałem (blueprint
   równowagowy nie eksploatuje 100-procentowego jammera — oczekiwane).
   Zakres zdania bez zmian: `dollar_fish` to skrypt z repozytorium, nie pole
   $1 — **nie wolno** czytać z tego „bijemy field $1" (decyzja 26).
8. **Pomiar w modelu nagród artefaktu (BG, 10x 80/20).** ROI neutralne
   (trzej identyczni gracze) to +233,33%, więc liczby jako różnice sparowane
   wobec `field_exploit`: vs `field_exploit` **+12,14 pp** (CI +8,67..+15,61;
   bootstrap +8,55..+15,79; przed: +8,02 pp), vs `dollar_fish` **+13,25 pp**
   (CI +9,14..+17,35; bootstrap +8,84..+17,32; przed: +7,49 pp), vs
   `always_jam` **−27,24 pp** (CI −31,63..−22,85; bootstrap −31,56..−23,08;
   przed: −25,60 pp). Wynik nie stoi na wyborze wypłaty.
9. **BH: reguła awaryjna przestała ważyć — przewaga jest przypisywalna
   artefaktowi.** Ta sama różnica sparowana co w pkt 7 bloku POKER-52
   (agent grający check-call → fold vs ten sam agent pasujący na każdym
   fallbacku, wspólne seedy bloków, 3x, N = 10 000):

   | przeciwnik | wpływ reguły przed | wpływ reguły po | CI po | bootstrap po |
   |---|---:|---:|---|---|
   | `field_exploit` | +4,22 pp | **−0,10 pp** | −0,39..+0,19 | −0,39..+0,21 |
   | `dollar_fish` | +5,06 pp | **+0,01 pp** | −0,21..+0,23 | −0,20..+0,24 |
   | `always_jam` | −0,11 pp | **−0,07 pp** | −0,53..+0,39 | −0,55..+0,36 |

   **Werdykt (tylko tyle, ile niosą przedziały):** wpływ reguły awaryjnej
   jest we wszystkich trzech parach **nieodróżnialny od zera** (każde CI
   obejmuje zero, najdalszy kres to 0,55 pp), a przewaga nad `field_exploit`
   wynosi +5,20 pp z dolnym kresem +3,74 pp — czyli **cała różnica sparowana
   leży poza tym, co reguła może wytłumaczyć** (dolny kres przewagi, +3,74 pp,
   jest 6,8× dalszy od zera niż najdalszy kres wpływu reguły, 0,55 pp). Zastrzeżenie z pkt 5/7
   bloku POKER-52 („mierzymy parę artefakt + reguła, nie artefakt") **jest
   zdjęte**: po domknięciu horyzontu i przeskoku trybu reguła rozstrzyga
   0,850% decyzji i nie widać jej w wyniku. Czego to nadal NIE znaczy:
   ani „to jest siła GTO", ani „bijemy field $1" — pomiar jest przeciw trzem
   skryptom z repozytorium i tyle niesie.
10. **Dane do decyzji o warstwach 1–5 (dla architekta, nie decyzja).**
   Reszta fallbacku to 0,850% decyzji: 0,844% stan spoza warstwy przyciętej
   (rozkład po ręce na próbce 156 904 decyzji: 365 / 719 / 191 / 13 dla rąk
   1 / 2 / 3 / 4, od ręki 5 zero — ten sam wzorzec co w POKER-52, gdzie na
   próbce 158 698 decyzji wypadło 335 / 717 / 197 / 13)
   i 0,006% wzorzec z pkt 6. Zmierzony wpływ reguły, która te miejsca
   rozstrzyga, to pkt 9: zero w granicach CI. Cena domknięcia z decyzji 28
   pkt 2d bez zmian: pełna siatka warstw 1–5 to +8 696 stanów-warstw wobec
   49 765 biegu produkcyjnego (+17,5%, czyli ~13,4 rdzenio-h wobec 76,6).
   Decyzja 29 wymagała tego pomiaru przed pomiarami tierowymi — jest.
11. **Co trzyma bramka** (`tests/test_blueprint_agent.py`; 434 testy zielone).
   Poza niezmiennikami POKER-52/54, które zostają: cykl horyzontu stoi na
   stałych blindach od ręki 18 (test na `blinds_for_hand`, nie na komentarzu);
   przenumerowanie przy odczycie cyklicznym sadza role WARSTWY na rolach
   areny, a w HU numer ręki nie jest zamienny z numerem warstwy; bliźniaczy
   węzeł zgadza się z chodzeniem po drzewie jam/fold treningu na wszystkich
   parach z próbki (4→4, 11→11, 12→12, 13→13, 2→4, 5→11, 6→12, 8→13 oraz
   HU 0→0, 3→3, 1→3) i jest `None` dokładnie dla drugiego wejścia roli, która
   otworzyła; `horizon_fallbacks` = 0 i `mode_flip_misses` = 0 blokująco na
   artefakcie bramki, każde z kontrolą na TEJ SAMEJ próbce (109 i 3); przy
   przeskoku trybu rozkład ma dokładnie akcje legalne areny i nigdy open;
   jeden pobór z rng na decyzję na KAŻDEJ ścieżce, teraz także na odczycie
   z warstwy cyklu i na ścieżce horyzontu.

Świadomie zostawione: (1) warstwy 1–5 — dane w pkt 10, decyzja architekta;
(2) wzorzec z pkt 6 (kwantyzacja wymusza wejście, którego arena nie wymusza) —
naprawa jest zmianą drzew, nie agenta; (3) AIVAT (POKER-53) — teraz ma już
naprawiony przyrząd i artefakt mierzony bez pary z regułą; (4) rejestr LAN
agenta — nadal poza kontraktem.

**POKER-54 (rozgrywacz areny Spin: akcja od agresora i wymuszone wejście
za darmo) DOSTARCZONY.** Realizacja
[decyzji 28](decisions/28-adjudykacja-objection-poker52-rozjazdy-areny.md)
pkt 2a (z korektą audytu F1) i 2b: przyrząd pomiarowy przestał wytwarzać
infosety, których nie ma w żadnym poprawnym modelu. Drzewo gry, rozliczenia,
talia i zegar nietknięte; zmiana siedzi w `poker.spin_arena` (kolejność głosu
i wejście wymuszone) oraz w liczniku `poker.blueprint_agent`.

1. **Kolejność licytacji idzie od agresora.** `to_act` skanowało stałą
   kolejkę ról [UTG, guzik, BB], więc po jamie guzika na open UTG pytało
   UTG przed BB. `speaking_order` obraca kolejkę ról o pozycję ostatniego
   grającego: rundę otwiera lewa strona BB (blind jest ostatnim głosem przed
   pierwszą decyzją), a po przebiciu głos ma **pierwszy niedopasowany gracz
   na lewo od agresora**. Reguła obejmuje jam z SB i z BB oraz dwa żywe
   miejsca po wybiciu (kolejka HU to guzik, BB). Czerwień przed poprawką:
   kolejność pytań `[0, 1, 0, 2]` zamiast `[0, 1, 2, 0]`.
2. **Dołożenie zerowe nie jest pytaniem.** Gracz, którego dołożenie do
   najwyższego wkładu wynosi zero, wchodzi do puli automatycznie i **bez
   poboru z rng**, bo decyzji nie ma (jeden pobór na decyzję dotyczy
   decyzji; podmiana książki na agenta nadal nie przesuwa strumienia — pod
   testem liczącym pobory na siatce stacków). Takie wejście jest zawsze
   OSTATNIĄ akcją ręki (też pod testem), więc jego wpisu w `SeatView.actions`
   ani przesunięcia głosu po nim nie widać z żadnego kolejnego widoku —
   obserwowalny jest sam fakt akcji, w logu `on_action`. Warunek nie pyta
   o to, CZY stoi przebicie: najwyższym
   wkładem bywa cudzy blind (gracz all-in z samego blindu), a fold jest
   wtedy tak samo darmowy — **F1 audytu**: pierwsza wersja naprawy miała
   strażnika „stoi przebicie" i zostawiała ~70% przypadków. Zerowe dołożenie
   BEZ przebicia to wyłącznie all-in z blindu: w zamrożonym drzewie nie ma
   limpa, więc przed pierwszym podbiciem wkłady to dokładnie blindy — pod
   testem wyczerpującym po siatce stacków 0–6. Czerwienie przed poprawką:
   BB pytany po jamie o dołożenie zerowe (log `[0, 1, 2]` zamiast `[0, 1]`),
   widok z turnieju `contrib=(7, 10, 0)` przy jamie za 7 na blindzie 10 oraz
   dwie sekwencje z F1 — HU z guzikiem all-in z SB (`[2, 0, 49]` zamiast
   `[0, 0, 51]`) i 3-max z BB all-in z blindu (`[50, 49, 2]` zamiast
   `[50, 51, 0]`).
3. **Trzy liczniki rozjazdu = 0 blokująco na artefakcie bramki**
   (`test_rozjazd_areny_z_kolejnoscia_i_maska_treningu_jest_zerem`):
   `out_of_order` i `order_collapse` — dwie twarze kolejności, w pomiarze BF
   POKER-52 odpowiednio 21 348 i 19 458 wpisów — oraz nowy
   `forced_action_misses`, czyli węzeł spoza maski stanu, którego nie
   tłumaczy przeskok trybu: dokładnie `node_misses` − `mode_flip_misses`
   z pkt 3 bloku POKER-52 (tam 1 092). Zero jest niepuste NA TEJ SAMEJ
   PRÓBCE (F2/F3 audytu): ten sam bieg agenta (4 przeciwników × 80 seedów,
   5 773 decyzji) powtórzony z kolejnością sprzed POKER-54 zapala oba
   liczniki kolejności (**2 i 136**), a agent odwiedza w nim 13 z 14 węzłów
   modelu 3-max — w tym 8, 9 i 10, na których rozjazd siedział. Każdy
   licznik ma osobny test wzrostu. Spacer po drzewie gry etapowej treningu
   **zużywający całą historię ręki** nie ma już ani jednego wyjątku na 764
   widokach z turniejów (przedtem trzy rodzaje) i odwiedza wszystkie 14
   węzłów modelu 3-max oraz 4 węzły endgame'u HU.
   **Adnotacja POKER-55:** ponowny pomiar produkcyjny potwierdził zera obu
   liczników kolejności, ale `forced_action_misses` zeruje **wyłącznie na
   artefakcie bramki** — na siatce produkcyjnej zostaje 94 wpisy (0,006%)
   o innej przyczynie niż darmowy call: kwantyzacja krokiem 2 sprowadza
   krótki stack do wysokości blindu, więc model wymusza mu wejście, którego
   arena nie wymusza (blok POKER-55 pkt 6). Ta sama próbka bramki ma po
   POKER-55 **5 770 decyzji**, nie 5 773 — wierniejszy agent gra inaczej;
   kontrola starej kolejności (**2 i 136**) wychodzi na niej tak samo.
3a. **Zgodność wymuszeń sprawdzana w OBIE strony** (F2 audytu,
   `test_wymuszenie_maski_zgadza_sie_z_arena_w_obie_strony`). Sam spacer po
   historii tego nie łapie: przy pustej kolejce i masce jednoelementowej
   konsumuje wymuszony slot milcząco. Test patrzy wprost na maskę węzła, do
   którego trafia KAŻDA z 3 075 akcji areny w próbce — także ta, o którą
   rozgrywacz nie pytał (widzi ją obserwator `on_action`, bo wejście za darmo
   jest zawsze ostatnią akcją ręki). Klasy, za które odpowiada rozgrywacz, są
   zerami: nie ma pytania o dołożenie zerowe (te same 3 075 akcji na
   rozgrywaczu sprzed naprawy F1 zawierało **8 takich pytań**) i nie ma
   wejścia za darmo poza maską wymuszoną w węźle nie-korzeniu. Zostają dwie klasy, które są cechami DRZEW, nie areny, i
   dlatego mają policzone liczby zamiast zera: `capped_call` (**2**) —
   model kapuje call na stacku jamującego, a `jam` areny znaczy „cały
   stack", więc gdy duży stack sprawdza krótki all-in, arena stawia trzeciego
   gracza przed realnym dołożeniem, którego model nie ma; `root_fold`
   (**8**) — w korzeniu model daje fold graczowi pokrywającemu cudzy krótki
   blind, choć ten fold nic nie oszczędza, więc po POKER-54 to arena jest
   w tym miejscu bliżej pokera niż model. Naprawa obu jest zmianą drzewa
   (treningu i zamrożonego drzewa decyzji 27), a więc poza tym kontraktem —
   liczby są tu po to, żeby rosły widocznie.
4. **Neutralność dystrybucyjna kolejności — argument i pomiar.** Decyzja
   `SeatBooka` jest funkcją klasy ręki, trzech flag kontekstu i JEDNEGO
   poboru z rng; kolejności nie widzi. Po przebiciu każdy niedopasowany żywy
   gracz jest pytany dokładnie raz i przy tych samych flagach w obu
   kolejnościach (kto wszedł, ma `contrib = stack` i nie jest pytany
   ponownie), więc zamiana kolejności permutuje wyłącznie przypisanie
   poborów do graczy. Pobory są jednakowe i niezależne, więc rozkład łączny
   decyzji — a przez to rozkład wyników bloku — zostaje ten sam; zmieniają
   się trajektorie per seed. Pomiar A/B w bramce (300 bloków, wspólne seedy,
   `wide_call` 0,30 vs 0,55, kontrola = kolejność sprzed POKER-54): **55
   z 300 bloków zmienia trajektorię**, różnica sparowana **+0,0167 buy-ina
   (CI −0,0344..+0,0677)**, SD 0,6426 wobec 0,6340 (zgodne w granicach 2%).
   Każda z tych liczb jest asercją testu. Książki ułamkowe są tu
   konieczne: przy częstotliwościach 0/1 decyzja nie zależy od wartości
   poboru, więc permutacja strumienia nie ruszyłaby nawet trajektorii
   (PUŁAPKA z audytu POKER-52).
5. **Które pary widzą kolejność, a które nie.** `field_exploit`,
   `dollar_fish` i `always_jam` mają częstotliwości 0/1 (`range_vs_random`
   zwraca 0,0 albo 1,0), więc ich decyzja nie zależy od WARTOŚCI poboru
   i zmiana kolejności jest dla nich **bit w bit niewidoczna** — pod
   osobnym testem na trzech parach. Nie dotyczy to `hero_book`
   i `exploit_book` z `tools/run_arena.py` (częstotliwości Nash
   z `solve_open`/`solve_jf`, ułamkowe) ani `wide_call`: w parach z nimi
   różnica z pkt 6 sumuje wpływ wymuszonego wejścia i dystrybucyjnie
   neutralną permutację poborów (pkt 4). Czysto zero-jedynkowe są dwie
   pary — `field` vs `always_jam` i `field` vs `dollar_fish` — i tylko
   w nich zmierzona różnica należy w całości do wymuszonego wejścia.
6. **Skala wpływu wymuszonego wejścia na liczby POKER-42/43/48
   ZMIERZONA.** Ramię „przed" to rozgrywacz z commita `3978d7c`, ramię „po"
   to HEAD; oba grają te same książki na tych samych seedach bloków, więc
   statystyka idzie na różnicach sparowanych (N = 320 bloków, wypłata 3x —
   dokładnie konfiguracja zamkniętych liczb). Pytanie o dołożenie zerowe
   dotyczyło **2 362 z 135 024 decyzji (1,749%)** tych siedmiu par — z czego
   680 (0,504%) po przebiciu, a reszta bez niego, czyli w klasie, którą
   dołożyła naprawa F1.

   | para | ROI przed | ROI po | różnica sparowana (CI) | bloki inne |
   |---|---:|---:|---|---:|
   | `tight` vs `always_jam` | −40,00% | −40,00% | 0,00 pp (−1,50..+1,50) | 6 |
   | `exploit` vs `always_jam` | +18,44% | +18,44% | **0,00 pp** (bit w bit) | 0 |
   | `exploit` vs `wide_call` | +11,56% | +11,87% | +0,31 pp (−4,24..+4,86) | 43 |
   | `field` vs `always_jam` | +15,94% | +15,94% | **0,00 pp** (bit w bit) | 0 |
   | `tight` vs `dollar_fish` | −38,44% | −35,62% | **+2,81 pp (+0,02..+5,61)** | 18 |
   | `field` vs `dollar_fish` | −2,50% | −2,81% | −0,31 pp (−1,68..+1,06) | 5 |
   | `field` vs `wide_call` | +27,81% | +27,50% | −0,31 pp (−5,10..+4,48) | 55 |

   Pary z książką ułamkową (`wide_call`, `hero_book`, `exploit_book`) mają
   więcej „innych bloków", bo permutuje je także kolejność —
   dystrybucyjnie neutralnie (pkt 4 i 5). **Jedna para wychodzi poza zero:**
   `tight` vs `dollar_fish` przesuwa się o +2,81 pp z przedziałem
   granicznie poza zerem (dolny kres +0,02 pp) — ta para NIE jest żadną
   z zamkniętych liczb POKER-42/43, ale pokazuje, że wymuszone wejście
   potrafi ruszyć pomiar o więcej niż jego własne CI. Pozostałe sześć
   przedziałów obejmuje zero. Liczby POKER-48 przesuwają się mało: redukcja
   SD (AA) 48,57% → 48,57% (`field` vs `always_jam`, bit w bit), 58,48% →
   58,41% (`field` vs `dollar_fish`, N bloków 5 pp 1 061 → 1 071) i 37,73% →
   38,07% (`tight` vs `always_jam`, 1 898 → 1 859); obciążenie pozycyjne
   (AB, 20 000 turniejów, SE ≤ 1,04 pp) rusza się o **≤ 0,11 pp** na każdym
   z sześciu miejsc, a rozstępy 3,15 pp i 3,55 pp przechodzą w 3,18 pp
   i 3,41 pp.
7. **Werdykt dla zamkniętych liczb: wszystkie pozostają ważne, żadna teza
   się nie zmienia**; bloki POKER-42/43/48 dostają adnotację, nie
   nadpisanie, bo są pomiarem rozgrywacza sprzed naprawy. „Exploit call vs
   random +18,4%" i „field vs always-jam +15,9%" wychodzą **co do bitu te
   same** (w obu parach nie zmienił się ani jeden blok); „tight vs
   always-jam −40,0%" wychodzi **tak samo co do liczby** (6 bloków innych,
   różnica zerowa); „vs $1-ish fish −2,5%" przechodzi w −2,8%, a werdykt
   **„bije $1-ish fisha nieosiągnięte" trzyma się tak samo** (CI po
   naprawie obejmuje zero). Zastrzeżenie: para `tight` vs `dollar_fish`,
   spoza zamkniętych liczb, przesuwa się o +2,81 pp poza własne CI — więc
   „wpływ mieści się w niepewności" jest twierdzeniem o TYCH czterech
   liczbach, nie o arenie w ogóle. Decyzja o unieważnieniu albo utrzymaniu
   liczb należy do architekta; ten blok dostarcza pomiar, którego decyzja 28
   pkt 2b wymagała przed nią.

Komendy odtwarzające (z katalogu repozytorium, venv bramki;
`/tmp/poker-przed` to nieistniejąca jeszcze ścieżka poza repozytorium —
worktree ramienia „przed"). `PYTHONPATH` jest konieczny: venv ma pakiet
zainstalowany edytowalnie z `src/` HEAD-a, a ścieżka z `PYTHONPATH` ma
pierwszeństwo, więc bez niej ramię „przed" grałoby naprawionym
rozgrywaczem. BI daje ROI i CI każdego ramienia osobno narzędziem
produktu (≈19 s na wywołanie książek, ≈9 min na `seats 20000`), BJ —
różnice sparowane na wspólnych seedach i częstość pytań o dołożenie
zerowe (≈39 s):

```
BI git worktree add /tmp/poker-przed 3978d7c
   PYTHONPATH=/tmp/poker-przed/src python /tmp/poker-przed/tools/run_arena.py 320 3x
   PYTHONPATH=/tmp/poker-przed/src python /tmp/poker-przed/tools/run_arena.py sd 320 3x
   PYTHONPATH=/tmp/poker-przed/src python /tmp/poker-przed/tools/run_arena.py seats 20000 3x
   python tools/run_arena.py 320 3x
   python tools/run_arena.py sd 320 3x
   python tools/run_arena.py seats 20000 3x
BJ git show 3978d7c:src/poker/spin_arena.py > /tmp/poker-przed/spin_arena_before.py
   python - <<'EOF'
import sys; sys.path[:0] = ["/tmp/poker-przed", "tools"]
import spin_arena_before as B
from run_arena import exploit_book, hero_book
from poker.spin import PAYOUTS
from poker.spin_arena import always_jam, dollar_fish, field_exploit, play_block, wide_call
old = lambda b: B.SeatBook(b.open, b.overjam, b.vs_open, b.vs_jam, b.jf_first, b.jf_vs_jam)
tally = [0, 0]
class Watch:  # gra dokładnie jak książka, ale liczy pytania o dołożenie zerowe
    def __init__(self, book): self.book = old(book)
    def act(self, view, rng):
        tally[0] += 1
        tally[1] += view.contrib[view.seat] >= max(view.contrib)
        return B.pick(self.book, view.klass, jamfold=view.jamfold,
                      opened=view.opened, jammed=view.jammed, rng=rng)
prizes, n = PAYOUTS["3x"].prizes, 320
pairs = {"tight_vs_always_jam": (hero_book("3x"), always_jam(), 21),
         "exploit_vs_always_jam": (exploit_book("3x"), always_jam(), 21),
         "exploit_vs_wide": (exploit_book("3x"), wide_call(0.45), 22),
         "field_vs_always_jam": (field_exploit(), always_jam(), 21),
         "tight_vs_dollar": (hero_book("3x"), dollar_fish(), 24),
         "field_vs_dollar": (field_exploit(), dollar_fish(), 24),
         "field_vs_wide": (field_exploit(), wide_call(0.45), 22)}
for name, (h, v, seed) in pairs.items():
    a = [play_block(h, v, prizes, seed + i) for i in range(n)]
    b = [B.play_block(Watch(h), Watch(v), prizes, seed + i) for i in range(n)]
    d = [x - y for x, y in zip(a, b, strict=True)]
    m = sum(d) / n
    se = (sum((x - m) ** 2 for x in d) / (n - 1)) ** 0.5 / n**0.5
    print(f"{name} po {sum(a)/n-1:+.4f} przed {sum(b)/n-1:+.4f} roznica {m:+.4f} "
          f"CI {m-1.96*se:+.4f}..{m+1.96*se:+.4f} bloki {sum(1 for x,y in zip(a,b) if x!=y)}")
print(f"pytania o dolozenie zerowe: {tally[1]} z {tally[0]} decyzji "
      f"({100.0*tally[1]/tally[0]:.3f}%)")
EOF
```

Świadomie zostawione: (1) **oba drzewa mają własne rozjazdy z regułą pokera
i naprawa rozgrywacza ich nie dotyka** — to są dokładnie te dwie klasy, które
pkt 3a liczy (`capped_call` = 2, `root_fold` = 8 na 3 075 akcji próbki),
a nie zeruje. Rodzina wymuszeń modelu jest szersza, niż mówiła pierwsza wersja
tego zdania: maskę jednoelementową dostaje trzynaście węzłów 3-max i cztery HU
po tej samej regule — „mój wkład pokrywa najkrótszy stack w tej gałęzi" — raz
mierzonej wobec `sb_posted` (węzły 1, 5, 11), raz wobec `bb_posted` (2, 4, 6,
8, 12, 13), raz wobec kwoty open (3, 7, 9, 10). Rozjazd bierze się stąd, że
model kapuje call na stacku jamującego, a `jam` areny znaczy „cały stack", oraz
stąd, że w korzeniu model daje fold graczowi, któremu fold nic nie oszczędza.
Nie ma na to dowodu z pkt 3 — spacer bez wyjątku dowodził czego innego (że
ŚCIEŻKA historii istnieje), a te liczby wychodzą dopiero z bezpośredniego
sprawdzenia masek w obie strony. Naprawa należy do drzew (treningu
i zamrożonego drzewa decyzji 27), nie do rozgrywacza. (2) Ponowny pomiar
BF/BG/BH artefaktu produkcyjnego należy do POKER-55 (dopiero po komplecie
napraw mierzy się artefakt, a nie parę artefakt + reguła) — **wykonany,
blok POKER-55 wyżej**; pokazał też trzecią, wtedy nierozróżnioną twarz
wymuszeń modelu (kwantyzacja krótkiego stacku do wysokości blindu, 94 wpisy).

**POKER-52 (agent blueprintu w arenie Spin i w rejestrze CLI)
DOSTARCZONY; OBJECTION kodera rozstrzygnięty
[decyzją 28](decisions/28-adjudykacja-objection-poker52-rozjazdy-areny.md)
(aneks w TaskSpec: kryterium-proxy „fallback w zasięgu siatki = 0"
zastąpione licznikami błędów odwzorowania blokująco = 0 pod testami;
rozjazdy areny z modelem mierzone i raportowane z przyczyną, progowane po
naprawach POKER-54/55).** Arena dostała stanowy port miejsca obok
`SeatBooków`, a pakiet — agenta `poker.blueprint_agent`, który każdą
decyzję czyta z artefaktu `.bpk` czytnikiem z POKER-51. Liczby zmierzone
na 4 rdzeniach (Intel Xeon @ 2.80GHz, Python 3.13.12) w venv bramki, bez
extras `train` (agent i arena to czysty stdlib); `PROD` to katalog
artefaktu produkcyjnego poza repozytorium (decyzja 25 pkt 6). Komendy
z katalogu repozytorium, każda ≈9,5 min rdzenio-czasu:

```
BF python tools/run_arena.py blueprint PROD/blueprint.bpk 10000 3x
BG python tools/run_arena.py blueprint PROD/blueprint.bpk 10000 10x
BH python tools/run_arena.py fallback PROD/blueprint.bpk 10000 3x
```

BF i BG liczą trzy pary (blueprint vs `field_exploit`, vs `dollar_fish`,
vs `always_jam`) na blokach POKER-48, do tego różnicę **sparowaną** wobec
`field_exploit` jako hero na tych samych seedach bloków, i wypisują
liczniki fallbacków; BH mierzy koszt samej reguły fallbacku (pkt 7).
N = 10 000 bloków (30 000 turniejów na ramię) jest powyżej największego
N z tabeli mocy POKER-48 dla 5 pp (1 898 bloków); zmierzone tu SD dają
odpowiednio 1 731 / 1 709 / 2 597 bloków na 5 pp.

1. **Port miejsca, drzewo gry nietknięte.** Miejsce obsadza `SeatBook`
   albo stanowy `SeatAgent`, który dostaje `SeatView` (numer ręki,
   miejsce, guzik, stacki sprzed blindów, wkłady, akcje ręki w kolejności,
   klasa własnej ręki, trzy flagi kontekstu) i rng akcji ręki. Legalność
   ma jedno źródło prawdy: `legal_actions` zwraca dokładnie zbiór wyjść
   `pick`, a rozgrywacz odrzuca akcję spoza niego `ValueError`-em. Agent
   bierze jeden pobór z rng na decyzję — tak jak `pick` — więc podmiana
   książki na agenta nie przesuwa ani decyzji przeciwników, ani sekwencji
   kart (pod testem: szpieg grający tą samą książką daje ten sam turniej
   i te same talie co sama książka). Rozliczenia, talia i zegar nietknięte,
   liczby POKER-42/43/48 nieruszone.
2. **Trzy odwzorowania areny na model treningu.** (a) numer ręki
   turnieju = numer warstwy artefaktu; (b) stacki → klucz siatki:
   najpierw **przenumerowanie miejsc**, potem kwantyzacja największych
   reszt krokiem siatki z metadanych (kopia reguły treningu, zgodność
   z `solve_grid.quantize_stacks` pod testem). Przenumerowanie jest
   konieczne, bo trening sadza guzik na miejscu `ręka % 3` (w HU na
   `sorted(żywi)[ręka % 2]`), a arena rotuje go po żywych: bez niego UTG
   areny czytałby rozkład BB, a **żaden licznik fallbacku by tego nie
   pokazał**, bo stan i węzeł istnieją. W HU etykieta wybitego miejsca
   zostaje wolna, więc agent ma trzy równoważne klucze (ten sam układ
   sił, inne numery miejsc) i bierze pierwszy obecny w warstwie (wariant
   z etykietą wybitego miejsca areny bywa nieobecny w przyciętych
   warstwach 1–5, choć artefakt ma tę samą sytuację pod inną
   etykietą — pod testem); (c) kontekst licytacji → slot węzła
   (14 slotów przy trzech żywych, 4 w endgame'ie HU) z ról i akcji już
   podjętych, z akcją wymuszoną doliczoną miejscu all-in z samego
   blinda, którego rozgrywacz nie pyta, a trening wymusza mu wejście
   maską.
3. **Fallback: liczniki rozłączne co do przyczyny.** Bieg BF przepuszcza
   te same rozdania dwa razy (`sample_blocks` i ramię hero w
   `compare_blocks` na tych samych seedach), więc liczniki są dwukrotnością
   liczby różnych decyzji: **1 582 048 wpisów na 791 024 różnych
   decyzji agenta**. Odsetki są od tego niezależne, liczby bezwzględne
   trzeba dzielić przez dwa. Liczniki BG są **identyczne co do sztuki**, bo
   nagrody nie wchodzą do decyzji — wchodzą dopiero do punktacji.
   Z artefaktu **1 545 678 (97,701%)**; fallback horyzontu (ręka poza
   warstwami, `LayerNotFound`/`PolicyMissing`) **21 354
   (1,350%)** — co do sztuki wszystkie decyzje w rękach ≥ 21, bo
   artefakt ma warstwy 0–20 i brzegową 21 z samym V; fallback „w zasięgu
   siatki" **15 016 (0,949%)**, z tego stan spoza warstwy 12 826
   (0,811%) i węzeł spoza maski 2 190 (0,138%). Fallback obu
   rodzajów gra check-call → fold: sprawdza all-in, inaczej pasuje.
   **Adnotacja POKER-55:** te odsetki zmierzył agent sprzed odczytu
   cyklicznego i przed węzłem bliźniaczym. Po naprawach 54+55 fallback
   horyzontu i przeskok trybu są zerami, a sumaryczny udział fallbacku
   spada z 2,299% do 0,850% decyzji — pomiar i liczniki w bloku POKER-55.
4. **Kryterium aneksu (decyzja 28) SPEŁNIONE; rozjazdy areny z modelem
   zmierzone i nieprogowane.** Cztery liczniki błędów odwzorowania są
   zerami w całym pomiarze i każdy ma w bramce test, że **umie rosnąć**
   (mutacja „licznik += 0" czerwieni): `full_layer_state_misses` = 0
   (stan spoza warstwy niosącej PEŁNĄ siatkę — rośnie, gdy agent dostanie
   krok siatki inny niż krok artefaktu), `mass_misses` = 0 (rozkład
   bez masy na akcjach legalnych), `class_misses` = 0 (artefakt
   liczy wszystkie 169 klas), `mode_mismatches` = 0 (artefakt nie
   zaoferował open tam, gdzie arena go nie ma). Kryterium-proxy z kontraktu
   („licznik fallbacku w zasięgu siatki = 0") było postawione na fałszywym
   założeniu totalności odwzorowania i zostało zastąpione tymi
   niezmiennikami — uzasadnienie w decyzji 28 pkt 1. To, co zapala licznik
   fallbacku, to **rozjazdy areny z modelem treningu**, każdy z własnym
   licznikiem:

   a) **Osiągalność wczesnych warstw** (12 826 wpisów). Warstwy rąk 0–4
      nie są pełną siatką (1 / 18 / 147 / 691 / 2 143 z 2 923 stanów, blok
      POKER-50): trening dochodzi do nich własnym, już skwantowanym
      łańcuchem, a arena idzie łańcuchem dokładnym i po dwóch–trzech
      rękach bywa w stanie siatki, którego trening nigdy nie policzył.
      Pudła siedzą **wyłącznie w rękach 1–4** (rozkład na próbce
      158 698 decyzji: 335 / 717 / 197 / 13) — w ręce 5 (2 920 z 2 923
      stanów) i dalej nie ma ich wcale, bo od ręki 6 warstwa niesie pełną
      siatkę.
      Cena domknięcia: warstwy 1–5 na pełnej siatce to +8 696
      stanów-warstw wobec 49 765 w biegu produkcyjnym (+17,5%) — decyzja
      po ponownym pomiarze (decyzja 28 pkt 2d).
      → **JEDYNA pozostała przyczyna fallbacku po 54+55** (0,844% decyzji,
      ten sam rozkład po rękach); dane do decyzji w bloku POKER-55 pkt 10.
   b) **Akcja wymuszona maską treningu** (1 092 wpisów, czyli
      `node_misses` − `mode_flip_misses`). Trening maskuje akcję, która
      nic nie kosztuje (call za darmo, gdy jamujący ma nie więcej niż
      wkład już wstawiony), a arena o nią pyta — przeciwnik pasuje za
      darmo i wprowadza rękę w gałąź, której w drzewie treningu nie ma.
      → NAPRAWIONE w POKER-54 (blok wyżej; licznik tej przyczyny nazywa
      się teraz `forced_action_misses` i jest zerem blokująco na artefakcie
      bramki). Ponowny pomiar produkcyjny (POKER-55 pkt 6) pokazał, że
      w tych 1 092 wpisach siedziała jeszcze druga, wtedy nierozróżniona
      przyczyna: 94 wpisy, w których wejście wymusza dopiero KWANTYZACJA
      krótkiego stacku do wysokości blindu.
   c) **Przeskok trybu na progu 7 bb** (`mode_flip_misses` = 1 098).
      Arena liczy jam/fold z dokładnych stacków, trening ze
      skwantowanych, więc tuż nad progiem (71 żetonów przy bb = 10 to
      7,1 bb, a stan siatki obok ma 70, czyli 7,0 bb) stan artefaktu
      jest jam/fold i nie ma węzłów drzewa głębokiego. Rozjazd jest
      **jednostronny**: progi 7 bb wypadają na parzystych liczbach
      żetonów, a kwantyzacja krokiem 2 przesuwa stack o jeden — może
      więc zepchnąć stan pod próg, ale nie nad. Stąd `mode_mismatches`
      = 0 przy `mode_flip_misses` = 1 098. → odwzorowanie agenta
      w POKER-55 (decyzja 28 pkt 2c): agent czyta bliźniaczy węzeł drzewa
      jam/fold i licznik jest zerem, a odczyty przeskoku trybu (4 502
      w BF) mają własny `mode_flip_reads`.
   d) **Kolejność licytacji po ponownym otwarciu — DWIE twarze, dwa
      liczniki.** Gdy BTN jamuje na open UTG, `to_act` pyta najpierw UTG,
      a dopiero potem BB; trening (i reguła „akcja idzie od agresora")
      pyta najpierw BB (węzeł 8), a UTG dopiero po nim.
      **`out_of_order` = 21 348 (1,349%)**: decyzja UTG, której
      infoset nie istnieje w artefakcie — agent czyta gałąź „BB
      spasował" (węzeł 9), bo tam pula modelu zgadza się z pulą areny
      w chwili decyzji. **`order_collapse` = 19 458 (1,230%)**: ta
      sama usterka widziana od strony BB — BB pytany PO odpowiedzi UTG
      czyta węzeł 8, który tej odpowiedzi nie zna, więc dwa różne
      infosety areny (UTG spasował / UTG sprawdził) czytają jeden węzeł
      artefaktu, a pula areny różni się od puli modelu. Razem rozjazd
      kolejności obejmuje **40 806 wpisów (2,579%)** —
      **nie 1,349%, jak podawała pierwsza wersja tego bloku**: druga twarz
      była wtedy nieliczona i opisana fałszywym zdaniem o zgodności puli
      (korekta z audytu POKER-52, decyzja 28 pkt 2a KOREKTA).
      → NAPRAWIONE w POKER-54 (blok wyżej): poprawna kolejność nie
      wytwarza żadnej z tych twarzy, oba liczniki są zerami blokująco.

   Bramka trzyma, że rozjazdy są dokładnie tych rodzajów: spacer po
   drzewie gry etapowej z `solve_grid` musi ZUŻYĆ całą historię ręki,
   a każde wejście z historią niezużytą albo z kolejnością sprzeczną
   z modelem musi mieć licznik.
5. **Siła na rotacjach POKER-48 (BF, wypłata 3x WTA, N = 10 000
   bloków, seedy 21…10020).** ROI hero w buy-inach, jednostka: blok
   trzech rotacji; obok CI normalnego bootstrap percentylowy (1 000
   replikacji, seed 0):

   | przeciwnik | ROI blueprintu | CI | bootstrap | ROI `field_exploit` | różnica sparowana (CI) |
   |---|---:|---|---|---:|---|
   | `field_exploit` | **+3,42%** | +1,96..+4,88 | +1,89..+4,96 | +0,00% | **+3,42 pp** (+1,96..+4,88) |
   | `dollar_fish` | **+3,92%** | +2,47..+5,37 | +2,38..+5,33 | +0,82% | **+3,10 pp** (+1,38..+4,82) |
   | `always_jam` | **+8,93%** | +7,15..+10,71 | +7,17..+10,70 | +19,78% | **−10,85 pp** (−12,70..−9,00) |

   Co te przedziały niosą (decyzja 26: nie twierdzimy więcej): przeciw
   obu polom „ludzkim" ROI jest **dodatni całym przedziałem**, a różnica
   sparowana wobec `field_exploit` na wspólnych seedach — też. Przeciw
   `always_jam` jest odwrotnie: blueprint zarabia, ale `field_exploit`
   zarabia **więcej całym przedziałem** — równowagowy blueprint nie
   eksploatuje 100-procentowego jammera, bo nie ma po czym; to jest
   oczekiwane i zmierzone, nie usterka. **Czego z tej tabeli czytać NIE
   wolno: że to jest siła samego artefaktu** — pkt 7 pokazuje, że zmiana
   reguły fallbacku (2,3% decyzji) przesuwa te same liczby o więcej, niż
   wynosi cała przewaga nad `field_exploit`. Mierzymy PARĘ (artefakt +
   reguła awaryjna), a nie artefakt. Drugie ograniczenie zakresu:
   `dollar_fish` to skrypt z repozytorium, nie pole $1 — z tych liczb
   **nie wolno** czytać „bijemy field $1".
   **Adnotacja POKER-55:** te liczby zmierzył rozgrywacz sprzed POKER-54
   i agent sprzed POKER-55; zastrzeżenie „mierzymy PARĘ artefakt + reguła"
   jest **zdjęte ponownym pomiarem** (blok POKER-55 pkt 7 i 9: reguła
   rozstrzyga 0,850% decyzji, a jej wpływ jest nieodróżnialny od zera).
   Zakaz z decyzji 26 („bijemy field $1") obowiązuje tak samo.
6. **Pomiar w modelu nagród artefaktu (BG, wypłata 10x 80/20).** Bieg
   produkcyjny liczył nagrody (0,8; 0,2; 0), czyli dokładnie 10x — więc
   dopiero ten pomiar jest **w modelu**, a 3x jest poza nim. ROI
   neutralne (trzej identyczni gracze dzielą pulę 10 buy-inów) wynosi tu
   **+233,33%**, więc liczby podaję jako odchylenie od niego i jako
   różnicę sparowaną: vs `field_exploit` **+8,02 pp** (CI +4,56..+11,48;
   bootstrap +4,41..+11,80), vs `dollar_fish` **+7,49 pp** (CI
   +3,42..+11,57; bootstrap +3,07..+11,59), vs `always_jam` **−25,60
   pp** (CI −29,97..−21,23; bootstrap −29,85..−21,50).
   Kierunek i rozstrzygnięcia są te same co przy 3x, więc wynik nie
   stoi na wyborze wypłaty — a zastrzeżenie z pkt 7 obowiązuje tak samo.
   **Adnotacja POKER-55:** ponowny pomiar w bloku POKER-55 pkt 8.
7. **Reguła fallbacku waży więcej niż zmierzona przewaga (BH) — to jest
   najważniejsze zastrzeżenie do pkt 5.** Fallback dotyka 2,299%
   decyzji, więc pytanie „czy mierzymy blueprint, czy regułę awaryjną"
   dostaje liczbę: różnica sparowana między agentem grającym
   check-call → fold a tym samym agentem pasującym w każdym takim
   miejscu, wspólne seedy bloków, wypłata 3x, N = 10 000: vs
   `field_exploit` **+4,22 pp** (CI +3,71..+4,73; bootstrap
   +3,69..+4,75), vs `dollar_fish` **+5,06 pp** (CI +4,56..+5,56;
   bootstrap +4,55..+5,54), vs `always_jam` **−0,11 pp** (CI
   −0,54..+0,32; bootstrap −0,55..+0,29). Wprost: z regułą „zawsze
   pasuj" ROI tego samego artefaktu wynosi −0,80% vs `field_exploit`
   i −1,14% vs `dollar_fish` — czyli **cała przewaga z pkt 5 mieści
   się we wpływie reguły**, choć reguła rozstrzyga o 2,299% decyzji.
   Wniosek dla czytającego pkt 5: **nie wolno** przypisać tej przewagi
   strategii z artefaktu, dopóki horyzont zegara nie jest domknięty
   (domknięcie horyzontu: decyzja 28 pkt 3, wchodzi w POKER-55, i dopiero
   tamten pomiar mierzy artefakt). Przeciw `always_jam` reguła
   nic nie zmienia (przedział obejmuje zero), bo tam turnieje kończą się
   przed horyzontem.
   **Adnotacja POKER-55: warunek tego wniosku jest spełniony i pomiar
   powtórzony** — po domknięciu horyzontu i przeskoku trybu wpływ reguły
   spada do −0,10 pp (CI −0,39..+0,19) vs `field_exploit` i +0,01 pp
   (CI −0,21..+0,23) vs `dollar_fish`, czyli do zera w granicach CI, przy
   przewadze sparowanej +5,20 pp (dolny kres +3,74). Werdykt i pełna
   tabela: blok POKER-55 pkt 9.
8. **Kotwica krzyżowa decyzji 27 pkt 4 (dług wymagalny od POKER-48)
   SPŁACONA i zielona.** Test porównuje rozliczenie ręki heads-up
   w `spin_arena` z `HeadsUpHand` przy **identycznych kartach**
   (talia areny jest przekładem rozdania silnika) i identycznych
   decyzjach, na wszystkich sześciu liniach zamrożonego drzewa (fold,
   jam/fold, open 2.2x, 3bet-jam, call) × 25 seedów × 2 poziomy blindów
   × 3 pary stacków × 3 pozycje wybitego miejsca — **ze showdownem
   włącznie**. Rozjazdu nie ma; test czerwienieje na mutacji kwoty open
   o jeden żeton. Nierozstrzygnięte: reszta niepodzielnej puli przy
   remisie (linie kotwicy nie wygenerowały split potu o nieparzystej
   puli, więc tej reguły kotwica nie sprawdza).
9. **Co trzyma bramka (`tests/test_blueprint_agent.py`,
   `tests/test_spin_arena.py`, `tests/test_architecture.py`).** Artefakt
   testów powstaje w bramce: solver liczy bieg na przestrzeni stanów
   areny (150 żetonów, start 50/50/50, pełny zegar `LEVELS`) przy siatce
   50 żetonów i czterech klasach tensora kontrolnego z repo, konwerter
   pakuje go do `.bpk` — **bramka nie dotyka artefaktu produkcyjnego**.
   Pod testem: port nie zmienia przebiegu ręki (szpieg = książka);
   kwantyzacja zgodna z regułą treningu i zachowująca sumę oraz żywych;
   przenumerowanie sadza role treningu na rolach areny (mutacja rotacji
   w drugą stronę czerwieni); slot węzła zgodny z **chodzeniem po
   drzewie** gry etapowej z `solve_grid` (samo sprawdzanie przynależności
   przepuszcza przestawioną tablicę — PUŁAPKA POKER-46; walk łapie
   zarówno transpozycję, jak i 3-cykl); żadna decyzja spoza
   `legal_actions` (właściwość na wielu seedach + `ValueError`
   rozgrywacza); liczniki fallbacku rozłączne co do przyczyny
   i policzalne — każdy licznik kryterium aneksu ma test, że **umie
   rosnąć**, obok asercji zera tam, gdzie kryterium tego wymaga;
   rozłączność obu twarzy rozjazdu kolejności; jeden pobór z rng na
   decyzję na KAŻDEJ ścieżce (z artefaktu i na każdym fallbacku);
   normalizacja rozkładu po przycięciu do akcji legalnych; pola widoku
   (zegar, guzik, wkłady) wobec zegara i rotacji areny;
   check-call → fold poza horyzontem; determinizm w procesie i między
   procesami (PYTHONHASHSEED); identyczność kart między rotacjami bloku
   z agentem w składzie; rejestr CLI z liczbami i licznikami; importy
   agenta wypisane (czytnik, `poker.spin`, model stanu areny — bez
   silnika zdarzeniowego, adapterów, `tools`, numpy i I/O) oraz kierunek
   portu (arena nie zna agenta).

Świadomie zostawione: (1) fallback horyzontu (1,350% decyzji,
pkt 3) kosztuje tyle, ile mówi pkt 7; warunek jego domknięcia („ręka ≥ 21
czyta warstwę 18 + (ręka − 18) mod 3") architekt **zweryfikował**
(decyzja 28 pkt 3: blindy stałe od ręki 18, więc ręce ≥ 21 żyją w tym
samym cyklu punktu stałego) — **zrobione w POKER-55** (licznik
`cyclic_reads`, `horizon_fallbacks` = 0 blokująco); kontrakt POKER-52
kazał w tym miejscu wołać fallback, więc wtedy tak było; (2) AIVAT (POKER-53) — przesunięty za naprawy
przyrządu (decyzja 28 pkt 4); (3) rejestr LAN agenta — poza kontraktem;
(4) próg czasu odczytu stanu z POKER-51 nadal nieustalony: pomiar 10 000
bloków to ≈9,5 min rdzenio-czasu na komendę przy 791 024 różnych
decyzjach agenta, więc odczyt nie jest wąskim gardłem areny i progu nie
potrzebuje.

**POKER-51 (format binarny blueprintu i czytnik stdlib).** Artefakt
solvera (warstwy `.npz` + `solve_manifest.json`) dostaje wersjonowany
format `.bpk` z dostępem swobodnym per stan i czytnik w pakiecie
produktu. Konwerter: `tools/blueprint/pack_blueprint.py` (numpy);
czytnik: `src/poker/blueprint_reader.py` (czysty stdlib). Liczby
zmierzone na 4 rdzeniach (Intel Xeon @ 2.80GHz, Python 3.13.12,
numpy 2.5.2, venv z extras `train`); `PROD` i `PILOT` to katalogi
artefaktów poza repozytorium.

```
BA python tools/blueprint/pack_blueprint.py pack \
       --run PROD/grid2 --out PROD/blueprint.bpk
BB python tools/blueprint/pack_blueprint.py bench \
       --file PROD/blueprint.bpk --samples 2000 --sweep
BC mkdir -p PILOT/grid5d_raw
   cp PILOT/grid5d/layer_*.npz PILOT/grid5d/boundary.npz \
      PILOT/grid5d/solve_manifest.json PILOT/grid5d_raw/
   python -c 'import json,sys;from pathlib import Path;p=Path(sys.argv[1]);\
m=json.loads(p.read_text());m["config"].setdefault("cost_limit_core_hours",140.0);\
p.write_text(json.dumps(m,indent=2,sort_keys=True,ensure_ascii=False)+"\n")' \
       PILOT/grid5d_raw/solve_manifest.json
BD python tools/blueprint/pack_blueprint.py requantize \
       --run PILOT/grid5d_raw --out PILOT/grid5d_q8 --packed PILOT/grid5d.bpk
BE python tools/blueprint/expost.py expost --out PILOT/grid5d_raw --jobs 3
   python tools/blueprint/expost.py expost --out PILOT/grid5d_q8  --jobs 3
```

BC nie jest ozdobnikiem: manifest biegu `grid5d` powstał przed POKER-50
i nie ma pola `cost_limit_core_hours`, więc `expost` na oryginale pada
`KeyError` w `config_from_dict`. Pole jest bezpiecznikiem kosztu solvera
i do ex-post nie wchodzi; uzupełnia się je **w kopii roboczej**, a `BD`
przenosi ten sam manifest na stronę skwantowaną — więc obie strony
porównania mają identyczną konfigurację, a oryginał (razem ze swoim
raportem ex-post z POKER-49) zostaje nietknięty.

1. **Specyfikacja z dokładnością do bajtów.** Wszystko little-endian,
   sekcje wyrównane do 8 bajtów, bez znaczników czasu. Układ pliku:
   nagłówek → metadane → katalog warstw → sekcje warstw rosnąco po
   ręce. Struktury `struct` żyją w `poker.blueprint_reader`
   (`HEADER_STRUCT`, `LAYER_STRUCT`, `BLOCK_INDEX_STRUCT`) i konwerter
   importuje je stamtąd — jedno źródło układu bajtowego, nie dwa.

   **Nagłówek, 128 B od offsetu 0:**

   | ofs | dł | pole |
   |----:|---:|------|
   | 0 | 8 | magia `POKERBP1` |
   | 8 | 2 | wersja formatu, uint16 (dziś **1**) |
   | 10 | 2 | bity kwantyzacji, uint16 (8 albo 16) |
   | 12 | 4 | liczba klas preflop, uint32 (produkcja: 169) |
   | 16 | 4 | liczba warstw, uint32 |
   | 20 | 4 | liczba slotów węzłów, uint32 (14) |
   | 24 | 8 | offset metadanych, uint64 |
   | 32 | 8 | długość metadanych po kompresji, uint64 |
   | 40 | 8 | długość metadanych przed kompresją, uint64 |
   | 48 | 8 | offset katalogu warstw, uint64 |
   | 56 | 8 | liczba stanów w pliku, uint64 |
   | 64 | 8 | długość pliku, uint64 |
   | 72 | 32 | **sha256 konfiguracji biegu**, surowe bajty |
   | 104 | 24 | rezerwa (zera) |

   **Metadane** — `zlib(JSON UTF-8)`, JSON kanoniczny (`sort_keys`, bez
   spacji). Niosą **kopię całego manifestu biegu** (`run_manifest`:
   konfiguracja, `config_hash`, `tensor_sha256`, pochodzenie —
   wersja Pythona i numpy, model CPU, seed i liczby prób tensora,
   opis warunku brzegowego, postęp per warstwa), opis kwantyzacji
   (`format`: wersja, bity, skala, zapisane sloty `[0, 1]`, slot
   z dopełnienia `2`, metoda `largest-remainder`) oraz `source_sha256`
   — sumy plików faktycznie spakowanych, policzone przez konwerter
   i skonfrontowane z manifestem (rozjazd = błąd zapisu, nie cichy
   artefakt). Czytnik oddaje ten blok jako bajty; parsowanie należy do
   konsumenta, bo silnik nie importuje `json`.

   **Katalog warstw** — po jednym rekordzie 48 B na warstwę, rosnąco
   po numerze ręki:

   | ofs | dł | pole |
   |----:|---:|------|
   | 0 | 4 | numer ręki, uint32 |
   | 4 | 4 | liczba stanów warstwy, uint32 |
   | 8 | 1 | `has_sigma`: 1 = warstwa niesie strategię, 0 = samo V |
   | 9 | 1 | liczba miejsc, uint8 (3) |
   | 10 | 6 | rezerwa (zera) |
   | 16 | 8 | offset tablicy kluczy stanów, uint64 |
   | 24 | 8 | offset tablicy V, uint64 |
   | 32 | 8 | offset indeksu bloków, uint64 (0 gdy `has_sigma`=0) |
   | 40 | 8 | offset obszaru bloków, uint64 (0 gdy `has_sigma`=0) |

   Warunek brzegowy biegu (`boundary.npz`) wchodzi jako warstwa
   o numerze `n_hands` z `has_sigma`=0 — niesie samo V horyzontu,
   którego potrzebują AIVAT i trener.

   **Sekcja warstwy** (w tej kolejności): tablica kluczy stanów —
   `n × 3 × int16` (6 B na stan), posortowana leksykalnie, po niej
   **tablica V — `n × 3 × float64`** (24 B na stan, pełna precyzja,
   nieskompresowana, ten sam porządek co klucze; decyzja 26 pkt 2),
   po niej indeks bloków — `n × 16 B` (offset w pliku uint64, długość
   po kompresji uint32, długość przed kompresją uint32), po nim same
   bloki. **Blok stanu** to `zlib` z ładunku: `uint16` maska
   osiągalności węzłów (bit *i* = węzeł *i* ma w artefakcie rozkład),
   a dalej — dla każdego ustawionego bitu rosnąco — dwie kolumny po
   `n_classes` wartości: cały slot 0 (fold), potem cały slot 1
   (open/call). Kolumnowo, nie przeplotem: sąsiednie klasy jednego
   slotu są podobne, więc zlib pakuje je ciaśniej. Slot 2 (jam)
   wynika z dopełnienia do skali.

2. **Kwantyzacja: metoda największych reszt, 2 z 3 akcji.** Rozkład
   trzech slotów skalowany do sumy `2**bits − 1` (uint8: 255), część
   całkowita plus reszty rozdane malejąco po części ułamkowej (remis
   rozstrzyga numer slotu — porządek stabilny, więc wynik nie zależy
   od implementacji sortowania). Suma jest zachowana **dokładnie**,
   więc trzeci slot naprawdę wynika z dopełnienia, a błąd pojedynczego
   prawdopodobieństwa jest **mniejszy niż jeden krok** (uint8:
   1/255 = 0,00392). Zmierzone maksimum na **wszystkich 21 warstwach
   artefaktu produkcyjnego** to **0,002610**, a na pilocie `grid5d`
   0,002607 — sama warstwa 0 produkcji daje 0,002410, więc to nie jest
   liczba, którą wolno czytać z jednej warstwy.
   Akcja o prawdopodobieństwie zero nigdy nie dostaje reszty — w tym
   artefakcie zero znaczy „akcja poza maską drzewa", a nie „mało
   prawdopodobna". **KOREKTA JEDNOSTKOWA (2026-08-29) obowiązuje:**
   0,0039 to błąd w przestrzeni prawdopodobieństw, a **nie** ε (udział
   puli); koszt kwantyzacji jest zmierzony w ε w punkcie 6, a nie
   wyprowadzony z tej liczby.

3. **Determinizm zapisu.** Ten sam katalog biegu daje **bajt w bajt
   ten sam plik** (pod testem na artefakcie kontrolnym z repo): brak
   znaczników czasu, kanoniczny JSON metadanych, stały poziom `zlib`,
   stany sortowane leksykalnie przed zapisem, plik powstaje jako
   `.tmp` obok celu i wchodzi na miejsce przez `os.replace`. Konwerter
   liczy sha256 każdego pakowanego pliku i odrzuca artefakt, którego
   manifest o nim kłamie (pod testem: podmieniona warstwa → `ValueError`).

4. **Czytnik: czysty stdlib i jawna nieosiągalność.** `import struct`,
   `import zlib` — i nic więcej; test architektury trzyma ten zbiór
   wypisany, pilnuje braku importów `poker.*`, `tools` i modułów I/O,
   a brak numpy w całym pakiecie pilnuje osobny test od POKER-12.
   Czytnik przyjmuje otwarty strumień binarny (silnik nie wykonuje
   I/O — INV-P7), więc otwarcie pliku należy do adaptera albo
   narzędzia. API: `value` / `seat_value` (V per miejsce i pojedyncza
   liczba), `state` (blok jednego stanu: maska + rozkłady),
   `policy` / `policy_table`, `state_key` (wyliczanie siatki),
   `has_state`, `meta_bytes`. Odczyt spoza artefaktu jest
   **rozróżnialny**, nie cichy: `LayerNotFound` (ręka spoza warstw),
   `StateNotFound` (wektor stacków spoza siatki warstwy),
   `NodeUnreachable` (węzeł spoza maski osiągalności),
   `PolicyMissing` (warstwa brzegowa niesie samo V) — wszystkie
   podtypy `LookupError`. Rozróżnienie niesie **wyjątek, nie
   predykat**: `has_state` zwraca `False` tak samo dla stanu spoza
   siatki, jak i dla ręki spoza horyzontu, więc fallback POKER-52
   („poza siatką" vs „poza horyzontem" vs „poza maską") pyta przez
   `value`/`state` i czyta typ błędu.

   Round-trip konwerter→czytnik na artefakcie
   kontrolnym sprawdza **wszystkie** węzły maski i **wszystkie** klasy:
   rozkłady wracają w granicach kroku kwantyzacji i sumują się do
   jedności, a V wraca **bajtowo dokładnie** (float64).

5. **Liczby na artefakcie produkcyjnym (BA, BB).** Bieg
   `PROD/grid2` (49 765 stanów-warstw + 2 923 stany warunku
   brzegowego, 169 klas, 22 warstwy) pakuje się w **19 016 752 B
   (18,1 MiB)** wobec **38 619 677 B (36,8 MiB)** warstw i warunku
   brzegowego w `.npz` — **2,03× mniej**; zapis trwa 24,1 s.
   Rozkład bajtów: obszar bloków strategii 16 634 705 B, z czego same
   skompresowane bloki to 16 634 518 B (**334,3 B na stan
   z polityką**), a 187 B to dopełnienia wyrównania sekcji do ośmiu
   bajtów; tablice V 1 264 512 B, indeks bloków 796 240 B,
   klucze stanów 316 128 B, metadane 3 983 B, nagłówek i katalog
   1 184 B. Maska osiągalności zarabia na siebie: w warstwach
   produkcji żywe jest **~39–40% z 14 slotów węzłów** na stan
   (`layer_10`: 40,25%, `layer_20`: 39,01%), więc 60% komórek nie
   trafia do pliku w ogóle.

   **Czas odczytu (BB, 2 000 losowań deterministycznych, maszyna
   obciążona równoległym pomiarem — czyli konserwatywnie):** jeden
   **stan** (wyszukiwanie binarne + `zlib` bloku + jeden rozkład)
   **mediana 25,3 µs, p95 42–49 µs**; jedna **wartość V** (`seek` +
   8 B) **mediana 8,5 µs, p95 ~15 µs**. Dwa przebiegi dały medianę
   25,3 i 25,4 µs. Liczba jest **raportowana, nie progowana** —
   próg ustali konsument w POKER-52 (tak stanowi kontrakt), dlatego
   nie ma dla niej asercji czasu w bramce. Zamiast czasu bramka
   trzyma niezmiennik deterministyczny i mocniejszy dla twierdzenia
   „bez ładowania całości": **liczbę bajtów przeczytanych ze
   strumienia**. Na artefakcie kontrolnym (8 328 B) najgorszy odczyt
   stanu to **116 B**, a wartości V **56 B**; asercje stoją na 160
   i 72 B — zapas jest na inną wersję `zlib`, nie na inny sposób
   odczytu (test podstawia strumień liczący).

   Na artefakcie produkcyjnym mierzy to `bench --sweep` (przemiał
   **wszystkich** stanów, nie próbka — stany różnią się liczbą żywych
   węzłów i stopniem kompresji bloku, więc percentyl próbki nie zna
   maksimum): odczyt stanu **maksimum 1 804 B, mediana 394 B, p95
   664 B** na 49 765 odczytów; odczyt wartości V **maksimum 80 B,
   mediana 74 B** na 52 688 odczytów. Najgorszy odczyt stanu to
   0,0095% pliku.

6. **Koszt kwantyzacji ZMIERZONY W ε — kryterium blokujące.** Mierzy go
   `expost`, to samo narzędzie i ta sama definicja ε co w POKER-46/50:
   bieg przepuszczony przez format (`requantize` pakuje artefakt i
   odczytuje strategie **czytnikiem stdlib**, a nie powtórzeniem
   kwantyzacji w numpy — mierzymy koszt formatu, nie koszt jego
   repliki) obok kopii surowej, oba przebiegi na tej samej maszynie
   i tym samym kodzie. Obie strony mają tę samą tablicę V (format
   przenosi ją bez straty), więc różnica ε jest czystym przyrostem
   wartości najlepszej odpowiedzi przeciw skwantowanemu profilowi.
   Próg kontraktu — przyrost ε maks ≤ **10%** wartości surowej — żyje
   jako `QUANT_EPS_LIMIT_SHARE` w konwerterze, a nie jako liczba
   przepisana do skryptu; przekroczenie oznacza kwantyzację uint16
   i ponowny pomiar (format ma tę ścieżkę w nagłówku i pod testem:
   błąd spada do ≤ 1/65535), a nie poluzowanie progu.

   **Artefakt kontrolny z repo (w bramce; 190 stanów w pliku, z tego
   22 stany-warstwy w ex-post, 4 klasy):** ε surowe maks 3,8314e−3 →
   skwantowane **3,6911e−3**, mediana 1,3633e−4 → **1,0865e−4**;
   przyrost **−3,7%**. Liczby mają asercje w
   `test_koszt_kwantyzacji_w_epsilon_na_artefakcie_kontrolnym`.

   **Pilot `PILOT/grid5d` (poza bramką, 8 654 stany, 169 klas) —
   KRYTERIUM BLOKUJĄCE SPEŁNIONE.** Sekwencja BC→BE; dwa przebiegi
   ex-post po ~14,6 min ściennych przy 3 procesach. Ten sam przepis
   wykonuje skrypt `p49/quant_cost.sh` w scratchpadzie sesji: robi
   CAŁY pomiar (kopie robocze, round-trip, oba ex-post, werdykt),
   a kwantyzacja uint16 jest w nim gałęzią awaryjną, uruchamianą
   dopiero po przekroczeniu progu — tu nie weszła. Sekwencja BC→BE
   została odtworzona dosłownie, w świeżych katalogach roboczych,
   i dała te same cyfry co pomiar zamknięcia (4,664108132224065e−4 /
   3,838025721973892e−4).

   | wielkość | surowe | po round-tripie | zmiana |
   |---|---:|---:|---:|
   | ex-post ε maks | 4,6641e−4 | **3,8380e−4** | **−17,7%** |
   | ex-post ε mediana | 1,0771e−4 | 4,6518e−5 | −56,8% |

   Przyrost ε maks wynosi **−8,26e−5 puli**, czyli **−17,7%** wartości
   surowej wobec dopuszczalnego **+10%**: kwantyzacja uint8 nie
   kosztuje tu nic, a zmierzone ε **spada**. Bieg surowy odtworzył
   raport POKER-49 **co do wszystkich cyfr** (4,664108132224065e−4 /
   1,0770827861122934e−4), więc porównanie stoi na sprawdzonym
   przewodzie, nie na dwóch różnych pomiarach.

   **Mechanizm i uczciwa granica tej liczby.** Kwantyzacja obcina
   ogony mieszania: **5 850 198 z 24,2 mln** wartości slotów żywych
   infosetów (24,2%) miało prawdopodobieństwo mniejsze od jednego
   kroku kwantyzacji i wyszło zerem, przy maksymalnej zmianie
   pojedynczego prawdopodobieństwa
   0,00261 i **24 zmianach dominującej akcji z 8 058 258** (0,0003%).
   Najlepsza odpowiedź traci na tym drobne przecieki, które
   eksploatowała w profilu surowym — stąd spadek. **To nie jest
   twierdzenie, że kwantyzacja poprawia blueprint**: ex-post trzyma
   tablicę V z biegu surowego (format przenosi ją bez straty), więc
   mierzy „o ile najlepsza odpowiedź bije wartość, którą artefakt
   sam deklaruje". Własna wartość profilu skwantowanego mogła się
   przesunąć i ta metryka tego nie widzi — dokładnie ta sama ślepota,
   którą POKER-49 zmierzył dla warunku brzegowego. Dla kontraktu to
   właściwa liczba (artefakt deklaruje V i gra σ skwantowanym), ale
   nie wolno z niej czytać więcej.

7. **Co trzyma bramka (`tests/test_blueprint_pilot.py`,
   `tests/test_architecture.py`).** Determinizm konwertera bajt
   w bajt; nagłówek i metadane niosące hash oraz kopię przepisu
   pochodzenia; odrzucenie artefaktu niezgodnego z manifestem;
   round-trip rozkładów w granicach kroku kwantyzacji na komplecie
   węzłów i klas; bajtowa dokładność V (także warstwy brzegowej);
   jawna nieosiągalność (maska zgodna co do węzła z zerami solvera,
   cztery rozróżnialne wyjątki); sufity bajtów przeczytanych na jeden
   stan i jedną wartość V; własności kwantyzacji (suma dokładna, zero
   zostaje zerem, błąd poniżej kroku, zerowa suma = błąd); ścieżka
   uint16; koszt kwantyzacji w ε z progiem 10%; ograniczenie importów
   czytnika i kierunek zależności konwerter → czytnik.

**POKER-50 (bieg produkcyjny blueprintu: siatka 2 żetonów pełnego
zegara) zamknięty.** Liczby zmierzone na 4 rdzeniach (Intel Xeon
@ 2.80GHz, Python 3.13.12, numpy 2.5.2, venv z extras `train`);
`PROD` to katalog artefaktu produkcyjnego poza repozytorium (decyzja
25 pkt 6) — w repo żyje wyłącznie artefakt kontrolny łańcucha
(`tools/blueprint/control/`, 24 KB) i jego test w bramce. Komendy
pełnej regeneracji (dwustopniowy dowód odtwarzalności decyzji 06;
wszystkie z `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
MKL_NUM_THREADS=1`):

```
AC python tools/blueprint/rollout_tensor.py --out PROD/tensor \
       --trials 15000 --hu-trials 60000 --seed 50 --jobs 4
AD python -m pytest tests/test_blueprint_pilot.py -q \
       -k "bezpiecznik or wycinku_produkcyjnym or lancuch_kontrolny \
or podzbioru_tensora"
AE python tools/blueprint/solve_grid.py --tensor PROD/tensor \
       --out PROD/grid2 --grid-step 2 --jobs 4
AF python tools/blueprint/expost.py expost --out PROD/grid2 --jobs 4
AG python tools/blueprint/expost.py icm --out PROD/grid2
AH python tools/blueprint/eps_curve.py decompose --out PROD/grid2 \
       --worst 10 --jobs 4
```

AD to bramka wycinka uruchamiana na maszynie biegu PRZED spaleniem
budżetu (wznowienie bajt w bajt na kroku 2, łańcuch kontrolny,
bezpiecznik); AE jest wznawialne (warstwa = jednostka; brakujące
warstwy dolicza z manifestu) i ma bezpiecznik kosztu 140 rdzenio-h
aktywny domyślnie (`--cost-limit`, 0 wyłącza; przekroczenie = exit 3
i status `aborted-cost-fuse` w manifeście).

1. **Tensor produkcyjny (AC).** 15 000 prób/multizbiór dla 818 805
   multizbiorów trójek (325 nierozdawalnych, waga 0), pary HU 60 000
   prób (14 365 par; proporcjonalnie do pilota 8 000 × 7,5, ponad
   podłogą kontraktu 32 000), seed 50, backend `table`. Zmierzony
   koszt: trójki 9 458,2 s ścienne przy 4 procesach (**10,5
   rdzenio-h**; ekstrapolacja POKER-46 mówiła 9,7 — niedoszacowanie
   8,4%), pary 609,4 s (0,68 rdzenio-h), tablica wartości 26,4 s —
   razem **11,2 rdzenio-h**. Reprodukcja podzbioru pod testem
   (`test_reprodukcja_podzbioru_tensora_produkcyjnego`): zaliczki
   trójki AA/KK/72o (indeksy 0/25/143) i pary AA/72o przybite
   w `tools/blueprint/control/chain_control.json` przy zamknięciu
   tury kodu; artefakt produkcyjny policzony później zgadza się
   z nimi **co do zliczenia** (zweryfikowane wprost na
   `PROD/tensor/rollout3.npz` i `rollout_hu.npz`), a próg equity
   testu jest wyprowadzony z liczb prób obu artefaktów.
2. **Bieg siatki 2 (AE): status `done`.** 2 923 stany siatki,
   21 warstw, 49 765 stanów-warstw o zmierzonej mieszance trybów
   `deep` 1 198, `jamfold` 44 550, `hu-deep` 932, `hu-jamfold` 3 085
   (warstwy rąk 0–4 są mniejsze od pełnej siatki — osiągalność tnie
   je do 1/18/147/691/2 143 stanów). Horyzont **zbiegł w 6 cyklach do
   delty 3,820e−4** (ciąg 0,0899 → 0,0123 → 6,57e−3 → 2,76e−3 →
   7,16e−4 → 3,82e−4) — o jeden cykl wolniej niż pilot siatki 5
   (5 cykli, 1,285e−4); tolerancja 5e−4 wiąże, sufit 12 ma zapas.
   Manifest niesie postęp per warstwa (czas, stany, tryby,
   rdzenio-sekundy dzieci) i pochodzenie (wersje, model CPU, seed
   i próby tensora, hash konfiguracji
   `4aecf64eccccd6de39ecd017ebf80f89a834f01fddcf888b10f22220e0fe41d8`).
3. **Bezpiecznik kosztu: nie zadziałał i słusznie, a prognoza była
   dobra.** Trajektoria ekstrapolacji całości (solve.log): pierwszy
   odczyt po trzech warstwach **60,55 rdzenio-h**, plateau ~60,4 na
   warstwach czysto `jamfold`, skok do maksimum **69,12** przy wejściu
   trybu `deep` (ręka 6), finał **65,41** — dokładnie zmierzony koszt
   solvera, więc błąd prognozy mieścił się w **−7,7%…+5,7%** (skrajne
   odczyty 60,36 i 69,12 wobec finału 65,41). Tempa
   zmierzone w biegu (średnie): `deep` 50,8 rdzenio-s/stan (pilot:
   mediana 29,45, maks 63,5 — średnia produkcji mieści się
   w rozrzucie pilota), `jamfold` 1,83, `hu-deep` 0,054, `hu-jamfold`
   0,018; kalibracja priorów 1,32, narzut forka 1,018.
4. **Koszt — dwie liczby, każda z definicją.** (a) **Koszt
   regeneracji artefaktu** (sumy czasów z manifestów; tyle płaci
   każdy, kto odtwarza artefakt komendami AC+AE): tensor 11,2 +
   horyzont 25,2 (22 723,6 s ściennych × 4) + warstwy 40,2
   (36 146,4 s × 4) = **76,6 rdzenio-h** — 6,6% poniżej dolnego końca
   przyjętego okna 82–114 z POKER-49 (horyzont droższy: 6 cykli,
   25,2 wobec 18,5 przy pięciu; warstwy tańsze od ekstrapolacji).
   (b) **Koszt faktyczny przedsięwzięcia**: bieg był dwukrotnie
   przerwany restartami kontenera; pierwszy zabił horyzont
   w 4. cyklu — horyzont nie ma checkpointu per cykl, więc przepadło
   14 552 s ściennych × 4 = **16,2 rdzenio-h**; drugi kosztował jedną
   częściową warstwę (≤2,8 rdzenio-h: między końcem warstwy 6
   a restartem minęły 42,5 min ścienne, śmierć kontenera nie zostawia
   znacznika) — razem **92,8–95,6 rdzenio-h**. Zegarowo całość
   2026-08-30T02:26Z → 2026-08-31T03:44Z (25,3 h z przerwami).
   Pomiary poza artefaktem: ex-post (AF) 4 122 s ścienne × 4 =
   **4,6 rdzenio-h**; icm 7 s, decompose 16 s.
5. **Ex-post ε (AF): maks 4,720e−4, mediana 1,075e−4**, min −1,19e−7
   (szum f32) na 49 765 stanach. **Kryterium blokujące ≤ 1e−3:
   spełnione** z zapasem 2,1×. **Punkt odniesienia 5e−4: NIE
   przekroczony** — zapas 5,6% (pilot: 6,7%; maksimum po 49 765
   stanach wyszło 1,2% wyżej niż po 8 654, więc ryzyko z kontraktu
   się nie zmaterializowało, ale zapas stopniał zgodnie
   z przewidywaniem). **Opcja sufitu 1536 się NIE uruchamia**
   (`expost_report.json` → `criteria.ceiling_1536_option_triggers:
   false`); pozostaje wyceniona (~4× na trybie `deep`) i warunkowa.
   Najgorszy stan to stan startowy 50/50/50 (ręka 0, miejsce 1) —
   spójnie z tym, że ε DAG-u akumuluje dług warstw za nim: dług
   odziedziczony 10 najgorszych stanów ma medianę **89,1%** (AH),
   a ε etapowe: `deep` maks 1,95e−4, **697 z 1 198 stanów powyżej
   tolerancji 5e−5, 739 na sufcie 384** (produkcyjne potwierdzenie
   wzorca pilota: 105/253); `jamfold`, `hu-deep`, `hu-jamfold` —
   zero stanów powyżej tolerancji (maksima 5,00e−5 / 4,99e−5 /
   4,98e−5).
6. **V vs ICM (AG) i rozkład per warstwa.** Stany krótkiego BB
   (< 5 bb): **27 078**, |V−ICM| maks **0,0948 puli** (ręka 20, stan
   22/2/126), średnia 0,0206 — na pełnej siatce błąd ICM sięga ~9,5%
   puli (pilot siatki 5: 7,9%). Maksimum warstwy idzie w górę wzdłuż
   zegara od 0,0105 (ręka 0) do 0,0948 (ręka 20) jako trend,
   z lokalnymi spadkami między poziomami blindów (np. 0,0586 → 0,0578
   w rękach 3–5) — to liczba uzasadniająca kierunek decyzji 25
   (ICM tylko na horyzoncie).
   Rozkład per warstwa (ε w jednostkach puli; ICM = |V−ICM| maks /
   średnia warstwy):

   | ręka | stany | ε maks | ε mediana | ICM maks | ICM śr. |
   |-----:|------:|-------:|----------:|---------:|--------:|
   | 0 | 1 | 4,72e−4 | 4,67e−4 | 0,0105 | 0,0105 |
   | 1 | 18 | 4,64e−4 | 2,73e−4 | 0,0094 | 0,0065 |
   | 2 | 147 | 4,50e−4 | 2,59e−4 | 0,0463 | 0,0066 |
   | 3 | 691 | 4,55e−4 | 2,34e−4 | 0,0586 | 0,0089 |
   | 4 | 2 143 | 3,89e−4 | 2,35e−4 | 0,0585 | 0,0111 |
   | 5 | 2 920 | 3,89e−4 | 2,15e−4 | 0,0578 | 0,0085 |
   | 6 | 2 923 | 3,88e−4 | 1,98e−4 | 0,0719 | 0,0125 |
   | 7 | 2 923 | 3,47e−4 | 1,85e−4 | 0,0689 | 0,0124 |
   | 8 | 2 923 | 3,52e−4 | 1,69e−4 | 0,0683 | 0,0109 |
   | 9 | 2 923 | 2,14e−4 | 1,58e−4 | 0,0775 | 0,0145 |
   | 10 | 2 923 | 2,02e−4 | 1,48e−4 | 0,0771 | 0,0143 |
   | 11 | 2 923 | 1,91e−4 | 1,37e−4 | 0,0763 | 0,0135 |
   | 12 | 2 923 | 1,73e−4 | 1,26e−4 | 0,0861 | 0,0172 |
   | 13 | 2 923 | 1,58e−4 | 1,14e−4 | 0,0824 | 0,0159 |
   | 14 | 2 923 | 1,49e−4 | 1,02e−4 | 0,0838 | 0,0182 |
   | 15 | 2 923 | 1,35e−4 | 8,88e−5 | 0,0915 | 0,0219 |
   | 16 | 2 923 | 1,30e−4 | 8,39e−5 | 0,0911 | 0,0211 |
   | 17 | 2 923 | 1,20e−4 | 7,47e−5 | 0,0929 | 0,0227 |
   | 18 | 2 923 | 1,07e−4 | 6,30e−5 | 0,0939 | 0,0246 |
   | 19 | 2 923 | 9,02e−5 | 4,75e−5 | 0,0938 | 0,0243 |
   | 20 | 2 923 | 5,00e−5 | 2,72e−5 | 0,0948 | 0,0246 |

7. **Wznowienia w praktyce (zmierzone zachowanie, nie deklaracja).**
   `boundary.npz` + warstwy wznowiły się po obu restartach zgodnie
   z projektem: bieg sklejony z trzech sesji zakończył się statusem
   `done` bez rozjazdu manifestu, a identyczność bajt w bajt wznowień
   na kroku 2 trzyma test wycinka (AD). Świadomie zostawione:
   **horyzont nie ma checkpointu per cykl** — restart w trakcie
   horyzontu kosztuje cały dotychczasowy postęp cykli (zmierzone:
   16,2 rdzenio-h; przy dzisiejszej stabilności kontenera to ryzyko
   ~4–6 h ściennych na bieg). Wycena domknięcia: zapis `boundary
   partial` per cykl tym samym mechanizmem co warstwy — osobny,
   mały kontrakt, jeśli planowane są kolejne pełne biegi.

**POKER-49 (kotwice `wt2_fold`, horyzont, CFR+, ślepota brzegu) zamknięty.**
Liczby zmierzone na 4 rdzeniach, numpy 2.5.2, venv z extras `train`;
`PILOT` to katalog artefaktów poza repozytorium. Wszystkie komendy
z `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`.

```
O  python tools/blueprint/solve_grid.py --tensor PILOT/tensor \
       --out PILOT/tail10 --grid-step 10 --tail-tol 0 --tail-cycles 16 \
       --jobs 4 --layers-limit 0
P  python tools/blueprint/eps_curve.py curve --out PILOT/g25 --mode hu-deep \
       --ladder 32,64,128,256,512,1024,2048 --worst 5 --extra 5 --seed 47 \
       --jobs 4 --report eps_curve_hu.json
R  python tools/blueprint/solve_grid.py --tensor PILOT/tensor \
       --out PILOT/ref10 --grid-step 10 --jobs 4
   python tools/blueprint/expost.py expost --out PILOT/ref10 --jobs 4
S  python tools/blueprint/solve_grid.py --tensor PILOT/tensor \
       --out PILOT/p10_KSZTALT --grid-step 10 --jobs 4 \
       --perturb 0.002 --perturb-kind KSZTALT --boundary-from PILOT/ref10
   python tools/blueprint/expost.py expost --out PILOT/p10_KSZTALT --jobs 4
T  python tools/blueprint/boundary_sensitivity.py \
       --reference PILOT/ref10 --perturbed PILOT/p10_KSZTALT
U  python tools/blueprint/solve_grid.py --tensor PILOT/tensor \
       --out PILOT/grid5d --grid-step 5 --jobs 4
W  python tools/blueprint/expost.py expost --out PILOT/grid5d --jobs 4
   python tools/blueprint/expost.py icm --out PILOT/grid5d
X  python tools/blueprint/eps_curve.py decompose --out PILOT/grid5d \
       --worst 10 --jobs 4
Y  python tools/blueprint/eps_curve.py cost --out PILOT/grid5d \
       --per-mode 10 --seed 47 --jobs 1
```

1. **Kotwice `wt2_fold` — finding blokujący zamknięty.** Tensor puli 2-way
   przy trzech żywych zasila 7 z 17 liści (3, 5, 8, 10, 11, 14, 15), czyli
   6 798 z 8 654 stanów pilota i 68 859 z 76 072 solve'ów siatki
   produkcyjnej, a nie miał żadnej kotwicy orientacji osi. Trzy nowe testy
   przechodzą wszystkie trzy pary osi — po jednym liściu 2-way na parę —
   i wszystkie sześć kolejności klas, jednocześnie w tensorze i u
   konsumenta. Czerwień odtworzona osobno dla obu mutacji z audytu, na
   prawdziwym tensorze (nie syntetycznym):

   | mutacja | czerwone testy | zmierzona wartość |
   |---|---|---:|
   | odwrócenie osi w kolapsie | orientacja, wypłaty, equity | 0,134 |
   | podmiana klucza pary | orientacja, wypłaty | 0,147 |

   Mutacja pierwsza to `first, second = ranks[axis_b], ranks[axis_a]`
   w `load_tensors`: equity roli posadzonej na AA spada do **0,134** wobec
   progu 0,75, a zmarginalizowane equity daje **0,195** przy 0,827
   z macierzy produktu i progu Monte Carlo 0,069. Mutacja druga to
   `base = tensors.wt2_fold[_AXIS_PAIRS[0]]` u konsumenta: na liściu 5
   tensor mówi 0,316 tam, gdzie konsument liczy 0,866, a rola z AA bierze
   **0,147** puli zamiast ponad 0,85. Żadna z nich nie ruszała pozostałych
   353 testów.

   Próg testu equity jest wyprowadzony z liczb prób obu artefaktów (tensor
   600 prób na multizbiór, macierz `poker.preflop_equity` 2 048 na parę;
   wariancja próby ≤ 1/4, próby efektywne marginalizacji (Σw)²/Σw²), a nie
   dobrany do wyniku — i sam test sprawdza, że próg jest ciaśniejszy niż
   różnica equity AA-72o od AA-J8o, więc odróżnia klasy, a nie tylko
   przepuszcza.

2. **Horyzont zbiega do podłogi, nie do zera (O).** Krzywa delta-vs-cykle
   na siatce 10 (133 stany, 3 015 s; tolerancja wyłączona, więc sufit jest
   jedynym ogranicznikiem):

   | cykl | delta | cykl | delta |
   |-----:|------:|-----:|------:|
   | 1 | 0,0573 | 6 | 2,14e−4 |
   | 2 | 0,0100 | 7 | 1,94e−4 |
   | 3 | 1,09e−3 | 8 | **1,81e−4** |
   | 4 | 8,33e−4 | 9–16 | ~2,05e−4 |
   | 5 | 4,34e−4 | | |

   Cykl 3 odtwarza rząd delty 0,00209 z POKER-47. Od ósmego cyklu delta
   **przestaje spadać**: ilorazy kolejnych cykli siadają na 0,95–1,05, więc
   osiem dalszych cykli nie kupuje nic. Podłoga ~2e−4 to szum samego
   solvera etapowego — tolerancja `--fp-tol` 5e−5 wzmocniona przez
   trzyrękowy cykl (~4×) — a nie brak cykli. **Dokładność warunku
   brzegowego jest więc ograniczona od dołu przez tolerancję etapową:**
   żeby zejść niżej, trzeba zacisnąć `--fp-tol`, a nie podnieść
   `--tail-cycles`. Stąd domyślne: tolerancja **5e−4** (osiągana w piątym
   cyklu, z zapasem 2,3× nad podłogą, więc wiąże tolerancja, a nie sufit)
   i sufit **12 cykli** (2,4× tego — zabezpieczenie, nie kryterium).
   Konsekwencja przed produkcją: nowa delta brzegu jest **tego samego
   rzędu** co ex-post ε biegu, czyli niepewność warunku brzegowego
   przestała być zaniedbywalna wobec wielkości, którą mierzymy. Brzeg jest
   **zbieżny do podłogi, a nie domknięty do zera** — to dwie różne rzeczy;
   ile ta różnica kosztuje, mierzy punkt 4.

3. **Krzywa CFR+ w endgame'ach HU (P).** Pierwszy pomiar samego CFR+
   (`eps_curve.py` mierzył dotąd wyłącznie PI-FP). Próbka 10 stanów
   `hu-deep`, średnia ważona własnym reachem, tolerancja w pomiarze
   wyłączona:

   | sufit | ε maks | ε mediana | rdzenio-s/stan |
   |------:|-------:|----------:|---------------:|
   |    32 | 4,51e−4 | 1,09e−4 | 0,015 |
   |    64 | 1,45e−4 | 3,26e−5 | 0,030 |
   |   128 | 4,76e−5 | 8,87e−6 | 0,060 |
   |   256 | 1,55e−5 | 2,64e−6 | 0,177 |
   |   512 | 4,35e−6 | 6,48e−7 | 0,247 |
   |  1024 | 1,16e−6 | 1,94e−7 | 0,492 |
   |  2048 | 3,13e−7 | 1,53e−7 | 0,963 |

   Nachylenie log ε vs log t: **−1,75**, stałe (iloraz 0,27–0,33 na
   podwojenie) aż do 2 048 — bez plateau. **Cena średniej nieważonej jest
   tu widoczna wprost:** przy tym samym sufcie 128, którego POKER-47 nie
   ruszał, średnia nieważona dawała ε etapowe maks 7,1e−5 i 39 stanów
   powyżej tolerancji, a ważona własnym reachem daje 4,76e−5 — poniżej
   tolerancji 5e−5. Stąd budżet: tolerancja **5e−5** (ta sama co PI-FP, bo
   dług obu sumuje się w tym samym DAG-u) i sufit **512** iteracji —
   tolerancję osiąga już 128, więc sufit jest zabezpieczeniem z zapasem
   11× za 0,25 rdzenio-s na stan, a nie kryterium.

4. **Ślepota metryki skwantyfikowana (R, S, T).** Bieg odniesienia na
   siatce 10 (2 347 stanów, horyzont zbiegł w 5 cyklach do delty 2,746e−4;
   671 s, cały bieg 2 076 s) i dwa biegi o brzegu zaburzonym o **0,002** —
   amplituda rzędu delty POKER-47 — w dwóch kształtach przybitych przed
   pomiarem: `tilt` (systematyczny: najniższe żywe miejsce w górę,
   najwyższe w dół) i `noise` (deterministyczny szum o tej samej
   amplitudzie). Oba importują punkt stały odniesienia (`--boundary-from`),
   więc jedyną różnicą jest zaburzenie; oba zaburzenia zachowują sumę
   nagród w stanie i zerową wartość miejsc wybitych.

   | wielkość | odniesienie | tilt 0,002 | noise 0,002 |
   |---|---:|---:|---:|
   | ex-post ε maks | 6,173e−4 | 6,068e−4 | 6,066e−4 |
   | ex-post ε mediana | 1,199e−4 | 1,198e−4 | 1,199e−4 |
   | ε stanu startowego | 6,173e−4 | 6,068e−4 | 5,971e−4 |
   | zmiana ε stanu startowego | — | −1,05e−5 | −2,01e−5 |
   | największa zmiana V | — | 2,383e−3 | 2,559e−3 |
   | największa zmiana σ na infosecie | — | 0,9994 | 0,9994 |
   | średnia zmiana σ | — | 2,04e−3 | 1,89e−3 |
   | zmiany dominującej akcji (z 2 012 959) | — | 2 154 (0,107%) | 2 039 (0,101%) |

   Trzy odczyty. (a) **Zaburzenie brzegu o 0,002 przesuwa ex-post ε o ~1e−5**
   — o 1,7% jego wartości i o dwa rzędy mniej niż samo zaburzenie; metryka
   jest na błąd brzegu ślepa, ale i sam błąd jest tłumiony. (b) **Tłumienie
   wzdłuż DAG-u jest ~10×**: największa zmiana V spada z 2,1–2,6e−3 przy
   ręce 20 (tuż przy horyzoncie) do 1,7–2,0e−4 przy ręce 0. (c) **Kształt
   zaburzenia nie ma znaczenia — liczy się amplituda:** tilt daje 5,6%
   więcej zmian akcji niż szum (2 154 wobec 2 039), a przy samym horyzoncie
   jest odwrotnie (289 wobec 616 w ręce 20), więc zaburzenie systematyczne
   **nie** propaguje się mocniej niż losowe o tej samej amplitudzie.
   **Werdykt: brzeg opanowany** — przy delcie 5e−4, czterokrotnie mniejszej
   od zaburzenia, wpływ na ε jest poniżej 3e−6.

   Zastrzeżenie, którego nie wolno zgubić: największa zmiana σ ≈ 1,0 przy
   horyzoncie znaczy, że **pojedyncze komórki bliskie obojętności
   przełączają akcję całkowicie** przy pomijalnej zmianie ε. Bajty
   artefaktu zależą więc od konfiguracji brzegu, a jakość nie —
   odtwarzalność bajt w bajt obowiązuje **przy ustalonej konfiguracji**
   i tylko tyle twierdzimy.

5. **Powtórzony pilot siatki 5 (U, W, X, Y).** Cały bieg **8 976,7 s
   (2,49 h)** wobec 11 587,3 s POKER-47 — **1,29× szybciej mimo zbieżnego
   horyzontu**, bo CFR+ kończy teraz na tolerancji zamiast chodzić stałe
   128 iteracji. Horyzont: **5 cykli, delta 1,285e−4, zbieżny** (2 815,4 s;
   7 395 solve'ów, 1,523 rdzenio-s/solve). Ciąg delt 0,0751 → 0,0104 →
   **0,002092** → 5,61e−4 → 1,285e−4: trzeci cykl odtwarza co do trzeciej
   cyfry deltę 0,00209 z POKER-47, więc zbieżność jest **16× lepsza** od
   punktu, w którym poprzedni bieg się zatrzymywał. Wartość 1,285e−4 leży
   poniżej podłogi ~2,05e−4 zmierzonej na siatce 10 przy starym CFR+ — obie
   siatki nie są wprost porównywalne, ale kierunek zgadza się z diagnozą,
   że podłoga jest szumem solvera etapowego, więc jego poprawa ją obniża.
   21 warstw: 8 654 stany w 6 159,0 s → 0,712 s/stan przy 4 procesach,
   **2,847 rdzenio-s/stan** (POKER-47: 1,068 / 4,272).

   **Ex-post ε (W): maks 4,664e−4, mediana 1,077e−4**, min −8,7e−8 (szum
   f32) na tych samych 8 654 stanach. Wobec POKER-47 (4,322e−4 / 8,376e−5)
   to **7,9% wyżej na maksimum i 28,6% wyżej na medianie** — liczby idą
   w złą stronę i tak trzeba je zapisać. Wyjaśnienie jest zmierzone, nie
   domniemane: to inny warunek brzegowy (zbieżny zamiast zamrożonego na
   trzecim cyklu, różnica rzędu 0,002) i inna średnia CFR+, a pomiar
   wrażliwości z punktu 4 mówi, że zmiana brzegu o 0,002 rusza ε o ~1e−5;
   reszta mieści się w zmianie profilu HU i szumie f32. **Maksimum 0,0466%
   puli nadal jest poniżej punktu odniesienia decyzji 25 (0,05%)** i 2,1×
   poniżej progu 0,001 z POKER-47, ale zapas do punktu odniesienia stopniał
   z 14% do 6,7%.

   ε **etapowe** po trybach na komplecie stanów (X, nie na próbce): `deep`
   maks 1,74e−4, mediana 4,92e−5, **105 z 253 stanów powyżej tolerancji,
   110 na sufcie 384**; `jamfold` maks 5,00e−5, mediana 4,17e−5, **zero
   z 6 798 powyżej tolerancji**; `hu-deep` maks **4,998e−5**, mediana
   3,86e−5, **zero z 397 stanów powyżej tolerancji i zero na sufcie**,
   mediana 96 iteracji z 512; `hu-jamfold` maks 4,94e−5, mediana 2,14e−5,
   zero z 1 206 powyżej tolerancji. Kryterium „żaden stan `hu-deep` powyżej
   tolerancji" jest więc **spełnione na komplecie 397 stanów**, a nie na
   próbce — bezpośredni skutek średniej ważonej reachem i stopu na
   tolerancji (POKER-47: 39 stanów powyżej). Udział długu odziedziczonego
   dla dziesięciu najgorszych stanów: mediana **90,1%**.

   V vs ICM (W): 4 327 stanów krótkiego BB, maks **0,0788**, średnia
   0,0200, najgorszy nadal ręka 15, stan 125/20/5 — bez zmian względem
   POKER-47.

6. **Nowa ekstrapolacja siatki 2-żetonowej (Y).** Koszt stanu per tryb
   (jobs 1, 10 stanów na tryb, seed 47) **z rozrzutem**, bo cena produkcji
   stała dotąd na samej medianie:

   | tryb | mediana | maksimum | rozrzut | stanów siatki 5 |
   |---|---:|---:|---:|---:|
   | `deep` | 29,45 | 63,53 | 2,16× | 253 |
   | `jamfold` | 1,497 | 2,089 | 1,40× | 6 798 |
   | `hu-deep` | 0,0463 | 0,0593 | 1,28× | 397 |
   | `hu-jamfold` | 0,0060 | 0,0123 | 2,05× | 1 206 |

   (POKER-47 podawał `deep` 38,56 przy maksimum 90,62 — ta sama procedura,
   inny bieg i inna próbka stanów, bo próbkę wybiera ranking ex-post.)
   Mieszanka siatki 5 po medianach daje 17 656 rdzenio-s czystego solvera
   wobec 24 636 zmierzonych w biegu, czyli narzut forka i zbiórki cykli to
   **1,395×** (POKER-47: 1,537×). Siatka 2-żetonowa to 2 923 stany: 49 765
   solve'ów warstw o mieszance `deep` 1 198, `jamfold` 68 859, `hu-deep`
   932, `hu-jamfold` 5 083, oraz horyzont 2 923 × 3 ręce × **5 cykli** =
   43 845 solve'ów (obie zmierzone siatki potrzebowały pięciu cykli).

   - warstwy: 138 467 rdzenio-s po medianach → po narzucie **53,7
     rdzenio-h**; po maksimach 220 070 → **85,3 rdzenio-h**;
   - horyzont: 43 845 × 1,523 rdzenio-s (stawka zmierzona w biegu, więc już
     z narzutem) = **18,5 rdzenio-h**;
   - solver razem **72,2 … 103,8 rdzenio-h**; z tensorem 15 000 prób
     (9,7 rdzenio-h, POKER-46) **~82 … ~114 rdzenio-godzin**.

   Wobec ~91 rdzenio-h z POKER-47 (liczby wyłącznie medianowe) mediana
   spadła do ~82, ale **górny koniec rozrzutu, ~114, przekracza ~108
   rdzenio-godzin z decyzji 25**. Zapasu nie ma po żadnej stronie: sam
   zbieżny horyzont kosztuje 18,5 rdzenio-h (przy trzech cyklach byłoby
   11,1), a rozrzut kosztu trybu `deep` 2,16× decyduje o tym, czy bieg
   zamknie się w budżecie. To jest liczba do decyzji o koszcie, nie do
   przemilczenia.

Świadomie zostawione: **105 z 253 stanów `deep` ma ε etapowe powyżej
tolerancji 5e−5 (maks 1,74e−4), a 110 kończy na sufcie 384 iteracji** — ten
sam nierozwiązany punkt co w POKER-47, i to on rządzi ex-post ε (dług
odziedziczony 90,1%). Krzywa POKER-47 mówi, ile kosztuje jego domknięcie:
żeby najgorszy stan `deep` zszedł do 5e−5, potrzeba sufitu 1 536 iteracji,
czyli ~4× drożej na trybie, który już teraz decyduje o rozrzucie budżetu.
Podłoga horyzontu ~2e−4 jest pochodną tej samej tolerancji etapowej, więc
obie sprawy są **jedną decyzją o cenie, nie dwiema** — i należą do
kontraktu produkcyjnego. Pomiar wrażliwości brzegu zrobiony jest na siatce
10 (2 347 stanów), nie 5: mechanizm propagacji jest ten sam (te same
21 warstw, ten sam zegar, ta sama gra etapowa), różni się rozdzielczość
stacków, a trzy biegi siatki 5 kosztowałyby ~7,5 rdzenio-godziny zamiast
1,4 bez zmiany wniosku.

**Rozstrzygnięcie architekta (weryfikacja niezależna 2026-08-30).**
Zakres, bramka i raporty commitów sprawdzone; liczby ε, kosztów
i czasu biegu odczytane z artefaktów `grid5d` i zgodne co do cyfry;
zakres finalnego commita to wyłącznie ten dokument. POKER-49
**zamknięty**. Dwie zostawione decyzje cenowe rozstrzygam tak:
(1) **koszt produkcji 82–114 rdzenio-godzin przyjęty** — ~108
z decyzji 25 było oszacowaniem (już dwukrotnie korygowanym), a miarą
jest wykonalność: górny koniec to ~29 h zegarowych na 4 rdzeniach
albo kilka szardowanych sesji, w klasie budżetu wybranej przez
operatora; (2) **podniesienia sufitu `deep` do 1 536 nie kupuję
teraz** — metryką celu jest ex-post ε, a ono siedzi pod punktem
odniesienia 5e−4 (zapas 6,7%); opcja pozostaje wyceniona i zostanie
wykonana osobnym kontraktem wyłącznie wtedy, gdy ε produkcji
przekroczy 5e−4 (twardy próg kontraktu produkcyjnego pozostaje
1e−3, raport zawsze porównuje z 5e−4). Cienki zapas jest zapisany
jako ryzyko biegu produkcyjnego, nie przemilczany.

**POKER-48 (moc pomiaru areny Spin: rotacja miejsc, wspólne seedy,
statystyka na blokach) zamknięty.** Realizacja decyzji 26 pkt 1.
Dotychczasowy pomiar `poker.spin_arena` miał dwie wady naraz: hero
siedział zawsze na miejscu 0 (obciążenie pozycyjne) i jeden RNG
prowadził cały turniej, więc talia ręki `i+1` zależała od liczby losowań
akcji ręki `i` — każda różnica decyzji przesuwała wszystkie późniejsze
karty i „wspólny seed" nie znaczył „wspólne karty". Po zmianie talia
i losowość akcji ręki pochodzą wyłącznie od pary (seed turnieju, indeks
ręki) — wzorzec `poker.table` — a jednostką statystyczną jest blok:
ten sam seed w trzech rotacjach cyklicznych, hero kolejno na każdym
miejscu przy identycznej sekwencji kart (pod testem). CI wyłącznie na
blokach; obok normalnego bootstrap percentylowy (replikacje parametrem,
domyślnie 1000, seed jawny, deterministyczny — pod testem).
`compare_blocks` porównuje dwa zestawy (hero, villain) na wspólnych
seedach bloków statystyką na różnicach sparowanych; identyczne ramiona
znoszą się do dokładnie zera — pod testem. Komendy:

```
Z  python tools/run_arena.py 320 3x
AA python tools/run_arena.py sd 320 3x
AB python tools/run_arena.py seats 20000 3x
```

1. **Zmierzona redukcja SD (AA):** SD ROI na turniej (estymator sprzed
   zmiany: miejsce 0, jednostka turniej) i SD na blok, te same seedy
   21…340, trzy pary agentów. N z jawnego wzoru
   N = ((z₀.₉₇₅ + z₀.₈₀) · SD / Δ)² = ((1,96 + 0,8416) · SD / Δ)²
   (moc 80%, α = 0,05, dwustronnie):

   | para | SD/turniej | SD/blok | redukcja | N turniejów 5/10 pp (sprzed) | N bloków 5/10 pp (po) |
   |---|---:|---:|---:|---:|---:|
   | field vs always-jam | 148,8 pp | 76,5 pp | 48,6% | 6 953 / 1 739 | 1 840 / 460 |
   | field vs $1 fish | 140,0 pp | 58,1 pp | 58,5% | 6 156 / 1 539 | 1 061 / 266 |
   | tight vs always-jam | 124,8 pp | 77,7 pp | 37,7% | 4 894 / 1 224 | 1 898 / 475 |

   Uczciwy rozkład tej redukcji: samo uśrednienie trzech niezależnych
   turniejów dałoby 1 − 1/√3 = 42,3%, więc rotacja realnie pomaga tam,
   gdzie wynik pary ma komponent pozycyjny (field vs $1 fish: 58,5%,
   SD bloku 58,1 pp wobec 80,8 pp przy niezależnych rotacjach), a na
   parze tight vs always-jam rotacje są dodatnio skorelowane przez
   wspólne karty (37,7% < 42,3%). W koszcie turniejowym (blok = 3
   turnieje) wykrycie 10 pp to odpowiednio 1 380 / 798 / 1 425
   turniejów wobec 1 739 / 1 539 / 1 224 sprzed zmiany. Cel decyzji 26
   (56% dla 10 pp przy N = 320) osiąga na blokach tylko para
   field vs $1 fish; do twierdzeń „bijemy X" służy jednak
   `compare_blocks` na wspólnych seedach (różnice sparowane), a dalsza
   redukcja bez obciążenia czeka na AIVAT po blueprincie
   (decyzja 26 pkt 2).

2. **Obciążenie pozycyjne zmierzone (AB):** ROI tego samego agenta
   osobno na każdym miejscu, wspólne seedy 21…20020, bez rotacji
   (SE pojedynczego miejsca ≤ 1,04 pp — `se_seat_max` w wyjściu):

   | para | miejsce 0 | miejsce 1 | miejsce 2 | rozstęp |
   |---|---:|---:|---:|---:|
   | field vs always-jam | +20,7% | +20,5% | +17,6% | 3,15 pp |
   | field vs $1 fish | +2,6% | −0,9% | +0,2% | 3,55 pp |

   Rozstęp ~3–3,6 pp (≈ 2 SE różnicy miejsc) to wielkość, którą
   rotacja usuwa z konstrukcji — a stary pomiar w całości wliczał do
   ROI hero; w obu parach miejsce 0, na którym hero siedział na
   stałe, jest najkorzystniejsze z trzech.

3. **Liczby przeliczone na blok (Z):** decyzje 22/23 i bloki POKER-42/43
   wyżej — stare liczby zastąpione. Punkty się przesunęły (np. field vs
   $1 fish z +4,1% na −2,5%), bo stary strumień kart był sprzężony
   z decyzjami agentów; przedziały zwęziły się (field vs $1 fish
   ±15,7 pp → ±6,4 pp przy tych samych 320 seedach; field vs
   always-jam ±16,1 pp → ±8,4 pp). Werdykty
   decyzji bez zmian: „bije $1-ish fisha" nadal nieosiągnięte (CI
   obejmuje zero), przewaga nad always-jam teraz rozstrzygnięta całym
   przedziałem.

**Adnotacja POKER-54 do obu tabel:** obie zmierzył rozgrywacz sprzed
naprawy kolejności i wymuszonego wejścia za darmo. Po naprawie, na tych
samych seedach: w tabeli AA para field vs always-jam jest **bit w bit ta
sama**, field vs $1 fish ma SD/blok 58,4 pp zamiast 58,1 (redukcja 58,4%,
N bloków 5 pp **1 071**), a tight vs always-jam SD/turniej 124,2 pp
i SD/blok 76,9 pp (redukcja 38,1%, N bloków 5 pp **1 859**); w tabeli AB
żadne z sześciu miejsc nie rusza się o więcej niż **0,11 pp** przy SE
1,04 pp, a rozstępy 3,15 pp i 3,55 pp przechodzą w 3,18 pp i 3,41 pp.
Werdykty tego bloku (rotacja usuwa rozstęp pozycyjny, „bijemy X" wymaga
`compare_blocks`) bez zmian — pomiar i komendy w bloku POKER-54.

Świadomie zostawione: kotwica krzyżowa rozgrywacza z silnikiem
(decyzja 27 pkt 4) jawnie poza tym kontraktem — wchodzi z następnym
kontraktem dotykającym rozgrywacza; AIVAT zablokowany na blueprincie
(decyzja 26 pkt 2).

Następne kroki:

1. **Kierunek treningu rozstrzygnięty
   ([decyzja 25](decisions/25-blueprint-po-dagu-zegara-pifp-cfrplus.md)):**
   blueprint po DAG-u zegara (backward induction, ICM tylko na
   horyzoncie), PI-FP w grze 3-osobowej + CFR+ w endgame'ach HU,
   169 klas z łącznymi rozkładami trójek; metryka: ex-post
   best-response ε. **Pilot POKER-46 zdany i zweryfikowany
   niezależnie**, **POKER-47 zamknięty wariantem (i)** (budżet PI-FP
   z krzywej: sufit 384, tolerancja 5e−5), **POKER-49 zamknięty**:
   kotwice `wt2_fold`, horyzont zbieżny do tolerancji (delta 1,285e−4
   w pięciu cyklach wobec 0,00209 na sufcie), CFR+ ważony własnym
   reachem ze stopem na tolerancji (zero z 397 stanów `hu-deep` powyżej
   niej), ślepota metryki na brzeg zmierzona (zaburzenie 0,002 przesuwa
   ex-post ε o ~1e−5). **POKER-50 zamknięty** (blok wyżej): bieg
   produkcyjny siatki 2-żetonowej pod tymi budżetami — ex-post ε maks
   4,720e−4 **poniżej punktu odniesienia 5e−4** (zapas 5,6%), kryterium
   blokujące 1e−3 z zapasem 2,1×, **opcja sufitu 1536 się nie
   uruchamia**; koszt regeneracji artefaktu 76,6 rdzenio-h (faktyczny
   z restartami 92,8–95,6); artefakt poza repozytorium, w repo artefakt
   kontrolny łańcucha pod testem bramki. **POKER-51 zamknięty**
   (blok wyżej): format binarny `.bpk` z dostępem swobodnym per stan
   i czytnik stdlib w pakiecie, kryterium kontraktu ZMIERZONE
   I SPEŁNIONE — przyrost ex-post ε po round-tripie −17,7% na pilocie
   i −3,7% na artefakcie kontrolnym wobec dopuszczalnego +10%;
   weryfikacja niezależna architekta i audyt świeżym kontekstem
   2026-09-04: trzy findingi blokujące (wszystkie w dokumencie,
   żaden w kodzie) naprawione z dowodami, sortowanie konwertera
   pod testem czerwonym na mutacji audytora. **POKER-52 zamknięty**
   (blok wyżej; weryfikacja niezależna architekta i audyt świeżym
   kontekstem 2026-09-04/05 — dwa findingi blokujące audytu, w tym
   trzecia twarz rozjazdu kolejności, naprawione z czerwienią przed
   poprawką i potwierdzone na ponownym biegu BF): agent gra z artefaktu
   w arenie i w rejestrze CLI, siła
   zmierzona na rotacjach POKER-48. OBJECTION kodera wobec kryterium
   „licznik fallbacku w zasięgu siatki = 0" rozstrzygnięty
   [decyzją 28](decisions/28-adjudykacja-objection-poker52-rozjazdy-areny.md):
   proxy stało na fałszywym założeniu totalności odwzorowania i zostało
   zastąpione licznikami błędów odwzorowania (blokująco 0, pod testami
   wzrostu), a cztery rozjazdy areny z modelem zakwalifikowane — dwa jako
   usterki rozgrywacza (POKER-54), przeskok trybu i horyzont jako
   odwzorowanie agenta (POKER-55), warstwy 1–5 do decyzji po ponownym
   pomiarze. **POKER-54 zamknięty** (blok wyżej; audyt świeżym kontekstem
   2026-09-05: kolejność od agresora czysta z niezależną wyrocznią, trzy
   findingi blokujące wokół darmowego wejścia i dowodów zer naprawione
   z czerwieniami, resztkowe rozjazdy drzew policzone jawnie zamiast
   zerowane): kolejność od agresora
   i wymuszone wejście za darmo, trzy liczniki rozjazdu zerami blokująco,
   wpływ na liczby POKER-42/43/48 zmierzony i mieszczący się w ich własnych
   CI. **POKER-55 DOSTARCZONY** (blok wyżej): agent czyta artefakt tam,
   gdzie dotąd wołał regułę awaryjną — warstwa cyklu punktu stałego dla rąk
   za horyzontem i bliźniaczy węzeł jam/fold przy przeskoku progu 7 bb;
   fallback spadł z 2,299% do **0,850% decyzji** i jest wyłącznie granicą
   artefaktu (warstwy 1–5), a ponowny pomiar BF/BG/BH **zdejmuje
   zastrzeżenie „mierzymy parę artefakt + reguła"**: wpływ reguły awaryjnej
   jest nieodróżnialny od zera (CI −0,39..+0,19 pp vs `field_exploit`) przy
   przewadze sparowanej +5,20 pp (CI +3,74..+6,66), więc przewaga jest
   przypisywalna artefaktowi — nadal wyłącznie wobec trzech skryptów areny,
   bez twierdzeń o polu $1. Następny krok linii: **decyzja architekta
   o warstwach 1–5** (dane: blok POKER-55 pkt 10 — 0,844% decyzji, wpływ
   reguły w granicach CI, cena +17,5% biegu produkcyjnego), a po niej AIVAT
   (POKER-53), który ma teraz naprawiony przyrząd (decyzja 28 pkt 4);
   decyzja 29 bramkowała pomiary tierowe tym pomiarem — jest wykonany.
   Otwarte i wycenione: **697 z 1 198 stanów `deep`
   produkcji kończy powyżej tolerancji etapowej (739 na sufcie 384)**
   — produkcyjne potwierdzenie wzorca pilota; domknięcie do 5e−5 to
   sufit 1 536 iteracji, ~4× drożej na najdroższym trybie — ta sama
   tolerancja etapowa wyznacza podłogę horyzontu, więc to jedna
   decyzja o cenie, nie dwie, i uruchamia się wyłącznie przy ε > 5e−4
   (werdykt architekta 2026-08-30). Format
   artefaktu przestał być szacunkiem: napisany i zmierzony w POKER-51
   plik produkcyjny ma **19 016 752 B** (szacunek z danych `grid5b`
   mówił ~38 MB, decyzja 25 zakładała 0,25–1 GB), bo 60% komórek to
   węzły nieosiągalne i nie trafiają do pliku wcale. Kwantyzacja do
   uint8 daje maksymalny błąd 0,0026 **w przestrzeni
   prawdopodobieństw akcji** — to inna jednostka niż ε (udział puli)
   i porównanie tych liczb wprost było błędem (korekta architekta
   2026-08-29); koszt w ε jest **zmierzony** tym samym narzędziem
   ex-post (−17,7% na pilocie, −3,7% na artefakcie kontrolnym), więc
   kryterium akceptacji kontraktu formatu jest spełnione;
2. **moc pomiaru areny: POKER-48 zamknięty** (blok wyżej) — rotacja
   miejsc, wspólne seedy i CI na blokach z bootstrapem; twierdzenie
   „bije X" wymaga `compare_blocks` na wspólnych seedach, a dalsza
   redukcja wariancji bez obciążenia czeka na AIVAT po blueprincie
   (decyzja 26 pkt 2, kolejność HU → Spin z decyzji 26 pkt 3);
3. duplikacja rozgrywacza `poker.spin_arena` względem silnika
   zdarzeniowego rozstrzygnięta
   ([decyzja 27](decisions/27-rozgrywacz-spin-arena-duplikacja-pod-straza.md));
   kotwica krzyżowa z pkt 4 tej decyzji spłacona w POKER-52 i zielona.
   Zakwalifikowane po POKER-52
   ([decyzja 28](decisions/28-adjudykacja-objection-poker52-rozjazdy-areny.md)):
   kolejność licytacji po ponownym otwarciu (obie twarze: arena pyta UTG
   przed BB, a potem BB po odpowiedzi UTG) i brak wymuszenia call-a za
   darmo to **usterki rozgrywacza jako przyrządu** — **naprawione
   w POKER-54** wraz z pomiarem wpływu na liczby POKER-42/43/48
   (adnotacje przy tamtych blokach; żadna teza się nie zmieniła);
4. POKER-26 (informacja zwrotna przy stole LAN) — szkic czeka na
   zatwierdzenie; POKER-28 (memoizacja parsowania w testach
   architektury, wiązanie checkpointu) nadal zasadny; POKER-27
   warunkowy — tylko przy powrocie do cash HU (decyzja 18).

Nie trenować cash-MCCFR. Nie twierdzić, że bijemy field $1.

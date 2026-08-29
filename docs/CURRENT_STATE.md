# Stan bieżący produktu Poker

Wersja pakietu: 0.1.0 · ostatnie zamknięte zadanie: POKER-47 (krzywa
ex-post ε vs budżet iteracji PI-FP zmierzona, budżet solvera wybrany
z pomiaru, pilot powtórzony; pakiet `poker` nietknięty); POKER-46 (pilot
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
  `_fp_solve` z tym sufitem — też pod testem). Testy
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
  testy do POKER-49.
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
od POKER-33. Pełna siatka stanów istnieje wyłącznie jako pilot
w `tools/blueprint/` (krok 5 żetonów, artefakt poza repozytorium,
POKER-46/47) — w pakiecie `poker` jej nie ma i żaden agent z niej nie
korzysta. Sandbox niezaufanych agentów to osobna decyzja, gdy pojawi
się agent spoza repozytorium.

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

**POKER-42 (arena ROI) zamknięty.** Pomiar POKER-45
(`tools/run_arena.py 360 3x`): tight vs always-jam −46.7% ROI.
Exploit call vs random: +18.3%, CI (+3.2, +33.5) > 0. Play woła jam
na głębokim stole exploitem.

**POKER-43 (field exploit) zamknięty.** Bez flata ciasny 3bet przegrywa
z szerokim openem. Field book: open 48% / 3bet 39% / call 48%.
Pomiar POKER-45 (`tools/run_arena.py 320 3x`): vs always-jam +16.3%
(CI +0.2..+32.3); vs $1-ish fish +4.1% (CI −11.6..+19.7) — CI obejmuje
zero, oczekiwanie „bije $1-ish fisha" **nieosiągnięte** na N=320
([decyzja 23](decisions/23-field-exploit.md)).

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
   dotyczyła budżetu 24/1e−3, który nie trzymał jakości; obowiązuje
   liczba z bloku POKER-47 (~91 rdzenio-godzin) i zapasu już nie ma.**

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
8. **Nowa ekstrapolacja siatki 2-żetonowej.** Koszt stanu pod
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
   wdrożono; `eps_curve.py` mierzy dziś wyłącznie PI-FP.

Świadomie zostawione: 39 stanów `hu-deep` ma ε etapowe powyżej nowej
tolerancji (maks 7,1e−5), bo CFR+ chodzi na stałych 128 iteracjach —
nietknięty, skoro jego wkład w ex-post ε jest o rząd wielkości mniejszy
niż solvera 3-osobowego. Horyzont nadal kończy się na sufcie trzech
cykli z deltą 0,00209 > `--tail-tol`; to błąd warunku brzegowego, a nie
solvera, i w ex-post ε się nie pojawia (ogon jest zamrożony dla obu
stron) — osobna sprawa do kwalifikacji.

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

Następne kroki:

1. **Kierunek treningu rozstrzygnięty
   ([decyzja 25](decisions/25-blueprint-po-dagu-zegara-pifp-cfrplus.md)):**
   blueprint po DAG-u zegara (backward induction, ICM tylko na
   horyzoncie), PI-FP w grze 3-osobowej + CFR+ w endgame'ach HU,
   169 klas z łącznymi rozkładami trójek; metryka: ex-post
   best-response ε. **Pilot POKER-46 zdany i zweryfikowany
   niezależnie**, **POKER-47 zamknięty wariantem (i)**: budżet PI-FP
   wybrany z krzywej (sufit 384, tolerancja 5e−5), pilot powtórzony,
   ex-post ε poniżej progu 0,001 puli (bloki wyżej). Następny krok
   linii blueprintu to **bieg produkcyjny siatki 2-żetonowej** pod tym
   budżetem (~91 rdzenio-godzin), wraz z tensorem 15 000 prób
   i formatem binarnym artefaktu (decyzja 25 pkt 6). **Przed nim
   obowiązkowo POKER-49** — domknięcie warunku brzegowego horyzontu
   (delta 0,00209 jest 4,8× większa od zmierzonego ε i niewidoczna
   w ex-post ε) oraz tolerancji w endgame'ach HU; bieg produkcyjny
   stojący na niezbieżnym horyzoncie byłby 91 rdzenio-godzin
   zapłaconych za liczbę, której nie umiemy obronić. Format
   artefaktu policzony z danych pilota: maska + uint8 (2 z 3) + zlib
   daje **~38 MB** na całą siatkę produkcyjną (201 B/stan zmierzone
   na `grid5b`), a nie 0,25–1 GB szacowane w decyzji 25 — 60% komórek
   to węzły nieosiągalne, a mediana prawdopodobieństwa dominującej
   akcji to 0,996; kwantyzacja do uint8 daje błąd 0,0039, o rząd
   wielkości mniejszy od ε;
2. **moc pomiaru areny** — różnice rzędu +5–15% ROI wymagają większego
   N albo redukcji wariancji (AIVAT/duplicate), zanim jakiekolwiek
   twierdzenie „bije X" wróci do dokumentów;
3. kwalifikacja duplikacji rozgrywacza `poker.spin_arena` względem
   silnika zdarzeniowego (wątek z audytu POKER-42);
4. POKER-26 (informacja zwrotna przy stole LAN) — szkic czeka na
   zatwierdzenie; POKER-28 (memoizacja parsowania w testach
   architektury, wiązanie checkpointu) nadal zasadny; POKER-27
   warunkowy — tylko przy powrocie do cash HU (decyzja 18).

Nie trenować cash-MCCFR. Nie twierdzić, że bijemy field $1.

# Stan bieżący produktu Poker

Wersja pakietu: 0.1.0 · ostatnie zamknięte zadanie: POKER-29
(Linear weighting w MCCFR); POKER-24 (skala) dostarczony częściowo
— kryterium skali w sprzeciwie, patrz „Następny krok".

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

Persystencji poza plikiem eksportu, side potów multiway, struktur
turniejowych, UI/sieci/wielu stołów (pokerroom), replayu i analizy
(trener), agentów ML (bot) — gałęzie przyszłe z decyzji 01 pozostają
otwarte i niezamówione. Sandbox niezaufanych agentów to osobna
decyzja, gdy pojawi się agent spoza repozytorium.

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

Następne kroki: **POKER-28** — findingi audytu POKER-24/25 (wiązanie
checkpointu z seedem i konfiguracją, memoizacja parsowania w testach
architektury); **POKER-27** — krzywa jakość-vs-skala (artefakty
z rosnących skal trenowane i mierzone poza repozytorium, arena o mocy
rozdzielającej różnice rzędu 50 BB/100) rozstrzyga, czy skala w ogóle
kupuje jakość, i dopiero na tej podstawie wybieramy formę artefaktu
(po 28; trener już waży liniowo). Potem c3 (restricted Nash response)
albo — gdy krzywa okaże się płaska — nowa kwalifikacja metody
(decyzja 09, pkt 4).
Ulepszenia agentów wyłącznie z pomiarem w arenie (decyzja 04, pkt 2).

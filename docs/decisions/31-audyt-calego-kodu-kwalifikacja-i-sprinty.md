# 31. Audyt całego kodu: kwalifikacja findingów, adjudykacja OBJECTION i sprinty naprawcze

Status: obowiązuje. Autor: architekt, 2026-09-26.
Podstawa: [raport audytu całego kodu](../AUDYT_2026-09-26.md) (werdykt
FINDINGI: 7 blokujących, 36 istotnych, 13 informacyjnych), polecenie
operatora „projektuj i nadzoruj sprinty" (2026-09-26) oraz mandat
autonomii z 2026-08-09 (`PAMIEC_OPERACYJNA.md`, DECYZJE Z CZATU).

## 1. Adjudykacja OBJECTION: seed talii nie pochodzi od gracza

Sprzeciw audytu wobec POKER-21 (acceptance 1: „seed" parametrem tworzenia
stołu) i POKER-10 („seed meczu argumentem") **uznany**. Oba kontrakty
kłóciły się z INV-P3 i z decyzjami 03 pkt 3 i 08 pkt 3: talia rozdania jest
czystą funkcją seeda meczu (`table.py` → `betting.py`), więc kto zna seed,
zna karty przeciwnika i board. Kontrakty są niemutowalne; zastępuje je
POKER-69 na zasadach:

1. **LAN:** seed meczu losuje serwer z własnego generatora — seedowanego
   `--serve-seed` operatora serwera (odtwarzalność testów), a bez niego
   entropią systemu. Pole `seed` znika z żądania `create`; protokół
   dostaje wersję 2, więc stary klient jest odrzucany jawnie, nie po cichu.
2. **Lokalny `--human`:** bez jawnego `--seed` seed meczu pochodzi z
   entropii systemu i jest wypisywany dopiero po meczu (replay nadal
   możliwy). Jawny `--seed` zostaje — to świadomy wybór człowieka albo
   testu, a README mówi wprost, że znający seed zna talię. Tryby bez
   człowieka zachowują domyślny seed 0 (bajtowa odtwarzalność z README).
3. Decyzja 03 pkt 3 i decyzja 08 pkt 3 obowiązują w brzmieniu: seed,
   z którego wynika talia, nie jest wejściem gracza przy stole z drugim
   graczem; lokalny wyjątek z pkt 2 jest jawny.

## 2. Kwalifikacja findingów

Waga i treść — z raportu audytu. Numery kontraktów od POKER-69 (58–68
zarezerwowane mapą decyzji 29).

| Finding | Kwalifikacja | Kontrakt / sprint |
|---|---|---|
| B1 + I-04 | zbuduj — INV-P3, OBJECTION uznany | POKER-69 · A |
| B2 + I-21 | zbuduj — jedna reguła miejsc w `poker.spin` | POKER-70 · A |
| B3 (arena, modele: spasowany gracz) | zbuduj | POKER-71 · A |
| B3 (jamfold `_three_way`, drugie miejsce przy 3 żywych) | zbuduj — zmiana modelu, dziś uśpiona (równe stacki) | sprint B |
| B4 + I-20 | zbuduj — przepis pochodzenia i etykieta metody | POKER-72 · A |
| B6 + I-25 | zbuduj — terminale i miara zbieżności openfold | POKER-73 · A |
| B7 | zbuduj — brzeg horyzontu; regeneracja produkcji = wejście operatora | POKER-74 · A |
| B5 | zbuduj — tożsamość z kanonicznej projekcji | POKER-75 · A |
| I-01, I-02, I-03, N-01, N-02, I-05 | zbuduj — odporność serwera LAN | sprint B |
| I-06, I-07, N-03 | zbuduj — CLI: wykluczenia trybów, błędy I/O | sprint B |
| I-08, I-09 | zbuduj — walidacja granicy silnika | sprint B |
| I-10, I-11, I-12, N-07, N-08, N-09 | zbuduj — testy chroniące reguły (mutanty z raportu) | sprint B |
| I-13 | zbuduj — strażnik kierunku importów | sprint B |
| I-18, I-19 | zbuduj — statystyka areny HU | sprint B |
| I-16 | zbuduj — skala stałej cechy klona, regeneracja wag | sprint B |
| I-29, I-30, I-31, N-10 | zbuduj — integralność czytnika `.bpk` | sprint B |
| I-23 | zbuduj — odcisk zegara u konsumenta | sprint B |
| I-22, I-24 | zbuduj — liczniki rozjazdów (bez zmiany drzewa — decyzja 27) | sprint B |
| I-28, I-15 | zbuduj — izolacja RNG portu agenta i test poborów | sprint B |
| I-26, I-27 | zbuduj — jamfold: ε jedną aproksymacją, korekta decyzji 12 | sprint B |
| I-14 | zbuduj — testy ICM z mocą | sprint B |
| I-32, N-11 | zbuduj — raport ε per tryb, sha przy odczycie | sprint B |
| nowy (przegląd POKER-74): reguła guzika HU po wybiciu w modelu (`sorted(żywi)[ręka % 2]`) ≠ arena (`_next_button`) w 9/18 przypadków; wrażliwość V wierszy 3-way do ~2e−2 | zbuduj — stan HU z guzikiem (zmiana modelu i klucza stanu; regeneracja i tak jest wejściem operatora) | sprint B |
| docstringi `blueprint_agent.py` o stacjonarnym cyklu 3 rąk (fałszywe dla 3-way po POKER-74) | zbuduj razem z pozycją wyżej | sprint B |
| nowy (POKER-74 r2): podłoga szumu PI-FP w ogonie brzegu (~1e−3 na e60 > tail_tol) | warunkowo — tylko gdy regeneracja produkcji nie zbiegnie do tail_tol: solver ogona 3-way ciągły w V (decyzja 25) | sprint B (warunkowy) |
| I-17 | już zatwierdzone — POKER-28; uśpione (decyzja 18) | bez zmian |
| N-04 | odłóż — walidacja semantyczna eksportu przy pierwszym konsumencie niezaufanych historii (korpus HH, P-10) | dług |
| N-12 | zbuduj razem z I-28 (widok a mutacja w miejscu) | sprint B |
| N-13 | odłóż — pakiet `tools/blueprint` przy najbliższym kontrakcie przebudowującym jego importy | dług |
| I-33…I-36, N-05, N-06 | zbuduj — dokumenty stanu (architekt) i drobne korekty | sprint C |

Kontrakty sprintu B i C architekt zatwierdza **po zamknięciu sprintu A**,
na świeżym stanie repozytorium (kolejność dowodowa: najpierw poprawność
rozliczeń i modeli, potem ochrona i odporność).

## 3. Pomiary unieważnione do czasu przeliczenia

Zgodnie z PUŁAPKĄ POKER-24 (regeneracja lub poprawka unieważnia pomiary
przy niej):

- **punktacja 10x areny Spin** (B2) — pomiar BG z bloków POKER-52 pkt 6
  i POKER-55 pkt 8 oraz każda liczba areny przy wypłatach 10x; przeliczane
  w POKER-70 tam, gdzie nie potrzeba artefaktu produkcyjnego;
- **rozliczenie side potów areny** (B3) — wszystkie ROI areny Spin
  (przesunięcie 0,1–0,7% rąk); przeliczane w POKER-71 jak wyżej;
- **open/3bet openfold** (B6) — liczby decyzji 20 i 21 oraz książki areny
  oparte na openfold; przeliczane w POKER-73;
- **artefakt produkcyjny blueprintu** (B7) — liczony starym brzegiem
  horyzontu. Regeneracja (przed POKER-74 ok. 76,6 rdzenio-h; po nim wycena
  `mode_census` dla prod-10x: solver 64,3 → 89,0 rdzenio-h, bo horyzont
  cyklu 6 kosztuje ~2× na cykl; poza tym środowiskiem) jest
  **wejściem operatora**; do niej pomiary BF/BG/BH i `prod_identity.json`
  opisują artefakt, którego obecny kod już nie produkuje.

## 4. Porządek sprintu A i nadzór

Zależności wynikają ze wspólnych modułów (konstytucja pkt 14):

- łańcuch Spin: POKER-70 → POKER-71 → POKER-73 (`spin.py`, `spin_arena.py`,
  `jamfold.py`, `openfold.py`, `icm.py`);
- łańcuch blueprintu: POKER-74 → POKER-75 (`solve_grid.py`,
  `tools/blueprint/control/`);
- POKER-69 i POKER-72 rozwijane równolegle, scalane w kolejności
  69 → 72 (wspólne `README.md` i `tests/test_mccfr.py`; właścicielem
  integracji i bramki wspólnego headu jest architekt).

Fale: **1** — POKER-69, 70, 72, 74; **2** — POKER-71, 75; **3** — POKER-73.
Każda fala startuje z headu po integracji poprzedniej.

Kontrakty przeszły przegląd w świeżym kontekście (siedmiu recenzentów,
2026-09-26): 72 poprawki brzmienia wprowadzone przed zatwierdzeniem, jeden
OBJECTION (POKER-74) uznany. Rozstrzygnięcia architekta z przeglądu:

- **POKER-74 — cykl 6 rąk.** W modelu role 3-way zależą od ręki mod 3,
  a guzik HU od ręki mod 2, więc stan ma okres 6. Zamiana etykiet naprawia
  tylko wiersze HU i psuje zbieżność; cykl 6 zbiega do zera maszynowego
  na siatce równoważnej na P przy budżetach testu (na siatkach bliższych
  produkcji — patrz rozstrzygnięcie OBJECTION niżej).
  Koszt: zmierzone +55,5 s bramki (szacunek przeglądu +68 s) i ok. 2×
  czasu horyzontu produkcyjnego na cykl
  (wycena w `mode_census` po zmianie) — przyjęty, bo regeneracja i tak jest
  wejściem operatora.
- **POKER-69 — `--serve-seed` przybija wyłącznie kody stołów.** Seed meczu
  losuje generator wstrzykiwany do `TableServer` (testy), domyślnie CSPRNG;
  kod stołu dostaje każdy gracz, więc seed, z którego wynika kod, nie może
  wyznaczać talii.
- **POKER-72 a decyzja 18.** Regeneracja `strategy_table.py` z POKER-72
  zmienia wyłącznie nagłówek i stałe pochodzenia — sekcja `STRATEGY` jest
  bajt w bajt ta sama — więc nie jest „regeneracją strategii" w rozumieniu
  decyzji 18, a zdania „strategy_table nietknięty" z decyzji 11–23
  pozostają prawdziwe co do strategii i pomiarów.
- **POKER-74 — rozstrzygnięcie BRAK z rundy 1 (2026-09-26).** Na siatce
  e60 delta cyklu 6 stoi na 1,05–1,48e−3 (> tail_tol 5e−4), a przy stałej
  liczbie iteracji PI-FP ten sam cykl zbiega do zera maszynowego: podłogę
  robi stop PI-FP na tolerancji, który czyni odwzorowanie cyklu
  nieciągłym. Kryterium ogona dotyczy więc odwzorowania
  deterministycznego i ciągłego. Wykonawca mierzy krzywe trzech wariantów
  (tolerancja PI-FP w ogonie × {1, 1/3, 1/10}; budżet iteracji zamrożony
  z cyklu 1 per stan; stały budżet równy medianie cyklu 1) i wybiera
  najtańszy osiągający tail_tol na obu siatkach — bez zmiany tail_tol
  i bez nowego pola `GridConfig`; żaden → `BLOCKED` z krzywymi.
- **POKER-74 — rozstrzygnięcie OBJECTION z rundy 2 (2026-09-26):
  opcja B.** Pomiary obaliły przesłankę rozstrzygnięcia BRAK: podłogę
  delty robi szum PI-FP (także argmax najlepszej odpowiedzi), nie sam stop
  na tolerancji. Na e60 (12 cykli) stop na fp_tol stoi na ~1,1–1,5e−3,
  fp_tol/3 i fp_tol/10 nie schodzą trwale pod 5e−4, oba warianty
  zamrożonego budżetu oscylują (stały sufit 384 zmierzony do końca
  tylko na x60 — bieg e60 przerwano po cyklu 1); zbiega wyłącznie krótki
  stały budżet (mediana cyklu 1), ale do punktu stałego słabszego solvera
  (ε gier etapowych ogona do 9,0e−4 wobec 2,6–3,2e−4 ze stopem na
  tolerancji w cyklach 1–12; odchylenie od dokładniejszych
  iteratów do 5,5e−3 — więcej niż naprawiany B7). `converged=True`
  poświadczyłby dokładność, której brzeg nie ma. **Decyzja:** integrowany
  jest cykl 6 z dotychczasowym stopem PI-FP na tolerancji; tail_tol bez
  zmian; flaga `converged` zostaje uczciwa. Cykl 6 usuwa błąd strukturalny
  B7 (wiersze HU dokładne, okres modelu właściwy), a jego podłoga szumu na
  e60 (~1e−3) jest niższa niż starego cyklu 3 na tej samej siatce
  (1,9–2,9e−3). Czy siatka produkcyjna (169 klas) zbiega do tail_tol, pokaże
  regeneracja (wejście operatora); jeśli nie — kontrakt warunkowy
  sprintu B: solver ogona 3-way ciągły w V (np. CFR+ o stałej liczbie
  iteracji, jak w HU, gdzie każdy wariant zbiega), w obszarze decyzji 25.
  Gałąź propozycji opcji A (`sprint-a/POKER-74-r2-fpmedian-propozycja`)
  zostaje nieintegrowana jako zapis pomiaru.
- **POKER-73 — rozstrzygnięcie OBJECTION z rundy 1 (2026-09-27).**
  (a) Konflikt kontraktu jest zasadny: acceptance 4 żądał testu przy
  N = 64, acceptance 8 dopuszczał w bramce tylko N ≤ 24. Reguła N ≤ 24
  chroniła wyłącznie koszt bramki; po przyspieszeniu wyceny (bitowo
  zgodnym z bazą) test przy N = 64 kosztuje 1,6 s, a suma `--durations`
  `test_openfold.py` 7,2 s ≤ 30 s — test zostaje przy N = 64 jako jawny
  wyjątek z docstringiem „dlaczego". (b) Krzywa miary nie jest
  monotoniczna: przy N = 128 wszystkie sześć poziomów mieści się
  w tolerancji 1e−3·Σnagród, przy N = 256 poziom 3x 2/4 ma 1,26e−3.
  Reguła „najmniejsze N w tolerancji" dałaby migawkę, a cel kontraktu to
  liczby modelu zbieżnego, nie z chwilowego dołka krzywej: N to
  najmniejszy punkt kontrolny, **od którego** miara mieści się
  w tolerancji na wszystkich eksportowanych poziomach we wszystkich
  dalszych punktach do 1024 — z krzywej rundy 1: N = 512. Runda naprawcza
  przelicza eksport i liczby areny przy N = 512; adnotacje KOREKTA
  w decyzjach 20–23 mają podać wartość przy N = 512 i rozrzut na
  [256, 512].
- **Obserwacje z raportów fali 1 do sprintu C:** decyzja 12:21-22
  („~+0,05 BI") wobec pomiaru +0,037 na (16, 50, 84) — rozjazd sprzed
  POKER-70; openfold nie daje blindowi all-in z samego SB szansy na pulę
  główną w gałęzi steal (uproszczenie modelu, do opisania albo
  kwalifikacji).
- **PUŁAPKI przy równoległych gałęziach:** koder zapisuje kandydata do
  PUŁAPEK w raporcie commita; do `PAMIEC_OPERACYJNA.md` przenosi go
  architekt przy integracji (limit 80 linii nie znosi równoległych edycji).

Nadzór każdego kontraktu: koder w izolowanym worktree (własna gałąź,
commity lokalne, pełna bramka) → audyt świeżym kontekstem wg
`PROMPT_POKER_AUDYTOR.md` → przy findingach runda naprawcza (najwyżej trzy
rundy; trzecia porażka tej samej klasy = `BLOCKED`, konstytucja pkt 7) →
integracja sekwencyjna na gałęzi sprintu `claude/poker-code-audit-gsfko9`
z pełną bramką po każdym scaleniu → blok stanu w `CURRENT_STATE.md`
pisze architekt. Koderzy nie edytują `CURRENT_STATE.md`, indeksu
dokumentacji ani `PRZEKAZANIE.md` — równoległe gałęzie konfliktowałyby na
dokumentach stanu, a ich treść należy do architekta. `main` pozostaje
operatora.

## 5. Którą gałąź rozwoju ta decyzja zamyka albo czyni droższą

- **pokerroom:** protokół LAN v2 zrywa zgodność z klientami v1 — koszt
  jawny i jednorazowy (odrzucenie wersją), w zamian gałąź zyskuje
  warunek konieczny gry dwóch ludzi: żaden z nich nie wyznacza talii.
  Nie zamyka niczego.
- **trener:** replay nadal pochodzi z eksportu (`DeckSeeded` per rozdanie),
  a lokalny tryb człowieka wypisuje seed meczu po grze — nic nie drożeje.
- **GTO-ML:** drożeje o koszt przeliczeń z pkt 3 i o regenerację artefaktu
  produkcyjnego; alternatywa (budowa P-7/P-8 na artefakcie z błędnym
  brzegiem i na arenie z błędną punktacją) kosztowałaby więcej, bo
  unieważniałaby każdy następny pomiar mapy decyzji 29.

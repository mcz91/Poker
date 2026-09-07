# Przekazanie pracy — produkt Poker (linia blueprintu GTO)

Stan na 2026-09-07. Autor: architekt produktu (sesja kończąca się tym
dokumentem). Adresat: **drużyna przejmująca**, bez kontekstu poprzednich
sesji.

Ten dokument nie jest źródłem statusu — źródłem jest
[`CURRENT_STATE.md`](CURRENT_STATE.md). Tu jest to, czego nowa drużyna
nie odczyta z repo w rozsądnym czasie: **co jest zrobione i dlaczego tak,
co zniknie razem z kontenerem, czego nie wolno twierdzić, i od czego
zacząć**. Każda liczba w tym dokumencie została sprawdzona na źródle
przez cztery niezależne weryfikacje przed jego wydaniem.

---

## 1. Pierwsze 30 minut

```bash
# 1. Konstytucja procesu — bez niej nic w tym repo nie ma sensu
cat ../foundry/CONSTITUTION.md          # repo mcz91/foundry

# 2. Instrukcja obsługi produktu i indeks dokumentów
cat README.md                           # jak uruchomić stół, agentów, LAN
cat docs/README.md                      # streszczenia 29 decyzji + status TaskSpeców

# 3. Stan produktu (długi, ale to JEST źródło prawdy)
cat docs/CURRENT_STATE.md               # Co istnieje / Czego nie ma / Następny krok

# 4. Decyzje — czytaj od 29 wstecz; 29 wyznacza cały bieżący kierunek
ls docs/decisions/

# 5. Pamięć operacyjna ról (dokładnie 80 linii, w tym PUŁAPKI — w całości)
cat PAMIEC_OPERACYJNA.md

# 6. Środowisko i bramka
#    UWAGA: `python` w kontenerze bywa 3.11, a pakiet wymaga >=3.12
python3.13 -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev,train]"
ruff check . && mypy && pytest          # ~5 min 50 s, 483 testy
#    aktualną liczbę sprawdzisz: pytest --collect-only -q | tail -1
```

Gałąź integracyjna: **`claude/poker-project-architecture-jw6ukd`**.
`main` podąża za nią po każdym komplecie audytów (stała autoryzacja
operatora); wykonuje to architekt, nigdy koder.

**Porównuj z `origin/main`, nie z lokalnym `main`** — lokalny ref w tym
checkoucie stoi 86 commitów w tyle (epoka POKER-29). Zanim cokolwiek
zrobisz: `git fetch && git log --oneline origin/main -1`.

---

## 2. Czym jest ten produkt

Silnik pokerowy i bot do **Spin & Go** (3-max hyper-turbo SNG,
winner-take-all z losowanym mnożnikiem). Linia blueprintu ma dwie
warstwy:

- **Pakiet `poker`** — czysty stdlib, bez numpy, bez I/O w silniku.
  Model gry, arena pomiarowa, agenci i **czytnik artefaktu** blueprintu
  (`blueprint_reader`, `blueprint_agent`).
- **`tools/blueprint/`** — solver poza produktem (numpy dozwolony), który
  liczy artefakt strategii. Artefakt **nie wchodzi do repozytorium**
  (decyzja 25 pkt 6) — w repo żyje wyłącznie mały artefakt kontrolny
  łańcucha (`tools/blueprint/control/`, 24 KB) i jego test w bramce.

Algorytm fundamentu GTO: **dokładna indukcja wsteczna po DAG-u zegara
blindów**; stany etapowe 3-osobowe rozwiązywane PI-FP, końcówki HU
CFR+ z uśrednianiem ważonym reach, horyzont jako punkt stały cyklu
ostatniego poziomu z brzegiem ICM. Jakość mierzona **ex-post ε**
(best-response jako MDP przeciw zamrożonym przeciwnikom).

Drzewo preflopowe jest **zamrożone** (jam/fold, open 2.2×, 3bet-jam,
call; 17 liści w `_LEAF_DEFS_3`), a **flat call jest w nim niewyrażalny**
— to trzeci dowód nasycenia z decyzji 29 pkt 2c i powód, dla którego
kontrakt P-14 wymaga nowego rekordu decyzyjnego.

**Czego ten dokument nie opisuje.** Poza linią blueprintu repo zawiera
drugi, zamknięty produkt: stół heads-up NLHE (`table`, `betting`,
`events`, `views`) z adapterami (CLI, gra człowieka z terminala, serwer
wielu stołów w LAN — decyzja 08, eksport historii, korpus self-play,
zbiór przykładów) oraz agentów `rule` / `rule-aggressive` / `clone` /
`mccfr` / `mlp-clone` i macierz equity preflop 169×169. Wszystko pod
bramką (ok. 101 z 483 testów) i pod niezmiennikami INV-P1…P8.
Instrukcja obsługi: `README.md`. Linia Spin/blueprintu ich nie dotyka,
ale kontrakt wychodzący poza `allowed_paths` może je złamać.

---

## 3. Proces fabryki — to nie jest opcjonalne

Repo jest prowadzone przez proces z `mcz91/foundry`. Jego rdzeń:

1. **Nic nie powstaje bez TaskSpec** (`docs/taskspecs/POKER-N.json`,
   schemat `schemas/task-spec.schema.json` z `mcz91/foundry`; wymagane
   `id`, `spec_version`, `class_hint`, `goal`, `acceptance` jako
   CHECKLISTA; dalej `context`, `non_goals`, `operator_inputs`,
   `allowed_paths`, `verification`, `approved`). **Wzorzec do
   skopiowania: `docs/taskspecs/POKER-57.json`.** Koder realizuje
   dokładnie jeden kontrakt i nie wychodzi poza `allowed_paths`.
2. **Role mają świeży kontekst**: architekt (kwalifikacja, decyzje,
   scalenia), koder (realizacja), audytor (adwersaryjna weryfikacja).
   Każda rola ma swój prompt w korzeniu repo:
   `PROMPT_POKER_ARCHITEKT.md`, `PROMPT_POKER_KODER.md`,
   `PROMPT_POKER_AUDYTOR.md` — wchodź w rolę stamtąd, nie z tego
   dokumentu. Prompt architekta definiuje niezmienniki **INV-P1…P8**.
   Audytor pisze wyłącznie PUŁAPKI do pamięci operacyjnej.
3. **Bramka zielona przed każdym commitem**: `ruff check .`, `mypy`,
   `pytest` (pilnuje ich `tests/test_repo_gate.py`). „Bramka zielona"
   ≠ „typy sprawdzone" poza `files` z pyproject.
4. **Liczba w dokumencie = niezmiennik w teście.** Każde kryterium
   ilościowe raportowane jako spełnione ma asercję. Dowód skryptem
   w scratchpadzie nie chroni następnego biegu.
5. **Komenda regeneracji w dokumencie musi działać jak napisana** —
   ze świeżego katalogu, dosłownie.
6. **OBJECTION** (CONFLICT | INCOMPLETE | UNSAFE | UNTESTABLE) to
   normalny wynik pracy, nie porażka; zgłasza go koder albo audytor.
   W tej linii uznano m.in. POKER-42 i POKER-33 (audytor) oraz
   POKER-45 i POKER-52 (koder) — wszystkie zmieniły kontrakty na lepsze.
7. **Zamknięcie zadania aktualizuje też „Następny krok"** w
   CURRENT_STATE — jednym commitem.

Wzorzec, który wielokrotnie się opłacił: **najpierw zmierz krzywą,
potem ustaw próg** (POKER-47). Kryterium ilościowe wymyślone przed
pomiarem kilka razy okazało się mierzyć nie to, co miało chronić
(POKER-52, adjudykacja w decyzji 28).

---

## 4. Stan linii na dziś

### Zamknięte (kontrakt → koder → weryfikacja niezależna → scalenie; przy kodzie produktu dodatkowo audyt świeżym kontekstem)

| kontrakt | co dał |
|---|---|
| POKER-44/45 | naprawa i scalenie linii Spin (decyzja 24) |
| POKER-46 | tensor rolloutów 3-way z kotwicami orientacji osi |
| POKER-47 | krzywa ε-vs-iteracje; budżet PI-FP 384/5e−5 |
| POKER-48 | arena z rotacjami miejsc, CI na blokach, bootstrap |
| POKER-49 | domknięcie horyzontu i endgame'ów HU, CFR+ na tolerancji |
| POKER-50 | **bieg produkcyjny**: 49 765 stanów, ε maks 4,720e−4, 76,6 rdzenio-h |
| POKER-51 | format binarny `.bpk` v1 + czytnik stdlib; koszt kwantyzacji w ε |
| POKER-52 | agent `blueprint` w arenie i w rejestrze CLI areny + pierwszy pomiar siły |
| POKER-54 | rozgrywacz areny: akcja od agresora, wymuszone wejście za darmo |
| POKER-55 | wierność agenta artefaktowi: cykl horyzontu, węzeł bliźniaczy |
| POKER-56 | higiena tierowa: tabela tierów, normalizacja, fingerprint, wycena per-mode |
| POKER-57 | format `.bpk` v2: maska uint32, cztery sloty, uint16, ε per stan, marginesy indyferencji |

### W locie

**Brak.** POKER-57 (`.bpk` v2) został zamknięty 2026-09-07 — patrz tabela
wyżej. Następny kontrakt do wzięcia: **POKER-58** (szkic w
[`docs/taskspecs/drafts/`](taskspecs/drafts/)).

### Kolejka — mapa decyzji 29, szkice w repo

Szkice TaskSpeców leżą w [`docs/taskspecs/drafts/`](taskspecs/drafts/)
(niezatwierdzone — bez pola `approved` koder ich nie realizuje):

| id | kontrakt | koszt [rdzenio-h] | blokady |
|---|---|---:|---|
| P-3 POKER-58 | domknięcie warstw 1–5 przez osiągalność łańcucha DOKŁADNEGO (nie pełna siatka) | 2–10 | — |
| P-4 POKER-59 | checkpoint horyzontu per cykl | ~1 | wymagany przed przebiegami > 12 h |
| P-5 POKER-53 | AIVAT w przestrzeni nagród | ~5 | 55+58 dla sensownych liczb |
| P-6 POKER-60 | trzy sondy błędu modelu (siatka / kwantyzacja / ziarno tensora) | ~24 | — |
| P-7 POKER-61 | artefakt WTA@25bb — jednozmienny A/B wypłat + kill-check | ~64 | 54+55+58+59 (tabela tierów NIE — decyzja 30) |
| P-8 POKER-62 | T-MODAL 90 żetonów WTA + krzywa zegara | ~18 (+18) | j.w. **+ tabela tierów** |
| P-9 POKER-63 | T-MID 120 WTA | ~36 | warunkowy |
| P-10..13 | warstwa eksploatacyjna DBR (builder modelu → HU → krzywa P_max → pełny DAG) | ~62 (sam P-13: 53,5) | **korpus hand histories** |
| P-14 POKER-68 | wyceniony spike gałęzi flat-call | ~5 | wymaga nowego rekordu decyzyjnego |

> **Koszty P-7…P-9 i P-13 są DOLNYMI oszacowaniami** (decyzja 29,
> KOREKTA 2026-09-05, fixture `mode_census`): założenie o przenośności
> tempa per stan między wektorami wypłat zostało **obalone co do
> kierunku** — WTA wymaga więcej iteracji PI-FP/CFR+ (na łańcuchu
> kontrolnym: jamfold 1,39×, hu-deep 1,12×, hu-jamfold 1,91×).
> Faktyczny mnożnik wyceni dopiero pierwszy przebieg WTA. Nie budżetuj
> tych pozycji jako wycen.

---

## 5. Artefakty — najważniejsza część tego dokumentu

**Artefakty produkcyjne żyją w scratchpadzie sesji i ZNIKNĄ razem
z kontenerem.** To nie jest awaria — tak stanowi decyzja 25 pkt 6
(artefakt poza gitem). Ceną jest regeneracja:

| artefakt | rozmiar | koszt regeneracji |
|---|---:|---:|
| tensor rolloutów (`PROD/tensor/`) | 20 473 439 B (19,5 MiB) | 11,2 rdzenio-h |
| bieg siatki (`PROD/grid2/`, 21 warstw + brzeg) | 39 586 164 B | 65,4 (horyzont 25,2 + warstwy 40,2) |
| `blueprint.bpk` v1 | 19 016 824 B (18,1 MiB) | 24 s (pakowanie, blok BA) |
| `blueprint_v2.bpk` | 40 490 256 B (38,6 MiB) | 32 s (pakowanie, blok BN + marginesy BP) |

> Artefakt v1 z 4 września ma 19 016 752 B — różnica 72 B to
> `fingerprint` dopisany przez POKER-56; regeneracja daje dziś bajt
> w bajt 19 016 824 B.

**Komendy pełnej regeneracji: bloki POKER-50 (AC–AH), POKER-51 (BA —
artefakt v1) i POKER-57 (BN + BP — artefakt v2, `--format-version 2`
i `margins.py`) w CURRENT_STATE.** Kolejność: AC → AD → AE → AF → AG →
AH → BA/BN → BP; wszystkie z `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
MKL_NUM_THREADS=1`. Są sprawdzone dosłownie ze świeżego katalogu.

Sam artefakt to ~19 h ściennych na 4 rdzeniach (AC+AE, 76,6 rdzenio-h);
z pomiarami ex-post/ICM/dekompozycji i pakowaniem (AF–AH, BA/BN) ~20,5 h.

**Zanim odpalisz regenerację, zrób POKER-59 (checkpoint horyzontu)** —
jeden restart kontenera w środku horyzontu kosztował 16,2 rdzenio-h,
bo jednostką wznowienia jest dopiero warstwa.

**Po regeneracji liczby z sekcji 6 przestają obowiązywać, dopóki nie
udowodnisz tożsamości artefaktu** — porównaj sha256 z
`prod_identity.json` (zgodność = pomiary obowiązują) albo powtórz
pomiary (BF/BG/BH, AF). To jest PUŁAPKA POKER-24: regeneracja unieważnia
pomiary przy artefakcie, a bramka tego nie łapie.

Dwustopniowy dowód odtwarzalności (decyzja 06): mały łańcuch kontrolny
chodzi w bramce przy każdym `pytest`, pełna regeneracja komendami
z dokumentu poza bramką.

**Dystrybucja artefaktu jest rozstrzygnięta**
([decyzja 30](decisions/30-dystrybucja-artefaktu-i-odblokowanie-p7.md)):
artefakt **nie wchodzi do żadnej formy dystrybucji przez repozytorium**,
bo `mcz91/Poker` jest publiczne — release, LFS i gałąź z plikiem to
nieodwracalna publikacja strategii, a przyszłe profile eksploatacyjne są
na to wrażliwsze niż blueprint. W zamian w repo żyje **manifest
tożsamości** `tools/blueprint/control/prod_identity.json`: sha256,
rozmiar i pochodzenie **32 plików** artefaktu (119 566 611 B opisanych
w kilku kilobajtach).

Manifest rozwiązuje problem, którego sam plik by nie rozwiązał: po
regeneracji porównujesz sha256 swoich plików z manifestem i przy
zgodności **zachowujesz wszystkie pomiary** (ε, ROI areny, liczniki,
koszty) zamiast powtarzać je za kolejne godziny — to jest wyjście
z PUŁAPKI POKER-24. Narzędzie porównujące katalog z manifestem jest
wymogiem kontraktu POKER-58 (szkic). Przekazanie samego pliku kanałem
prywatnym pozostaje możliwe i nie wymaga zmiany decyzji 30 — zakazana
jest publikacja, nie przekazanie.

### Jak to uruchomić

```bash
# arena: książki / agent z artefaktu / cena samej reguły awaryjnej
python tools/run_arena.py 320 3x                                   # książki referencyjne (POKER-48)
python tools/run_arena.py blueprint PROD/blueprint.bpk 10000 3x    # blok BF — źródło ROI z sekcji 6
python tools/run_arena.py fallback  PROD/blueprint.bpk 10000 3x    # blok BH — źródło −0,10 pp

# stół HU, gra człowieka, LAN, korpus, trenerzy — README.md
python -m poker.adapters.cli --seed 7 --hands 50 --export mecz.json
```

---

## 6. Liczby, które wolno cytować — i czego twierdzić nie wolno

### Wolno (wszystkie zmierzone na tym systemie, z komendami w dokumencie)

| wielkość | wartość |
|---|---|
| ex-post ε artefaktu produkcyjnego | maks **4,720e−4**, mediana **1,075e−4** (49 765 stanów) |
| próg blokujący / punkt odniesienia | 1e−3 (zapas 2,1×) / 5e−4 (zapas 5,6%) |
| V vs ICM (uzasadnienie kierunku) | do **9,5% sumy wypłat** (maksimum po pełnej siatce) |
| ROI agenta w arenie (3x, N=10 000 bloków) | **+5,20%** vs `field_exploit` (CI +3,74..+6,66), +6,36% vs `dollar_fish`, +8,23% vs `always_jam` |
| wpływ reguły awaryjnej po naprawach | **−0,10 pp** (CI −0,39..+0,19) — nieodróżnialny od zera |
| fallback agenta | **0,850%** decyzji, w całości granica artefaktu |
| udział decyzyjny trybów | `deep` 33,3%, `jamfold` 10,5%, `hu-deep` 39,1%, `hu-jamfold` 17,1% |
| koszt kwantyzacji uint16 w ε (POKER-57) | **+0,015%** wobec limitu +10% |

### Zakazy twierdzeń — obowiązują bezterminowo

1. **Nie twierdzić, że bijemy pole $1.** Pomiar jest przeciw trzem
   skryptom z repozytorium (`field_exploit`, `dollar_fish`,
   `always_jam`), nie przeciw realnej populacji. `dollar_fish` to skrypt,
   nie pole.
2. **Nie cytować cudzych liczb jako naszych** — ani redukcji wariancji
   (85%, 54×, 74× to 2p0s chip-EV HUNL), ani magnitud eksploatacji.
3. **Nie twierdzić „dorównujemy SOTA"** — $0,049 u Ganzfrieda–Sandholma
   to ich próg zatrzymania, nie osiągnięta podłoga. **Nie porównywać
   naszej bezstratności z „abstrahowanym" Pluribusem** — używa tej samej
   bezstratnej abstrakcji 169 klas przy bogatszej abstrakcji akcji, więc
   nasze drzewo jest grubsze, nie cieńsze. Ex-post cytować jako
   **Algorytm 3** Ganzfried–Sandholm IJCAI-09, nie 6.
4. **ε jest w jednostkach sumy wektora wypłat**, nie „puli pota".
   Prawo przeliczenia: **ROI [pp] = ε × mnożnik × 100**.
5. **Nie czytać ROI z areny jako „siły GTO"** — to pomiar pary
   (artefakt + reguła decyzyjna) w konkretnym zestawie przeciwników.
6. **Zakazy metodologiczne AIVAT (decyzja 26, w mocy przez decyzję 29
   pkt 7)** — obowiązują od pierwszej linii P-5: zakaz Jensena (nigdy
   redukcja wariancji w przestrzeni żetonów z mapowaniem przez ICM —
   AIVAT działa w przestrzeni NAGRÓD); zakaz liczenia CI na rozdaniach
   wewnątrz turnieju; zakaz strojenia funkcji wartości po zobaczeniu
   danych ewaluacyjnych; zakaz handlu nieobciążonością za wariancję;
   kryterium blokujące ≥ 56% redukcji SD; formuła uczciwości
   zewnętrznej: „adaptujemy AIVAT z własną walidacją", nigdy „stosujemy
   sprawdzoną technikę" (oryginał wyklucza turnieje i ICM ze swojego
   zakresu).

---

## 7. Kierunek — decyzja 29 w pięciu zdaniach

1. **Policzyliśmy niewłaściwą grę.** Artefakt produkcyjny rozwiązuje
   wypłaty 80/20 przy 25 bb — konfigurację ~1% turniejów. Modalny Spin
   (~96,5%) to winner-take-all na 15–20 bb, a przy WTA wartość
   turniejowa zachowuje się inaczej (przy (1,0,0) ICM degeneruje się do
   liniowego udziału w stacku).
2. **Linia doszlifowywania ε jest nasycona.** Pełna wyzyskiwalność to
   0,14 pp ROI **przy 3×**, wobec **połowy szerokości** CI areny 1,46 pp
   (10×) i wpływu samej reguły awaryjnej 4,22 pp (30×). Dokręcanie
   tolerancji do podłogi f32 kosztuje ~3 900 rdzenio-h i jest warte
   0,0004 pp.
3. **Fundament = ten sam algorytm, wycelowany we właściwe gry**:
   rodzina blueprintów per tier (T-MODAL pierwszy, ~87% gier za dolne
   oszacowanie ~18 rdzenio-h — mnożnik kosztu WTA nieznany do pierwszego
   przebiegu).
4. **Warstwa eksploatacyjna = seat-restricted DBR offline**, walidowana
   najpierw w końcówce HU (gdzie twierdzenie obowiązuje), bramkowana
   ex-post ε profilu ograniczonego.
5. **Bramka STOP**: żaden kolejny kontrakt blueprintowy nie otwiera się
   bez pomiaru wyzwalającego — (1) P-6(a) błąd siatki nad tolerancją,
   (2) P-6(c) ≥ 1e−4 puli, (3) CI areny po 55+AIVAT istotnie węższe od
   budżetowanych.

Katalog obaleń (co odrzucono i dlaczego) jest w decyzji 29 pkt 4 —
przeczytaj go przed zaproponowaniem czegokolwiek z literatury CFR/FOM.
Kilka „oczywistych ulepszeń" (PED, warm start, maximin, migracja HU na
PCFR+/DCFR) padło w weryfikacji adwersaryjnej na źródłach pierwotnych.

---

## 8. Pułapki, które kosztowały najwięcej

Pełna lista w `PAMIEC_OPERACYJNA.md` (sekcja PUŁAPKI) — z zastrzeżeniem,
że wpis znika stamtąd, gdy fakt zostaje utrwalony w repo (tak stało się
z checkpointem horyzontu: żyje w bloku POKER-50 i jako kontrakt P-4).
Cztery najdroższe:

- **Tabela permutacji w złą stronę przeżywa testy na transpozycjach**
  (inwolucje) — psują się dopiero 3-cykle. Kotwicz każdą oś i KAŻDĄ
  tablicę osobno. Dwie mutacje osi przeżyły 343 testy, a equity AA
  leciało 0,917 → 0,083 (POKER-46).
- **Horyzont nie ma checkpointu per cykl** — restart kosztuje wszystkie
  policzone cykle (16,2 rdzenio-h; blok POKER-50). Naprawa: POKER-59.
- **`pytest.raises(Błąd)` bez `match` nie odróżnia strażnika od
  potknięcia piętro niżej** — usunięcie kontroli formatu przeżywało całą
  bramkę, bo plik i tak wywracał się na cudzym katalogu warstw
  (POKER-57, audyt).
- **Regeneracja artefaktu unieważnia pomiary przy nim**, a bramka tego
  nie łapie (POKER-24).
- **Zero na artefakcie bramki ≠ zero na siatce produkcyjnej** — krok
  siatki bywa przyczyną pudła (0 przy kroku 50, 94 przy kroku 2).

Do tego pułapka środowiskowa (nie repo): przy testach mutacyjnych
modułów `tools/` czyść `__pycache__` — mutant o identycznej długości
bajtowej zostawia zmutowany `.pyc`.

---

## 9. Wejścia operatorskie — co blokuje co

| wejście | blokuje | stan |
|---|---|---|
| **potwierdzenie tabeli tierów** wobec żywego lobby (mnożnik → stack, zegar, wypłaty) | **tylko P-8 T-MODAL** i dalsze przebiegi tierowe; P-7 odblokowane decyzją 30 pkt 3, bo nie bierze z tabeli nic (dzisiejsze 150 żetonów, zmieniony wyłącznie wektor wypłat) | tabela w `poker.spin` z `confirmed=False`; `tier_for_run` rzuca `UnconfirmedTierError` bez jawnego `allow_unconfirmed` |
| **korpus realnych hand histories** | całą warstwę eksploatacyjną P-10..P-13 | brak; bez niego uczciwe zatrzymanie na P-11 (maszyneria zwalidowana w HU) |
| ~~decyzja o dystrybucji artefaktu~~ | — | **rozstrzygnięta** (decyzja 30): brak publikacji, manifest tożsamości w repo |
| **realny hands-per-level** | krzywa zegara w P-8 (kontrakt emituje BRAK zamiast zgadywać) | w kodzie jest zegar produktu (3), jawnie oznaczony jako NIE research |

Osobno: agent rzuca wyjątek przy niezgodności **fingerprinta** przebiegu
(POKER-56) — to inna bramka niż potwierdzenie tabeli tierów.

---

## 10. Długi i wątki otwarte

- **F2 audytu POKER-5**: księgowość żetonów w `_view` (betting)
  równoległa do projekcji — unifikacja przy najbliższym kontrakcie
  dotykającym `poker.betting`.
- **F1 audytu POKER-22**: zduplikowana formuła equity-przeciw-polu;
  publiczne API w `preflop_equity` osobnym kontraktem.
- **Resztkowe rozjazdy drzew** (POKER-55): `capped_call` = 2,
  `root_fold` = 8 na próbce bramki — naprawa wymaga zmiany drzewa
  treningu, czyli nowego rekordu decyzyjnego (zamrożenie z decyzji 27).
- **`forced_action_misses` = 94** na artefakcie produkcyjnym
  (kwantyzacja sprowadza stack do wysokości blindu) — ta sama klasa.
- **Marginesy indyferencji nie są policzone dla produkcji** (POKER-57):
  format je niesie, artefakt produkcyjny nie ma sekcji i mówi to jawnie;
  doliczenie to jeden przechód wyceniony na ~4,6 rdzenio-h. Kontrakt,
  który je policzy, musi zmierzyć jedną rzecz: skala marginesów jest
  liczona **per stan**, więc klasa o bardzo małej masie dotarcia potrafi
  ustawić skalę tak, że realne marginesy sąsiadów spadają do zera —
  a zero znaczy „doskonała obojętność", czyli najsilniejszy alarm.
  Format rozróżnia dziś „nieokreślony" od zera, ale ile infosetów wpada
  w zero z powodu skali, a ile z obojętności, wie dopiero pomiar.
- **POKER-26** (informacja zwrotna przy stole LAN) — szkic czeka
  na zatwierdzenie; **POKER-28** (memoizacja parsowania w testach
  architektury) nadal zasadny.

---

## 11. Od czego zacząć

1. **Domknij POKER-57**: audyt świeżym kontekstem commita `aefc3c8` →
   zamknięcie w indeksie → scalenie do main. Praca jest dostarczona
   i bramka zielona; brakuje wyłącznie audytu.
2. **Zrób POKER-59** (checkpoint horyzontu, ~1 rdzenio-h) — zanim
   odpalisz jakikolwiek długi przebieg. To jedyna pozycja, która chroni
   przed powtórzeniem straty 16,2 rdzenio-h.
3. **Jeśli regenerujesz artefakt** — zweryfikuj tożsamość wobec
   `prod_identity.json` przed użyciem jakiejkolwiek liczby z sekcji 6.
4. Dalej mapa decyzji 29: P-3 (POKER-58, niesie też narzędzie
   weryfikacji tożsamości) → P-5 → P-6 (sondy rozstrzygają bramkę STOP)
   → **P-7** (pierwszy jednozmienny A/B wypłat wraz z prerejestrowanym
   kill-checkiem całej tezy tierowej — odblokowany decyzją 30, nie czeka
   na operatora).

Jedna uwaga na koniec, wynikająca z historii tej linii: **każdy audyt
świeżym kontekstem w tym projekcie znalazł coś istotnego** — w tym dwa
razy błąd w moich własnych dokumentach architekta (kryterium-proxy
w POKER-52, zaniżona dokładność cyklu w decyzji 28), a weryfikacja tego
dokumentu przed wydaniem znalazła jedenaście rzeczy do naprawy, w tym
przepis instalacji, który padał jak napisany. Nie skracaj tego kroku,
nawet gdy praca wygląda na oczywistą.

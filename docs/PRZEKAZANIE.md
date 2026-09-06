# Przekazanie pracy — produkt Poker (linia blueprintu GTO)

Stan na 2026-09-06. Autor: architekt produktu (sesja kończąca się tym
dokumentem). Adresat: **drużyna przejmująca**, bez kontekstu poprzednich
sesji.

Ten dokument nie jest źródłem statusu — źródłem jest
[`CURRENT_STATE.md`](CURRENT_STATE.md). Tu jest to, czego nowa drużyna
nie odczyta z repo w rozsądnym czasie: **co jest zrobione i dlaczego tak,
co zniknie razem z kontenerem, czego nie wolno twierdzić, i od czego
zacząć**.

---

## 1. Pierwsze 30 minut

```bash
# 1. Konstytucja procesu — bez niej nic w tym repo nie ma sensu
cat ../foundry/CONSTITUTION.md          # repo mcz91/foundry

# 2. Stan produktu (długi, ale to JEST źródło prawdy)
cat docs/CURRENT_STATE.md               # sekcje: Co istnieje / Czego nie ma / Następny krok

# 3. Decyzje obowiązujące — czytaj od 29 wstecz
ls docs/decisions/                      # 29 wyznacza cały bieżący kierunek

# 4. Pamięć operacyjna ról (80 linii, w tym PUŁAPKI — czytaj w całości)
cat PAMIEC_OPERACYJNA.md

# 5. Bramka (musi być zielona przed każdym commitem)
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,train]"
ruff check . && mypy && pytest          # ~5,5 min, obecnie 459 testów
```

Gałąź integracyjna: **`claude/poker-project-architecture-jw6ukd`**.
`main` podąża za nią po każdym komplecie audytów (stała autoryzacja
operatora); wykonuje to architekt, nigdy koder.

---

## 2. Czym jest ten produkt

Silnik pokerowy i bot do **Spin & Go** (3-max hyper-turbo SNG,
winner-take-all z losowanym mnożnikiem). Produkt ma dwie warstwy:

- **Pakiet `poker`** — czysty stdlib, bez numpy, bez I/O w silniku.
  Zawiera model gry, arenę pomiarową, agentów i **czytnik artefaktu**
  blueprintu (`blueprint_reader`, `blueprint_agent`).
- **`tools/blueprint/`** — solver poza produktem (numpy dozwolony), który
  liczy artefakt strategii. Artefakt **nie wchodzi do repozytorium**
  (decyzja 25 pkt 6) — w repo żyje wyłącznie mały artefakt kontrolny
  łańcucha (`tools/blueprint/control/`, 24 KB) i jego test w bramce.

Algorytm fundamentu GTO: **dokładna indukcja wsteczna po DAG-u zegara
blindów**; stany etapowe 3-osobowe rozwiązywane PI-FP, końcówki HU
CFR+ z uśrednianiem ważonym reach, horyzont jako punkt stały cyklu
ostatniego poziomu z brzegiem ICM. Jakość mierzona **ex-post ε**
(best-response jako MDP przeciw zamrożonym przeciwnikom).

---

## 3. Proces fabryki — to nie jest opcjonalne

Repo jest prowadzone przez proces z `mcz91/foundry`. Jego rdzeń:

1. **Nic nie powstaje bez TaskSpec** (`docs/taskspecs/POKER-N.json`):
   goal, acceptance jako CHECKLISTA, non_goals, allowed_paths,
   verification, approved. Architekt kwalifikuje i zatwierdza; koder
   realizuje dokładnie jeden kontrakt i nie wychodzi poza allowed_paths.
2. **Role mają świeży kontekst**: architekt (kwalifikacja, decyzje,
   scalenia), koder (realizacja), audytor (adwersaryjna weryfikacja
   po kontrakcie dotykającym kodu produktu). Audytor pisze wyłącznie
   PUŁAPKI do pamięci operacyjnej.
3. **Bramka zielona przed każdym commitem**: `ruff check .`, `mypy`,
   `pytest`. „Bramka zielona" ≠ „typy sprawdzone" poza `files`
   z pyproject.
4. **Liczba w dokumencie = niezmiennik w teście.** Każde kryterium
   ilościowe raportowane jako spełnione ma asercję. Dowód skryptem
   w scratchpadzie nie chroni następnego biegu.
5. **Komenda regeneracji w dokumencie musi działać jak napisana** —
   ze świeżego katalogu, dosłownie.
6. **OBJECTION** (CONFLICT | INCOMPLETE | UNSAFE | UNTESTABLE) to
   normalny wynik pracy kodera, nie porażka. Dwa OBJECTION w tej linii
   (POKER-42, POKER-52) zmieniły kontrakty na lepsze.
7. **Zamknięcie zadania aktualizuje też „Następny krok"** w
   CURRENT_STATE — jednym commitem.

Wzorzec, który wielokrotnie się opłacił: **najpierw zmierz krzywą,
potem ustaw próg** (POKER-47). Kryterium ilościowe wymyślone przed
pomiarem kilka razy okazało się mierzyć nie to, co miało chronić
(POKER-52, adjudykacja w decyzji 28).

---

## 4. Stan linii na dziś

### Zamknięte (pełny cykl: kontrakt → koder → audyt świeżym kontekstem → scalenie)

| kontrakt | co dał |
|---|---|
| POKER-44/45 | naprawa i scalenie linii Spin (decyzja 24) |
| POKER-46 | tensor rolloutów 3-way z kotwicami orientacji osi |
| POKER-47 | krzywa ε-vs-iteracje; budżet PI-FP 384/5e−5 |
| POKER-48 | arena z rotacjami miejsc, CI na blokach, bootstrap |
| POKER-49 | domknięcie horyzontu i endgame'ów HU, CFR+ na tolerancji |
| POKER-50 | **bieg produkcyjny**: 49 765 stanów, ε maks 4,720e−4, 76,6 rdzenio-h |
| POKER-51 | format binarny `.bpk` v1 + czytnik stdlib; koszt kwantyzacji w ε |
| POKER-52 | agent `blueprint` w arenie i rejestrze CLI + pierwszy pomiar siły |
| POKER-54 | rozgrywacz areny: akcja od agresora, wymuszone wejście za darmo |
| POKER-55 | wierność agenta artefaktowi: cykl horyzontu, węzeł bliźniaczy |
| POKER-56 | higiena tierowa: tabela tierów, normalizacja, fingerprint, wycena per-mode |

### W locie

**POKER-57** (`.bpk` v2: maska uint32, cztery sloty, kwantyzacja uint16,
ε per stan, marginesy indyferencji, blok fingerprinta). Kontrakt
zatwierdzony (`6f2a0b6`), praca kodera w drzewie **niezacommitowana**
w chwili pisania tego dokumentu; artefakt `blueprint_v2.bpk` (39 MB)
już powstał w scratchpadzie. Sprawdź `git status` i raport kodera.

### Kolejka — mapa decyzji 29, szkice gotowe

Szkice TaskSpeców leżą w scratchpadzie sesji architekta
(`…/scratchpad/drafts/POKER-{58,59,53,60}.szkic*.json`) i **znikną razem
z kontenerem** — jeśli są potrzebne, przenieś je do repo albo odtwórz
z opisów w decyzji 29 pkt 5:

| id | kontrakt | koszt [rdzenio-h] | blokady |
|---|---|---:|---|
| P-3 POKER-58 | domknięcie warstw 1–5 przez osiągalność łańcucha DOKŁADNEGO (nie pełna siatka) | 2–10 | — |
| P-4 POKER-59 | checkpoint horyzontu per cykl | ~1 | wymagany przed przebiegami > 12 h |
| P-5 POKER-53 | AIVAT w przestrzeni nagród | ~5 | 55+58 dla sensownych liczb |
| P-6 POKER-60 | trzy sondy błędu modelu (siatka / kwantyzacja / ziarno tensora) | ~24 | — |
| P-7 POKER-61 | artefakt WTA@25bb — jednozmienny A/B wypłat | ~64 | 54+55+58 |
| P-8 POKER-62 | T-MODAL 90 żetonów WTA + krzywa zegara | ~18 (+18) | + tabela tierów od operatora |
| P-9 POKER-63 | T-MID 120 WTA | ~36 | warunkowy |
| P-10..13 | warstwa eksploatacyjna DBR (builder modelu → HU → krzywa P_max → pełny DAG) | ~54 | **korpus hand histories** |
| P-14 POKER-68 | wyceniony spike gałęzi flat-call | ~5 | wymaga nowego rekordu decyzyjnego |

---

## 5. Artefakty — najważniejsza część tego dokumentu

**Artefakty produkcyjne żyją w scratchpadzie sesji i ZNIKNĄ razem
z kontenerem.** To nie jest awaria — tak stanowi decyzja 25 pkt 6
(artefakt poza gitem). Ceną jest regeneracja:

| artefakt | rozmiar | koszt regeneracji |
|---|---:|---:|
| tensor rolloutów (`prod/tensor/`) | 20 MB | 11,2 rdzenio-h |
| bieg siatki (`prod/grid2/`, 21 warstw + brzeg) | 38 MB | 65,4 rdzenio-h (horyzont 25,2 + warstwy 40,2) |
| `blueprint.bpk` v1 | 19 016 752 B | 24 s (pakowanie) |
| `blueprint_v2.bpk` | 39 MB | j.w. (POKER-57) |

**Komendy pełnej regeneracji: bloki POKER-50 (AC–AH) i POKER-51 (BA)
w CURRENT_STATE.** Są sprawdzone dosłownie ze świeżego katalogu.
Cała regeneracja to ~19 h ściennych na 4 rdzeniach. **Zanim ją odpalisz,
zrób POKER-59 (checkpoint horyzontu)** — jeden restart kontenera
w środku horyzontu kosztował 16,2 rdzenio-h, bo jednostką wznowienia
jest dopiero warstwa.

Dwustopniowy dowód odtwarzalności (decyzja 06): mały łańcuch kontrolny
chodzi w bramce przy każdym `pytest`, pełna regeneracja komendami
z dokumentu poza bramką.

**Decyzja o dystrybucji artefaktu należy do operatora** i nie została
podjęta (git-LFS? release? regeneracja u odbiorcy?). Jeśli przekazanie
ma być kompletne, to jest pierwsza rzecz do rozstrzygnięcia z operatorem.

---

## 6. Liczby, które wolno cytować — i czego twierdzić nie wolno

### Wolno (wszystkie zmierzone na tym systemie, z komendami w dokumencie)

| wielkość | wartość |
|---|---|
| ex-post ε artefaktu produkcyjnego | maks **4,720e−4**, mediana 1,076e−4 (49 765 stanów) |
| próg blokujący / punkt odniesienia | 1e−3 (zapas 2,1×) / 5e−4 (zapas 5,6%) |
| V vs ICM (uzasadnienie kierunku) | do **9,5% puli** |
| ROI agenta w arenie (3x, N=10 000 bloków) | **+5,20%** vs `field_exploit` (CI +3,74..+6,66), +6,36% vs `dollar_fish`, +8,23% vs `always_jam` |
| wpływ reguły awaryjnej po naprawach | **−0,10 pp** (CI −0,39..+0,19) — nieodróżnialny od zera |
| fallback agenta | **0,850%** decyzji, w całości granica artefaktu |
| udział decyzyjny trybów | `deep` 33,3%, `jamfold` 10,5%, `hu-deep` 39,1%, `hu-jamfold` 17,1% |

### Zakazy twierdzeń — obowiązują bezterminowo

1. **Nie twierdzić, że bijemy pole $1.** Pomiar jest przeciw trzem
   skryptom z repozytorium (`field_exploit`, `dollar_fish`,
   `always_jam`), nie przeciw realnej populacji. `dollar_fish` to skrypt,
   nie pole.
2. **Nie cytować cudzych liczb jako naszych** — ani redukcji wariancji
   (85%, 54×, 74× to 2p0s chip-EV HUNL), ani magnitud eksploatacji.
3. **Nie twierdzić „dorównujemy SOTA"** — $0,049 u Ganzfrieda–Sandholma
   to ich próg zatrzymania, nie osiągnięta podłoga (obalone na PDF-ie
   źródłowym w researchu decyzji 29).
4. **ε jest w jednostkach sumy wektora wypłat**, nie „puli pota".
   Prawo przeliczenia: **ROI [pp] = ε × mnożnik × 100**.
5. **Nie czytać ROI z areny jako „siły GTO"** — to pomiar pary
   (artefakt + reguła decyzyjna) w konkretnym zestawie przeciwników.

---

## 7. Kierunek — decyzja 29 w pięciu zdaniach

1. **Policzyliśmy niewłaściwą grę.** Artefakt produkcyjny rozwiązuje
   wypłaty 80/20 przy 25 bb — konfigurację ~1% turniejów. Modalny Spin
   (~96,5%) to winner-take-all na 15–20 bb, a przy WTA wartość
   turniejowa zachowuje się inaczej (przy (1,0,0) ICM degeneruje się do
   liniowego udziału w stacku).
2. **Linia doszlifowywania ε jest nasycona.** Pełna wyzyskiwalność to
   0,14 pp ROI przy szerokości CI areny 1,46 pp. Dokręcanie tolerancji
   do podłogi f32 kosztuje ~3 900 rdzenio-h i jest warte 0,0004 pp.
3. **Fundament = ten sam algorytm, wycelowany we właściwe gry**:
   rodzina blueprintów per tier (T-MODAL pierwszy, ~87% gier za ~18
   rdzenio-h — jedna sesja Colab).
4. **Warstwa eksploatacyjna = seat-restricted DBR offline**, walidowana
   najpierw w końcówce HU (gdzie twierdzenie obowiązuje), bramkowana
   ex-post ε profilu ograniczonego.
5. **Bramka STOP**: żaden kolejny kontrakt blueprintowy nie otwiera się
   bez pomiaru wyzwalającego z sond P-6.

Katalog obaleń (co odrzucono i dlaczego) jest w decyzji 29 pkt 4 —
przeczytaj go przed zaproponowaniem czegokolwiek z literatury CFR/FOM.
Kilka „oczywistych ulepszeń" (PED, warm start, maximin, migracja HU na
PCFR+/DCFR) padło w weryfikacji adwersaryjnej na źródłach pierwotnych.

---

## 8. Pułapki, które kosztowały najwięcej

Pełna lista w `PAMIEC_OPERACYJNA.md` (sekcja PUŁAPKI). Trzy najdroższe:

- **Tabela permutacji w złą stronę przeżywa testy na transpozycjach**
  (inwolucje) — psują się dopiero 3-cykle. Kotwicz każdą oś i KAŻDĄ
  tablicę osobno. Dwie mutacje osi przeżyły 343 testy, a equity AA
  leciało 0,917 → 0,083 (POKER-46).
- **Horyzont nie ma checkpointu per cykl** — restart kosztuje wszystkie
  policzone cykle (16,2 rdzenio-h). Naprawa: POKER-59.
- **Zero na artefakcie bramki ≠ zero na siatce produkcyjnej** — krok
  siatki bywa przyczyną pudła (0 przy kroku 50, 94 przy kroku 2).

Do tego pułapka środowiskowa (nie repo): przy testach mutacyjnych
modułów `tools/` czyść `__pycache__` — mutant o identycznej długości
bajtowej zostawia zmutowany `.pyc`.

---

## 9. Wejścia operatorskie — co blokuje co

| wejście | blokuje | stan |
|---|---|---|
| **potwierdzenie tabeli tierów** wobec żywego lobby (mnożnik → stack, zegar, wypłaty) | P-8 T-MODAL i dalsze przebiegi tierowe (NIE blokuje P-7 WTA@25bb) | tabela w `poker.spin` z `confirmed=False`, agent rzuca bez jawnej flagi |
| **korpus realnych hand histories** | całą warstwę eksploatacyjną P-10..P-13 | brak; bez niego uczciwe zatrzymanie na P-11 (maszyneria zwalidowana w HU) |
| **decyzja o dystrybucji artefaktu** | przekazanie artefaktu bez regeneracji | niepodjęta |
| **realny hands-per-level** | krzywa zegara w P-8 (kontrakt emituje BRAK zamiast zgadywać) | w kodzie jest zegar produktu (3), jawnie oznaczony jako NIE research |

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
- **POKER-26** (informacja zwrotna przy stole LAN) — szkic czeka
  na zatwierdzenie; **POKER-28** (memoizacja parsowania w testach
  architektury) nadal zasadny.

---

## 11. Od czego zacząć

1. **Domknij POKER-57** (jeśli nie jest zamknięty): raport kodera →
   weryfikacja niezależna → audyt świeżym kontekstem → scalenie do main.
2. **Zrób POKER-59** (checkpoint horyzontu, ~1 rdzenio-h) — zanim
   odpalisz jakikolwiek długi przebieg. To jedyna pozycja, która chroni
   przed powtórzeniem straty 16,2 rdzenio-h.
3. **Rozstrzygnij z operatorem dystrybucję artefaktu** — inaczej
   pierwsza rzecz, jaką zrobi nowa drużyna, to 19 godzin regeneracji.
4. Dalej mapa decyzji 29: P-3 → P-5 → P-6 (sondy rozstrzygają bramkę
   STOP) → P-7 (pierwszy jednozmienny A/B wypłat).

Jedna uwaga na koniec, wynikająca z historii tej linii: **każdy audyt
świeżym kontekstem w tym projekcie znalazł coś istotnego** — w tym dwa
razy błąd w moich własnych dokumentach architekta (kryterium-proxy
w POKER-52, zaniżona dokładność cyklu w decyzji 28). Nie skracaj tego
kroku, nawet gdy kontrakt wygląda na oczywisty.

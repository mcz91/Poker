# Audyt kodu Poker — raport dla nietechnicznego czytelnika

Data: 2026-09-12 · gałąź audytu: `claude/poker-code-audit-0z8i49` ·
commit bazowy: `16dc6f8` · ostatnie zamknięte zadanie w repozytorium: POKER-57

Ten raport jest napisany tak, żeby dał się przeczytać bez znajomości Pythona
i bez znajomości pokera. Każde twierdzenie o stanie kodu ma obok siebie liczbę
albo komendę, którą można je odtworzyć — załącznik na końcu zbiera je w jednym
miejscu. Wszystko, co niżej nazywam „zmierzone", zmierzyłem sam na tym
commicie; nie przepisałem ani jednej liczby z dokumentacji repozytorium bez
sprawdzenia.

---

## 1. O co w tym w ogóle chodzi

### 1.1. Co to jest

To nie jest gra w pokera dla ludzi. To **silnik pokerowy z botami** — biblioteka,
która umie rozdać karty, poprowadzić licytację, rozliczyć żetony i podstawić do
stołu programy grające zamiast ludzi. Człowiek może zagrać, ale jest to jedna
z wielu końcówek, nie cel.

Konkretnie obsługiwane są dwie dyscypliny:

- **Heads-up No-Limit Hold'em** — Texas Hold'em jeden na jednego, bez limitu
  stawek. „Heads-up" to dwóch graczy, „No-Limit" to możliwość postawienia
  w każdej chwili całego stosu żetonów. To jest główny, najlepiej dopracowany
  tor produktu.
- **Spin & Go** — trzyosobowy turniej błyskawiczny. Każdy wpłaca wpisowe,
  losowany jest mnożnik nagrody (2×, 3× albo 10× wpisowego), blindy rosną
  co trzy rozdania, gra się do wyeliminowania dwóch graczy. To jest tor
  młodszy i badawczy.

### 1.2. Po co to jest

Z dokumentów decyzyjnych repozytorium (`docs/decisions/01`, `03`, `04`) wynika
plan na trzy produkty z jednego rdzenia: **pokerroom** (stół w sieci lokalnej),
**trener** (narzędzie do nauki gry dla człowieka) i **bot** (program grający
możliwie dobrze). Dziś zbudowany jest rdzeń, pierwszy krok pokerroomu i kilka
generacji botów. Trenera nie ma.

### 1.3. Słownik, bez którego dalsza część nie ma sensu

| Termin | Co znaczy tutaj |
|---|---|
| **blind** (mały/duży) | przymusowa stawka wnoszona przed rozdaniem kart; napędza grę |
| **button** | pozycja rozdającego; rotuje po każdym rozdaniu |
| **flop / turn / river** | trzy, czwarta i piąta karta wspólna na stole |
| **showdown** | odkrycie kart na koniec rozdania i porównanie układów |
| **fold / check / call / bet / raise** | spasować / sprawdzić za darmo / wyrównać / postawić / podbić |
| **all-in** | wstawienie całego stosu żetonów |
| **min-raise** | reguła: podbicie musi być co najmniej tak duże jak poprzednie |
| **split pot** | podział puli przy remisie układów |
| **stack** | stos żetonów gracza |
| **BB/100** | standardowa miara tempa wygrywania: ile dużych blindów na 100 rozdań |
| **ICM** | przelicznik żetonów turniejowych na oczekiwane pieniądze |
| **GTO** | strategia teoretycznie niewykorzystywalna („optymalna" w sensie teorii gier) |
| **MCCFR / CFR** | rodzina algorytmów szukających takiej strategii przez miliony rozgrywek z samym sobą |
| **blueprint** | wyliczona z góry tablica strategii, z której bot odczytuje ruchy |
| **equity** | szansa wygrania puli z danymi kartami |

---

## 2. Z czego to jest zbudowane

### 2.1. Rozmiary — i pierwsza rzecz, która zaskakuje

| Warstwa | Linie kodu |
|---|---|
| Rdzeń produktu, pisany ręcznie (`src/poker/`) | **6 631** |
| **Dane wygenerowane, leżące w repozytorium jako pliki Pythona** | **125 217** |
| Testy (`tests/`) | 10 265 |
| Narzędzia solvera pod kontrolą typów (`tools/blueprint/`) | 5 186 |
| Pozostałe narzędzia (`tools/`) | 1 489 |

Czyli **95% objętości katalogu `src/` to nie kod, a wyliczone dane**
przechowywane w formie plików Pythona: tablica strategii bota
(`strategy_table.py` — 3,2 MB, 122 tysiące linii), macierz szans preflop
(180 KB), wagi dwóch modeli uczonych. To nietypowa decyzja, ale świadoma
i opisana: dzięki temu produkt nie czyta żadnych plików z dysku w trakcie gry
i nie ma żadnej zależności zewnętrznej. Koszt tej decyzji zmierzyłem — punkt
6.13.

### 2.2. Główna idea konstrukcyjna: dziennik zdarzeń

To najważniejsza rzecz do zrozumienia w tym kodzie i warto ją wyjaśnić dokładnie,
bo od niej zależy większość dobrych ocen w tym raporcie.

Typowy program do pokera trzymałby „stan stołu" w pamięci jako zestaw zmiennych:
ile kto ma żetonów, ile jest w puli, jaka jest faza. Gdy ktoś stawia, program
zmniejsza jedną zmienną i zwiększa drugą. Problem: jeśli którakolwiek z tych
operacji ma błąd, żetony cicho znikają albo się mnożą, i nikt tego nie zauważy.

Ten kod robi to inaczej. Jedyną prawdą jest **dziennik zdarzeń** — lista
niezmienialnych zapisów typu „rozdanie się rozpoczęło z taką konfiguracją",
„miejsce 0 wniosło mały blind 1", „miejsce 1 dostało karty X i Y", „rozdano
flop", „miejsce 0 podbiło o 5", „pulę 40 przyznano miejscu 1". Do dziennika
można tylko **dopisywać** — nie da się nic zmienić ani usunąć, a dopisanie
czegokolwiek po zdarzeniu końca rozdania jest błędem (`history.py`).

Stan stołu nie jest przechowywany. Jest **wyliczany na żądanie** przez przejście
całego dziennika od początku (`projection.py`). Konsekwencja jest bardzo mocna:
nie istnieje stan, który rozjechałby się z historią, bo nie istnieje żaden inny
stan poza tym, który z historii wynika. Do tego każde rozdanie jest w pełni
odtwarzalne: dziennik zawiera ziarno losowości talii, więc z zapisu można
odtworzyć dokładnie ten sam przebieg.

### 2.3. Granica informacyjna: co gracz może zobaczyć

Druga kluczowa konstrukcja. Każde zdarzenie w dzienniku **samo deklaruje swoją
widoczność**: `Public` (widzą wszyscy), `PrivateToSeat(n)` (widzi tylko miejsce
n), `EngineOnly` (nie widzi nikt przy stole). Ziarno talii jest zadeklarowane
jako `EngineOnly` — to znaczy, że nie da się go dostać przez widok gracza,
bo widok gracza jest *budowany wyłącznie z przefiltrowanego dziennika*
(`views.py`).

To nie jest kosmetyczna deklaracja. Bot dostaje na wejściu obiekt `PlayerView`
i nic więcej — nie dostaje uchwytu do silnika, do talii ani do historii. Nie może
więc podejrzeć kart przeciwnika, nawet gdyby jego autor chciał. Sprawdziłem,
czy ta bariera naprawdę trzyma — punkt 4.5.

### 2.4. Osiem niezmienników i „fabryka"

Repozytorium jest prowadzone przez rygorystyczny proces opisany w osobnym repo
(`mcz91/foundry`, plik `CONSTITUTION.md`). Z punktu widzenia audytu ważne jest
to, że produkt ma **osiem spisanych niezmienników INV-P1…P8** — reguł, których
naruszenie jest uznawane za błąd blokujący, na przykład:

- **INV-P1**: w silniku nie ma zegara, wejścia/wyjścia ani nieseedowanej
  losowości — każde rozdanie da się odtworzyć z ziarna i sekwencji akcji;
- **INV-P3**: żaden kanał (widok, log, `repr`, eksport, sieć) nie ujawnia kart
  przeciwnika przed showdownem;
- **INV-P4**: bot nie może zmienić stanu gry ani sięgnąć poza swój widok;
- **INV-P7**: zależności płyną od końcówek (terminal, sieć, pliki) do silnika,
  nigdy odwrotnie;
- **INV-P8**: w logice gry nie ma ani modelu językowego, ani wywołania sieciowego;
- osobno: **żetony są liczbami całkowitymi**, a ich suma przy stole jest stała.

Co ważniejsze — te reguły nie są tylko spisane. Część z nich jest **egzekwowana
mechanicznie przez testy**, które czytają kod źródłowy i sprawdzają listy
dozwolonych zależności modułu po module (`tests/test_architecture.py`, 333 linie).
Sprawdziłem szczelność tego mechanizmu — punkt 6.9.

### 2.5. Mapa części

```
KARTY I UKŁADY          cards, evaluation, preflop, preflop_equity(+_data), preflop_sim
SILNIK ROZDANIA         events, history, projection, dealing, betting, views, agent, table
BOTY                    rule_agent  (ręczne reguły)
                        clone_agent + clone_weights          (regresja logistyczna)
                        mlp_agent + mlp_weights              (mała sieć neuronowa)
                        strategy_agent + strategy_table      (MCCFR, 20 971 sytuacji)
                        blueprint_agent + blueprint_reader   (odczyt artefaktu solvera)
POMIAR                  arena (heads-up, BB/100), spin_arena (Spin, ROI)
SPIN & GO               spin, icm, jamfold, openfold
KOŃCÓWKI (adapters/)    cli, human, lan_server, lan_client, protocol, export, corpus,
                        dataset, registry
NARZĘDZIA (tools/)      trenerzy, generatory, solver blueprintu (tools/blueprint/)
```

---

## 3. Jak audytowałem

Nie poprzestałem na przeczytaniu kodu i uruchomieniu cudzych testów, bo cudze
testy mogą być napisane pod kod. Zrobiłem trzy rzeczy:

1. **Uruchomiłem pełną bramkę jakości** repozytorium (analizator stylu,
   kontrola typów, testy) w świeżym środowisku na Pythonie 3.13.
2. **Przeczytałem rdzeń linia po linii** — cały silnik rozdania, wszystkie boty,
   arenę, końcówki, oraz strukturę części Spin/solver.
3. **Napisałem własne, niezależne testy** — nie korzystające z testów
   repozytorium — w tym **własny, od zera napisany ewaluator układów pokerowych
   innym algorytmem**, żeby móc porównać wyniki z ewaluatorem produktu.

Punkt 3 jest istotny: gdy sprawdzam poprawność pokerową, porównuję kod produktu
z własną, niezależną implementacją tych samych reguł. Jeśli oba dają ten sam
wynik na dziesiątkach tysięcy losowych przypadków, to bardzo mocna przesłanka,
że oba są poprawne — bo trudno, żeby dwie niezależne implementacje myliły się
identycznie.

---

## 4. Co sprawdziłem i z jakim wynikiem

### 4.1. Bramka jakości: zielona bez zastrzeżeń

| Kontrola | Wynik |
|---|---|
| `ruff check .` (styl i typowe błędy) | **czysto** |
| `mypy` w trybie `strict` (kontrola typów) | **czysto, 94 pliki** |
| `pytest` | **483 testy, wszystkie przechodzą** |
| Obejścia kontroli typów (`type: ignore`) w całym repo | **zero** |

Zero obejść kontroli typów w projekcie tej wielkości jest rzadkie i warto to
docenić — to znaczy, że nikt nie uciszył ani jednego ostrzeżenia, żeby „było
zielono".

### 4.2. Żetony: 4 000 losowych rozdań, ani jeden żeton nie zginął

Napisałem bota, który gra **losowo, ale wyłącznie legalnie** — w każdej sytuacji
losuje z pełnego zbioru dopuszczalnych akcji, w tym z kwotami skrajnymi
(minimalną i maksymalną). Taki bot dociera do stanów, których normalny bot nigdy
nie odwiedzi. Rozegrałem 4 000 rozdań z losowymi konfiguracjami (blindy 1/2, 2/4,
5/10; stosy od 2 do 200 żetonów; oba położenia buttona) i po **każdym pojedynczym
zdarzeniu każdego rozdania** sprawdzałem cztery rzeczy:

- suma żetonów w stosach plus pula jest równa sumie początkowej,
- żaden stos nie jest ujemny,
- pula nie jest ujemna,
- po zakończeniu rozdania pula jest wyzerowana (wszystko rozdysponowane).

**Wynik: 0 naruszeń.** Pokrycie było przy tym realne: w 2 048 rozdaniach ktoś
spasował, 1 106 skończyło się wyeliminowaniem gracza, a **76 rozdań skończyło się
remisem i podziałem puli** — czyli najbardziej podatny na błędy przypadek
(dzielenie niepodzielnej reszty żetonów) był przetestowany 76 razy na losowych
danych.

Dodatkowo każde z 4 000 rozdań powtórzyłem z tym samym ziarnem i tymi samymi
decyzjami: **wszystkie 4 000 dały bajt w bajt identyczną sekwencję zdarzeń.**
Odtwarzalność nie jest deklaracją.

### 4.3. Reguły pokera: porównanie z niezależną implementacją

**Ewaluator układów** (czyli „kto ma lepsze karty") porównałem z własnym,
napisanym innym algorytmem:

- 20 000 losowych układów pięciokartowych — zgodność **kategorii układu
  i wszystkich kickerów** (kart rozstrzygających remis): **100%**;
- 20 000 losowych **par** rąk siedmiokartowych — zgodność relacji
  „lepszy / równy / gorszy": **100%**. To mocniejszy test, bo sprawdza porządek,
  a nie tylko klasyfikację.

Osobno sprawdziłem klasyczne pułapki ewaluatorów pokerowych:

- **koło** (as–2–3–4–5, gdzie as gra jako najniższa karta): rozpoznane jako
  strit, z piątką jako kartą wysoką ✓
- **koło w jednym kolorze**: rozpoznane jako strit-flush, i poprawnie
  **słabsze** od strit-flusha od szóstki ✓
- koło poprawnie słabsze od najniższego zwykłego strita ✓

**Kolejność działania heads-up** — klasyczne miejsce błędu, bo w grze jeden na
jednego reguły są odwrotne niż przy pełnym stole:

- button wnosi **mały** blind ✓ (przy pełnym stole nie wnosi żadnego)
- button działa **pierwszy przed flopem** ✓
- button działa **ostatni po flopie** ✓

**Drabinka min-raise** — sprawdzona niezależnym rachunkiem przez sześć kolejnych
podbić o minimalną kwotę, oraz po flopie:

| Krok | Poziom zakładu | Wymagane minimum podbicia | Zgodne? |
|---|---|---|---|
| duży blind | 2 | — | — |
| 1. podbicie | 4 | 3 | ✓ |
| 2. podbicie | 6 | 4 | ✓ |
| 3.–6. podbicie | 8, 10, 12, 14 | 4 każde | ✓ |
| po flopie, pierwszy zakład | 0 | 2 (= duży blind) | ✓ |
| po zakładzie 10 | 10 | 20 | ✓ |

**Krótki all-in nie otwiera licytacji ponownie** — reguła, którą bardzo łatwo
zaimplementować błędnie. Sprawdzone: gracz z małym stosem, którego all-in jest
mniejszy niż wymagane minimalne podbicie, faktycznie **nie daje** przeciwnikowi
prawa do kolejnego podbicia; przeciwnik może już tylko sprawdzić albo spasować ✓

**Zwrot nadpłaty**: gracz wstawił 100 przy przeciwniku mającym 5 — zwrócono
dokładnie 95, suma żetonów zachowana ✓

**Podział puli**: 400 kombinacji (pule 0–199 × zwycięzcy × pozycje buttona) —
w każdej suma wypłat równa puli, żadne miejsce nie pojawia się dwukrotnie,
niepodzielna reszta idzie deterministycznie do miejsca po lewej buttona ✓

### 4.4. Spin & Go i ICM

**Side poty** (`spin.award_allin` — podział puli, gdy gracze mają różne stosy):
30 000 losowych kombinacji wkładów i układów, w tym remisy i wkłady zerowe.
Suma wypłat równa sumie wkładów w **każdym** przypadku, żadna wypłata ujemna ✓

**Model ICM**: 2 000 losowych stanów po trzech graczach. Dla każdego sprawdziłem,
że macierz prawdopodobieństw zajęcia miejsc jest poprawnym rozkładem — każdy
wiersz sumuje się do 1 **i każda kolumna też** (drugie jest mocniejsze: znaczy,
że każde miejsce w klasyfikacji jest zajęte przez dokładnie jednego gracza).
Suma oczekiwanych wypłat równa się dokładnie sumie nagród ✓

### 4.5. Przeciek informacji — test najważniejszy

W produkcie pokerowym to jedyna kategoria błędu, która niszczy produkt całkowicie.
Sprawdziłem ją najostrzej, jak umiałem: **na granicy procesu**, czyli tam, gdzie
dane naprawdę wychodzą do drugiego komputera.

Uruchomiłem serwer stołów LAN, podłączyłem się jako klient, rozegrałem pełny mecz
25 rozdań przeciwko botowi i **przechwyciłem każdy bajt**, jaki serwer wysłał do
klienta: 23 383 bajty w 145 wiadomościach. Równolegle serwer zapisał pełną
historię meczu (kanał operatora, zawierający wszystko: ziarna talii i karty obu
graczy). Następnie porównałem:

- zbiór **wszystkich** żetonów informacyjnych o kartach obecnych w strumieniu do
  klienta: **48 różnych kart**;
- zbiór kart, które klient **miał prawo** zobaczyć w tym meczu (własne karty +
  karty wspólne + karty odkryte na showdownie): **48 kart**;
- **różnica: zbiór pusty.**

Do tego: żadne z 25 ziaren talii nie pojawiło się w strumieniu, żadna nazwa
wewnętrznej struktury silnika też nie.

Warto opisać, jak doszedłem do tego wyniku, bo pokazuje, jak łatwo tu o fałszywy
alarm. Mój **pierwszy** test szukał w całym strumieniu par kart bota z rozdań bez
showdownu — i **znalazł trafienie**: „Kc 8h" z rozdania 16. Zanim to zgłosiłem,
sprawdziłem kontekst. Okazało się, że „Kc 8h" w strumieniu to **własne karty
klienta z rozdania 0** — talia jest tasowana co rozdanie, więc ta sama para
naturalnie powtarza się w innej roli. Mój test był zły, nie kod. Poprawny test
(porównanie per karta ze zbiorem legalnie widocznych) daje zbiór pusty.
**Nie ma przecieku.**

### 4.6. Odtwarzalność: wszystkie trzy obiecane własności potwierdzone

| Obietnica z `README.md` | Sprawdzenie | Wynik |
|---|---|---|
| eksport meczu identyczny bajt w bajt dla tych samych argumentów | dwa przebiegi, `cmp` | ✓ identyczny |
| korpus self-play niezależny od liczby procesów roboczych | `--jobs 1` vs `--jobs 4`, `diff -r` | ✓ identyczny, 13 plików |
| ten sam seed serii daje ten sam raport areny | dwa przebiegi | ✓ identyczny |

---

## 5. Co jest naprawdę dobre

Podaję to osobno, bo w audytach zwykle tonie pod listą usterek, a tutaj byłoby
to mylące — jakość rzemiosła w rdzeniu jest wyraźnie powyżej przeciętnej.

1. **Architektura dziennika zdarzeń jest zrobiona konsekwentnie do końca.**
   Nie ma „stanu na boku". Wszystkie moje testy sumy żetonów nie znalazły nic,
   co jest bezpośrednim skutkiem tej decyzji, nie szczęścia.

2. **Granica informacyjna jest konstrukcyjna, nie umowna.** Widoczność jest
   właściwością zdarzenia, a widok gracza to przefiltrowany dziennik. Żeby
   przeciek powstał, trzeba by zmienić architekturę, nie zapomnieć o warunku.

3. **Niezmienniki są egzekwowane maszynowo.** `tests/test_architecture.py` czyta
   drzewo składniowe każdego modułu i sprawdza **wypisane z nazwy** listy
   dozwolonych zależności. Autorzy świadomie wybrali listę zamiast reguły —
   komentarz w kodzie mówi wprost: „nowy import ma być decyzją, nie skutkiem".
   To jest dobra inżynieria.

4. **Odmowa jest zawsze jawna.** W czytniku artefaktu blueprintu
   (`blueprint_reader.py`) jest hierarchia **16 klas wyjątków** i ponad 30
   jawnych sprawdzeń: brak warstwy, brak stanu, węzeł nieosiągalny, brak
   strategii, brak sekcji, niezdefiniowany margines, niezgodny odcisk przebiegu.
   Każdy brak ma własną nazwę i rzuca wyjątek. **Nigdzie nie zwraca się cicho
   zera ani rozkładu równego** — a to jest dokładnie ten błąd, który w solverach
   powoduje, że bot „gra" losowo i nikt nie wie dlaczego.

5. **Testy są używane jako sondy mutacyjne, nie jako podkładka.** W 16 miejscach
   testy celowo **podmieniają funkcję produkcyjną na wersję sprzed naprawy**
   i sprawdzają, że test to wychwytuje. To odwrotność typowego nadużycia
   („zamockuj to, co testujesz, żeby przechodziło") i oznaka dojrzałej dyscypliny.

6. **Dokumentacja podaje kierunek własnego błędu.** W `tools/blueprint/mode_census.py`
   docstring wymienia „dwa założenia, których ten moduł NIE mierzy, **oba
   w kierunku zaniżenia**". Projekt, który dokumentuje, w którą stronę może się
   mylić jego własna wycena, jest rzadkością.

7. **Zero zależności zewnętrznych w produkcie.** Cały silnik i wszystkie boty
   działają na czystej bibliotece standardowej Pythona. `numpy` jest dopuszczony
   wyłącznie w narzędziach treningowych i to jest pilnowane testem. Wersja
   `numpy` jest przypięta co do łatki, z komentarzem wyjaśniającym dlaczego
   (identyczność bitowa artefaktów).

8. **Dziennik decyzji.** 30 dokumentów decyzyjnych i 56 specyfikacji zadań.
   Można odtworzyć nie tylko *co* zbudowano, ale *dlaczego* i co odrzucono.

---

## 6. Co jest nie tak

Uszeregowane po tym, ile realnie kosztują. Żadne z poniższych nie jest błędem
w rozliczaniu żetonów ani przeciekiem informacji — tych nie znalazłem.

### 6.1. ISTOTNE — arena BB/100 nie mierzy tego, co ogłasza

`README.md` reklamuje „arenę porównawczą agentów": `--series 100 --hands 200`
i raport w BB/100 z przedziałem ufności. Zmierzyłem, co ta arena naprawdę robi
przy konfiguracji z dokumentacji (20 par × 50 rozdań, stosy 100/100):

| Wielkość | Zmierzona wartość |
|---|---|
| limit rozdań w konfiguracji | 50 |
| **mediana rozdań faktycznie zagranych w meczu** | **1** |
| średnia rozdań na mecz | 3,4 |
| maksimum | 16 |
| powód zakończenia meczu | **bust w 40 meczach na 40** |
| rozdań ogłoszonych (20 par × 2 × 50) | 2 000 |
| **rozdań faktycznie zagranych** | **135** |

Przyczyna jest strukturalna: mecz kończy się wyeliminowaniem gracza, a boty przy
50 dużych blindach wchodzą all-in niemal natychmiast. Nie ma odtwarzania stosów
między rozdaniami, więc pierwsze rozdanie zwykle rozstrzyga cały mecz. A skoro
BB/100 to „zysk ÷ duży blind ÷ liczba rozdań × 100", to przy mianowniku równym
1 rozdaniu wynik nie jest tempem wygrywania — jest przeskalowanym wynikiem
jednego rzutu monetą.

Stąd nagłówkowe liczby rzędu **279 BB/100** (realne tempo w pokerze to jednostki,
maksymalnie kilkadziesiąt BB/100). Co gorsza, sam wybór estymatora zmienia wynik
o trzecią część:

- średnia nieważona po parach (tak liczy `arena.py`): **279,17 BB/100**
- ta sama próbka ważona liczbą rozdań: **370,37 BB/100**

Dokumentacja **wie, że pomiar jest szumiący** — `docs/CURRENT_STATE.md` pisze
o odchyleniu „~800–1100 BB/100 na parę" i o tym, że 20 par nie rozdziela różnic.
Nie podaje jednak przyczyny, a przyczyna nie jest „mała próbka": jest nią to,
że **jednostka pomiaru jest niewłaściwa dla gry kończącej się bustem**. Żadna
liczba par tego nie naprawi.

*Kierunek naprawy (bez pisania kodu za wykonawcę):* albo raportować statystykę
dobrze zdefiniowaną dla meczów kończących się bustem (odsetek wygranych meczów —
patrz 6.2), albo zmienić regulamin areny tak, żeby rozdania były niezależne
(odtwarzanie stosów co rozdanie), albo — najprościej — przestać nazywać to
BB/100.

### 6.2. ISTOTNE — skutek 6.1: nie wiedziano, który bot jest najlepszy

To nie jest osobny defekt kodu, ale najważniejszy praktyczny skutek poprzedniego
punktu, więc podaję go osobno. Zmierzyłem siłę botów statystyką, która **jest**
dobrze zdefiniowana dla meczów kończących się bustem: **odsetek wygranych
meczów**, na 300 parach lustrzanych (600 meczów na każdą parę botów, limit 200
rozdań).

Kontrola poprawności statystyki: każdy bot przeciw samemu sobie dał **dokładnie
50,0%** — co przy okazji niezależnie potwierdza, że lustrzana konstrukcja pary
w arenie znosi się idealnie.

Wyniki (wiersz przeciw kolumnie, odsetek wygranych meczów):

|  | clone | mccfr | mlp-clone | rule | rule-aggr. |
|---|---|---|---|---|---|
| **clone** | — | 46,8% | 43,7% | 27,8% | 46,3% |
| **mccfr** | 53,2% | — | 53,0% | 41,3% | 40,2% |
| **mlp-clone** | 56,3% | 47,0% | — | 30,5% | 45,8% |
| **rule** | **72,2%** | **58,7%** | **69,5%** | — | **69,8%** |
| **rule-aggressive** | 53,7% | 59,8% | 54,2% | 30,2% | — |

Z przedziałami ufności (n = 600 meczów na komórkę):

| Porównanie | Odsetek wygranych meczów |
|---|---|
| rule vs clone | **72,2% ± 3,6** |
| rule vs mlp-clone | **69,5% ± 3,7** |
| rule vs rule-aggressive | **69,8% ± 3,7** |
| rule vs mccfr | **58,7% ± 3,9** |

Wniosek jest jednoznaczny i wszystkie przedziały wykluczają 50% z dużym
zapasem: **najprostszy bot w repozytorium — kilkudziesięciolinijkowy
`rule_agent` z ręcznie napisanymi progami — bije wszystkie trzy boty uczone
maszynowo.** Klony przegrywają z nauczycielem, na którym je trenowano (27,8%
i 30,5%). Bot MCCFR, czyli cała gałąź „teorii gier", wygrywa 41,3% przeciw
regułom.

Uczciwie: **dokumentacja repozytorium mówi to samo co do znaku.**
`docs/CURRENT_STATE.md` raportuje, że clone, mlp-clone i mccfr przegrywają
z `rule`, i pisze wprost, że oczekiwanie decyzji 07 zostało *„nieosiągnięte"*.
Zasługa jest po stronie autorów — nie ukryli tego. Brakuje natomiast pomiaru
o mocy wystarczającej do rozstrzygnięcia; powyższa tabela go dostarcza.

Praktyczne znaczenie dla właściciela produktu: **kilka miesięcy pracy nad
uczeniem maszynowym nie dało jeszcze nic ponad baseline.** To normalne na tym
etapie (abstrakcja jest bardzo zgrubna, artefakt MCCFR ma 1 000 iteracji przy
sufi­cie 317 048 sytuacji), ale trzeba to wiedzieć przed dosypaniem kolejnych
rdzenio-godzin.

### 6.3. ISTOTNE — powód obcięcia turnieju jest wyliczany i wyrzucany

`spin_arena.run_spin` prowadzi turniej Spin i zwraca dwie rzeczy: końcowe stosy
**oraz powód zakończenia** — `"bust"` (ktoś wyleciał) albo `"guard"` (przekroczono
bezpiecznik 80 rozdań). Bezpiecznik jest potrzebny, bo przy pewnych strategiach
turniej nigdy się nie kończy.

Problem jest w `play_spin` (`spin_arena.py:279`), czyli w funkcji, która zamienia
turniej na nagrody:

```python
stacks, _ = run_spin(books, seed)          # powód zakończenia wyrzucony
order = sorted(range(3), key=lambda i: (-stacks[i], i))
```

Powód jest podstawiany pod `_` i ginie. Turniej **obcięty** w połowie dostaje
więc miejsca przydzielone po liczbie żetonów i wchodzi do statystyki ROI jako
turniej rozegrany — bez żadnego sygnału.

Zmierzyłem, czy to teoretyczne. Nie jest:

| Zestaw strategii | Powody zakończenia (400 ziaren) |
|---|---|
| trzech „always_jam" | bust 400 |
| exploit vs dwa fishe | bust 400 |
| wide_call vs dwa fishe | bust 400 |
| **trzech „always_fold"** | **guard 400** ← 100% obciętych |
| fold vs dwa jamy | bust 400 |

Strategia `always_fold` nie jest hipotetyczna — występuje w **11 miejscach
w `tests/test_spin_arena.py`**, w tym co najmniej cztery razy jako pełna trójka
(linie 241, 387, 541, 732), czyli dokładnie w konfiguracji obcinanej zawsze.

Dodatkowo: **nikt w całym repozytorium nie sprawdza wartości `"guard"`.**
Jedyny test dotyczący powodu sprawdza `reason == "bust"` dla jednego przypadku
(`tests/test_spin_arena.py:157`). To jest „flaga bez konsumenta" — wprost
zakazana przez regułę 11 konstytucji.

*Kierunek naprawy:* albo `play_spin` odmawia punktowania obciętego turnieju,
albo podaje powód wyżej, żeby statystyka mogła obcięte turnieje odrzucić lub
zaraportować osobno.

### 6.4. ISTOTNE — interfejs wiersza poleceń cicho ignoruje flagi

CLI ma siedem trybów pracy (mecz, człowiek, arena, korpus, zbiór, serwer,
klient). Dla trzech z nich wykluczenia są sprawdzane i zgłaszane błędem.
Dla pozostałych **pierwszy tryb w kolejności sprawdzania po prostu wygrywa,
a reszta flag jest ignorowana bez słowa.** Sprawdzone na żywo:

| Komenda | Co się dzieje | Kod wyjścia |
|---|---|---|
| `--dataset X --series 5` | **błąd z komunikatem** (udokumentowane) | — |
| `--connect host:port --export plik` | **`--export` zignorowany**, pliku nie ma | 0 |
| `--serve 0 --corpus katalog` | **`--corpus` zignorowany**, katalogu nie ma | — |

Użytkownik prosi o eksport historii, dostaje ciszę i kod sukcesu. To dokładnie
wzorzec, który prompt audytora produktu nazywa defektem: „fallbacki maskujące
porażkę jako sukces". `README.md` dokumentuje wykluczenia tylko dla
`--series`, `--corpus` i `--dataset` — tryby sieciowe nie są tam wspomniane.

### 6.5. ISTOTNE — eksport meczu nadpisuje plik, korpus i zbiór odmawiają

Trzy tryby zapisujące dane na dysk chronią je w trzech różnych stopniach:

| Tryb | Zachowanie wobec istniejących danych | Kod |
|---|---|---|
| `--corpus` | **odmawia**: „katalog docelowy niepusty — korpus nie nadpisuje" | `corpus.py:74` |
| `--dataset` | **odmawia**: „plik wyjściowy istnieje — zbiór nie nadpisuje" | `dataset.py:24` |
| `--export` | **nadpisuje bez pytania** | `cli.py:263` |

Sprawdzone: plik z treścią „STARA TREŚĆ" został nadpisany bez ostrzeżenia.
Historia meczu to dane, których nie da się odtworzyć bez znajomości wszystkich
argumentów — niespójność ochrony w jednym narzędziu jest pułapką na użytkownika.

### 6.6. ISTOTNE — odmowa połączenia = surowy zrzut stosu

Najbardziej prawdopodobny błąd użytkownika przy grze w sieci lokalnej to
podanie złego portu albo próba połączenia przed uruchomieniem serwera.
Co dostaje użytkownik:

```
ConnectionRefusedError: [Errno 111] Connection refused
  File "/usr/lib/python3.13/socket.py", line 864, in create_connection
  ...
```

Surowy ślad stosu Pythona. Przyczyna: `lan_client.run_client` otwiera gniazdo
bez zabezpieczenia (`lan_client.py:30`), a `cli.main` przechwytuje tylko
`ArgumentError` i `ValueError` — `OSError` przechodzi na wylot. Ironia polega
na tym, że docstring `run_client` **obiecuje** kod wyjścia 2 dla błędów
(`lan_client.py:29`) — obietnica, której nic nie realizuje dla najczęstszego
błędu.

### 6.7. ISTOTNE — ta sama formuła policzona dwa razy, w dwóch modułach

`abstraction._field_equity_mille` i `encoding._FIELD_EQUITY_MILLE` liczą
**ten sam słownik 169 wartości** (średnia szansa każdej klasy kart przeciwko
losowej ręce). Sprawdziłem: słowniki są **identyczne**. Czyli jedna liczba ma
dwie definicje w dwóch miejscach — i nic nie pilnuje, żeby przy zmianie jednej
zmieniła się druga.

Koszt jest mierzalny, bo obie definicje wykonują się **w momencie importu
modułu**, zanim cokolwiek się zdarzy:

| Import | Czas |
|---|---|
| `poker.abstraction` | **340 ms** |
| `poker.encoding` (już po abstraction) | **277 ms** |

To ponad pół sekundy płacone przez każdy proces, który dotknie obu modułów —
w tym przez każdy z 483 testów, który je importuje.

Co ważne: **to jest znany, zapisany i niespłacony dług.** `PAMIEC_OPERACYJNA.md`
nosi wpis z **2026-08-10**: „F1 audytu POKER-22 — formuła equity-przeciw-polu
zduplikowana; publiczne API w preflop_equity osobnym kontraktem". Minął miesiąc,
diagnoza była poprawna, kontrakt nie powstał.

### 6.8. INFORMACYJNE — cztery publiczne funkcje bez konsumenta

Funkcje wołane **wyłącznie z testów**, nigdzie w `src/` ani `tools/`:

| Funkcja | Plik |
|---|---|
| `tier_for_multiplier` | `spin.py:111` |
| `utg_shove_ev` | `spin.py:291` |
| `risk_premium` | `icm.py:84` |
| `wta_equities` | `icm.py:76` |

Reguła 11 konstytucji („usuń martwy kod… kod »na przyszłość«") i lista kontrolna
audytora („gałęzie bez wywołań, flagi bez konsumenta") obejmują ten przypadek.
Są przetestowane, więc nie są niebezpieczne — są tylko utrzymywane bez powodu.
Każda z nich ma sensowny powód istnienia w planie, ale plan nie jest konsumentem.

### 6.9. INFORMACYJNE — strażnik architektury ma jedną lukę (dziś niewykorzystaną)

`test_silnik_nie_wykonuje_io` pilnuje, żeby silnik nie **importował** modułów
wejścia/wyjścia (`os`, `pathlib`, `socket`, `json`…). Ale otwarcie pliku
w Pythonie nie wymaga żadnego importu — `open()` jest funkcją wbudowaną. Strażnik
nie wychwyciłby więc modułu silnika, który po prostu robi `open("x").read()`.
To samo dotyczy importu dynamicznego przez `importlib`.

Sprawdziłem, czy luka jest wykorzystana: **nie jest.** W całym pakiecie `poker`
nie ma ani jednego wywołania `open(`, `importlib`, `__import__`, `eval` czy
`exec`. Czyli dzisiejszy stan jest w porządku, ale bariera jest o jedno
niedopatrzenie od przecieku — i niedopatrzenie tego rodzaju przeszłoby całą
bramkę.

### 6.10. INFORMACYJNE — trzy prywatne nazwy przekroczyły granicę modułu

Nazwa z podkreśleniem na początku to w Pythonie umowa: „to jest wewnętrzne, nie
polegaj na tym". Umowa jest łamana w trzech miejscach:

| Import | Gdzie |
|---|---|
| `from poker.openfold import WEIGHTS, _hu` | `spin_arena.py:38` |
| `from poker.openfold import _threebet_from_open, …` | `tools/run_arena.py:30`, `tools/export_open_nash.py:9` |
| `from poker.openfold import _mass, …` | `tests/test_spin_arena.py:19` |

Skutek: `openfold.py` nie może już zmienić tych funkcji, mimo że oznaczył je
jako wewnętrzne. Albo powinny zostać publiczne (bez podkreślenia, z dokumentacją),
albo konsumenci nie powinni ich używać.

### 6.11. INFORMACYJNE — język dokumentacji rozjechał się w nowszych modułach

Cały starszy kod jest konsekwentnie polski. W nowszych modułach Spin/ICM język
się miesza, czasem w obrębie jednego pliku, czasem jednego docstringa:

- `icm.py` — docstring modułu **w całości po angielsku**: „Malmuth–Harville ICM
  and winner-take-all chip EV."
- `spin.py` — docstring modułu po polsku, ale `roles()`, `blinds_for_hand()`
  i komentarz o `DEPTHS` po angielsku
- `spin_arena.py` — **pierwsza linia docstringa po angielsku**, resztę po polsku

Nie łapie tego żaden lint i niczego nie psuje, ale dla następnej osoby jest to
realny koszt czytania. Reguła 11 konstytucji (higiena H0 w dotkniętym obszarze)
to pokrywa.

### 6.12. INFORMACYJNE — dziura w kontroli typów: udokumentowana, ale niepusta

`pyproject.toml` uczciwie przyznaje, że kontrola typów obejmuje `src`, `tests`
i `tools/blueprint`, a resztę `tools/` nazywa „osobnym długiem". Zmierzyłem ten
dług: **1 489 linii poza bramką**, a po uruchomieniu na nich `mypy --strict`
wychodzi **30 błędów w 3 plikach** (28 w `tools/docs/mk_pdf.py`, po jednym
w `run_arena.py` i `export_open_nash.py`).

Osobno, **wewnątrz** obszaru objętego bramką: `tools/blueprint/mode_census.py`
przyjmuje konfigurację solvera jako `config: Any` w **7 sygnaturach** bez
komentarza wyjaśniającego (`Any` występuje łącznie w 11 sygnaturach tego pliku).
`Any` wyłącza kontrolę typów, więc tryb `strict` jest tam formalny — tych siedem
funkcji nie jest sprawdzanych. Powód istnieje (konfiguracja przychodzi z modułu
ładowanego dynamicznie, bo `tools/` nie jest pakietem Pythona), ale nie jest
zapisany przy kodzie, a lista kontrolna audytora wymienia „nowe `Any`" jako
pozycję do zgłoszenia.

### 6.13. INFORMACYJNE — koszt utrzymania danych w plikach Pythona

Konsekwencja decyzji z punktu 2.1, zmierzona:

| Pomiar | Wartość |
|---|---|
| `strategy_table.py` — rozmiar | **3,2 MB / 122 004 linie** |
| **zimny** import (bez cache bajtkodu) | **771 ms** |
| ciepły import (z `.pyc`) | 9,5 ms |
| rozmiar cache bajtkodu | 1,5 MB |

Dopóki cache bajtkodu istnieje, koszt jest znikomy. Problem pojawia się przy
skali: `docs/CURRENT_STATE.md` sam diagnozuje, że dominującym kosztem bramki
przy większym artefakcie jest **pięciokrotne parsowanie wygenerowanego modułu
przez testy architektury**, nie kontrola typów. Diagnoza jest trafna, ale
wskazana naprawa (memoizacja parsowania) nie została wykonana.

### 6.14. INFORMACYJNE — cztery asercje, które nie odróżniają strażników

W repozytorium jest 103 użyć `pytest.raises`, z czego **80 podaje `match=`**
(sprawdza treść komunikatu) — bardzo dobry stosunek. Z pozostałych 23 większość
to wyjątki jednoznaczne (`FrozenInstanceError`, `TypeError`, `SystemExit`), gdzie
`match` nic nie dodaje. Ale w czterech miejscach **dwa różne strażniki w tym
samym teście są sprawdzane tym samym, gołym `ValueError`**:

| Plik i linie | Dwa różne strażniki, jedna asercja |
|---|---|
| `tests/test_spin_arena.py:110` i `:112` | za mała próbka / zero replikacji |
| `tests/test_blueprint_pilot.py:726` | nieznany tryb perturbacji |
| `tests/test_blueprint_pilot.py:849` | niezgodny limit iteracji |

Gdyby implementacja rzuciła **nie ten** błąd co trzeba, test i tak przeszedłby.
To jest dokładnie pułapka, którą audytor POKER-57 sam zapisał do
`PAMIEC_OPERACYJNA.md`: *„`pytest.raises(Błąd)` bez `match` nie odróżnia
strażnika od potknięcia piętro niżej"*. Lekcja jest zapisana, cztery miejsca
jej nie zastosowały.

### 6.15. INFORMACYJNE — nazwa `roles()` myli button z małym blindem w grze trzyosobowej

`spin.roles()` zwraca trójkę `(utg, btn_sb, bb)` i docstring mówi: *„Button
posts SB"* — button wnosi mały blind. To jest prawda w grze **dwuosobowej**
i nieprawda w **trzyosobowej**, gdzie button, mały blind i duży blind to trzy
różne miejsca, a button nie wnosi niczego.

Sprawdziłem konsekwencje rachunkowe: **nie ma ich.** Kolejność licytacji, którą
ta funkcja produkuje (miejsce bez blinda działa pierwsze, potem mały, potem duży
blind), jest **poprawna dla trzyosobowego jam/fold** — pod warunkiem czytania
`utg` jako buttona. Nic się więc dziś nie liczy źle.

Koszt jest w nazwie: ktokolwiek rozszerzy Spin o licytację po flopie, dostanie
od tej funkcji błędną kolejność, bo po flopie porządek zależy od tego, gdzie
naprawdę jest button. A dokument decyzyjny 10 (`10-spin-and-go-icm-bez-pokerkit.md`)
nie opisuje tego uproszczenia.

### 6.16. INFORMACYJNE — cicha podmiana funkcji aktywacji w sieci neuronowej

`mlp_agent._activate` (`mlp_agent.py:29`):

```python
def _activate(value: float) -> float:
    if ACTIVATION == "relu":
        return value if value > 0.0 else 0.0
    return tanh(value)
```

Jeśli w module wag pojawi się jakakolwiek inna wartość `ACTIVATION` —
`"sigmoid"`, `"gelu"`, literówka — funkcja **cicho policzy `tanh`**. Bot zagra
złą matematyką i nie będzie o tym żadnego sygnału. Wartości dopuszczalne powinny
być wyliczone, a nieznana powinna być błędem. Dzisiejsze wagi mają `relu`, więc
defekt jest uśpiony.

### 6.17. INFORMACYJNE — dwa drobniejsze spostrzeżenia

- **Serwer LAN przyjmuje od klienta nieograniczoną konfigurację meczu.**
  `hand_limit` i stosy nie mają górnej granicy, więc klient może poprosić
  o mecz miliarda rozdań (`lan_server.py:180`). Decyzja 08 deklaruje sieć
  lokalną jako **zaufaną**, więc to mieści się w przyjętym modelu zagrożeń —
  odnotowuję, bo to jest zalążek pokerroomu, a założenie „sieć zaufana"
  przestanie obowiązywać najpóźniej przy pierwszym stole w internecie.
- **Nieograniczona pamięć podręczna w `icm._remaining`.** Funkcja rekurencyjna
  z dekoratorem `@cache`, kluczowana układem stosów. Przy trzech graczach nie ma
  znaczenia; gdyby ten sam model obsłużył większe stoły, rośnie bez ograniczenia,
  a liczba wywołań rekurencyjnych rośnie jak silnia z liczby graczy.

### 6.18. Uwaga o kosztach bramki w dokumentacji

`docs/CURRENT_STATE.md` podaje twarde liczby: `tests/test_mode_census.py` kosztuje
**73 s**, a bramka rośnie „z 3 min 17 s do 4 min 30–40 s". Zmierzone u mnie:

| Element | Dokumentacja | Mój pomiar |
|---|---|---|
| `tests/test_mode_census.py` (przygotowanie) | 73 s | **124 s** |
| bramka, ciepła | 4 min 30–40 s | **7 min 47 s** (467 s) |
| z czego `pytest` | — | 466,8 s |
| z czego `ruff` + `mypy` | — | < 1 s |
| liczba testów | 457 (POKER-56) | **483** (zgodne z POKER-57 ✓) |

**Nie zgłaszam tego jako błędu w dokumentacji** — to inna maszyna, a sekundy nie
są przenośne. Zgłaszam natomiast, że liczby są podane **bez wskazania maszyny**,
więc nie da się ich zweryfikować ani odtworzyć; a różnica 1,7× jest na tyle duża,
że ktoś planujący pracę na podstawie „4,5 minuty" pomyli się o 3 minuty na każdym
przebiegu. Liczba testów natomiast zgadza się dokładnie.

Niezależnie od maszyny: **bramka trwa ~8 minut i jeden plik testowy zjada 27%
tego czasu.** To realny koszt pętli zwrotnej.

---

## 7. Czego ten produkt nie potrafi

Sekcja dla uniknięcia nieporozumień — spisana z `docs/CURRENT_STATE.md`
(sekcja „Czego nie ma") i potwierdzona w kodzie.

- **Nie gra przy stole większym niż dwuosobowy.** Maszyna licytacji wprost
  odmawia (`betting.py:167`). Trzy osoby istnieją tylko w uproszczonym modelu
  Spin (wyłącznie all-in/pas, bez licytacji po flopie).
- **Nie ma side potów w głównym silniku.** Są tylko w rozliczeniu all-inów Spin.
  Przy dwóch graczach nie są potrzebne; przy trzech byłyby.
- **Nie ma bota, który biłby dobrego człowieka.** Najlepszy bot w repozytorium to
  kilkadziesiąt linii ręcznych reguł (punkt 6.2). Boty „GTO" i uczone maszynowo
  przegrywają z nim.
- **Nie ma trenera** — jednego z trzech zapowiadanych produktów.
- **Nie ma pełnego artefaktu solvera w repozytorium.** Jest czytnik i agent,
  który z niego gra, ale sam plik (koszt regeneracji ok. **76,6 rdzenio-godzin**)
  leży poza repozytorium. W repo jest tylko mały artefakt kontrolny.
- **Nie ma interfejsu graficznego** — tylko terminal i protokół sieciowy.
- **Nie ma zabezpieczeń przed nieuczciwym graczem w sieci.** Kod stołu (osiem
  znaków, ~39,6 bita) to jedyna kontrola dostępu i dokumentacja mówi o tym
  wprost. To wystarcza w sieci domowej i nie wystarczy nigdzie indziej.
- **Nie ma pieniędzy, kont ani trwałego stanu** poza plikami eksportu.

---

## 8. Ocena całościowa

**Rzemiosło w rdzeniu: bardzo dobre.** Nie znalazłem ani jednego błędu
w rozliczaniu żetonów w 4 000 losowych rozdaniach sprawdzanych po każdym
zdarzeniu, ani jednej rozbieżności ewaluatora układów wobec niezależnej
implementacji na 40 000 przypadkach, ani jednego przecieku informacji
w 23 383 bajtach faktycznie wysłanych przez sieć. Reguły pokerowe, w tym te
trudne (kolejność heads-up, drabinka min-raise, krótki all-in nieotwierający
licytacji, zwrot nadpłaty, podział niepodzielnej reszty), są poprawne.
Bramka jakości jest zielona bez ani jednego obejścia kontroli typów.

To jest kod, w którym dobre własności są **konstrukcyjne**, nie przypadkowe.
Niezmienność dziennika zdarzeń, widoczność jako właściwość zdarzenia, jawny
wyjątek na każdy brak, testy sprawdzające listy zależności modułów — to wszystko
sprawia, że całe klasy błędów są tu nie tyle nieobecne, ile trudne do popełnienia.

**Słabe punkty nie są w silniku — są w pomiarze i na brzegach.** Trzy najbardziej
kosztowne rzeczy, które znalazłem, to: arena, która ogłasza tempo wygrywania,
a mierzy pojedyncze rozdanie (6.1); wynikające z tego nierozstrzygnięcie, że cała
gałąź uczenia maszynowego przegrywa z baseline'em (6.2); oraz końcówki użytkowe,
które cicho gubią flagi, nadpisują pliki i pokazują zrzuty stosu zamiast
komunikatów (6.4–6.6). Żadne z nich nie psuje gry — wszystkie psują możliwość
podjęcia dobrej decyzji na podstawie tego, co produkt raportuje.

**O procesie.** Widać, że proces „fabryki" działa: znalazłem lekcje zapisane
w `PAMIEC_OPERACYJNA.md` **przed** defektem, który miały złapać, i znalazłem
w dokumentacji uczciwe „oczekiwanie nieosiągnięte" tam, gdzie łatwo byłoby
napisać coś ładniejszego. Widać też jego koszt: dwa z moich findingów (6.7
duplikacja, 6.14 asercje bez `match`) to **już zdiagnozowane i wciąż niespłacone
długi**. Diagnoza jest w tym projekcie sprawniejsza niż spłata.

**Jedna rekomendacja, gdyby wolno było podać tylko jedną:** naprawić pomiar,
zanim dosypie się kolejne rdzenio-godziny do solvera. Punkt 6.1 znaczy, że
narzędzie, którym ten projekt ocenia własne postępy, nie odpowiada na pytanie,
które mu się zadaje. Punkt 6.2 pokazuje, że gdy zadać je poprawnie, odpowiedź
jest zniechęcająca — i lepiej ją znać przed wydatkiem niż po.

---

## Załącznik: jak odtworzyć moje pomiary

Środowisko: Python 3.13.12, Linux, świeży `venv` z `pip install -e ".[dev,train]"`
na commicie `16dc6f8`.

**Bramka i jej koszt:**
```bash
ruff check . ; mypy ; pytest -q --durations=25
```

**Obietnice odtwarzalności:**
```bash
python -m poker.adapters.cli --seed 7 --hands 20 --export e1.json
python -m poker.adapters.cli --seed 7 --hands 20 --export e2.json
cmp e1.json e2.json                                    # bajt w bajt

python -m poker.adapters.cli --corpus k1 --matches 12 --seed 7 --jobs 1 \
  --agent0 rule --agent1 rule-aggressive
python -m poker.adapters.cli --corpus k4 --matches 12 --seed 7 --jobs 4 \
  --agent0 rule --agent1 rule-aggressive
diff -r k1 k4                                          # identyczne
```

**Arena i jej problem (punkt 6.1):**
```bash
python -m poker.adapters.cli --series 20 --hands 50 --seed 7 \
  --agent0 rule --agent1 rule-aggressive
```
Długość meczów mierzy się przez `poker.arena.play_mirrored_pair` i pole
`hands_played` każdego `MatchResult`; powód zakończenia — przez `reason`.

**Cicho ignorowane flagi (punkt 6.4):**
```bash
python -m poker.adapters.cli --connect 127.0.0.1:1 --export y.json ; ls y.json
python -m poker.adapters.cli --serve 0 --corpus kk    ; ls kk
```

**Koszt importu i duplikacja (punkty 6.7 i 6.13):**
```bash
find src -name __pycache__ -type d -exec rm -rf {} +
python -X importtime -c "import poker.strategy_table" 2>&1 | tail -2
python -c "
import time, poker.abstraction as A, poker.encoding as E
print({c: A._field_equity_mille(c) for c in A.ALL_CLASSES} == E._FIELD_EQUITY_MILLE)"
```

**Martwy kod (punkt 6.8):**
```bash
for f in tier_for_multiplier utg_shove_ev risk_premium wta_equities; do
  echo "$f:"; grep -rn "\b$f\b" src/ tools/ --include=*.py | grep -v "def $f"
done
```

**Skrypty moich testów własnych** (fuzz silnika, niezależny ewaluator, drabinka
min-raise, test przecieku LAN, tabela odsetka wygranych meczów) nie wchodzą do
repozytorium — audytor niczego nie dodaje do kodu produktu. Wszystkie opierają
się wyłącznie na publicznym API pakietu `poker` i dają się odtworzyć z opisów
w punktach 4.2–4.6 i 6.2.

# 34. Najkrótsza droga do bota, który pewnie bije field

Status: **PROJEKT — czeka na zatwierdzenie operatora.** Autor: doradca,
2026-09-20. Podstawa: zlecenie operatora („zaplanuj to tak, aby możliwie
szybko dojść do bota o bezpiecznie dobrej jakości, bijącego pewnie field").
Kontekst: [29](29-tier-first-fundament-gto-mapa-po-researchu.md) (prawo
kosztu, szew `_settle()`, bramka DBR),
[31](31-nauka-nie-komercja-compute-i-pomiar-za-zero.md) (darmowy compute),
[32](32-koncepcja-algo-uczacego-boardy-model-pola.md) (model pola),
[33](33-droga-do-dobrego-bota-gto-kroki-i-koszt.md) (mapa 18 kroków).
**Ta decyzja zmienia kolejność z decyzji 33, nie jej treść merytoryczną.**

## 0. Co się zmienia: inny cel to inna kolejność

Decyzja 33 planowała „dobrego bota GTO" i mierzyła go **wyzyskiwalnością ε**.
Zlecenie mówi teraz „pewnie bije field" — a to jest **ROI przeciw realnym
przeciwnikom**. To dwie różne liczby i dają dwie różne kolejności prac:

| | cel ε (decyzja 33) | cel ROI (ta decyzja) |
|---|---|---|
| co maksymalizujemy | brak słabości wobec kontr-strategii | zysk wobec pola, jakie jest |
| gdzie leży marginalna godzina | precyzja solvera | model pola i warstwa odchyłu |
| kolejność tierów | od najtrudniejszego (elegancja) | **po udziale w wolumenie** |
| przyrząd | ε ex-post | **odsetek wygranych turniejów** |
| próbka do wniosku | brak — ε jest deterministyczne | 0,4–15 tys. turniejów (pkt 2) |

Trzy wnioski tej zmiany, każdy policzony niżej: **(a)** wydaliśmy compute na
tier wart 1% wolumenu, a nie wydaliśmy na tier wart 87%; **(b)** próg „bije
field" liczony dzisiejszymi wagami tabeli tierów **myli się bardziej niż cała
szukana przewaga**; **(c)** cała faza obejmująca 87% wolumenu mieści się
w jednym 6-godzinnym oknie darmowych runnerów.

## 1. Cel liczbowy — ROI, wyprowadzone z ekonomii formatu

Struktura Spin & Go (potwierdzona kodem: `poker.spin.PAYOUTS` niesie wektor
nieznormalizowany, `"2x"` → `(2.0, 0, 0)`): pula = mnożnik × buy-in, trzech
graczy płaci 3 buy-iny, **mnożnik jest losowany niezależnie od gry**. Stąd
dwie tożsamości, obie do sprawdzenia rachunkiem, nie do uwierzenia:

```
E[mnożnik] = 3 · (1 − rake)                     [definicja rake]
ROI        = P(win) · E[mnożnik] − 1            [tiery WTA]
```

Konsekwencja, która porządkuje cały plan: **pojedynczy tier nie jest oceniany
w ROI.** Break-even `P(win)` w tierze 2x to 50%, w 4x — 25%. Gracz przeciętny
(33,33%) ma w 2x ROI −33%, a w 4x +33%. Tylko agregat ważony wolumenem ma sens.

**Warunek celu (Q).** Przy rake `r`:

| rake | E[M] | break-even `P(win)` | ROI gracza przeciętnego |
|---:|---:|---:|---:|
| 5% | 2,850 | 35,09% | −5,0% |
| 6% | 2,820 | 35,46% | −6,0% |
| **7%** | **2,790** | **35,84%** | **−7,0%** |
| 8% | 2,760 | 36,23% | −8,0% |

Kontrola poprawności ramy: gracz przeciętny traci **dokładnie rake**. Rachunek
się domyka. Wartość `r` dla docelowej stawki: `BRAK` — wejście operatorskie,
jedna liczba z lobby.

**Ile ROI daje punkt win rate** (rake 7%, E[M] = 2,79): każdy punkt procentowy
`P(win)` to **2,79 pp ROI**. 37,0% → +3,2%; 38,0% → +6,0%; 40,0% → +11,6%.

## 2. Przyrząd — dlaczego mierzymy win rate, a nie pieniądze

To jest miejsce, w którym „pewnie" staje się tanie. Mnożnik ma ogon
jackpotowy, więc ROI liczone z wypłat ma wariancję zdominowaną przez
losowanie, które **z grą nie ma żadnego związku**. Odsetek wygranych
turniejów tej wariancji nie ma — rozkład mnożnika jest znany i wchodzi jako
stała, nie jako losowa. Stąd próbka (test jednostronny 95%, rake 7%):

| prawdziwe `P(win)` | ROI | turniejów do wniosku |
|---:|---:|---:|
| 36,5% | +1,8% | 14 499 |
| **37,0%** | **+3,2%** | **4 706** |
| 37,5% | +4,6% | 2 308 |
| 38,0% | +6,0% | 1 369 |
| 39,0% | +8,8% | 646 |
| 40,0% | +11,6% | 376 |

**To jest kilka tysięcy turniejów, nie miliony.** Pomiar nie jest kosztowną
częścią tego przedsięwzięcia — pod warunkiem, że mierzy się właściwą
statystykę. Arena Spin ma już jednostkę buy-in, bloki rotacji i bootstrap CI
(`spin_arena.sample_blocks`), więc brakuje **estymatora agregatu ważonego
wolumenem**, nie przyrządu od zera.

## 3. Tabela tierów nie domyka się rachunkowo — i to jest krok zerowy

Tożsamość z pkt 1 jest **darmowym testem falsyfikującym** tabelę `TIERS`.
Wiersze w repo: T-MODAL `(2,3)` 87%, T-MID `(4,)` 9%, T-DEEP `(10,)` 1%;
suma 97%, reszta to odroczone pasmo 25x+ (komentarz w `spin.py`).

Wkład minimalny, przy założeniach **najłagodniejszych z możliwych** (T-MODAL
w całości 2x, pasmo 25x+ dokładnie 25x):

```
0,87·2 + 0,09·4 + 0,01·10 + 0,03·25 = 2,950   →   implikowany rake 1,67%
```

Każde inne założenie daje **rake ujemny**, czyli kasyno tracące pieniądze:
T-MODAL 2,2x → −4,1%; T-MODAL 2,5x → −12,8%; pasmo 25x+ o średniej 40x →
−13,3%. Wniosek: **przy jakimkolwiek rake powyżej ~1,7% tabela przeważa
wysokie mnożniki.** Co najmniej jedna z trzech liczb {87% dla T-MODAL, mieszanka
2x/3x, 3% wolumenu przy ≥25x} jest błędna.

Dlaczego to jest krok zerowy, a nie higiena:

| | E[M] | break-even `P(win)` |
|---|---:|---:|
| wagi tabeli (najłagodniej) | 2,950 | 33,90% |
| ekonomia formatu przy rake 7% | 2,790 | 35,84% |
| **błąd progu** | | **1,94 pp** |

Szukana przewaga (ROI +3,2%) to **1,16 pp nad break-even**. Błąd tabeli jest
**większy niż cała przewaga**. Konkretnie: bot o `P(win) = 35,5%` raportowałby
wagami tabeli **+4,7% ROI, tracąc realnie 1,0%**. Bez poprawnych wag każdy
pomiar ROI jest bez wartości — i dlatego jedna liczba z lobby (rake) plus
potwierdzenie udziałów wyprzedza w tym planie cały compute.

## 4. Kolejność po wolumenie — liczby z własnego fixture'a

Z `tools/blueprint/mode_census.py table` (uruchomione 2026-09-20):

| tier | wolumen | solver [rdz-h] | +tensor | z callem (×1,41) | **rdz-h na pp wolumenu** |
|---|---:|---:|---:|---:|---:|
| **T-MODAL** (2x,3x) | **87%** | **17,83** | 29,03 | 25,17 | **0,20** |
| T-MID (4x) | 9% | 36,44 | 47,64 | 51,44 | 4,05 |
| T-DEEP (10x) | 1% | 64,31 | 75,51 | 90,79 | 64,31 |
| pasmo 25x+ (3-paid) | 3% | — | — | — | **nie ma w tabeli** |

**T-DEEP jest 314× mniej efektywny na punkt wolumenu niż T-MODAL.** Stan
faktyczny: policzono najdroższy tier o najmniejszym wolumenie (64,3 rdz-h na
1%), nie policzono najtańszego o największym (17,8 rdz-h na 87%). To nie był
błąd przy celu ε — T-DEEP jest najtrudniejszy, więc zaczynanie od niego było
uzasadnione. Przy celu ROI kolejność się odwraca.

## 5. „Bezpiecznie" — dwie bramki, nie jedna

Operator postawił dwa warunki naraz („bezpiecznie dobrej jakości"
i „pewnie bije"). To są **dwie różne bramki** i obie muszą przejść:

**Bramka S1 — nie daj się rozebrać** (już w decyzji 29 pkt 3B, bez zmian):
ex-post ε profilu z odchyłami ≤ ε czystego blueprintu tieru **i** < 1e−3
bezwzględnie. Jeśli eksploatacja czyni nas bardziej wyzyskiwalnymi niż
blueprint — nie wchodzi.

**Bramka S2 — przetrwaj błąd modelu** (nowa; bez niej „bezpiecznie" nic nie
znaczy): ROI mierzone nie tylko przeciw modelowi pola, ale przeciw
**modelom zaburzonym** — pole o zakresach ±20% węższych i szerszych niż
model, oraz pole zmieszane 50/50 z blueprintem. Warunek: ROI pozostaje
dodatnie we **wszystkich** wariantach, a nie tylko w punkcie centralnym.

Bot, który bije modelowane pole i przegrywa z polem o 20% innym, nie jest
„bezpiecznie dobry" — jest dopasowany do własnego założenia. S2 kosztuje
tylko dodatkowe przebiegi areny (grosze), a jest jedyną rzeczą, która czyni
słowo „pewnie" sprawdzalnym offline.

## 6. Plan — trzy fazy, 15 kontraktów

Koszt ścienny jest zdominowany przez **godziny kontraktów i wejścia
operatora**, nie przez compute.

> **Tempo przepustowości: `BRAK` wiarygodnego oparcia.** Sprawdzalne dziś:
> `docs/taskspecs/` ma **53 kontrakty**, a historia git to **50 commitów przed
> tą sesją między 2026-08-30 a 2026-09-07** (9 dni). Te dwie liczby nie dają
> tempa, bo historia jest wyraźnie skompresowana — dokumenty opisują pracę od
> 2026-08-08, czyli sprzed pierwszego commita. Decyzja 31 pkt 9.6 podaje
> „57 TaskSpeców między 2026-08-08 a 2026-09-12, czyli ~1,6 kontraktu
> dziennie" i **tego w tym środowisku potwierdzić nie umiem** (taskspeki nie
> mają pól datowych, git ma inny zakres). Terminy dzienne w tym punkcie są
> więc **szacunkiem opartym na nieweryfikowanej przepustowości**, a nie
> pomiarem — jedyne twarde liczby tu to rdzenio-godziny z fixture'a.

### Faza 0 — cel, przyrząd, wagi. **0 rdzenio-h, ~3 dni**

| # | krok | dlaczego teraz |
|---|---|---|
| F-1 | Estymator agregatu: `P(win)` per tier + ROI ważone wolumenem + CI + funkcja próbki z pkt 2 | bez tego nie ma czym orzec celu |
| F-2 | Test falsyfikujący tabelę tierów z pkt 3 jako test jednostkowy; rake i udziały od operatora | błąd wag > szukana przewaga |
| F-3 | Finding **6.3**: `play_spin` przestaje punktować turniej ucięty gwardią jak rozegrany; arena przestaje być zaszyta na jeden tier | dzisiejszy pomiar cicho miesza dwie populacje |
| F-4 | Parser korpusu + model pola + licznik `n(I)` (decyzja 32 pkt 3) | jedyne realne pole, jakie mamy |
| F-5 | Workflow darmowego compute'u na Actions, artefakty szyfrowane (decyzja 30 pkt 1) | nośnik dla Faz 1–2 |

**Ta faza może unieważnić resztę planu** — jeśli wagi tierów wyjdą inne, zmienia
się kolejność z pkt 4.

### Faza 1 — 87% wolumenu. **75,5 rdzenio-h solver / 91,3 z tensorem, ~4 dni**

| # | krok | koszt |
|---|---|---|
| F-6 | Flat call w drzewie szwem `_settle()` (17 → 24 liście); **wymaga własnego rekordu decyzyjnego** (decyzja 27) | ×1,41 na wszystkim dalej |
| F-7 | Podzbiór reprezentatywnych flopów (1755 → K) z bramką błędu na realnych zakresach flat-calla | 0 |
| F-8 | **T-MODAL z callem** — blueprint + DBR, 3 tablice V | 75,5 rdz-h |
| F-9 | Krzywa `P_max` i `s`; bramka **S1** | ≤2 |
| F-10 | Pomiar celu: próbka z pkt 2 przeciw modelowi pola | grosze |
| F-11 | Bramka **S2**: te same przebiegi na modelach zaburzonych ±20% | grosze |

Na darmowych runnerach (20 jobów × 6 h = 240–480 rdz-h na okno) **cała Faza 1
to jedno 6-godzinne okno.** Po niej bot pokrywa 87% wolumenu, umie flat call
i ma zmierzone ROI z przedziałem ufności.

### Faza 2 — pozostałe 13% wolumenu. **142,2 rdzenio-h, ~3 dni**

| # | krok | koszt |
|---|---|---|
| F-12 | T-MID z callem (9% wolumenu) | 51,4 rdz-h |
| F-13 | T-DEEP przeliczony z callem (1%) | 90,8 rdz-h |
| F-14 | **Pasmo 25x+ / 3-paid: struktura tierów, której w kodzie NIE MA** — wiersze, wektory wypłat, ε_span | wymaga danych z lobby |
| F-15 | Agregat końcowy: ROI ważone pełnym wolumenem, S1 + S2 na całości | grosze |

Faza 2 kosztuje **1,9× Fazę 1 za 11% jej wolumenu**. To jest świadoma
kolejność, nie przeoczenie: pełne pokrycie jest warunkiem gry na wszystkim,
ale nie jest warunkiem *wniosku*, że bot bije field.

**Razem: ~218 rdzenio-h, 15 kontraktów, 0–46 USD.** Compute to jedyna
część, którą umiem podać twardo: **~218 rdzenio-h ≈ 1–2 okna darmowych
runnerów ≈ pół doby ściennej.** Termin całości zależy od przepustowości
kontraktów (`BRAK`, zastrzeżenie wyżej) i od wejść operatora z pkt 9 — i to
one, nie obliczenia, są harmonogramem.

## 7. Przesłanka, na której stoi ta kolejność — i jej test

Twierdzenie: **przy celu ROI marginalna godzina jest warta więcej w modelu
pola niż w precyzji solvera.** To jest przesłanka, nie dowód, więc dostaje
test, który ją obala albo potwierdza — w Fazie 1, za grosze:

> Zmierz ROI dwóch profili przeciw temu samemu modelowi pola: **(A)** T-MODAL
> zgrubny + warstwa odchyłu, **(B)** T-MODAL dopracowany + zero odchyłu, przy
> równym budżecie rdzenio-godzin. Plan przewiduje, że **A wygrywa**. Jeśli
> wygra B, kolejność Faz 1–2 się odwraca i ta decyzja wymaga korekty.

Bez tego testu pkt 4 i 6 są deklaracją, a deklaracja nie jest dowodem
(konstytucja pkt 2).

## 8. Czego ten plan świadomie NIE robi

**Nie planuje gry na żywym serwisie komercyjnym.** Regulaminy tych serwisów
zakazują botów; uruchomienie tam pomiaru jest decyzją i ryzykiem operatora,
nie założeniem tego planu. Plan mierzy **offline przeciw modelowi pola
zbudowanemu z realnych rąk** i podaje przez bramkę S2 granicę, jak bardzo
model może być zły, żeby wniosek się utrzymał. To jest maksimum, jakie da się
uczciwie orzec bez gry na pieniądze — i trzeba to nazywać tak, a nie „bije
field".

**Nie wchodzi w GPU ani w sieci neuronowe.** Uzasadnienie bez zmian
(decyzje 25, 29, 31): wąskim gardłem jest brakująca gałąź w drzewie i wagi
tierów, nie pojemność reprezentacji strategii. Karta staje się właściwą
odpowiedzią przy postflopie z realnymi rozmiarami zakładów — to jest za
Fazą 2, nie przed Fazą 0. Zmiana tego kierunku wymaga nowego rekordu
uchylającego decyzję 25.

**Nie odrzuca decyzji 33**, tylko przestawia jej kroki pod inny cel. Wszystkie
odrzucenia z decyzji 33 pkt 7 (oszczędność 430,8 rdz-h) zostają w mocy.

## 9. Co blokuje i u kogo leży

1. **Rake docelowej stawki** — jedna liczba. Bez niej próg z pkt 1 jest
   przedziałem 35,1–36,2%, a nie liczbą.
2. **Potwierdzenie udziałów i mnożników wobec żywego lobby** — pkt 3 pokazuje,
   że dzisiejsza tabela się nie domyka. Wszystkie wiersze mają `confirmed=False`.
3. **Struktura pasma 25x+ (3-paid)** — tego w kodzie nie ma w ogóle, więc
   wprost zamówione „wyższe mnożniki, 3 paid" nie da się dziś wycenić.
4. **Korpus** ~1 mln rąk plus metadane (format, stawka, data, Spin czy cash) —
   cztery pytania z decyzji 32 pkt 3.3.
5. **Artefakt `.bpk`** — `find . -name '*.bpk'` w tym środowisku jest pusty
   (sprawdzone 2026-09-20). Cała warstwa GTO T-DEEP stoi na pliku, którego tu
   nie ma.

## 10. Źródła liczb

- Struktura wypłat i jednostka buy-in: `src/poker/spin.py` (`PAYOUTS`
  nieznormalizowany, `TIERS` znormalizowany, `PRIZE_SUM_TOLERANCE`).
- Rdzenio-godziny per tier: `tools/blueprint/mode_census.py table`, uruchomione
  2026-09-20 (T-MODAL 17,83; T-MID 36,44; T-DEEP/WTA@25bb 64,31;
  DBR-T-MODAL 53,48 = 3 × T-MODAL, trzy tablice V).
- Mnożnik ×1,41 za flat call: prawo kosztu Θ(L·C³·iter) liniowe w liściach,
  17 → 24 — [decyzja 29](29-tier-first-fundament-gto-mapa-po-researchu.md) pkt 3C.
- Limity darmowych runnerów (4 vCPU, 6 h/job, 20 jobów):
  [decyzja 31](31-nauka-nie-komercja-compute-i-pomiar-za-zero.md) pkt 3.
- Model pola, licznik `n(I)`, wzór `P_conf`, 1755 klas flopów:
  [decyzja 32](32-koncepcja-algo-uczacego-boardy-model-pola.md) pkt 2–4.
- Tożsamości ROI, progi break-even, tabela próbek, test falsyfikujący tabelę
  tierów i błąd 1,94 pp: własny rachunek z 2026-09-20 na danych `poker.spin`;
  skrypt w scratchpadzie sesji — do repo wchodzi kontraktem F-1/F-2.

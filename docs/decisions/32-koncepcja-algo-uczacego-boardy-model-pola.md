# 32. Koncepcja algorytmu uczącego: jedna pętla, trzy wejścia, jedno pokrętło

Status: **PROJEKT — czeka na zatwierdzenie operatora.** Autor: doradca,
2026-09-19. Podstawa: zlecenie operatora („mamy ~1 mln moich łapek; chcę
reprezentatywne zestawy boardów jak w Pio; jaka koncepcja algo uczącego").
Kontekst: decyzje [25](25-blueprint-po-dagu-zegara-pifp-cfrplus.md) (pętla
solvera), [29](29-tier-first-fundament-gto-mapa-po-researchu.md) (DBR, prawo
kosztu, szew `_settle()`), [31](31-nauka-nie-komercja-compute-i-pomiar-za-zero.md).

## 0. Koncepcja w jednym akapicie

**Nie ma drugiego algorytmu.** Jest ta sama pętla co dziś — PI-FP + CFR+
wstecz po DAG-u zegara — do której wchodzą trzy wejścia (drzewo, tensor kart,
model przeciwnika) i jedno pokrętło `P_max`. Przy `P_max = 0` pętla liczy
równowagę, czyli dzisiejszy blueprint. Przy `P_max > 0` ta sama pętla liczy
odpowiedź na model pola. **Sieci neuronowej nie ma nigdzie**: „uczenie się"
z 1 mln rąk to liczenie częstości plus mały fit per węzeł, a nie trening.

```
   [A] drzewo gry ──────┐
   [B] tensor kart ─────┼──►  PI-FP + CFR+ po DAG-u zegara  ──► artefakt .bpk
   [C] model pola ──────┘            ▲
                                     │
                              pokrętło P_max
                        0 = równowaga … 1 = czysty best response
```

## 1. Wejście A — drzewo: flat call wchodzi szwem `_settle()`

Dziś `_LEAF_DEFS_3` ma 17 liści, wszystkie fold albo showdown — flat call
(51–60% rąk przy 25 bb) jest **niewyrażalny** (decyzja 29 pkt 2c). Rozszerzenie
nie oznacza liczenia postflopu w pętli. Decyzja 29 pkt 3C nazwała mechanizm:
payload liścia = (wspólny tensor kartowy `base`) @ (maleńkie `payoffs`
z `_settle()`), więc **rozstrzyganie rozegranego pota grą postflop zmienia
wyłącznie alfabet K wspólnego tensora**. Cała złożoność postflopowa idzie
offline.

Prawo kosztu Θ(L·C³·iter) jest liniowe w liczbie **liści**: 17 → 24 liście to
**1,41×**, nie rząd wielkości.

## 2. Wejście B — tensor kart: tu wchodzą reprezentatywne boardy

Alfabet K z punktu 1 to jest właśnie „zestaw boardów jak w Pio". Policzone
(skrypt prototypu w scratchpadzie sesji, nie w repo — wchodzi kontraktem):

| fakt | wartość |
|---|---:|
| wszystkich flopów `C(52,3)` | 22 100 |
| klas strategicznie różnych (izomorfizm kolorów) | **1 755** |
| krotności klas | 4 (299×), 12 (1170×), 24 (286×) |

Rozkład tekstur na pełnym zbiorze — to jest rozkład, który podzbiór ma odtworzyć:

| tekstura | klas | waga | udział |
|---|---:|---:|---:|
| bez pary, two-tone | 858 | 10 296 | 46,59% |
| bez pary, rainbow | 286 | 6 864 | 31,06% |
| para, two-tone | 156 | 1 872 | 8,47% |
| para, rainbow | 156 | 1 872 | 8,47% |
| bez pary, monotone | 286 | 1 144 | 5,18% |
| trips | 13 | 52 | 0,24% |

**Metoda:** cechy strukturalne (rangi, rozpiętość, sparowanie, tonalność,
potencjał strita) → ważony k-means → **medoid** klastra jako reprezentant,
waga = suma wag klastra. Deterministycznie z seeda, jak każdy artefakt tu.

**Pomiar (wzorzec 47: najpierw krzywa, potem próg).** Klastrowanie na cechach
strukturalnych, walidacja na celu **behawioralnym** — rozkład 9 kategorii
układów realnego zakresu na flopie — więc walidacja nie jest okrężna:

| K | błąd L1 | maks. na kategorii | ten sam K losowo |
|---:|---:|---:|---:|
| 13 | 0,0541 | 0,0224 | — |
| 25 | 0,0490 | 0,0237 | 0,0916 |
| **49** | **0,0194** | 0,0091 | 0,0608 |
| 100 | 0,0099 | 0,0034 | — |
| 184 | 0,0062 | 0,0031 | 0,0265 |

Dwa wnioski, oba zmierzone: **klastrowanie jest warte 2–4× wobec losowego
podzbioru tej samej wielkości**, a **49 flopów daje błąd 1,9%** przy 36-krotnej
redukcji z 1755. Kolano krzywej leży między 25 a 49.

> **Czego ten prototyp NIE zrobił.** Walidował na zastępczym zakresie (górne
> 40% klas wg porządku `poker.abstraction`). Kontrakt musi walidować na
> **zakresach, które w tej grze realnie dochodzą do flopa** — czyli na
> zakresach flat-calla z rozwiązanego drzewa, nie na zakresie z półki.
> Liczby wyżej są dowodem, że metoda działa, nie wyborem K.

## 3. Wejście C — model pola z 1 mln rąk

### 3.1. Dlaczego akurat w tej grze dane są czyste

Ogólny problem data miningu: historie dają akcje, ale karty tylko na
showdownie, więc `P(akcja | klasa)` jest obciążone selekcją. **W jam/fold
to się nie dzieje:**

- **zakres jamującego** — karty widać, gdy ktoś sprawdził; sprawdzający nie
  zna kart jamującego, więc selekcja jest niezależna od jego klasy:
  `P(klasa | jam ∧ sprawdzony) = P(klasa | jam)`. **Nieobciążone.**
- **zakres sprawdzającego** — pokazuje karty zawsze, gdy sprawdza.
  **Obserwowane wprost.**
- **zakres pasujący** — nigdy niewidoczny, ale jest dopełnieniem do 1326
  kombinacji przy znanych częstościach. **Wyliczalny.**

Czyli akurat w węzłach, w których ta gra się rozstrzyga, 1 mln rąk daje
zakresy pola niemal dokładnie. To nie jest szczęście — to własność formatu.

### 3.2. Dwa sygnały, jeden fit

- **wszystkie ręce** → częstość akcji w węźle publicznym („SB jamuje 47%
  z 12 bb"). Wiąże **rozmiar** zakresu.
- **ręce z showdownem** → pary (klasa, akcja). Wiążą **kształt** zakresu.

Fit per węzeł: znajdź `σ(akcja | klasa)`, które maksymalizuje wiarygodność
obserwacji showdownowych **przy twardym warunku** zgodności z częstością
zagregowaną. To jest mały problem wypukły na 169 zmiennych, a nie trening.

Do tego licznik `n(I)` — ile obserwacji stoi za każdym infosetem. On jest
całym mechanizmem bezpieczeństwa z punktu 4.

### 3.3. Cztery pytania do operatora, które rozstrzygają, co te dane odblokowują

Koncepcja jest wobec odpowiedzi odporna — maszyneria ta sama. Zmienia się
**która linia dostaje model najpierw**:

1. **Spin & Go czy cash/MTT?** Spin → odblokowuje P-12/P-13 wprost.
   Cash HU → odblokowuje linię HU (i wtedy miernikiem jest benchmark
   z decyzji 31 pkt 4), a blokada Spina z decyzji 29 pkt 6 **zostaje**.
2. **Jakie stawki?** Pole 0,50 $ i 25 $ to dwa różne pola.
3. **Jak stare?** Pole dryfuje; model z pola sprzed lat opisuje tamto pole.
   To jest do **nazwania w metadanych artefaktu**, nie do ukrycia.
4. **Format plików?** Od tego zależy parser w P-10 (`phh` z decyzji 31 jest
   gotowym celem konwersji).

Zakaz z decyzji 29 pkt 6 obowiązuje bez zmian: pola z własnych skryptów nie
wolno raportować jako realnego. Te dane są realne — i dlatego trzeba jawnie
powiedzieć, **jakiego pola** dotyczą.

## 4. Pokrętło — jedyna nowa idea w całej koncepcji

Przeciwnik gra modelem z prawdopodobieństwem `P_conf(I)`, a best response
z `1 − P_conf(I)`:

```
P_conf(I) = P_max · n(I) / (s + n(I))
```

- `n(I) = 0` → `P_conf = 0` → **czysta równowaga**. Bez przypadku szczególnego:
  tam, gdzie nie ma danych, bot gra blueprintem.
- `n(I)` duże → `P_conf → P_max` → eksploatacja tam, gdzie dane są gęste.
- `s` to próg zaufania, `P_max` sufit odchylenia. **Oba z własnej krzywej**
  (wzorzec POKER-47), nie z literatury.

**Bramka, bez której to nie wchodzi** (decyzja 29 pkt 3B): ex-post ε profilu
ograniczonego ≤ ε własnego blueprintu tieru **i** < 1e−3 bezwzględnie. Jeśli
eksploatacja czyni nas bardziej wyzyskiwalnymi, niż bramka dopuszcza — nie
wchodzi. Dwie asercje: prior modelu == blueprint przy `n=0`; `0 < P_max < 1`.

## 5. Kolejność — co po czym, z kosztem

| # | krok | koszt | zależy od |
|---|---|---:|---|
| 1 | Naprawa przyrządu (findingi 5.1, 5.3 audytu) | 0 | — |
| 2 | **P-16** generator podzbioru flopów + bramka błędu na realnych zakresach | 0 rdzenio-h | — |
| 3 | P-10 parser historii + model pola + licznik `n(I)` | 0 | dane operatora |
| 4 | P-14 szew `_settle()` i flat call w drzewie (wymaga rekordu decyzyjnego) | ~5 | P-16 |
| 5 | Tensor osadzenia postflopowego na K flopach, szczebel 0→1→2 | mierzy P-16 | 2, 4 |
| 6 | P-11 DBR w końcówce HU + krzywa `P_max` | ≤2 | 3 |
| 7 | P-13 pełny DBR na T-MODAL, 3 tablice V | 53,5 | 4, 5, 6 |

Bramka STOP z decyzji 29 (P-15) obowiązuje: krok 5 nie rusza bez liczby
z kroku 2.

## 6. Czego ta koncepcja nie zmienia

Algorytmu solvera (PI-FP + CFR+), abstrakcji 169 klas bezstratnych, runtime'u
stdlib, niezmienników INV-P1…P8, zakazu publikacji artefaktu (decyzja 30),
bramki STOP. Nie wprowadza sieci neuronowej ani zależności do pakietu `poker`.
Rozszerzenie drzewa **nadal wymaga własnego rekordu decyzyjnego** (decyzja 27).

## 7. Źródła liczb

- 1755 klas, krotności, rozkład tekstur, tabela błędu K: własne wyliczenie
  z 2026-09-19 na `poker.cards` / `poker.evaluation` / `poker.abstraction`;
  skrypt prototypu w scratchpadzie sesji — do repo wchodzi kontraktem P-16,
  nie tą decyzją.
- Prawo kosztu Θ(L·C³·iter), szew `_settle()`, bramka DBR, wzór `P_conf`:
  [decyzja 29](29-tier-first-fundament-gto-mapa-po-researchu.md) pkt 3B i 3C.
- Koszt P-13 (53,5 rdzenio-h): fixture `tools/blueprint/mode_census.py`,
  pomiar z [decyzji 31](31-nauka-nie-komercja-compute-i-pomiar-za-zero.md) pkt 9.

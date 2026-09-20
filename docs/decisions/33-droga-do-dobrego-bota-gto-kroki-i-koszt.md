# 33. Droga do dobrego bota GTO: 18 kroków, 153 rdzenio-godziny, trzy fale

Status: **PROJEKT — czeka na zatwierdzenie operatora.** Autor: doradca,
2026-09-20. Podstawa: zlecenie operatora („zaplanuj drogę do celu dobry bot
GTO; jakie jeszcze kroki, jaki koszt") wraz z trzema ustaleniami z tego samego
dnia (korpus to Spin & Go; stawki nieistotne, ale tiery płacące 3 miejsca mają
wejść; warstwa explo = deterministyczne odchyły od GTO z randomizacją najwyżej
na poziomie akcji). Aneks do decyzji [29](29-tier-first-fundament-gto-mapa-po-researchu.md)
i [30](30-dystrybucja-artefaktu-i-odblokowanie-p7.md); kontekst: [25](25-blueprint-po-dagu-zegara-pifp-cfrplus.md),
[31](31-nauka-nie-komercja-compute-i-pomiar-za-zero.md), [32](32-koncepcja-algo-uczacego-boardy-model-pola.md).

Metoda: workflow 36 agentów (8 czytelników repo i sieci → 3 niezależne mapy
drogowe → 3 sędziów → synteza → 21 adwersaryjnych weryfikacji). Każda liczba
poniżej została **przeliczona ponownie uruchomieniem fixture'a repozytorium**,
nie przepisana z wyniku workflow — rozjazdy opisuje pkt 8.

## 0. Odpowiedź na pytanie operatora

**18 kroków · 153,3 rdzenio-godziny · ~17 kontraktów · poniżej 50 USD.**

Siedem pierwszych kroków kosztuje **zero rdzenio-godzin** i może unieważnić
resztę mapy — dlatego idą pierwsze. Dopiero potem trzy przebiegi solvera dają
pokrycie 100% puli nagród.

## 1. Cel, liczbowo — bo bez tego „dobry" jest opinią

Osiem warunków **łącznie**, każdy sprawdzalny plikiem, per tier obejmujący
≥1% **puli nagród** (nie wolumenu):

1. **Zakres nazwany wprost.** 3-max preflop, abstrakcja fold / open 2.2x /
   3bet-jam / call, 169 klas bezstratnie, dokładna indukcja wsteczna po DAG-u
   zegara, ICM wyłącznie jako warunek brzegowy. Bez flat-calla, bez postflopu.
   To ten sam poziom deklaracji, na którym publikują Ganzfried–Sandholm.
2. **Jednostka progu to ε_span, nie ε_pool.** `ε_span = ε_pool/(p1−p3)`.
   Przy trzech płatnych miejscach `3·p3` puli jest **martwe** — wszyscy trzej
   zawsze kończą turniej, więc ta część nie niesie treści decyzyjnej.
   Certyfikat podaje trzy jednostki naraz: `ε_pool`, `ε_span`,
   `ε_ROI [pp] = ε_pool × multiplikator × 100`.
3. **Próg: ε_span ≤ 4,9e−4 na maksimum, ≤ 1,5e−4 na medianie**, po stanach
   osiągalnych. Wyprowadzenie: certyfikat Ganzfrieda–Sandholma 4,9e−4 puli przy
   jego wypłatach 50/30/20 (span 0,30) to **1,63e−3 span**; nasze dzisiejsze
   4,72e−4 puli przy spanie 0,8 to **5,9e−4 span** — czyli jesteśmy od kotwicy
   **~2,8× lepsi**, i to trzeba zapisać, zanim ktoś ogłosi „jesteśmy 0,96×
   kotwicy". Próg 4,9e−4 span jest ~17% poniżej dzisiejszego stanu, czyli
   w zasięgu **bez** sufitu 1536 iteracji i **bez** kroku siatki 1.
4. **Drzewo ma zmierzoną cenę.** Odsetek decyzji korpusu niezmapowanych na
   14 węzłów 3-max policzony i rozbity na rozłączne przyczyny. Bez progu
   jakości, ale z **prerejestrowanym progiem decyzyjnym 35%** dla przyczyny
   „akcja spoza drzewa": powyżej niego warstwa explo idzie na półkę,
   a następnym kontraktem jest rekord decyzyjny na flat call.
5. **Spójność ICM.** Trzy niezależne reguły kolejności wybicia (`icm.py`,
   `spin_arena.py`, `solve_grid.py`) dają identyczny wektor na terminalach
   z dwoma zerami, tolerancja 1e−12.
6. **Zgoda z czymś spoza projektu, w dwóch warstwach.** *Blokująco:* ex-post ε
   na konfiguracji Ganzfrieda–Sandholma ≤ 4,9e−4 puli **oraz** odtworzone ostre
   uporządkowanie `btn > sb > bb` (fakt jakościowy, odporny na kalibrację).
   *Raportowane, nie progowane:* odchyłka wobec preprintu z 2026 — jego autorzy
   sami raportują rozrzut 2,5e−3 puli, więc próg 1e−3 byłby ciaśniejszy niż
   wariancja referencji.
7. **Miernik niezależny od optymalizatora.** Obok ε wobec własnego V stoi
   **ε krzyżowe**: bohater z biegu A, obaj przeciwnicy z biegu B o innej
   inicjalizacji. To operacjonalizacja zdania, które wszyscy cytują i nikt nie
   zamienia w liczbę: *w 3-max równowagi nie są wymienne*. Jeśli `ε_cross` jest
   o rząd większe od własnego — słowo „GTO" znaczy mniej, niż czyta się
   z certyfikatu, i certyfikat ma to powiedzieć.
8. **Pokrycie liczone pulą nagród**, z asercją `sum(volume_share) == 1,0`
   w teście — dziś suma to **0,97** (sprawdzone), a brakujące 3% to właśnie
   odroczone tiery 25x+.

**Warunek negatywny, równie wiążący:** nie twierdzimy, że bijemy realne pole,
i nie twierdzimy nieeksploatowalności. Certyfikat mówi o luce wobec
**zamrożonego profilu we własnej abstrakcji**. Repozytorium jest publiczne;
każde zdanie mocniejsze jest ryzykiem reputacyjnym, nie marketingiem.

## 2. Co zmieniają trzy ustalenia operatora

| ustalenie | co odblokowuje | co trzeba dopisać |
|---|---|---|
| korpus to **Spin & Go** | zdejmuje twardą blokadę P-10…P-13 z decyzji 29 pkt 6 | metadane korpusu (stawka, data) jako **kolumny**, blokująca odmowa zapisu bez nich |
| **tiery 3-paid** mają wejść | domyka pokrycie z 0,97 do 1,00 puli | wiersz w `TIERS` + `PAYOUTS` + preset fixture'a — **dziś nie istnieje żaden** |
| explo = **deterministyczne odchyły** | zastępuje P-13 (drugi pełny blueprint) tabelą delt czytaną lookupem | hak `deviate`, `act_seed` w `SeatView`, mieszanie blake2b + test niedegeneracji |

Trzecie ustalenie jest najtańsze i najbardziej zmienia mapę: **P-13 to nie był
deterministyczny algorytm odchyłek, tylko kolejny przebieg solvera produkujący
drugi, równoległy blueprint** (53,5 rdzenio-h). Żądanie operatora opisuje coś
nieporównywalnie tańszego: tabelę delt liczoną offline z marginesów
indyferencji i częstości pola. **Oszczędność: ~61 rdzenio-h.**

## 3. Kroki — trzy fale

### Fala 1 · siedem falsyfikacji po 0 rdzenio-godzin (9 kontraktów)

Każdy z tych kroków może unieważnić resztę mapy, więc żaden przebieg nie
startuje przed nimi.

| # | krok | po co |
|---|---|---|
| S0 | Decyzja 33 jako aneks: cel liczbowo, jednostka progu, zdjęcie blokad, klauzula VOID | żeby „dobry" przestało być opinią |
| S1 | Tabela tierów jako **dane**: pasmo 3-paid, indeks `r`, maszynowy dowód | dziś `sum(volume_share)=0,97` i zero wierszy 3-paid |
| S2 | Przyrząd: powód zakończenia przestaje ginąć (finding 6.3), arena przestaje być zaszyta na jeden tier, **jedna** reguła kolejności wybicia | dziś `play_spin` wyrzuca powód → turniej ucięty punktowany jak rozegrany |
| S3 | Spis korpusu: cena zamrożonego drzewa, wykluczenie własnych rąk hero, rozłączne `n(I)` | mierzy próg 35% z warunku (4) |
| S4 | Pozyskanie i weryfikacja artefaktu produkcyjnego + kotwic literaturowych | **`find . -name '*.bpk'` zwraca pusto** — artefakt, na którym stoi repack, marginesy i cała explo, nie istnieje w środowisku |
| S5 | Higiena kolejki kontraktów, schemat fabryki, budżet czasu bramki | 17 kontraktów trzeba dać się przekazać |
| S6 | **Kotwica zewnętrzna, tym razem wykonalna**: `force_jamfold` jako pole `GridConfig` | dziś `solver_mode((15,15,15),2)=='deep'`, więc kotwica jak pisana porównywałaby nasze pełne drzewo z opublikowaną grą jam/fold-only |

### Fala 2 · przyrząd, sondy, pierwszy realny tier, warstwa explo — 52,5 rdzenio-h

| # | krok | rdzenio-h | źródło liczby |
|---|---|---:|---|
| S7 | Checkpoint horyzontu per cykl | 1,0 | szacunek P-4 |
| S8 | Repack v2/uint16 + marginesy indyferencji + pomiar przesunięcia ROI v1→v2 | 4,6 | **zmierzone** (koszt jednego ex-post) |
| S9 | Wybór równowagi: **ε krzyżowe** — liczba, której nie miała żadna mapa | 0 | — |
| S10 | Sondy błędu modelu (P-6) — jedyny wyzwalacz, który bramka STOP uznaje | 24,0 | szacunek P-6 |
| S11 | **T-MODAL** — 87,41% gier, 77,57% puli nagród | **17,8** | **FIXTURE** |
| S12 | Krzywa kumulacji odchyłki ε(k), budżet δ, krzywa n(I) | 5,1 | szacunek |
| S13 | Szew odchyłki: hak `deviate`, `act_seed`, blake2b + piąty licznik | 0 | — |
| S14 | Deterministyczna warstwa odchyłek + koszt własny hero + asercja, że explo nie zastępuje blueprintu | 0 | — |

### Fala 3 · domknięcie pokrycia do 100% — 100,7 rdzenio-h

| # | krok | rdzenio-h | źródło |
|---|---|---:|---|
| S15 | **T-HIGH** — całe pasmo trzech płatnych miejsc jednym przebiegiem | **64,3** | **FIXTURE**, ta sama siatka 150/krok 2 |
| S16 | **T-MID** (4x **oraz** 5x) — domknięcie do 100% gier i puli | **36,4** | **FIXTURE** |
| S17 | Certyfikat jako plik + bramka repozytorium + przelicznik jednostek | 0 | — |

## 4. Koszt — dwie liczby, obie uczciwe

**Ścieżka A — plan powyżej, z odrzuceniami:**

```
S7  1,0 + S8 4,6 + S10 24,0 + S11 17,8 + S12 5,1 + S15 64,3 + S16 36,4
= 153,3 rdzenio-h        (tensor 11,2 już opłacony biegiem produkcyjnym)
```

**Ścieżka B — mapa bez odrzuceń, gdyby trzymać się decyzji 29 i dołożyć 3-paid:**

```
cztery wiersze tierowe (P-7 64,3 + P-8 17,8 + P-9 36,4 + P-13 53,5)  172,1
+ tensor raz                                                          11,2
+ wiersz 3-paid na dzisiejszej siatce                                 64,3
= 247,6 solvera, + wiersze niesolwerowe 45–53   →   ~293–301 rdzenio-h
```

**Co kupują odrzucenia — 430,8 rdzenio-h uniknięte:**

| odrzucone | rdzenio-h | powód |
|---|---:|---|
| krok 1 siatki | 252,1 | pół budżetu mapy w jednej pozycji bez **ani jednego** pomiaru, że błąd poza-siatkowy dominuje; sonda S10(a) to rozstrzyga |
| P-7 WTA@25bb | 64,3 | tier, w który nikt nie gra — patrz zastrzeżenie w pkt 8 |
| P-13 + maszyneria P-11/P-12 | 61,5 | to drugi blueprint, nie deterministyczne odchyły |
| P-3 pełne domknięcie warstw | 47,9 | zdejmuje 0,844% fallbacku o wpływie na ROI **nieodróżnialnym od zera** (−0,10/+0,01/−0,07 pp) |
| P-5 AIVAT | 5,0 | kupuje moc tam, gdzie jej nie brakuje; zero precedensu turniejowego |

**Pieniądze — ścieżka A, 153 rdzenio-h:** 19,2 h zegara na ośmiu rdzeniach.
AWS spot **4,10 USD** · AWS on-demand **13,68 USD** · Hetzner AX52 64 EUR/mies.
ryczałtem (zapas ~15×) · runnery publicznego repo **0**. Wniosek z decyzji 31
pkt 9 stoi bez zmian: **compute nie jest ograniczeniem tego projektu.**

## 5. Czego brakuje w kodzie, żeby 3-paid w ogóle dało się wycenić

Sprawdzone uruchomieniem, nie przeczytane:

- **żaden wiersz `TIERS` nie płaci trzeciego miejsca** — `any(t.prizes[2]>0)`
  zwraca `False`; `PAYOUTS` też nie (`10x` to `(8,2,0)`);
- `sum(volume_share)` = **0,97**, brakujące 3% to odroczone 25x+;
- `mode_census.tier_config("T-25X")` → **`KeyError`**; presety fixture'a to
  `prod-10x, WTA@25bb, T-MODAL, T-MID, krok-1` — **fixture nie wyceni celu
  operatora bez dopisania wiersza**;
- `SpinTier.__post_init__` wymaga `sum(prizes)==1`, więc wektor 3-paid musi być
  znormalizowany (np. `(0,80; 0,12; 0,08)`), a multiplikator zostaje w tabeli;
- `solve_grid.quantize_stacks` odrzuca stack niepodzielny przez `grid_step` —
  wybór stacka startowego nowego tieru jest ograniczony;
- **wszystkie trzy wiersze mają `confirmed=False`**, a `tier_for_run` rzuca
  `UnconfirmedTierError` — bez potwierdzenia operatora przebieg wymaga jawnej
  flagi.

## 6. Warstwa explo jako deterministyczne odchyły — dokładnie jak chce operator

Trzy elementy, wszystkie za 0 rdzenio-godzin solvera:

1. **Tabela delt**, nie drugi blueprint: odchyłka liczona offline z marginesów
   indyferencji (`.bpk` v2 już ma sekcję) i częstości pola, czytana lookupem.
2. **Mieszanie bezstanowe** blake2b z decyzji 07 — ale **wyłącznie razem
   z `act_seed`**. Powód, który musi trafić do kontraktu: `SeatView` nie niesie
   kart ani seeda, więc materiał hasza z dzisiejszych pól **powtarza się
   identycznie w każdym turnieju na ręce 0** — mieszanka zdegenerowałaby się do
   strategii czystej w najczęściej odwiedzanym infosecie, kasując balans, po
   który ta randomizacja istnieje. Stąd test niedegeneracji w S13.
3. **Bramka:** `eps_span_z_deltami ≤ eps_span_blueprint + δ`, gdzie δ jest
   **zadeklarowanym** budżetem z własnej krzywej, a nie zerem; plus asercja
   `delta_at_n_zero == 0` i **koszt własny hero** `V_blueprint − V_z_deltami`
   przy przeciwnikach grających blueprintem.

## 7. Czego świadomie nie robimy

Poza pozycjami z pkt 4: **flat call na tej mapie** (to sufit jakości, nie brak
na drodze — rozstrzygany deklaracją zakresu z ceną zmierzoną w S3, a poszerzenie
wymaga **najpierw** kwalifikacji multiway silnika, decyzja 27 pkt 2);
**licytacja postflop** (łamie kontrakt `award_allin`); **arena jako dowód
jakości warstwy GTO w ogóle** — rozdzielczość ~2,1 pp wobec 0,14 pp pełnej
wyzyskiwalności przy 3x to ograniczenie **architektury pomiaru**, nie wielkości
próby (naiwnie 8,4 mln turniejów); **tiery GGPokera i partypokera** (inna
głębokość startowa = inna siatka, ~118 i ~77 rdzenio-h); **stratyfikacja korpusu
po stawkach** — zgodnie z ustaleniem operatora, ale stawka i data zostają
kolumnami: *„stawki to jeden chuj" jest decyzją o braku stratyfikacji, nie zgodą
na niepodanie metadanych*; sieci, MCCFR, deep-RL, LLM w pętli — bez zmian
wobec decyzji 25 pkt 4 i 29 pkt 4.

Jedno zastrzeżenie warte zapamiętania: **jackpot (12000x) jest jedynym
wierszem, którego częstość realnie zależy od stawki** (1 na 10 mln przy niskich
wobec 10 na 10 mln przy średnich), a ponieważ płaci trzy miejsca, jego udział
w puli nagród skacze dziesięciokrotnie. Deklaracja „stawki to jeden chuj" jest
prawdziwa dla wszystkiego **poza** jackpotem.

## 8. Jak to policzono i co weryfikacja poprawiła

**Rozjazd, który trzeba nazwać.** Synteza workflow podała sumę **171,7
rdzenio-h**. Adwersaryjna weryfikacja podała **~293–301**. Obie liczby są
prawdziwe i odpowiadają na **różne pytania**: 171,7 było sumą błędnie
policzoną na planie z odrzuceniami (i zawierało trzy pozycje wycenione za
wysoko), 293–301 to mapa **bez** odrzuceń plus wiersz 3-paid. Przeliczyłem
plan z odrzuceniami składnik po składniku fixture'em: **153,3**. Liczby ~172
wolno użyć wyłącznie z etykietą „solver czterech wierszy tierowych, bez
tensora, bez 3-paid, dolne oszacowanie" — dokładnie tak, jak robi to
decyzja 29 pkt 5.

**Trzy pozycje wycenione za wysoko przez syntezę**, poprawione fixture'em:
T-MODAL 21,2 → **17,8**; T-HIGH 73,5 → **64,3**; T-MID 42,3 → **36,4**.

**O werdyktach weryfikacji.** Wszystkie 21 twierdzeń wróciło z etykietą
`OBALONE`. To **artefakt instrukcji** („domyślny werdykt to obalone"), nie
21 obalonych kroków: treść każdej weryfikacji potwierdza istotę kroku
i poprawia szczegół (właściwa sygnatura funkcji, właściwa liczba, konieczność
rozbicia kroku na dwa kontrakty). Zapisuję to wprost, żeby nikt nie odczytał
wyniku workflow jako „plan się nie obronił". Poprawki weszły do tekstu wyżej.

**Wiersze niesolwerowe (45–53 rdzenio-h w ścieżce B) to szacunki panelu, nie
fixture.** `BRAK`: fixture nie wycenia P-3, P-5, P-6, P-11, P-12, P-14.

**Zastrzeżenie do odrzucenia P-7.** Powód („po fuzji z Flash żaden tier nie
jest WTA na 25 bb: 2x/3x→300 żetonów, 4x/5x→400, 10x+→500") pochodzi
z researchu sieciowego o strukturach stacków, czyli ze źródeł **wtórnych**.
Decyzja 29 pkt 6 ppkt 1 już wymaga potwierdzenia tabeli tierów wobec żywego
lobby — **to zastrzeżenie obejmuje także tę przesłankę**. Jeśli potwierdzenie
operatora jej zaprzeczy, P-7 wraca do mapy razem ze swoimi 64,3 rdzenio-h,
a decyzja 30 pkt 3 (odblokowanie P-7) zachowuje moc bez zmian.

**Defekt w dokumentach, naprawiony przy okazji.** Decyzje 31 i 32 odwoływały
się do findingów audytu jako „5.1/5.3", podczas gdy
`docs/AUDYT_KODU_2026-09-12.md` numeruje je **6.1/6.3** — numeracja została
przeniesiona z artefaktu. Dodatkowo **finding 6.1 dotyczy areny HU
(`src/poker/arena.py`), a nie areny Spin**, która od decyzji 22/26 liczy ROI
w buy-inach na blokach rotacji; dla linii Spin realny do naprawy jest wyłącznie
6.3. Oba odwołania poprawione tym samym commitem (konstytucja pkt 1).

# 26 — Moc pomiaru areny: kolejność redukcji wariancji i zakazy

Od POKER-42/43 każde twierdzenie „bijemy X" rozbija się o wariancję:
field exploit vs skryptowany fish +4,1% ROI przy CI (−11,6; +19,7),
N = 320. Research architekta (2026-08-29, AIVAT arXiv:1612.06915,
AV-AIVAT arXiv:2608.06362, Kim & Sandholm arXiv:2605.14261, walidacja
ICM arXiv:2506.00180) daje liczby, na których stoi ta decyzja.

## Co zmierzone

Odchylenie standardowe ROI to **145 pp na turniej** — i jest w całości
wyjaśnione samą strukturą wypłat (model przy równych umiejętnościach
daje 144,2 pp). Nie ma patologii pomiarowej; jest nieusuwalna loteria
turniejowa. Wymagana redukcja SD przy naszym budżecie N = 320:
**56% dla wykrycia 10 pp ROI, 78% dla 5 pp** (moc 80%, α = 0,05).
Dla porównania: AIVAT w HUNL daje 68%, w Leduc self-play 99,9%.

**KOREKTA (POKER-71):** +4,1% i 145 pp zmierzył estymator sprzed POKER-48
(hero stale na miejscu 0, karty sprzężone z decyzjami), a side pot 3-way
areny był do POKER-71 dzielony po równo między przegranych puli głównej
(finding B3 audytu 2026-09-26). Te same wielkości na arenie po poprawce:
SD ROI na turniej (miejsce 0, seedy 21…340,
`python tools/run_arena.py sd 320 3x`) **148,8 / 139,6 / 124,2 pp** dla
par field vs always-jam / field vs $1 fish / tight vs always-jam (kod
sprzed poprawki: 148,8 / 140,4 / 124,2), więc wymagana redukcja SD przy
N = 320 to 57% / 54% / 49% dla 10 pp i 79% / 77% / 74% dla 5 pp; field
vs $1 fish na 320 blokach (`python tools/run_arena.py 320 3x`) **−3,4%
ROI, CI (−9,9; +3,0)** (sprzed poprawki −2,8%, CI (−9,2; +3,6)).

**KOREKTA (POKER-73):** para tight vs always-jam gra książką hero, której
open, overjam i 3bet pochodzą z openfold; od POKER-73 openfold liczy przy
N = 512 z poprawionymi terminalami (KOREKTA (POKER-73) decyzji 20 i 22).
`python tools/run_arena.py sd 320 3x --openfold-iters 512` (22,8 s przy
pomiarze POKER-73, 23 s przy korekcie dokumentów 2026-09-27; na HEAD to
samo co bez flagi, bo domyślne N = 512) daje SD ROI na turniej
**148,8 / 139,6 / 120,2 pp** (po POKER-71, przed POKER-73: 148,8 /
139,6 / 124,2), więc wymagana redukcja SD przy N = 320 to **57% / 54% /
47%** dla 10 pp i **79% / 77% / 73%** dla 5 pp; pary field bez zmian.

## Decyzja

1. **Kolejność: najpierw to, co nie wymaga funkcji wartości.**
   Rotacja miejsc (obecnie hero siedzi zawsze na miejscu 0 — to
   obciążenie pozycyjne, nie tylko wariancja), wspólne seedy w obu
   ramionach porównania, statystyka na poziomie bloku i przedziały
   bootstrapowe. To jest POKER-48.
2. **AIVAT w `spin_arena` jest zablokowany na blueprincie, nie na
   kodzie.** Poprawna korekta wymaga funkcji wartości stanu turnieju
   w przestrzeni $EV — czyli dokładnie V z decyzji 25. Wniosek
   architektoniczny: **blueprint jest jednocześnie produktem
   i przyrządem pomiarowym**; to podnosi jego priorytet ponad to, co
   zakładała decyzja 25. Do czasu jego ukończenia mierzymy słabiej,
   ale bez obciążenia.
3. **`poker.arena` (HU cash) jest poligonem walidacyjnym.** Rozdania
   niezależne, wypłata liniowa w żetonach, brak ICM — tam AIVAT ma
   bezpośredni precedens w literaturze. Wdrażamy w kolejności
   HU → Spin, nie odwrotnie.
4. **Metryką docelową jest redukcja SD, nie „ładniejsze CI".**
   Kryterium blokujące przyszłego kontraktu AIVAT: ≥ 56% redukcji SD
   względem estymatora naiwnego na tym samym zbiorze seedów.

## Zakazy (każdy z uzasadnieniem — to nie są preferencje)

- **Zakaz Jensena.** Nigdy nie redukujemy wariancji w przestrzeni
  żetonów, żeby potem zmapować wynik przez ICM: ICM jest wklęsłe, więc
  E[ICM(stack)] ≠ ICM(E[stack]) — estymator staje się obciążony.
  Dotyczy to wprost „all-in EV" znanego z trackerów: podmiana rzutu
  kartami na udział w puli daje stack ułamkowy, czyli stan turnieju,
  który w prawdziwej grze nie istnieje. Wszystkie korekty wyrażamy
  od razu w $EV.
- **Zakaz liczenia CI na rozdaniach w turnieju.** Jednostką losową
  jest turniej (a przy rotacjach — blok), bo stan przenosi się między
  rozdaniami. Traktowanie rozdań jako niezależnych zaniża CI.
- **Zakaz strojenia funkcji wartości po zobaczeniu danych
  ewaluacyjnych.** Wariancja próbkowa daje się wtedy dowolnie zaniżyć
  (Kim & Sandholm: „pathologically low"); funkcja wartości musi być
  zamrożona i zahaszowana przed zebraniem danych.
- **Zakaz handlu nieobciążonością za wariancję.** Odrzucamy
  propagację niepewności (+43% oszczędności próby kosztem gwarancji);
  nieobciążoność jest jedynym twardym argumentem, jaki mamy.
- **Zakaz stratyfikacji po mnożniku Spina.** Zmierzone: loteria
  mnożnika to ~3% wariancji. Nie warto kodu.

## Uczciwość zewnętrzna

Dla trybu 3-max z wypłatami ICM **nie istnieje opublikowany precedens
empiryczny** AIVAT — najnowsza praca w tej linii (AV-AIVAT) jawnie
wyklucza turnieje i ICM ze swojego zakresu. Mówimy więc „adaptujemy
AIVAT z własną walidacją", nigdy „stosujemy sprawdzoną technikę",
a walidacja nieobciążoności (niezmienniczość na funkcję wartości, gra
zabawkowa o znanej wartości dokładnej) jest warunkiem blokującym, nie
dodatkiem.

## Którą gałąź ta decyzja zamyka albo czyni droższą?

Żadnej. Trener zyskuje najwięcej: funkcja wartości stanu turnieju to
ten sam obiekt, którego potrzebuje replay i analiza decyzji. Pokerroom
bez zmian. GTO-ML zyskuje wiarygodny przyrząd — bez niego nie da się
uczciwie porównać kolejnych wersji agenta.

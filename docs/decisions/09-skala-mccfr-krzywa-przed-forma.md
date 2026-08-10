# Decyzja 09 — Skala MCCFR: sprzeciw uznany, krzywa jakość-vs-skala przed wyborem formy artefaktu

Status: obowiązuje · 2026-08-10 · decyzja architekta w ramach mandatu
autonomii operatora; rozstrzyga `OBJECTION: CONFLICT` zgłoszony przez
kodera wobec kontraktu POKER-24

## Sprzeciw uznany

Kryteria POKER-24 były wewnętrznie sprzeczne: pkt 2 wymagał artefaktu
z co najmniej 50 000 iteracji, pkt 4 — bramki „w rzędzie kilkunastu
sekund". Weryfikacja niezależna (architekt, reprodukcja na czystym
worktree) potwierdza niespełnialność łączną i koryguje liczby kodera:

- wzrost liczby infosetów nie jest potęgą o stałym wykładniku —
  0,65 obowiązuje do ~2000 iteracji, dalej spada do ~0,45; przy
  50 000 iteracji realny zakres to **110–145 tys. infosetów**
  (~18–22 MB), a nie 268 tys.; twardy sufit przestrzeni infosetów
  przy abstrakcji c2a wynosi 317 048;
- artefakt tej wielkości podnosi bramkę z 22,7 s do 56,7 s (ciepła);
- dominującym kosztem jest `pytest`, nie `mypy`: testy architektury
  parsują wygenerowany moduł pięciokrotnie (`ast.parse` bez pamięci
  wyniku). Memoizacja tego parsowania zbija bramkę **dzisiejszego**
  repozytorium z 22,7 s do 16,1 s i jest wartościowa niezależnie od
  skali — ale przy artefakcie kontraktowej wielkości nie wystarcza
  (32 s ciepła, 93 s zimna), bo jednego parsowania i importu usunąć
  się nie da.

Wina leży po stronie kontraktu, nie wykonania: kryterium ilościowe
zostało wpisane bez oszacowania budżetu bramki. To druga instancja tej
klasy (pierwsza: F1 audytu POKER-19); mechanizacja — wpis w PUŁAPKACH
pamięci ról, trzecia instancja oznacza `BLOCKED` (reguła 7).

## Decyzja

1. **Kryterium ≥50 000 iteracji zostaje wycofane.** POKER-24 zamyka
   się jako dostarczony częściowo: wznowienia deterministyczne
   i wydajność (1,52× potwierdzone niezależnie) wchodzą do produktu,
   reszta nie obowiązuje.
2. **Zanim wybierzemy formę artefaktu — mierzymy, czy skala cokolwiek
   kupuje.** Kolejny kontrakt (POKER-27) wyznacza **krzywą
   jakość-vs-skala**: artefakty z rosnących skal (rzędu 1k, 2k, 4k,
   8k, 16k iteracji) trenowane i mierzone **poza repozytorium**, przy
   mocy areny podniesionej tak, by rozdzielać różnice rzędu 50 BB/100.
   Repozytorium nie zmienia artefaktu ani abstrakcji.
3. **Wybór formy artefaktu jest odroczony** do wyniku krzywej, z jawną
   listą opcji i warunkami z panelu doradczego:
   - *przycięcie progiem odwiedzin* — dopuszczalne wyłącznie z progiem
     jawnym w pochodzeniu i z ramieniem kontrolnym „pusta tabela"
     w pomiarze, inaczej kupuje lepszą liczbę zamiast lepszej
     strategii;
   - *inna forma artefaktu* (zasób pakietowy zamiast modułu) —
     wymaga **uprzedniej jawnej zmiany brzmienia INV-P1** wraz
     z zaostrzeniem testu „silnik nie wykonuje I/O"; bez tego byłoby
     cichym obejściem niezmiennika, na co nie ma zgody;
   - *grubsza abstrakcja* — tylko jako cięcie zbioru akcji (mniej
     kubełków nie daje oszczędności), z podbiciem `ABSTRACTION_VERSION`
     i ponownym pomiarem, osobnym kontraktem.
4. **Jeśli krzywa jest płaska** (jakość nie rośnie ze skalą w mierzalny
   sposób), skala nie jest kupowana wcale: metoda c2 dostaje wtedy
   nową kwalifikację (np. inna rodzina algorytmu albo powrót do
   klasycznego solvera push/fold odłożonego w decyzji 04), a nie
   kolejny kontrakt na większy artefakt.
5. **Pomiar rozstrzygający wobec decyzji 07 pkt 6** wykonuje POKER-27
   przy podniesionej mocy — na artefakcie obecnym w repo oraz na
   najlepszym artefakcie z krzywej. Dotychczasowy pomiar (20 par)
   jest za słaby, by cokolwiek rozstrzygnąć, i tak został opisany
   w `CURRENT_STATE.md`.

## Którą gałąź (pokerroom / trener / GTO-ML) ta decyzja zamyka albo czyni droższą?

Żadnej nie zamyka. **GTO-ML**: droga zostaje, ale kolejność jest teraz
uczciwa — najpierw dowód, że skala kupuje jakość, potem koszt formy
artefaktu; ryzyko, że krzywa okaże się płaska, jest wkalkulowane i ma
przygotowaną odpowiedź (pkt 4). **Pokerroom**: neutralna —
odroczenie formy artefaktu chroni go przed podrożeniem (pakiet
produktu pozostaje lekki i bez I/O przy odczycie). **Trener**: tanieje
— krzywa jakość-vs-skala i pomiary o wyższej mocy to gotowy materiał
analityczny.

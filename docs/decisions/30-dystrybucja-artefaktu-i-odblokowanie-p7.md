# 30. Dystrybucja artefaktu: tożsamość zamiast pliku; odblokowanie P-7 bez tabeli tierów

Status: obowiązuje. Autor: architekt, 2026-09-07.
Podstawa: delegacja operatora („podejmij najlepszą decyzję", 2026-09-07)
wobec dwóch pozycji jawnie zostawionych jemu w
[decyzji 25](25-blueprint-po-dagu-zegara-pifp-cfrplus.md) pkt 6
(dystrybucja artefaktu) i
[decyzji 29](29-tier-first-fundament-gto-mapa-po-researchu.md) pkt 6
(potwierdzenie tabeli tierów).

## 1. Fakt, który rozstrzyga sprawę dystrybucji: repozytorium jest PUBLICZNE

`mcz91/Poker` ma `visibility: public` (sprawdzone przez API 2026-09-07).
Każda forma „przekazania artefaktu przez repozytorium" — release, LFS,
gałąź z plikiem — jest **publikacją w internecie**, nieodwracalną:
opublikowanego pliku nie da się cofnąć, bo zdąży zostać skopiowany.

Bilans dla opcji „artefakt w release":

- **korzyść**: jedna drużyna oszczędza ~20 h ściennych regeneracji;
- **koszt**: trwałe ujawnienie strategii produktu, w tym przyszłych
  profili eksploatacyjnych, których **wyzyskiwalność jest z definicji
  wyższa niż blueprintu** (DBR odchyla od równowagi w mierzalny sposób —
  decyzja 29 pkt 3B). Ujawniony blueprint kosztuje niewiele (ε = 0,14 pp
  ROI przy 3×), ujawniony profil DBR kosztuje dokładnie tyle, ile jest
  wart.

Korzyść jest jednorazowa i mała, koszt trwały i rosnący. **Artefakt nie
wchodzi do publicznej dystrybucji.**

## 2. Co wchodzi zamiast artefaktu: manifest tożsamości

`tools/blueprint/control/prod_identity.json` — sha256, rozmiar w bajtach
i pochodzenie **32 plików** artefaktu produkcyjnego (tensor, 21 warstw,
brzeg, raporty, `blueprint.bpk` v1 i `blueprint_v2.bpk`), razem
119 566 611 B opisanych w kilku kilobajtach tekstu, plus `config_hash`
biegu i konfiguracja.

To nie jest namiastka artefaktu — to rozwiązanie problemu, którego sam
artefakt by nie rozwiązał. PUŁAPKA POKER-24 mówi: *regeneracja artefaktu
unieważnia pomiary przy nim, a bramka tego nie łapie*. Z manifestem
tożsamości drużyna, która zregeneruje artefakt komendami AC–AH/BA/BN,
**udowadnia zgodność sha256 i zachowuje wszystkie pomiary** (ε, ROI
areny, liczniki fallbacku, koszty). Bez manifestu musiałaby powtórzyć
pomiary za kolejne godziny — nawet gdyby regeneracja była bit w bit
poprawna.

Warunek, który to umożliwia, został wypracowany wcześniej i jest pod
testem: pakowanie jest deterministyczne bajt w bajt (POKER-51, POKER-57),
a bieg siatki wznawialny bez zmiany wyniku (POKER-50).

Przekazanie samego pliku artefaktu kanałem prywatnym (dysk operatora,
przekaz bezpośredni) pozostaje możliwe i **nie wymaga zmiany tej
decyzji** — zakazana jest publikacja, nie przekazanie.

**KOREKTA (POKER-75):** zgodności sha256 po regeneracji nie dało się
udowodnić z konstrukcji (finding B5 audytu 2026-09-26). Manifesty biegu
niosą pola ulotne — ścieżki bezwzględne, model CPU, czasy ścienne, liczbę
procesów — a konwerter wkładał do metadanych `.bpk` cały manifest biegu
i sha256 surowego `solve_manifest.json`, więc dwie bezbłędne regeneracje
różniły się zawsze w 4–5 z 32 pozycji, w tym w obu plikach `.bpk`.
Determinizm pakowania z POKER-51/57 dotyczył tego samego katalogu biegu,
nie regeneracji. Obecny mechanizm (`python tools/blueprint/identity.py
--run KATALOG`): tożsamością `solve_manifest.json`, `rollout_manifest.json`
i `eps_decomposition.json` jest sha256 ich kanonicznej projekcji bez pól
ulotnych, każdego innego pliku — sha256 pliku. Metadane `.bpk` niosą tę samą
projekcję manifestu biegu, a pełny przepis pochodzenia (z modelem CPU
i czasami) zostaje w `solve_manifest.json` obok artefaktu — świadome
zawężenie kryterium 1 POKER-51.

- **Potwierdza:** dwie regeneracje tym samym kodem na jednej maszynie,
  w różnych katalogach i przy różnej liczbie procesów, dają tę samą
  tożsamość każdej pozycji i bajt w bajt te same pliki `.bpk` (test w bramce
  na łańcuchu kontrolnym: 13 pozycji, od tensora do `.bpk` v1 i v2). Wersje
  python i numpy należą do tożsamości (numpy przypięty w `pyproject.toml`).
- **Nie potwierdza:** (1) zgodności między maszynami — model CPU jest poza
  tożsamością, ale bramka sprawdza jedną maszynę, a łańcuch kontrolny
  porównuje liczby solvera z tolerancją na arytmetykę f32; rozjazd po
  regeneracji na innym CPU wymusza powtórzenie pomiarów, nie dowodzi błędu
  kodu; (2) artefaktu opisanego wyżej — 29 z 32 pozycji opisywało artefakt,
  którego obecny kod nie produkuje (bieg `grid2/` liczony brzegiem horyzontu
  sprzed POKER-74 i oba pliki `.bpk` spakowane z niego z metadanymi sprzed
  POKER-75; wpis `blueprint.bpk` 19 016 752 B pochodził wręcz sprzed
  POKER-56), a `rollout_manifest.json` powstał z niezmienionego kodu tensora,
  lecz jego tożsamością jest od POKER-75 sha256 projekcji, której dla pliku
  produkcyjnego (poza repozytorium) nie policzono. Te 30 pozycji ma więc
  w `prod_identity.json` status „do przeliczenia” bez sha, a pomiary przy
  artefakcie są unieważnione do regeneracji operatora (decyzja 31 pkt 3).
  Sha zostaje wyłącznie przy dwóch plikach `npz` tensora; „119 566 611 B”
  opisuje artefakt sprzed korekty.

## 3. Odblokowanie P-7 (WTA@25bb) bez potwierdzenia tabeli tierów

Decyzja 29 pkt 6 wiązała potwierdzenie tabeli tierów z P-7 **i** P-8.
Rozdzielam te dwa przypadki, bo zależą od różnych rzeczy:

- **P-8 (T-MODAL)** bierze z tabeli **stack startowy 90 żetonów
  i zegar** — bez potwierdzenia liczby te są zgadywaniem ze źródeł
  wtórnych. **Pozostaje zablokowane.**
- **P-7 (WTA@25bb)** nie bierze z tabeli **nic**: uruchamia dzisiejszą
  konfigurację (150 żetonów, ten sam zegar, ten sam tensor) ze zmienionym
  wyłącznie wektorem wypłat na (1, 0, 0). Winner-take-all nie jest
  spornym faktem z tabeli — to definicja formatu dla niskich
  mnożników. **Odblokowane.**

Dodatkowy powód, by nie trzymać P-7 za bramką operatorską: kontrakt
niesie **prerejestrowany kill-check** (krzywa V vs ICM przy WTA). Jeśli
dywergencja przy (1,0,0) okaże się mała, cała teza tierowa traci
uzasadnienie i mapa przesuwa się z przebiegów blueprintowych na drzewo
i eksploatację. To najtańsza dostępna falsyfikacja kierunku — trzymanie
jej za bramką, której P-7 merytorycznie nie potrzebuje, opóźnia
wyłącznie moment, w którym moglibyśmy się dowiedzieć, że się mylimy.

Zależności techniczne P-7 (POKER-54, 55 zamknięte; 58 i 59 przed
przebiegiem) obowiązują bez zmian.

## 4. Czego ta decyzja nie robi

Nie zmienia decyzji 25 pkt 6 (artefakt nadal poza historią gita — teraz
z podanym powodem i z tożsamością w zamian). Nie zmienia zakazu twierdzeń
z decyzji 26/29. Nie przesądza o przyszłej dystrybucji profili
eksploatacyjnych — te są objęte tym samym zakazem publikacji, mocniej.
Nie zwalnia P-8 ani dalszych przebiegów tierowych z potwierdzenia tabeli
przez operatora.

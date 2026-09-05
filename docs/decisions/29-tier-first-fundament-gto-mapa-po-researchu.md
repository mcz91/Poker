# 29. Fundament GTO po głębokim researchu: rodzina blueprintów per tier, warstwa DBR, bramka STOP

Status: obowiązuje. Autor: architekt, 2026-09-05.
Podstawa: workflow badawczy z weryfikacją adwersaryjną (7 kierunków źródeł
pierwotnych, sceptyk per kierunek, panel 3 projektów, 3 sędziów, synteza —
pełny raport w scratchpadzie sesji architekta `research/synteza.md`; ta
decyzja streszcza to, co WIĄŻE). Kontekst: decyzje
[25](25-blueprint-po-dagu-zegara-pifp-cfrplus.md),
[26](26-moc-pomiaru-areny-redukcja-wariancji.md),
[27](27-rozgrywacz-spin-arena-duplikacja-pod-straza.md),
[28](28-adjudykacja-objection-poker52-rozjazdy-areny.md).
Zlecenie operatora: „badaj głęboko, stwórz optymalny algorytm jako
podstawa GTO. Aim high".

## 1. Odkrycie centralne: policzyliśmy niewłaściwą grę

Artefakt produkcyjny POKER-50 rozwiązuje wypłaty (0,8, 0,2, 0) — kształt
multiplikatora 10x, ~1% realnych turniejów — na stacku 25 bb. Modalny
turniej Spin (2x/3x/4x, ~96,5% gier wg tabeli rozkładu multiplikatorów
zweryfikowanej w researchu) to **winner-take-all na 15–20 bb**. To nie jest
przeskalowanie: zweryfikowano na naszym `poker.icm`, że przy (1,0,0)
Malmuth-Harville degeneruje się do liniowego udziału w stacku, a przy
(0,8, 0,2, 0) stack 2 żetonów niesie +88% equity ponad udział — inna gra.
Naprawa to URUCHOMIENIE, nie przepisanie: `GridConfig` już parametryzuje
`prizes`, `total_chips`, `start_stacks`; siatka 90 żetonów krokiem 2 ma
1 078 stanów/warstwę (0,37× dzisiejszych 2 923; formuła (u+1)(u+2)/2−3
potwierdzona na 2 923 / 11 473 / 1 078).

Tabela tierów (multiplikator → stack startowy, długość poziomu, kształt
wypłat) pochodzi ze źródeł wtórnych i JEST wejściem operatorskim:
**operator potwierdza ją wobec żywego lobby przed pierwszym przebiegiem
tierowym** (format był raz restrukturyzowany — fuzja Flash 2025).

## 2. Werdykt o obecnej linii: słuszna i NASYCONA

Architektura zostaje w całości (dokładny DAG zegara, 169 klas bezstratnie,
PI-FP + CFR+ z uśrednianiem ważonym reach, f32, odtwarzalność bajt w bajt,
runtime stdlib). Nasycenie ma trzy niezależne dowody:

a) **Prawo przeliczenia** (z `expost.py:136,155` — ε jest w jednostkach
   SUMY WEKTORA WYPŁAT, nie „puli pota"): ROI [pp] = ε × multiplikator
   × 100. Pełna wyzyskiwalność blueprintu 4,72e−4 = **0,14 pp ROI przy
   3x**, wobec połowy szerokości CI areny 1,46 pp (10×) i wpływu samej
   reguły awaryjnej 4,22 pp (30×). Antywzorzec do utrwalenia: zejście
   tolerancji do podłogi f32 kosztuje ~3 900 rdzenio-h i jest warte
   0,0004 pp ROI.
b) **Błąd modelu > błąd solvera**: szum MC tensora (SE ~4,1e−3 na
   prawdopodobieństwo), kwantyzacja uint8 (2,6e−3), błąd kroku siatki
   (niezmierzony) — wszystkie 5–9× większe od ε i wszystkie niewidoczne
   dla metryki. Wycena: kontrakt sond (P-6).
c) **Twardy sufit = zamrożone drzewo**: `_LEAF_DEFS_3` ma 17 liści,
   wszystkie fold/showdown — flat call (~51–60% rąk przy 25 bb wg
   zweryfikowanego researchu) jest niewyrażalny. Pluribus używa TEJ SAMEJ
   bezstratnej abstrakcji 169 klas preflop przy BOGATSZEJ abstrakcji
   akcji — nasze drzewo jest grubsze, nie cieńsze.

## 3. Wybrany fundament GTO

**A. Rodzina blueprintów per tier** (multiplikator ujawniony przed
pierwszą ręką → wybór artefaktu jest lookupem, zero kosztu w runtime):
T-MODAL (2x/3x, 90 żetonów, WTA, ~87% gier), T-MID (4x, 120, WTA, ~9%),
T-DEEP (dzisiejszy artefakt 10x). Pułapka normalizacji: multiplikator
żyje w tabeli tierów, NIGDY w wektorze wypłat; `GridConfig` dostaje
`assert sum(prizes) == 1.0` (dziś `PAYOUTS["3x"] = (3,0,0)` po cichu
dzieliłoby ε przez 3 — sprawdzone w kodzie).

**B. Warstwa eksploatacyjna: seat-restricted Data-Biased Response,
offline**, wewnątrz istniejącej pętli PI-FP (miks czystego BR z modelem
populacyjnym wagą P_conf(I) = P_max · n/(s+n); n=0 → gra równowagi).
RNR odrzucone (przy małych próbach gorsze w obie strony; na danych
z self-play bezużyteczne — DBR działa). Dyscyplina HU-FIRST: maszyneria
budowana i walidowana najpierw w końcówce HU (rzeczywiście dwuosobowej
o stałej sumie, gdzie twierdzenie DBR obowiązuje, koszt ≈0); w trybach
3-osobowych DBR jest heurystycznym regularyzatorem, którego jedynym
uzasadnieniem jest zmierzona bramka: **ex-post ε profilu ograniczonego
≤ ε własnego blueprintu tieru i < 1e−3 bezwzględnie**. Artefakt DBR
niesie TRZY indeksowane hero tablice V (nigdy zmiksowaną); V z DBR nie
zasila AIVAT. Dwie bramki z zmierzonych katastrof literatury:
prior modelu == blueprint (asercja); 0 < P_max < 1, próg z WŁASNEJ
krzywej (wzorzec POKER-47).

**C. Prawo kosztu i szew `_settle()`** (do dokumentacji niezależnie od
budowy gałęzi flat-call): koszt gry etapowej ≈ Θ(L·C³·iter) — liniowy
w liczbie LIŚCI (arytmetyka skaluje 17→24 = 1,41×, strumieniowanie
9→14 = 1,56×, budżet poszerzenia drzewa 1,6–1,8× na `deep`); payload
liścia = (wspólny kartowy `base`) @ (maleńkie `payoffs` z `_settle()`),
więc rozstrzyganie rozegranego pota grą postflop zmienia TYLKO alfabet
K wspólnego tensora — cała złożoność postflopowa idzie offline, jak
tensor rolloutów. Zamienia to wycenę ~3e5 rdzenio-h na jednorazowy
tensor osadzenia (drabina wierności 0/1/2; szczebel 1 = checkdown,
znany jednokierunkowy błąd — wzorzec HRC).

## 4. Jawnie odrzucone (obalenia z weryfikacji adwersaryjnej)

PED/FP-PED (robi więcej pracy niż FP; publikowane wyniki gorsze niż nasze
PI-FP już osiąga); „FP bije CFR wieloosobowo" jako reguła (tylko
waniliowy CFR, gry 20–24 infosetów); inicjalizacja maximin (efekt
selekcji best-of-5); regret transfer/warm start między stanami (liczby
dotyczą 2p0s CFR/RM, jedyny izolowany pomiar zerowy); migracja końcówki
HU na PCFR+/DCFR (cała końcówka = 0,029 rdzenio-h, zero stanów nad
tolerancją); ε-safe equilibrium; certyfikat polimatrycowy (ogranicza
inną wielkość); online portfolio/bandyci (26 anonimowych decyzji na
turniej); BBR/Thompson; sieci neuronowe/MCCFR/deep-RL/LLM w pętli;
search w czasie rzeczywistym w produkcie (stdlib; Pluribus na preflopie
robi to samo z wyboru); GPU jako ścieżka referencyjna artefaktu (cuBLAS
nie gwarantuje bitowości między architekturami, Colab jawnie zmienia
GPU; dopuszczalny wyłącznie jako pilotaż walidowany wobec CPU).
Do tego 4 korekty dokumentacyjne (w P-1): ε jest w jednostkach sumy
wypłat, nie „puli pota"; ex-post to Algorytm 3 Ganzfried–Sandholm
IJCAI-09, nie 6; skreślić „my bezstratni vs Pluribus abstrahowany";
skreślić „dorównujemy SOTA" ($0,049 to ich próg STOPU, nie podłoga —
obalenie z PDF-u źródłowego).

## 5. Mapa kontraktów (koszty na górnym końcu przedziałów panelu)

Zależności w locie: POKER-54/55 bramkują WSZYSTKIE pomiary areny (do ich
domknięcia mierzymy parę artefakt+reguła). Kolejność:

| id | kontrakt | koszt [core-h] | zależy od |
|---|---|---:|---|
| P-1 POKER-56 | higiena: tabela tierów (potwierdzenie operatora), assert normalizacji, fingerprint przebiegu (agent RZUCA przy niezgodności), fixture wyceny per-mode, licznik udziału decyzyjnego trybów, 4 korekty dok. | 0 | — |
| P-2 POKER-57 | `.bpk` v2: maska uint32, 4 sloty, kwantyzacja uint16 (błąd 171× mniejszy za darmo), ε per stan w pliku, marginesy indyferencji, blok fingerprinta | ~0 | — |
| P-3 POKER-58 | domknięcie warstw 1–5 przez osiągalność łańcucha DOKŁADNEGO (suma łańcuchów, solve tylko różnicy) — in-grid fallback 0,949%→~0,14% | 2–10 | — |
| P-4 POKER-59 | checkpoint horyzontu per cykl (zmierzona strata restartu: 16,2) | ~1 | — |
| P-5 POKER-53 | AIVAT w przestrzeni NAGRÓD (V artefaktu na granicach rozdań; zakaz Jensena; 2 asertowalne bramki nieobciążoności: ROI analityczne +233,33% trzech identycznych blueprintów przy 10x; zgodność średnich) | ~5 | 55+58 dla liczb |
| P-6 POKER-60 | trzy sondy błędu modelu: (a) poza-siatkowa (rozstrzyga krok 1 za <1), (b) uczciwy koszt kwantyzacji (policy-eval własnego V profilu kwantyzowanego), (c) wrażliwość na ziarno tensora | ~24 | — |
| P-7 POKER-61 | artefakt WTA@25bb: JEDNOZMIENNY A/B wypłat + prerejestrowany kill-check (krzywa V−ICM przy WTA; mała dywergencja = falsyfikacja wartości DAG-u w tierze modalnym) | ~65 | 54+55+58 |
| P-8 POKER-62 | T-MODAL 90/WTA (21 warstw — zegar ustala liczbę warstw, nie żetony) + krzywa wrażliwości zegara {3,6} rąk/poziom w JEDNYM kontrakcie | ~30 (+30) | 54+55+58 |
| P-9 POKER-63 | T-MID 120/WTA — warunkowy: tylko gdy P-7/P-8 pokażą, że teza tierowa płaci | ~71 | P-7/P-8 |
| P-10 POKER-64 | builder modelu populacyjnego z realnych hand histories przez tabele węzłów agenta; licznik decyzji niezmapowanych | 0 | **korpus HH (operator)** |
| P-11 POKER-65 | DBR wyłącznie końcówka HU + krzywa P_max | ≤2 | P-10 |
| P-12 POKER-66 | krzywa P_max na próbkowanych stanach 3-osobowych (wzorzec 47) | ~6 | P-11 |
| P-13 POKER-67 | pełny DAG seat-restricted DBR na T-MODAL (3 przebiegi hero, 3 tablice V) + A/B z AIVAT | ~96 | P-4,10,11,12 |
| P-14 POKER-68 | wyceniony spike flat-call: szew `_settle()`, drabina 0/1/2, budżet pamięci jako asercja, częstość squeeze; rozszerzenie drzewa WYMAGA nowego rekordu decyzyjnego (decyzja 27) | ~5 | P-2 |

**Bramka STOP (P-15), prerejestrowana:** żaden kolejny kontrakt
blueprintowy nie otwiera się bez pomiaru wyzwalającego — (1) P-6(a)
pokaże błąd siatki nad tolerancją → krok 1 (na T-MODAL mnożnik 1,43×);
(2) P-6(c) ≥ 1e−4 puli → próby tensora 60 000 PRZED każdym wydatkiem na
tolerancję; (3) CI areny po 55+AIVAT istotnie węższe od budżetowanych →
dopiero wtedy tolerancja wraca do rozważenia. Bez wyzwalacza następny
kontrakt należy do drzewa albo eksploatacji, nie do kolejnego solve'a.
**KOREKTA (2026-09-05, POKER-56 — fixture wyceny per-mode, potwierdzony
niezależnie audytem co do cyfry):** koszty panelu były szacunkami
mnożnikiem liczby stanów; fixture `tools/blueprint/mode_census.py`
(skalibrowany na biegu produkcyjnym: 64,3 wobec 65,4 zmierzonych — różnica
to narzut forka, kalibracja dowodzi rachunkowości, nie przenośności temp)
daje: WTA@25bb 64,3 · T-MODAL **17,8** (nie ~30) · T-MID **36,4** (nie ~71)
· pełny DBR **53,5** (nie ~96) · krok 1 na 150 żetonach 252,1 solvera /
263,3 z tensorem (nie ~444/555 — tensor jest kartowy i nie skaluje się
z siatką) · warstwy 1–5 do PEŁNEJ siatki **+47,9** (górne ograniczenie;
P-3 rozwiązuje różnicę łańcucha dokładnego za 2–10). Cztery wiersze WTA
i ich suma (~172 rdzenio-h zamiast ~262) są **DOLNYMI oszacowaniami**:
stoją na trzech jawnie nazwanych założeniach — (a) 6 cykli horyzontu jak
w biegu 80/20, (b) przenośność tempa per stan między wektorami wypłat
(OBALONA co do kierunku na łańcuchu kontrolnym: WTA wymaga więcej iteracji
PI-FP/CFR+ — jamfold 1,39×, hu-deep 1,12×, hu-jamfold 1,91× w iteracjach;
mnożnika z 34 żetonów/4 klas NIE przenosimy na produkcję — wyceni go
pierwszy przebieg WTA), (c) niezależność tempa od kroku siatki
(niezweryfikowana). Spis trybów (pomiar BF): `deep` + `hu-deep` obsługują
**72% decyzji** przy 4,3% komórek siatki, a `jamfold` zjada 57% budżetu
warstw za 10,5% decyzji — odpowiedź na otwarte pytanie 2: udział komórek
≠ udział odwiedzin o rząd wielkości, więc jakość trybu `deep` waży
w produkcie ~14× więcej, niż sugeruje jego udział w siatce.

Suma mapy ~325–375 rdzenio-h; wszystko mieści się w Colab (największy
przebieg ~96 < bezpiecznik 140; P-4 przed każdym przebiegiem > 12 h
ściennych; budżetujemy w rdzenio-h, nie w CU).

## 6. Wejścia operatorskie (blokują wyłącznie swoje gałęzie)

1. Potwierdzenie tabeli tierów wobec żywego lobby (przed P-7/P-8).
2. **Korpus realnych hand histories** — twarda blokada P-10..P-13; bez
   niego uczciwe zatrzymanie na P-11 (maszyneria zwalidowana w HU)
   i powiedzenie tego wprost; pola z własnych skryptów NIGDY nie wolno
   raportować jako pola realnego.

## 7. Czego ta decyzja nie zmienia

Niezmienniki produktu i proces bez zmian; drzewo gry zamrożone do
ewentualnego rekordu z P-14; decyzje 26 (zakaz Jensena, kolejność
HU→Spin) i 28 (naprawy przyrządu przed pomiarami) obowiązują; POKER-54/55
kończą się przed pierwszym pomiarem tierowym. Zakaz twierdzeń: „bijemy
pole $1" oraz cudzych liczb redukcji wariancji/eksploatacji jako naszych.

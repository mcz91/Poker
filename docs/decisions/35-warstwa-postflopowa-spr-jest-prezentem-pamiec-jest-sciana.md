# 35. Warstwa postflopowa: SPR jest prezentem, pamięć jest ścianą

Status: **PROJEKT — czeka na zatwierdzenie operatora.** Autor: doradca,
2026-09-20. Podstawa: zlecenie operatora („chcemy też grę postflop; bota to
możliwie skutecznego przybliżenia Spin & Go"). Rozszerza
[decyzję 34](34-najkrotsza-droga-do-bota-bijacego-field.md) o warstwę, której
tam nie było. Mechanizm z [decyzji 29](29-tier-first-fundament-gto-mapa-po-researchu.md)
pkt 3C (szew `_settle()`) i [25](25-blueprint-po-dagu-zegara-pifp-cfrplus.md)
pkt 6 (format artefaktu) bez zmian.

## 0. Dwa wnioski, oba policzone

**Pierwszy: postflop w Spin & Go jest tani, bo SPR jest mały.** Po otwarciu
2,2× i callu zostaje SPR **4,65 przy 25 bb, 2,61 przy 15 bb, 1,59 przy 10 bb**,
wobec ~11 w cashu 100 bb, który jest domem PioSOLVERA. Drzewo licytacji jest
przez to **3,3× mniejsze przy 25 bb i 21× mniejsze przy 10 bb** (abstrakcja
bogata). Postflop, który w cashu jest nieosiągalny za nasze pieniądze, tutaj
mieści się w jednym oknie darmowych runnerów.

**Drugi, ważniejszy: wąskim gardłem przestaje być compute, a staje się
pamięć.** Rekomendowany szczebel kosztuje **52 rdzenio-h** (jedno okno), ale
produkuje **791 MB** strategii. Pełne pokrycie 1755 flopów to 1 865 rdzenio-h
(osiem okien — wykonalne) i **28,3 GB** (niewykonalne). **To odwraca kierunek
optymalizacji: dźwignią jest kompresja wyjścia, nie więcej rdzenio-godzin.**

## 1. Skąd SPR i dlaczego on rozstrzyga o koszcie

Szczeble głębokości z `poker.spin.DEPTHS` i próg `JAM_FOLD_BB = 7`
(sprawdzone uruchomieniem 2026-09-20):

| szczebel | stacki | jam/fold? | pot po open 2,2× + call | za stackiem | **SPR** |
|---|---|---|---|---:|---:|
| 25 bb | 50 | nie | 4,9 bb | 22,8 bb | **4,65** |
| 15 bb | 30 | nie | 4,9 bb | 12,8 bb | **2,61** |
| 10 bb | 20 | nie | 4,9 bb | 7,8 bb | **1,59** |
| 6 bb | 12 | **tak** | — | — | postflopu nie ma |

Przy SPR 1,59 jeden zakład wielkości puli kończy licytację. Przy 4,65 mieszczą
się trzy ulice umiarkowanych zakładów. To jest różnica jakościowa wobec cashu.

**Węzły decyzyjne drzewa postflopowego HU** (własny licznik, stany chipowe
deduplikowane — tak jak projekt abstrahuje DAG zegara):

| abstrakcja akcji | 10 bb | 15 bb | 25 bb | cash 100 bb |
|---|---:|---:|---:|---:|
| minimalna (1 sizing) | 30 | 34 | 36 | 36 |
| standardowa (2 sizingi, 1 raise, cap 2) | 138 | 229 | **334** | 429 |
| bogata (4 sizingi, 2 raise'y, cap 3) | 407 | 979 | **2 585** | 8 634 |

## 2. Tempo — zmierzone, nie założone

Jądro CFR+ na numpy (regret matching + akumulacja + backup), zmierzone na tej
maszynie: **7 028 412 aktualizacji infosetu na rdzenio-sekundę** (5 akcji,
tablice ≥1e6, mediana). Do wyceny przyjęty **narzut ×5** na traversal, karty,
liście i propagację reach — **to jest założenie, nie pomiar**, więc wrażliwość
jest podana jawnie:

| narzut | rdzenio-h rekomendowanego szczebla |
|---:|---:|
| ×3 | 31,2 |
| **×5 (przyjęte)** | **52,1** |
| ×10 | 104,2 |
| ×20 | 208,3 |

Nawet przy ×20 szczebel mieści się w jednym oknie. **Wniosek o taniości
postflopu jest odporny na tę niepewność** — i to jest jedyny powód, dla
którego wolno tu wyceniać przed pilotem.

## 3. Menu — co za ile

Założenia jawne: 1000 iteracji CFR+, 2 pętle uzgodnienia preflop↔postflop,
4 pary zakresów („sprawdzony pot" w rozszerzonym drzewie), 3 szczeble
głębokości. Karty: turn i river klastrowane do klas runoutów, ręce do
kubełków per ulica (zgrubna 6/6 i 20/30/40; średnia 10/10 i 40/80/120).

| akcje / karty | 13 flopów | 49 flopów | 184 flopy | 1755 flopów |
|---|---:|---:|---:|---:|
| minimalna / zgrubna | 1,5 h | **5,7 h** | 21,3 h | 202,8 h |
| minimalna / średnia | 12,0 h | 45,0 h | 169,2 h | 1 613 h |
| standardowa / zgrubna | 13,8 h | **52,1 h** | 195,5 h | 1 865 h |
| standardowa / średnia | 112,0 h | 422,1 h | 1 585 h | 15 119 h |
| bogata / zgrubna | 81,2 h | 306,2 h | 1 150 h | 10 965 h |
| bogata / dokładna | 5 534 h | 20 859 h | 78 328 h | **747 000 h** |

Ostatni wiersz to skala PioSOLVERA: **85 rdzenio-lat**. Nie jest naszą opcją
i nie musi być.

## 4. Ściana, której się nie spodziewałem — artefakt

Format `.bpk` v2: 4 sloty akcji, **3 zapisane** (czwarty wyliczany), uint16
domyślnie, uint8 legalne (błąd pojedynczego prawdopodobieństwa 2,61e−3).

| wariant | infosetów | rdzenio-h | uint16 | uint8 |
|---|---:|---:|---:|---:|
| minimalna / zgrubna / 49 | 14,3 mln | 5,7 h | 86 MB | 43 MB |
| **standardowa / zgrubna / 49** | **131,8 mln** | **52,1 h** | **791 MB** | **395 MB** |
| standardowa / zgrubna / 184 | 494,8 mln | 195,5 h | 3,0 GB | 1,5 GB |
| bogata / zgrubna / 49 | 774,6 mln | 306,2 h | 4,6 GB | 2,3 GB |
| standardowa / zgrubna / 1755 | 4,72 mld | 1 865 h | 28,3 GB | 14,2 GB |

Decyzja 25 pkt 6 przewidziała tablicę strategii rzędu **0,25–1 GB** i dlatego
odrzuciła moduł Pythona (sufit ~5 MB, PUŁAPKA POKER-24) na rzecz formatu
binarnego. Rekomendowany szczebel trafia **dokładnie w górną granicę tej
prognozy** — czyli plan z 2026-08-28 był trafny, ale zapasu nie ma.

**Powyżej 49 flopów compute rośnie liniowo, a pamięć uderza w ścianę
pierwsza.** To jest nowy fakt wobec wszystkich wcześniejszych decyzji.

## 5. Dwa różne produkty, które trzeba rozdzielić

Nazwa „postflop" ukrywa dwie rzeczy o różnej cenie i różnej wartości:

**(A) Preflop świadomy postflopu.** Dziś pot sprawdzony rozlicza się tak,
jakby obaj czekali do showdownu — bo `_LEAF_DEFS_3` ma 17 liści, wszystkie
fold albo showdown (decyzja 29 pkt 2c). Wystarczy, żeby **tensor kartowy
niósł poprawne EV rozegranego pota**, a decyzje preflop przestają stać na
fałszywym założeniu. Artefakt: **kilobajty** (tensor, nie strategia). Koszt:
zawarty w szczeblu z pkt 3. **To naprawia największe zniekształcenie
w bocie, jaki mamy, i nie wymaga, żeby bot umiał zagrać flopa.**

**(B) Gra postflop.** Bot faktycznie betuje, raisuje i pasuje na flopie —
wymaga przechowania strategii w każdym węźle, czyli tabeli z pkt 4.

**Kolejność: (A) najpierw, (B) potem.** (A) jest prawie darmowe, działa na
87% wolumenu razem z T-MODAL i zdejmuje wadę, którą audyt nazwał najcięższą.
(B) jest dopiero wtedy, i dopiero wtedy ma sens pytanie o rozmiar.

## 6. Tu — i dopiero tu — sieć neuronowa zarabia na siebie

Decyzje 25, 29, 31 i 34 odrzucały sieci, bo wąskim gardłem była brakująca
gałąź w drzewie i wagi tierów, a nie pojemność reprezentacji. **Pkt 4 zmienia
tę przesłankę po raz pierwszy w historii tego projektu:** 0,8–28 GB strategii
to jest dokładnie ten problem, do którego sieć jest właściwym narzędziem —
**jako kompresja własnej tablicy, nie jako solver.**

To nie jest odwrócenie wcześniejszych decyzji, tylko spełnienie warunku,
który one same postawiły: decyzja 25 wymienia **SD-CFR** jako plan awaryjny.
Sieć trenowana na wyjściu naszego solvera:

- **nie zastępuje** PI-FP + CFR+ — solver zostaje tabelaryczny i na CPU;
- ma cel mierzalny: odtworzyć strategię z błędu ≤ tolerancja, przy rozmiarze
  ≤ sufit pamięci produktu — czyli **krzywa błąd/rozmiar, a nie wiara**;
- **łamie INV-P8**, jeśli inferencja wymaga biblioteki. Mała sieć (rzędu 1e5
  wag) liczy się w czystym Pythonie; duża nie. **To jest bramka, nie detal** —
  i nowy rekord decyzyjny musi podać zmierzony czas decyzji, nie deklarację.

Kolejność pozostaje: **najpierw tabela, potem jej kompresja.** Sieć trenowana
zanim istnieje tablica nie ma na czym się uczyć.

## 7. Czego to przybliżenie świadomie nie obejmuje

1. **Flopy trójstronne.** Cały rachunek zakłada postflop HU (jeden gracz
   spasował preflop). Postflop 3-way jest istotnie większy. Potrzebny pomiar:
   **jaki odsetek rozdań dochodzi do flopa w trzech** — to jest liczba z
   rozwiązanego drzewa, do policzenia za zero. Do czasu jej poznania warstwa
   postflopowa obsługuje 3-way **awaryjnie** (strategia HU z zacieśnieniem)
   i tak musi być nazwana w manifeście artefaktu.
2. **Turn i river są klastrowane**, nie enumerowane. Enumeracja 49×48 runoutów
   mnoży rozmiar o ~235× — pkt 3 wiersz „bogata / dokładna" pokazuje, dokąd
   to prowadzi.
3. **Liczba par zakresów (4) jest założeniem**, nie pomiarem — wyjdzie
   z rozszerzonego drzewa (krok F-6 decyzji 34).
4. **Tolerancje i kubełki nie są wybrane, tylko sparametryzowane.** Wybór
   szczebla należy do pomiaru, nie do tej decyzji (wzorzec POKER-47: najpierw
   krzywa, potem próg).

## 8. Kroki — wchodzą do planu decyzji 34

| # | krok | faza 34 | koszt |
|---|---|---|---|
| P-1 | Odsetek flopów 3-way z rozwiązanego drzewa | 0 | 0 |
| P-2 | Pilot tempa: jeden flop, jeden szczebel, zmierzony narzut wobec ×5 | 0 | <1 h |
| P-3 | Tensor rozegranego pota → **produkt (A)**, preflop świadomy postflopu | 1 | w szczeblu |
| P-4 | Krzywa błąd/szczebel: 13 → 25 → 49 → 184 flopów przy stałej abstrakcji akcji | 1 | ≤80 h |
| P-5 | **Produkt (B)** na szczeblu wybranym krzywą z P-4 | 2 | 52–196 h |
| P-6 | Krzywa błąd/rozmiar kompresji (SD-CFR) + pomiar czasu decyzji wobec INV-P8 | 2 | wymaga rekordu |

P-3 wchodzi do Fazy 1 decyzji 34 razem z flat callem (krok F-6) — to jest ta
sama zmiana drzewa widziana z drugiej strony szwu.

## 9. Źródła liczb

- Szczeble głębokości, `JAM_FOLD_BB`, tryby solvera: `src/poker/spin.py`,
  uruchomione 2026-09-20.
- Format artefaktu (4 sloty, 3 zapisane, uint16/uint8, błąd 2,61e−3):
  `tools/blueprint/pack_blueprint.py`, stałe `DEFAULT_QUANT_BITS*`.
- Sufit modułu ~5 MB i prognoza 0,25–1 GB:
  [decyzja 25](25-blueprint-po-dagu-zegara-pifp-cfrplus.md) pkt 6.
- Szew `_settle()` i prawo kosztu liniowe w liściach:
  [decyzja 29](29-tier-first-fundament-gto-mapa-po-researchu.md) pkt 3C.
- Liczba węzłów drzewa, tempo jądra CFR+, tabele kosztu i rozmiaru: własne
  wyliczenie i pomiar z 2026-09-20; skrypty w scratchpadzie sesji — do repo
  wchodzą kontraktem P-2/P-4, nie tą decyzją.

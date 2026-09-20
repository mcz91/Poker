# Koszty zbiorczo — wszystkie rozważane rozwiązania

Rollup z 2026-09-20. **To jest zestawienie, nie źródło.** Każdy wiersz ma
wskazany dokument źródłowy; przy rozbieżności obowiązuje źródło, nie ta tabela.
Rdzenio-godziny pochodzą z `tools/blueprint/mode_census.py` i z pomiarów
[decyzji 35](decisions/35-warstwa-postflopowa-spr-jest-prezentem-pamiec-jest-sciana.md);
stawki pieniężne wyprowadzone ze stawek
[decyzji 31](decisions/31-nauka-nie-komercja-compute-i-pomiar-za-zero.md) pkt 9.2.

## 1. Stawki nośników

| nośnik | $/rdzenio-h | uwaga |
|---|---:|---|
| **GitHub Actions, repo publiczne** | **0** | 20 jobów × 6 h = 240–480 rdz-h/okno |
| Hetzner AX52 (ryczałt 64 €/mies.) | 0,011 | 5 840 rdz-h/mies.; artefakt nie wychodzi z maszyny |
| AWS c7i spot | 0,014–0,033 | |
| Hetzner CCX43 | 0,033–0,066 | |
| AWS c7i on-demand | 0,052–0,109 | |

## 2. Compute — wszystko, co policzone

Czas ścienny liczony zachowawczo (240 rdz-h na okno Actions).

| pozycja | źródło | rdz-h | czas ścienny | Actions | AX52 | AWS on-dem. |
|---|---|---:|---:|---:|---:|---:|
| Faza 0: cel, przyrząd, wagi tierów | d.34 | **0** | — | 0 $ | 0 $ | 0 $ |
| Faza 1: preflop, 87% wolumenu, z flat callem | d.34 | 75,5 | 1,9 h | 0 $ | <1 $ | 4–8 $ |
| Faza 2: preflop, pozostałe 13% | d.34 | 142,2 | 3,6 h | 0 $ | 2 $ | 7–15 $ |
| **Razem preflop** | d.34 | **217,7** | **5,5 h** | **0 $** | **2 $** | **11–24 $** |
| Postflop (A): tensor rozegranego pota | d.35 | w szczeblu | — | 0 $ | 0 $ | 0 $ |
| Postflop (B) minimalny: 49 flopów, 1 sizing | d.35 | 5,7 | 0,1 h | 0 $ | <1 $ | <1 $ |
| **Postflop (B) rekomendowany: 49, 2 sizingi** | d.35 | **52,1** | **1,3 h** | **0 $** | **<1 $** | **3–6 $** |
| Postflop (B) szeroki: 184 flopy | d.35 | 195,5 | 4,9 h | 0 $ | 2 $ | 10–21 $ |
| Postflop (B) pełny: 1755 flopów | d.35 | 1 865,2 | 1,9 dnia | 0 $ | 20 $ | 97–202 $ |
| Postflop w skali Pio (bogata/dokładna/1755) | d.35 | 747 000 | **2,1 roku** | 0 $ | 8 186 $ | 38–81 tys. $ |
| Najgorszy przypadek: krok 1 siatki | d.31 | 464 | 11,6 h | 0 $ | 5 $ | 24–50 $ |

**Zalecany zestaw (Faza 0 + 1 + 2 + postflop A + postflop B rekomendowany):
270 rdzenio-h, ~7 h ściennych, 0 $ na Actions, ~3 $ na własnym serwerze,
14–30 $ u dostawcy chmurowego.**

Wiersz „skala Pio" jest w tabeli po to, żeby pokazać granicę: na darmowym
nośniku kosztuje 0 $ i **2,1 roku**, czyli jest nieosiągalny czasem, nie ceną.

## 3. Koszty niebędące compute — tu są prawdziwe pieniądze

| pozycja | źródło | koszt | uwaga |
|---|---|---:|---|
| Korpus operatora (~1 mln rąk, już posiadany) | d.32 | **0 $** | wymaga metadanych: format, stawka, data |
| Zbieranie własnych historii: 3 000 turniejów | d.31 9.3 | 150–250 $ | ~50 h gry; waliduje maszynerię |
| Zbieranie własnych historii: 10 000 turniejów | d.31 9.3 | 350–800 $ | ~170 h gry; model populacyjny |
| **HRC Classic — kontrola preflopu ICM** | d.31 9.4 | **0 $** | **trial 14 dni, bez karty**; potem 16,66 $/mies. |
| **TexasSolver — kontrola postflopu chipEV** | d.31 9.4 | **0 $** | AGPL, uruchamiany osobno; 0,015% różnicy wobec Pio |
| HRC Pro | d.31 1 | 49,99 $/mies. | niepotrzebny |
| ICMIZER Pro | d.31 1 | ~159,99 $/rok | alternatywa dla HRC |
| GTO Wizard | d.31 1 | 26–116 $/mies. | zły format (cash HU/6-max) |
| PioSOLVER Pro / Edge | d.31 9.4 | 450 / 800 € wieczyste | **zbędny** — TexasSolver robi to samo za 0 $ |
| MonkerSolver | d.31 1 | 499 € jednorazowo | zła gra |
| **Godziny kontraktów** | d.34 6 | **`BRAK` wyceny** | ~15 kontraktów; przepustowość nieustalona |

## 4. Linia neuronowa — wycena, którą trzeba podać uczciwie

Jeden przebieg treningowy klasy **AlphaHoldem** (8×TITAN V + 64 rdzenie CPU,
3 dni — [decyzja 31](decisions/31-nauka-nie-komercja-compute-i-pomiar-za-zero.md) pkt 2):

| składnik | ilość | stawka | koszt |
|---|---:|---|---:|
| GPU | 576 GPU-h | 0,50–1,50 $/h (klasa V100, spot→on-demand) | 288–864 $ |
| CPU | 4 608 rdz-h | 0,014–0,109 $/rdz-h | 65–498 $ |
| **Razem jeden przebieg** | | | **353–1 362 $** |

To jest **40–153× drożej** niż cały zalecany zestaw z pkt 2 — ale w liczbach
bezwzględnych kilkaset dolarów, nie „rzędy wielkości poza budżetem". Wcześniejsze
sformułowania w tej sesji sugerowały nieosiągalność cenową; **cena nie jest
blokadą.** Blokady są trzy i żadna nie jest finansowa:

1. Dla Spin & Go 3-max z ICM **nie istnieje żadna opublikowana praca**, więc to
   są badania oryginalne bez wzorca odniesienia.
2. **Nie mamy przyrządu**, który odróżniłby udany przebieg od nieudanego
   (decyzja 34 pkt 2 naprawia to dla linii tabelarycznej, nie dla neuronowej).
3. **INV-P8**: inferencja w czasie gry musi zmieścić się w czystym stdlib.

**Kompresja (SD-CFR)** — sieć trenowana na wyjściu własnego solvera, żeby
zmieścić 0,8–28 GB strategii postflopowej — to inna pozycja i inna cena:
trening nadzorowany na gotowych danych, **<5 rdzenio-h + jeden kontrakt**.
To jest jedyne zastosowanie sieci, które ten projekt dziś uzasadnia
(decyzja 35 pkt 6).

## 5. Czego pieniądze nie kupią

Bez zmian wobec [decyzji 31](decisions/31-nauka-nie-komercja-compute-i-pomiar-za-zero.md)
pkt 9.6: naprawy przyrządu (findingi 6.1/6.3), godzin kontraktów i realnego
pola. Do tego dochodzą trzy pozycje operatorskie, każda za 0 zł i każda
blokująca: **rake docelowej stawki**, **potwierdzenie tabeli tierów wobec
żywego lobby** (decyzja 34 pkt 3 pokazuje, że dzisiejsza się nie domyka)
i **struktura pasma 25x+ z trzema płatnymi**, której w kodzie nie ma.

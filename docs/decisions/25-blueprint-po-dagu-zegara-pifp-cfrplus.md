# 25 — Droga Pluribusa u nas: blueprint po DAG-u zegara, PI-FP + CFR+

Operator (2026-08-28) wybrał kierunek treningu: droga Pluribusa —
tabelaryczny CFR/FP na ręcznej abstrakcji, CPU, budżet klasy Google
Colab; sieci neuronowe odrzucone (Deep CFR przegrywa z dobrą tablicą
w HULH o 11 mbb/g; ReBeL/SoG poza budżetem o 3–4 rzędy). Głęboki
research architekta (2026-08-28, dwa raporty ze źródeł pierwotnych:
supplementary Science 2019, Modicum arXiv:1805.08195, Ganzfried &
Sandholm AAMAS 2008 / IJCAI 2009 / arXiv:2010.13860, AIVAT
arXiv:1612.06915, GPU-CFR arXiv:2408.14778) rozstrzyga, jak ta droga
wygląda na naszej skali.

## Decyzja

1. **Przestrzeń stanów to DAG zegara, rozwiązywany dokładnie wstecz.**
   Stan = (poziom blindów, ręka-w-poziomie, wektor stacków). Licznik
   rąk rośnie monotonicznie, więc nie ma cykli: jedno przejście
   backward induction od horyzontu do startu zastępuje pętlę value
   iteration (Ganzfried potrzebował 21 iteracji zewnętrznych; u nas
   ~20× taniej i wynik dokładny). ICM wyłącznie jako warunek brzegowy
   na horyzoncie, inicjalizacja i baseline pomiaru — nigdy jako
   wartość „po ręce" (błąd ICM u Ganzfrieda sięgał 3% puli i jest
   największy dokładnie w naszym reżimie: krótko, 3-max, rosnące
   blindy). Cykliczny wyjątek: ostatni poziom zegara domykany PI-FP
   do punktu stałego.
2. **Solver stanu: PI-FP w grze 3-osobowej, CFR+ w endgame'ach HU.**
   Fictitious play empirycznie bije CFR we wszystkich klasach gier
   poza 2-osobowymi o sumie zerowej (arXiv:2001.11165); nasz stage
   game ma 2 366 infosetów (14 węzłów publicznych × 169 klas), więc
   pełny best response jest tani — MCCFR (sampling) jest u nas zbędny,
   to narzędzie na drzewa, których nie da się enumerować. Endgame HU
   po odpadnięciu gracza to gra o stałej sumie — tam CFR+ z gwarancją
   zbieżności. Zakaz: pula 2-way przy trzech żywych graczach NIE jest
   grą o sumie zerowej (equity ICM pasującego się zmienia) — nie wolno
   jej tak rozwiązywać. Restarty z kilku inicjalizacji, wybór profilu
   po ε.
3. **Abstrakcja: 169 klas lossless, łączne rozkłady trójek.** Zgodnie
   z Pluribusem i Modicum preflop gra bez kubełków. Strategie na 169
   klasach, ale propagacja łącznych (nienormalizowanych) rozkładów
   trójek klas — nie iloczynu marginałów — żeby zachować card removal
   w wąskich zakresach callujących (węzły po dwóch agresjach; u
   Ganzfrieda call BB vs jam/jam to 2,1% zakresu). Przejście na 1326
   kombinacji kosztuje ~480× w terminalach 3-way i się nie zwraca.
4. **Z Pluribusa przenosimy zasady, nie sampling:** progi wyrażone
   w iteracjach (nigdy w czasie zegarowym — determinizm), randomized
   pseudo-harmonic action translation dla akcji spoza drzewa (wzór
   f(x;A,B) = (B−x)(1+A) / ((B−A)(1+x)), zakaz mapowań geometrycznych),
   bootstrapowy dobór sizingów (trenuj gęsto → zbierz używane →
   przytnij → trenuj docelowo), asymetryczna abstrakcja akcji (więcej
   akcji przeciwnika niż naszych), tani self-improvement (log betów
   off-tree → rozszerzenie abstrakcji → retrening). Real-time search,
   k-means/EMD, purification, negative-regret pruning — u nas zbędne
   (uzasadnienia w raporcie: Pluribus sam gra preflop z blueprintu,
   preflop jest lossless, a reguły pruningu wyłączają go w całym
   drzewie preflopowym).
5. **Trening w `tools/` (numpy f32, płaskie macierze, seedowany),
   siatka: pilot 5 żetonów → produkcja 2 żetony** (~48,6 tys. solve'ów,
   szac. ~108 rdzenio-godzin — do weryfikacji pilotem, zgodnie z
   PUŁAPKĄ o kryteriach ilościowych). Sharding po warstwach DAG-u
   (w warstwie stany niezależne — zrównoleglenie liniowe), checkpoint
   atomowy z manifestem — stan rekursji to tablica V (megabajty), nie
   strategie (setki MB). Colab: co najwyżej runner CPU z checkpointami
   na Drive; GPU nic tu nie kupuje (numpy CPU bije nawet OpenSpiel C++
   w tej klasie rozmiaru — arXiv:2408.14778).
6. **Artefakt produkcyjny NIE jest modułem Pythona.** Sufit ~5 MB
   modułu (PUŁAPKA POKER-24) wyklucza tablicę strategii siatki
   (0,25–1 GB). Forma: dwupoziomowa — mała tablica V + skwantowana
   (uint8) tablica strategii we własnym, wersjonowanym formacie
   binarnym czytanym w produkcie czystym stdlib (struct/array, bez
   numpy — INV-P8 i decyzja 06 nietknięte), z manifestem pochodzenia
   i dwustopniowym dowodem odtwarzalności (decyzja 06: mały łańcuch
   kontrolny w bramce, pełna regeneracja poza nią). Miejsce
   przechowywania pełnego artefaktu (poza historią gita) — do
   rozstrzygnięcia przy kontrakcie produkcyjnym, opcjami z decyzji 09.
7. **Metryka jakości: ex-post best-response check, nie winrate.**
   W 3-max samo „algorytm się uspokoił" ani wynik w arenie nie dowodzą
   równowagi (VI-FP udokumentowanie potrafi zbiec do nie-równowagi).
   Miarą jest ε z ex-post checku (Ganzfried, Algorithm 6: best
   response przez MDP przy zamrożonych pozostałych strategiach);
   punkt odniesienia: 0,05% puli. Równolegle AIVAT w arenie (u nas
   warunki lepsze niż w pracy źródłowej: preflop-only, znamy strategie
   wszystkich miejsc, V niemal dokładne) + duplicate, z własną
   walidacją nieobciążoności dla 3 graczy (w literaturze niezbadane).

## Czego świadomie nie robimy

MCCFR w stage game (zbędny przy 2 366 infosetach); sieci neuronowe
(plan awaryjny: SD-CFR, udokumentowany w researchu); 1326 kombinacji;
pruning; search w czasie gry; GPU. Publiczne solucje Spin (chipEV na
stałej głębokości) to sanity-check pierwszych akcji, nie ground truth —
w węzłach po dwóch agresjach turniejowa równowaga różni się od nich
nawet 9,4× (Ganzfried, Tabela 2) i to nasz wynik będzie poprawny.

## Którą gałąź ta decyzja zamyka albo czyni droższą?

Żadnej nie zamyka. GTO-ML: rdzeń kierunku. Trener: tablica V(stan)
i pełne strategie to gotowy podkład pod replay/analizę/podpowiedzi —
gałąź tanieje. Pokerroom: bez zmian (artefakt wchodzi portem Agent).
Koszt otwarty: format binarny artefaktu poza gitem wymaga decyzji
o dystrybucji przy kontrakcie produkcyjnym.

## Niepewności (jawne)

Tensor rolloutu 3-way (169³×13) to jedyne miejsce, gdzie numpy może
nie wystarczyć — pomiar w pilocie przed planowaniem produkcji; koszt
~15 ms/iterację/stan to model, nie benchmark (±2–3×); brak gwarancji
teoretycznych w 3-max — ex-post check jest obowiązkowy i część stanów
może wymagać restartów; AIVAT dla 3 graczy wymaga własnej walidacji;
drabinka zegara L przesuwa budżet liniowo.

# Indeks dokumentacji produktu Poker

- [`CURRENT_STATE.md`](CURRENT_STATE.md) — stan bieżący, bramka,
  następny krok.

## Dokumenty decyzji

1. [`01-trzy-produkty-jeden-rdzen.md`](decisions/01-trzy-produkty-jeden-rdzen.md)
   — trzy produkty docelowe (pokerroom, trener, bot), jeden wspólny
   rdzeń, zakaz pustych szkieletów produktów;
2. [`02-jezyk-rdzenia-python.md`](decisions/02-jezyk-rdzenia-python.md)
   — język rdzenia: Python ≥3.12, toolchain wspólny z Foundry;
3. [`03-kierunek-bot-interfejs-czlowieka.md`](decisions/03-kierunek-bot-interfejs-czlowieka.md)
   — kierunek bot etapami: interfejs człowieka (a), baseline (b),
   warstwa eksploatacyjna (c);
4. [`04-reguly-dzis-ml-docelowo.md`](decisions/04-reguly-dzis-ml-docelowo.md)
   — etap (b) drogą operatora: proste reguły dziś, silnik GTO/explo
   na ML docelowo; podetapy equity → arena → dane self-play → ML;
5. [`05-b4-plastrami-dane-baseline-zaleznosci.md`](decisions/05-b4-plastrami-dane-baseline-zaleznosci.md)
   — podetap b4 plastrami (zbiór przykładów → baseline stdlib →
   zależności po pomiarze), granica informacyjna danych treningowych,
   bezstanowość agentów w rozgrywce (zamyka wątek audytu POKER-13);
6. [`06-b43-zaleznosci-w-narzedziach-droga-gto-explo.md`](decisions/06-b43-zaleznosci-w-narzedziach-droga-gto-explo.md)
   — b4.3: zależności ML wyłącznie w narzędziach, inferencja
   w stdlib, plastry c1 (MLP-klon) → c2 (self-play) → c3 (explo),
   dwustopniowe dowody odtwarzalności na skalę;
7. [`07-c2-mccfr-na-abstrakcji-strategia-mieszana.md`](decisions/07-c2-mccfr-na-abstrakcji-strategia-mieszana.md)
   — c2: seedowany MCCFR w self-play na wersjonowanej abstrakcji,
   artefakt strategii z pochodzeniem, mieszanie akcji bez stanu
   (deterministyczna funkcja seeda i widoku); plastry c2a→c2c;
8. [`08-pokerroom-krok1-stoly-heads-up-w-lan.md`](decisions/08-pokerroom-krok1-stoly-heads-up-w-lan.md)
   — otwarcie gałęzi pokerroom na zamówienie operatora: serwer wielu
   stołów heads-up w LAN (adapter, mono-repo), separacja informacji
   na granicy procesu; multiway = osobna kwalifikacja silnika;
9. [`09-skala-mccfr-krzywa-przed-forma.md`](decisions/09-skala-mccfr-krzywa-przed-forma.md)
   — sprzeciw kodera wobec POKER-24 uznany (kryteria sprzeczne),
   kryterium ≥50k wycofane; krzywa jakość-vs-skala poza repozytorium
   przed wyborem formy artefaktu; warunki dla trzech opcji formy.
10. [`10-spin-and-go-icm-bez-pokerkit.md`](decisions/10-spin-and-go-icm-bez-pokerkit.md)
    — Spin & Go pierwszy: własny ICM Harville, bez PokerKit i bez
    otwierania INV-P5; 2×/3× WTA, 10× 80/20;
11. [`11-jamfold-fictitious-play.md`](decisions/11-jamfold-fictitious-play.md)
    — Nash jam/fold 3-max fictitious play na jednym stanie stacków
    (Ganzfried & Sandholm 2008), payoff ICM/WTA;
12. [`12-one-step-continuation.md`](decisions/12-one-step-continuation.md)
    — pierwszy backup zewnętrzny: V¹ = E[ICM(s′)] pod Nash vs cash-out;
13. [`13-spin-clock.md`](decisions/13-spin-clock.md) — zegar głębokości
    25/15/10/6 bb; krzywa jamu przeliczona w POKER-45;
14. [`14-playable-spin.md`](decisions/14-playable-spin.md) — grywalny
    Spin z eskalacją blindów (LEVELS, HANDS_PER_LEVEL);
15. [`15-tani-trening-jamfold.md`](decisions/15-tani-trening-jamfold.md)
    — offline Nash na zegarze; monotoniczność jamu potwierdzona
    pomiarem po naprawach POKER-45;
16. [`16-exploitability-jamfold.md`](decisions/16-exploitability-jamfold.md)
    — ε vs best response w buy-inach; porównanie do Ganzfrieda
    unieważnione decyzją 17;
17. [`17-epsilon-to-model.md`](decisions/17-epsilon-to-model.md)
    — self-ε mierzy równowagę modelu, nie jakość pokera; koniec
    porównań zewnętrznych;
18. [`18-plan-rozbudowy-spin.md`](decisions/18-plan-rozbudowy-spin.md)
    — plan rozbudowy Spin $1 plastrami; POKER-27 tylko przy powrocie
    do cash HU (uwaga: dokument przepisany w miejscu — adnotacja);
19. [`19-push-fold-siedem-bb.md`](decisions/19-push-fold-siedem-bb.md)
    — próg push/fold ≤ 7 bb efektywnych; wyżej open 2.2x, bez flata;
20. [`20-open-tree.md`](decisions/20-open-tree.md) — first-in 2.2x;
    3bet z drzewa bez flata nie jest polityką;
21. [`21-threebet-spot.md`](decisions/21-threebet-spot.md) — ciasny
    3bet vs zamrożony open; zakres i procent generowane z kodu
    (POKER-45);
22. [`22-arena-roi.md`](decisions/22-arena-roi.md) — arena ROI vs
    fish; pomiary przeliczone w POKER-45;
23. [`23-field-exploit.md`](decisions/23-field-exploit.md) — field
    exploit; teza „bije $1-ish fisha" nieosiągnięta na N=320
    (CI obejmuje zero);
24. [`24-audyt-i-scalenie-linii-spin.md`](decisions/24-audyt-i-scalenie-linii-spin.md)
    — audyt linii Spin w trzech transzach (2026-08-28), uznane
    sprzeciwy, naprawy POKER-44/45, scalenie do main;
25. [`25-blueprint-po-dagu-zegara-pifp-cfrplus.md`](decisions/25-blueprint-po-dagu-zegara-pifp-cfrplus.md)
    — droga Pluribusa na naszej skali: backward induction po DAG-u
    zegara z ICM na horyzoncie, PI-FP (3-handed) + CFR+ (endgame HU),
    169 klas z łącznymi rozkładami trójek, ex-post ε jako metryka,
    artefakt binarny poza modułem Pythona.

## TaskSpeki

Kontrakty zadań żyją w [`taskspecs/`](taskspecs/) według
`schemas/task-spec.schema.json` z `mcz91/foundry`:

- [`POKER-1.json`](taskspecs/POKER-1.json) — szkielet i pełna bramka
  (zamknięty, commit `5a74ab9`);
- [`POKER-2.json`](taskspecs/POKER-2.json) — karty i ewaluator rąk
  (zamknięty, commit `bd3473c`);
- [`POKER-3.json`](taskspecs/POKER-3.json) — zdarzenia rozdania
  i projekcja stanu (zamknięty, commit `68df34e`);
- [`POKER-4.json`](taskspecs/POKER-4.json) — ujednolicenie bramki po
  audycie POKER-1 (zamknięty, commit `bd6dd56`);
- [`POKER-5.json`](taskspecs/POKER-5.json) — maszyna licytacji heads-up
  z rozliczeniem rozdania (zamknięty, commit `fa6a25c`);
- [`POKER-6.json`](taskspecs/POKER-6.json) — kontrakt agenta i widok
  gracza z testem przecieku (zamknięty, commit `8e7d9e6`);
- [`POKER-7.json`](taskspecs/POKER-7.json) — stół i pętla meczu
  (zamknięty, commit `462576d`; domknięcie audytu `4a01775`);
- [`POKER-8.json`](taskspecs/POKER-8.json) — pierwszy agent regułowy
  (zamknięty, commit `95d004a`; audyt: CZYSTY);
- [`POKER-9.json`](taskspecs/POKER-9.json) — CLI i eksport historii
  (zamknięty, commit `b6f7035`; audyt: CZYSTY);
- [`POKER-10.json`](taskspecs/POKER-10.json) — interfejs człowiek vs
  bot w terminalu (zamknięty, commit `b1da201`; audyt: 1 finding
  informacyjny → POKER-11);
- [`POKER-11.json`](taskspecs/POKER-11.json) — showdown na żywo
  w trybie człowieka (zamknięty, commit `80899ce`; audyt: CZYSTY);
- [`POKER-12.json`](taskspecs/POKER-12.json) — equity preflop 169
  klas rąk jako dane (zamknięty, commit `f166f41`; audyt: CZYSTY);
- [`POKER-13.json`](taskspecs/POKER-13.json) — arena porównawcza
  agentów: BB/100 na lustrzanych rozdaniach (zamknięty, commit
  `5f5302b`; audyt: CZYSTY);
- [`POKER-14.json`](taskspecs/POKER-14.json) — korpus self-play:
  masowa generacja historii w formacie eksportu (zamknięty, commit
  `5a75ef8`; audyt: CZYSTY);
- [`POKER-15.json`](taskspecs/POKER-15.json) — zbiór przykładów
  decyzyjnych z korpusu, plaster b4.1 decyzji 05 (zamknięty, commit
  `cb2298d`; audyt: CZYSTY);
- [`POKER-16.json`](taskspecs/POKER-16.json) — baseline behavior
  clone, plaster b4.2 decyzji 05 (zamknięty, commit `eea6b81`;
  audyt: F1 ISTOTNY — odtwarzalność wag z samego repo → POKER-17);
- [`POKER-17.json`](taskspecs/POKER-17.json) — przepis pochodzenia
  wag w artefakcie i test pochodzenia (zamknięty, commit `469f2db`;
  audyt: CZYSTY — F1 audytu POKER-15/16 domknięty z dowodem
  mechanicznym);
- [`POKER-18.json`](taskspecs/POKER-18.json) — sufit baseline'u
  stdlib: cechy v2 (equity, siła układu), korpus 100 meczów, pomiar
  w arenie (zamknięty, commit `cd645ed`; audyt: 1 finding
  informacyjny — niedoliczony dowód czerwieni, bez obowiązku
  działania);
- [`POKER-19.json`](taskspecs/POKER-19.json) — MLP-klon, plaster c1
  decyzji 06: trening numpy w tools/, inferencja stdlib, trzeci
  punkt pomiarowy (zamknięty, commit `0dfa48b`; audyt: F1 ISTOTNY —
  sprzeczność kryterium czasu bramki w kontrakcie, uznana przez
  architekta → POKER-20; F2 informacyjny — nieprzypięty numpy
  → POKER-20);
- [`POKER-20.json`](taskspecs/POKER-20.json) — porządek dowodów po
  c1: dwustopniowy dowód dla klona liniowego, przypięcie numpy
  (zamknięty, commit `72305b1`; audyt: CZYSTY — F1 i F2 audytu
  POKER-19 domknięte z dowodem);
- [`POKER-21.json`](taskspecs/POKER-21.json) — pokerroom krok 1:
  serwer stołów heads-up w LAN, klient terminalowy, przeciek
  protokołu pod testem (zamknięty, commit `c9231e3`; audyt:
  1 finding informacyjny — przewidywalny kod stołu → wątek na
  najbliższy kontrakt sieciowy);
- [`POKER-22.json`](taskspecs/POKER-22.json) — abstrakcja kart
  i akcji pod MCCFR, plaster c2a decyzji 07 (zamknięty, commit
  `fb61bf2`; audyt: 1 finding informacyjny — duplikacja formuły
  equity-przeciw-polu → wątek na publiczne API w preflop_equity);
- [`POKER-23.json`](taskspecs/POKER-23.json) — trener MCCFR,
  artefakt strategii i agent tabelowy `mccfr`, plaster c2b
  (zamknięty, commit `3e7c0c2`; audyt: CZYSTY — odstępstwo stempla
  po starcie zbadane, treść identyczna ze szkicem, uznane przez
  architekta);
- [`POKER-24.json`](taskspecs/POKER-24.json) — skala treningu MCCFR:
  wznowienia deterministyczne, artefakt ≥50k iteracji, pomiar
  rozstrzygający, plaster c2c (zamknięty częściowo, commit
  `fd253f5`: wznowienia i wydajność dostarczone i zweryfikowane;
  kryterium skali ≥50k wycofane — `OBJECTION: CONFLICT` uznany za
  zasadny [decyzją 09](decisions/09-skala-mccfr-krzywa-przed-forma.md),
  reszta wchodzi kontraktem POKER-27);
  w serwerze LAN, domknięcie F1 audytu POKER-21 (zamknięty, commit
  `e901335`; audyt architekta: 4 findingi informacyjne, wszystkie
  kryteria spełnione);
- [`POKER-26.json`](taskspecs/POKER-26.json) — informacja zwrotna
  przy stole LAN: oczekiwanie na przeciwnika i wynik z perspektywy
  gracza (szkic z weryfikacji użyteczności architekta; POKER-25
  scalony, więc kontrakt gotowy do zatwierdzenia — wchodzi razem
  z uwagami informacyjnymi audytu POKER-25);
- [`POKER-27.json`](taskspecs/POKER-27.json) — krzywa
  jakość-vs-skala MCCFR poza repozytorium i pomiar rozstrzygający
  przy podniesionej mocy, plaster c2c po decyzji 09 (zatwierdzony,
  u kodera);
- [`POKER-28.json`](taskspecs/POKER-28.json) — findingi audytu
  POKER-24/25: wiązanie checkpointu z parametrami biegu, jednokrotne
  parsowanie plików w testach architektury (zatwierdzony; kolejność
  integracji: 28 przed 27).
- [`POKER-29.json`](taskspecs/POKER-29.json) — Linear weighting
  w MCCFR (Linear CFR, waga t); `--averaging linear` domyślnie,
  artefakt produkcyjny nietknięty (zamknięty, commit `a9f7444`).
- [`POKER-30.json`](taskspecs/POKER-30.json) — ICM Malmuth–Harville
  i wypłaty Spin 3-max (2×/3× WTA, 10× 80/20), rozliczenie all-in
  jam/fold; PokerKit odrzucony (decyzja 10).
- [`POKER-31.json`](taskspecs/POKER-31.json) — Nash jam/fold 3-max
  na jednym stanie (fictitious play, Ganzfried & Sandholm 2008);
  payoff ICM/WTA (decyzja 11).
- [`POKER-32.json`](taskspecs/POKER-32.json) — pierwszy backup
  zewnętrzny: E[ICM(s′)] vs cash-out (decyzja 12).
- [`POKER-33.json`](taskspecs/POKER-33.json) — zegar głębokości
  25/15/10/6 bb, jam UTG rośnie na krótkim (decyzja 13).
- [`POKER-34.json`](taskspecs/POKER-34.json) — eskalacja blindów
  i grywalny Spin (zamknięty na linii Spin; audyt 2026-08-28:
  FINDINGI — decyzja 24);
- [`POKER-35.json`](taskspecs/POKER-35.json) — tani trening jam/fold
  na zegarze (zamknięty; audyt: FINDINGI — teza doprecyzowana
  pomiarem w POKER-45);
- [`POKER-36.json`](taskspecs/POKER-36.json) — exploitability
  jam/fold vs best response (zamknięty; audyt: FINDINGI — typowanie
  wyniku naprawione w POKER-44);
- kroki 37–39 (uczciwe ε, plan rozbudowy, próg 7 bb) — bez
  TaskSpeców; odstępstwo odnotowane
  w [decyzji 24](decisions/24-audyt-i-scalenie-linii-spin.md);
- [`POKER-40.json`](taskspecs/POKER-40.json) — first-in open 2.2x
  powyżej 7 bb (zamknięty; audyt: FINDINGI);
- [`POKER-41.json`](taskspecs/POKER-41.json) — ciasny 3bet spot vs
  zamrożony open (zamknięty; audyt: FINDINGI — zakres w decyzji 21
  wygenerowany z kodu w POKER-45);
- [`POKER-42.json`](taskspecs/POKER-42.json) — arena ROI (zamknięty;
  audyt: OBJECTION: INCOMPLETE wobec kontraktu uznany — naprawa
  w POKER-44, pomiary przeliczone w POKER-45);
- [`POKER-43.json`](taskspecs/POKER-43.json) — field exploit
  (zamknięty; audyt: FINDINGI; teza główna nieosiągnięta po pomiarze
  POKER-45);
- [`POKER-44.json`](taskspecs/POKER-44.json) — arena HU przywrócona,
  `poker.spin_arena` wydzielona, INV-P1 w tasowaniu, typowany
  `solve` (zamknięty, commit `52dbe01`; weryfikacja niezależna
  architekta);
- [`POKER-45.json`](taskspecs/POKER-45.json) — wierne rozliczenia
  żetonów i zmierzone liczby (zamknięty, commit `310d592`; sprzeciw
  kodera uznany decyzją 24);
- [`POKER-46.json`](taskspecs/POKER-46.json) — pilot blueprintu po
  DAG-u zegara: zgrubna siatka, PI-FP + CFR+, ex-post ε, pomiar
  budżetu produkcji (zatwierdzony, decyzja 25; u kodera).

## Operator

Prompty ról żyją w korzeniu repozytorium:
[`PROMPT_POKER_ARCHITEKT.md`](../PROMPT_POKER_ARCHITEKT.md),
[`PROMPT_POKER_KODER.md`](../PROMPT_POKER_KODER.md),
[`PROMPT_POKER_AUDYTOR.md`](../PROMPT_POKER_AUDYTOR.md).

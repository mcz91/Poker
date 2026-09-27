# 28. Adjudykacja OBJECTION: CONFLICT z POKER-52 — rozjazdy areny z modelem treningu

Status: obowiązuje. Autor: architekt, 2026-09-04.
Kontekst: OBJECTION kodera POKER-52 (blok POKER-52 w
[CURRENT_STATE](../CURRENT_STATE.md), pkt 4), decyzje
[25](25-blueprint-po-dagu-zegara-pifp-cfrplus.md),
[26](26-moc-pomiaru-areny-redukcja-wariancji.md),
[27](27-rozgrywacz-spin-arena-duplikacja-pod-straza.md).

## 1. Rozstrzygnięcie OBJECTION: kryterium (a) było proxy na fałszywym założeniu architekta

Kontrakt POKER-52 uczynił licznik „fallback w zasięgu siatki" kryterium
blokującym „= 0", uzasadniając to zdaniem architekta „mapowanie krokiem 2
jest totalne, trafienie = błąd mapowania". Pomiar obalił założenie:
odwzorowanie JEST poprawne (`full_layer_state_misses` = 0 na 1 582 048
decyzji, `mass/class/mode_mismatches` = 0), a licznik zapalają rozjazdy
**areny z modelem treningu**, każdy z własnym licznikiem przyczyny.
Proxy mierzyło więc nie to, co miało chronić.

Decyzja: kryterium (a) zostaje zastąpione niezmiennikami bezpośrednimi —
**licznikami błędów odwzorowania** (`full_layer_state_misses`,
`mass_misses`, `class_misses`, `mode_mismatches`; wszystkie blokująco 0,
pod testami) — a liczniki rozjazdów modelu (osiągalność warstw 1–5,
akcja wymuszona, przeskok trybu, kolejność licytacji) są **mierzone
i raportowane z przyczyną**, nie progowane w POKER-52. Aneks w TaskSpec
POKER-52 odsyła tutaj. To nie jest poluzowanie progu dla zieleni:
zamienione zostało kryterium pośrednie na mocniejsze bezpośrednie,
a intencja proxy (błąd mapowania nie ujdzie jako szczegół) jest
egzekwowana silniej niż przedtem.

Lekcja architekta do PUŁAPEK: kryterium-proxy postawione na cudzej
warstwie systemu mierzy także jej rozjazdy; rozdziel liczniki po
przyczynie, zanim ustawisz próg.

## 2. Kwalifikacja czterech rozjazdów

a) **Kolejność licytacji po ponownym otwarciu** (21 348 wejść, 1,349%
   decyzji): `to_act` pyta UTG przed BB po jamie BTN na open UTG —
   wbrew regule pokera „akcja idzie od agresora" i wbrew modelowi
   treningu. To **usterka rozgrywacza jako przyrządu pomiarowego**,
   nie cecha; infoset areny nie istnieje w żadnym poprawnym modelu.
   → naprawa w POKER-54.

   **KOREKTA (2026-09-05, audyt POKER-52, F1):** liczba 21 348 liczy
   tylko pierwszą twarz rozjazdu (UTG pytany przed BB). Trzecia,
   pierwotnie nieliczona twarz: BB pytany PO odpowiedzi UTG na 3bet
   czyta węzeł 8, którego pula modelowa nie zgadza się ze stanem areny
   (dwa różne infosety areny kolapsują do jednego węzła artefaktu) —
   19 458 wejść w biegu BF. Realny zasięg rozjazdu (a) to **40 806
   decyzji (2,579%)**, nie 1,349%. Naprawa kolejności w POKER-54 usuwa
   wszystkie twarze naraz (poprawna kolejność nie wytwarza tych
   infosetów); licznik i test spaceru zużywającego całą historię —
   naprawa w POKER-52 (audyt).

b) **Pytanie o darmowy call** (1 092 wejścia): arena pyta gracza,
   którego dołożenie wynosi zero (jam nie przewyższa jego wkładu),
   i pozwala mu spasować za darmo; trening wymusza wejście maską
   (call za darmo dominuje fold). Pytanie o fold przy zerowym becie
   to również rozjazd z logiką pokera. → naprawa w POKER-54.
   UWAGA: ta zmiana — inaczej niż (a) — **zmienia rozkłady wyników
   SeatBooków** tam, gdzie occurruje (skryptowany gracz mógł pasować
   za darmo); POKER-54 musi zmierzyć skalę wpływu na liczby
   POKER-42/43/48, zanim je unieważni albo utrzyma.

c) **Przeskok trybu na progu 7 bb** (1 098 wejść): stan artefaktu po
   kwantyzacji jest jam/fold, a arena z dokładnych stacków oferuje
   drzewo głębokie. Rozkład jam/fold artefaktu jest **legalnym
   podzbiorem** akcji drzewa głębokiego ({jam, fold} ⊂ {jam, open,
   fold}), więc agent może grać rozkładem stanu artefaktu zamiast
   wołać fallback — wierność artefaktowi bez zmiany rozgrywacza.
   → odwzorowanie po stronie agenta w POKER-55.

d) **Osiągalność warstw 1–5** (12 826 wejść, 0,811%): granica
   artefaktu (trening dochodzi do wczesnych warstw własnym
   skwantowanym łańcuchem), wyceniona: pełna siatka warstw 1–5 =
   +8 696 stanów-warstw (+17,5% biegu produkcyjnego). → decyzja
   PO ponownym pomiarze z naprawami (a)–(c) i domknięciem horyzontu:
   dopiero wtedy będzie widać, ile z wpływu reguły awaryjnej
   (pkt 7 bloku POKER-52) zostało.

## 3. Horyzont zegara: odczyt cyklu punktu stałego — warunek ZWERYFIKOWANY

Propozycja kodera („ręka ≥ 21 czyta warstwę 18 + (ręka − 18) mod 3")
stoi na warunku, że warstwy 18–20 są cyklem punktu stałego horyzontu.
Weryfikacja architekta 2026-09-04: `blinds_for_hand` daje od ręki 18
stały poziom (10/20, poziom 6, `LEVELS[-1]`), więc ręce ≥ 21 żyją
w dokładnie tym samym stacjonarnym cyklu 3 rąk (guzik: warstwa ≡ ręka
mod 3, bo 18 ≡ 0), którego punktem stałym jest brzeg horyzontu
z POKER-49/50 (liczony cyklami do tolerancji ogona). Warstwy 18–20 są
policzone przeciw temu punktowi stałemu, więc odczyt cykliczny jest
ścisły z dokładnością do zmierzonej delty zbieżności ogona (rząd 1e−4
puli; blok POKER-50) — wobec fallbacku check-call→fold, którego wpływ
pkt 7 bloku POKER-52 mierzy w punktach procentowych ROI.
**KOREKTA (2026-09-05, audyt POKER-55, F2):** „rząd 1e−4" było
o rząd optymistyczne. Zmierzona na artefakcie produkcyjnym niezgodność
V między warstwami 18/19/20 opisującymi tę samą sytuację fizyczną (po
przenumerowaniu) wynosi w 3-max średnio 1,09e−3 i maks 6,6e−3 puli
(stacki ≥ 20 żetonów), w HU maks 5,7e−4 — 2× (średnia) do 13× (maks)
ponad deklarację; drugie źródło asymetrii to rozstrzyganie remisów
kwantyzatora po numerze etykiety. Wniosek stoi (wpływ całej reguły
awaryjnej po POKER-55 nieodróżnialny od zera w CI), ale liczbę w
dokumentach podaje się zmierzoną, nie z rzędu wielkości. Decyzja:
wprowadzić w POKER-55, z licznikiem odczytów cyklicznych osobno od
odczytów wprost (rozróżnialność zostaje).
**KOREKTA (POKER-74, 2026-09-26; finding B7
[audytu całego kodu](../AUDYT_2026-09-26.md),
[decyzja 31](31-audyt-calego-kodu-kwalifikacja-i-sprinty.md)):** warunek
„ręce ≥ 21 żyją w tym samym stacjonarnym cyklu 3 rąk" był w modelu
treningu fałszywy. Role trzech żywych liczą się z ręki mod 3, ale guzik
HU (`sorted(żywi)[ręka % 2]`) z ręki mod 2, więc stan modelu na ostatnim
poziomie ma okres lcm(3, 2) = 6 rąk. Brzeg horyzontu domykany cyklem
3 rąk był punktem stałym innej gry (na zawinięciu ten sam gracz HU był
guzikiem dwie ręce z rzędu), a delta zbieżności ogona mierzy zbieżność
iteracji, nie błąd domknięcia — zdanie „odczyt cykliczny jest ścisły
z dokładnością do zmierzonej delty zbieżności ogona" jest nieprawdziwe.
Od POKER-74 `_boundary` liczy cykl 6 rąk
(`solve_grid.BOUNDARY_CYCLE_HANDS`; manifest niesie
`boundary.scheme = "cycle6"`, a wznowienie i import brzegu innego
schematu są odmawiane). Artefakt produkcyjny policzono starym brzegiem;
jego regeneracja jest wejściem operatora (decyzja 31 pkt 3). Zmierzono
(komendy w raporcie commita POKER-74; odniesienie: punkt stały cyklu
6 rąk):

a) **Wiersze HU, konfiguracja produkcyjna podgry HU** — 169 klas, część
   HU tensora produkcyjnego odtworzona co do zliczenia (60 000 prób na
   parę, seed 50; kotwica (AA, 72o) zgodna z `chain_control.json`),
   150 żetonów, krok 2, 10/20, wypłaty 0,8/0,2/0, CFR+ 512/5e−5; podgra
   HU jest zamknięta, więc brzeg liczy się na samych 222 stanach HU:
   stary brzeg odchyla się o **maks 1,37e−3, średnio 7,2e−4** udziału
   sumy wypłat (≈2,7× `tail_tol`); nowy o 4,0e−6.
b) **Wiersze 3-way, siatka testu horyzontu w bramce** (100 żetonów, krok
   25, 25/50, tensor syntetyczny, 0 przejść HU niesymetrycznych na
   zamianę etykiet): stary brzeg **maks 1,74e−3, średnio 9,7e−4**
   (HU 1,24e−3); nowy 8,6e−8. Na siatce e60 przeglądu kontraktu (60
   żetonów, krok 2, 10/20, tensor kontrolny, budżety domyślne): 3-way
   maks 1,9e−2, średnio 6,5e−4 (HU maks 1,3e−3) — tam odniesieniem jest
   brzeg cyklu 6 po 14 cyklach, który sam stoi na delcie ~1,3e−3, więc
   te liczby niosą szum tego rzędu.
c) **Odczyt cykliczny agenta `18 + (ręka − 18) mod 3` jest dla trzech
   żywych przybliżeniem**, nie odczytem ścisłym: w modelu stan ma okres
   6, więc warstwa t i t+3 opisują przy trzech żywych różne gry (inny
   guzik HU po wybiciu). Wielkość przybliżenia |V_t − V_{t+3}| w punkcie
   stałym cyklu 6 w wierszach 3-way: siatka testu horyzontu **maks
   1,96e−3, średnio 1,03e−3**; siatka e60 maks 1,6e−2, średnio 9,7e−4
   (z tym samym zastrzeżeniem szumu co w b).
   Poprawka agenta i jego docstringów oraz reguła guzika HU po wybiciu
   (model ≠ arena) — sprint B (decyzja 31 pkt 2).
d) **Kryterium ogona: podłoga szumu PI-FP, a `converged=False` na e60
   jest wynikiem uczciwym** (runda naprawcza POKER-74, 2026-09-27;
   rozstrzygnięcie OBJECTION z rundy 2 —
   [decyzja 31](31-audyt-calego-kodu-kwalifikacja-i-sprinty.md) pkt 4,
   opcja B). Na siatce e60 delta cyklu 6 nie schodzi do
   `tail_tol` 5e−4. Krzywe wariantów ogona (pętla `_boundary` z wariantem
   podmienionym w skrypcie pomiarowym, 12 cykli, bez stopu na
   `tail_tol`) na e60 i na siatce x60 (60 żetonów, krok 6, 10/20, stacki
   18/18/24, tensor kontrolny, budżety domyślne, 63 stany):

   | ogon (cykle ≥ 2, chyba że zaznaczono) | e60, delta cykli 4–12 | x60, delta cykli 4–12 |
   |---|---|---|
   | stop PI-FP na `fp_tol` (bez zmian) | 1,05–1,48e−3 | 2,0–2,4e−4, od 6. cyklu 8,6e−5 |
   | `fp_tol`/3 | 5,8e−4–1,6e−3 | 1,7e−5–1,1e−3 |
   | `fp_tol`/10 | 3,9e−4–1,8e−3 (≤ 5e−4 tylko w 11.) | 1,3–4,8e−4 |
   | budżet PI-FP zamrożony per stan z cyklu 1 | 9,2e−4–1,3e−3 | — |
   | budżety PI-FP i CFR+ zamrożone per stan z cyklu 1 | 4,6e−4–1,3e−3 (≤ 5e−4 tylko w 5.) | 1,0–5,3e−4 |
   | stałe 384 aktualizacje PI-FP bez stopu, od cyklu 1 | — | 1,9–7,6e−4, od 9. cyklu 7,5e−4 |
   | sufit PI-FP = mediana iteracji cyklu 1 (56), bez stopu | 6,7e−5 w 4., zero w 9. | 1,0e−6 w 4., zero w 8. |

   Wiersze HU zbiegają w każdym zmierzonym wariancie do zera maszynowego
   (najpóźniej w 9. cyklu), więc podłoga siedzi w wierszach 3-way, czyli
   w PI-FP. Nie robi jej sam stop na tolerancji (przesłanka
   rozstrzygnięcia BRAK z rundy 1): stałe 384 aktualizacje i budżety
   zamrożone per stan też oscylują — odwzorowanie cyklu jest nieciągłe
   także przez argmax najlepszej odpowiedzi PI-FP, a zaostrzenie `fp_tol`
   przesuwa szum, nie usuwa go. Zbiega wyłącznie krótki stały sufit
   (mediana cyklu 1), ale
   do punktu stałego słabszego solvera: ε gier etapowych ogona **do
   9,0e−4** (e60; ze stopem na `fp_tol` 2,6–3,2e−4), a jego V(total)
   wychodzi poza rozrzut ostatnich iteratów wariantów dokładniejszych
   (stop na `fp_tol` i `fp_tol`/3, oba zamrożone) o ponad 5e−4 w 34 z 493
   stanów e60, **maks 5,5e−3** (stan (6, 26, 28)) — więcej niż naprawiany
   błąd B7 (pkt a i b); na x60 (te same odniesienia oraz `fp_tol`/10
   i stałe 384) w 2 z 63, maks 1,1e−3. `converged=True` poświadczałby
   tam zbieżność odwzorowania, a nie dokładność brzegu.

   **Stan po POKER-74 (opcja B):** ogon ze stopem PI-FP na tolerancji,
   `tail_tol` 5e−4 i `tail_max_cycles` 12 bez zmian. Na e60 brzeg kończy
   się na suficie z deltą ~1,1–1,5e−3 i **`converged=False` — to wynik
   uczciwy**: flaga mówi, że iteracja nie zeszła pod próg, zamiast
   poświadczać dokładność, której brzeg nie ma; x60 schodzi pod próg
   w 4. cyklu. Delta cyklu 6 stoi na e60 niżej niż delta starego cyklu 3
   na tej samej siatce (1,86–2,89e−3 od 5. do 12. cyklu), a błąd
   strukturalny B7 (wiersze HU, okres modelu) jest usunięty. Czy siatka
   produkcyjna (169 klas) zbiegnie do `tail_tol`, pokaże regeneracja
   (wejście operatora); jeśli nie — warunkowy kontrakt sprintu B: solver
   ogona 3-way ciągły w V (decyzja 31 pkt 2 i 4, obszar decyzji 25).
   Skrypt pomiaru i warianty: raport commita POKER-74 wnoszącego ten
   punkt; wykonanie wariantu z ostatniego wiersza tabeli leży
   nieintegrowane na gałęzi `sprint-a/POKER-74-r2-fpmedian-propozycja`
   (zapis pomiaru, decyzja 31 pkt 4).

## 4. Kolejność linii (aktualizacja mapy)

POKER-54 (rozgrywacz: kolejność od agresora + wymuszony darmowy call;
kotwica zgodności z modelem treningu; zmierzony wpływ na liczby
POKER-42/43/48) → POKER-55 (agent: tryb jam/fold przy przeskoku progu,
odczyt cykliczny horyzontu; PONOWNY pomiar BF/BG/BH — dopiero on mierzy
artefakt, a nie parę artefakt+reguła) → decyzja o warstwach 1–5 →
POKER-53 (AIVAT; przesunięty za 54/55, bo estymator ma mierzyć
naprawiony przyrząd, nie rozjazd). Zakaz z decyzji 26 („bijemy field
$1") i zastrzeżenie pkt 5/7 bloku POKER-52 obowiązują do ponownego
pomiaru.

## 5. Czego ta decyzja nie robi

Nie zmienia drzewa gry (jam/fold/open preflop — decyzja 27), nie
podnosi budżetów solverów, nie otwiera dystrybucji artefaktu, nie
unieważnia zamkniętych pomiarów POKER-42/43/48 przed pomiarem skali
wpływu (pkt 2b).

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

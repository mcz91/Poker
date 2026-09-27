# Pamięć operacyjna ról produktu Poker

Nośnik stanu między sesjami czatu ról (architekt / koder / audytor); nie jest
źródłem statusu produktu — to wyłącznie `docs/CURRENT_STATE.md`. Tu wyłącznie
to, czego repo nie wie. Kopia faktu dostępnego w repo jest błędem; linkuj.

Protokół (koszt czytelnika > koszt pisarza):

- czytaj na starcie sesji; nadpisz swoje wpisy przed zamknięciem;
- limit pliku: 80 linii; nowy wpis wchodzi kosztem najsłabszego;
- format wpisu: `RRRR-MM-DD rola: fakt` — telegraficznie, bez narracji;
- fakt utrwalony w repo (dokument, test, TaskSpec) → usuń wpis;
- zero śladów dialogu, zero „w trakcie" bez wskazania gałęzi/pliku;
- audytor czyta i pisze wyłącznie PUŁAPKI.

## STAN — praca w locie

- 2026-08-08 arch: F2 POKER-1 — odstępstwo decyzją operatora;
  regeneracja equity ≈40 min/4 rdzenie (POKER-12).
- 2026-09-27 arch: sprint B na `…gsfko9` (main = operator; B1 scalona, B2 w
  toku): `…/scratchpad/sprintb/`, `…/sprint-b-POKER-N/`; równolegli agenci —
  tylko unikalne podkatalogi (kolizja `base`, fala 1).

## WĄTKI — otwarte, bez TaskSpec

- 2026-09-27 arch: F2 POKER-5 i F1 POKER-22 utrwalone w PRZEKAZANIE, sekcja 10.

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

- 2026-08-08 operator: autoryzacja stała — main podąża za headem
  integracyjnym po każdym komplecie audytów; wykonuje architekt.
- 2026-08-09 operator: mandat autonomii — na drodze b4/GTO+explo
  architekt kwalifikuje i zatwierdza kontrakty bez pytania (skala,
  prostota architektury); do operatora wracają tylko naruszenia
  niezmienników, nowe produkty/gałęzie i zmiany jego decyzji.

## PUŁAPKI — koszt odkrycia > koszt linii

- Regeneracja unieważnia pomiary przy artefakcie, przepis na domyślnych kłamie
  po ich zmianie — bramka milczy o obu (24; B4: opcje jawnie, parsowane testem;
  74: kalibracja z biegiem 50 = 18 WARSTW, `--tail-cycles 3`); zgodny sha256 nie
  chroni BF/BG/BH (arena 70/71), `config_hash` — schematu brzegu (74).
- Bajt w bajt z katalogu ≠ regeneracja (75): pole manifestu zależne od maszyny
  bez wpisu w `identity.EPHEMERAL` przejdzie bramkę (jedna maszyna), a psuje
  tożsamość między maszynami; zmiana EPHEMERAL/projekcji unieważnia tożsamości.
- ARCHITEKT: próg ilościowy po budżecie z repo (19/24; 47: najpierw krzywa);
  cel-pomiar bez asercji = liczby bez dowodu (42/43); acceptance = lista (5) z
  raportem kodera (bramka przed/po, --durations, plik:linia, PUŁAPKI; 71/75).
- Moduł w allowed_paths ≠ pusty: konsument poza nimi = OBJECTION (POKER-42).
- Nie chronią: asercja werdyktu produkcyjnego, mianownik na replice modelu,
  monotoniczność z pary punktów (35/37/40), tożsamość sprawdzona maszynowo
  (treść: wielkość, trwałość; 84), ε w 1 punkcie (84), zero na artefakcie bramki
  wobec siatki (55); liczby bez asercji model rusza cicho — łapie je sonda (74).
- Okres stanu = lcm WSZYSTKICH reguł ról (3-way mod 3, guzik HU mod 2 → 6);
  krótszy cykl brzegu = punkt stały innej gry, ślepy dla converged i ex-post ε;
  zamiana etykiet HU psuje zbieżność; podłogi ogona (szum PI-FP) nie zdejmie
  fp_tol ani krótki budżet: converged=False (e60) to wynik (74).
- ε ex-post warstwy DAG-u to suma długów warstw za nią (start 97,5%): rozłóż na
  etapowe i odziedziczone, znajdź próg wiążący (47: tolerancja, nie sufit).
- Zielony test z niewłaściwego powodu: `pytest.raises` bez `match` (strażnik czy
  potknięcie piętro niżej? 57); strażnik na surowych napisach ślepy na formy
  równoważne (80); samospójność ślepa na wagi węzłów — kotwica w niezależnej
  wycenie; jedna kolejność argumentów — sprawdź permutacje (84); 1 żeton nie
  odróżni True od 1 (78); mutant ze starszego commita wygasa — na headzie (76).
- Stała suma żetonów ≠ dobre rozliczenie: rangi {wygrany, reszta} w
  `award_allin` przeżyły w 4 miejscach (71: 3, 84: `_three_way`); nowe
  rozliczenie gra seedem inną trajektorię: szukaj od nowa, nie przybijaj jej.
- Zdania porównawcze i ilościowe sprawdzaj jak liczby (47); raport dryfu grepuje
  KAŻDĄ wartość zmienionej asercji w obu zapisach („5 770"/„5770") (71);
  „zmierzone" przy progu = statystyka zbioru asercji, nie mediana z zerami (74);
  trafna liczba z fałszywym wspólnym powodem — powód per pozycja (75).
- Openfold: miara FP nie maleje monotonicznie z N (dołek 3x 2/4 przy 128), a w
  tolerancji ≠ stałe liczby (open 3x 28,9% → 33,9%): N = punkt, OD którego miara
  zostaje w tolerancji; N rusza 3bet książki — „bit w bit" to zbieg (73).
- Przed zmianą gniazd i typów na granicy (76/78) czytaj komentarze `lan_server`,
  `protocol`, `events`, `betting` i testu drenażu w `test_lan_resilience`.

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

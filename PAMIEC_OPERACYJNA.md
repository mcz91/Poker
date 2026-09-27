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
- 2026-09-26 arch: sprint A decyzji 31 na `claude/poker-code-audit-gsfko9`
  (main = operator; stara `…architecture-jw6ukd` = main); równolegli
  agenci — tylko unikalne podkatalogi scratchpadu (kolizja `base`, fala 1).
- 2026-09-04 arch: artefakty produkcyjne w scratchpadzie sesji
  `…/scratchpad/prod/` (tensor, grid2, blueprint.bpk); regeneracja AC–AH, BA.

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

- Zamknięcie zadania aktualizuje „Następny krok" jednym commitem (2/8/25/31–33).
- Regeneracja artefaktu unieważnia pomiary przy nim, a przepis na domyślnych
  narzędzia kłamie po ich zmianie — bramka milczy o obu (24; B4: opcje jawnie,
  parsowane testem; 74: kalibracja z biegiem 50 = 18 WARSTW, `--tail-cycles
  3`). Zgodny sha256 nie chroni pomiarów konsumenta (BF/BG/BH zależą też od
  areny: 70/71), a `config_hash` — schematu brzegu (tylko `scheme`, 74).
- ARCHITEKT: próg ilościowy po budżecie z repo (19/24; 47: najpierw krzywa);
  cel-pomiar bez asercji = liczby bez dowodu (42/43); acceptance = lista (5).
- Moduł w allowed_paths ≠ pusty: konsument poza nimi = OBJECTION (POKER-42).
- Asercja werdyktu produkcyjnego, mianownik na replice modelu ani
  monotoniczność z jednej pary punktów nie chronią zachowania (35/37/40).
- Tabela permutacji w złą stronę przeżywa testy transpozycji (inwolucje),
  psują ją 3-cykle; kotwicz KAŻDĄ oś i tablicę (46: wt2_fold, AA 0,917→0,083).
- Okres stanu = lcm WSZYSTKICH reguł ról (3-way mod 3, guzik HU mod 2 → 6);
  krótszy cykl brzegu = punkt stały innej gry, ślepy dla converged i ex-post ε;
  zamiana etykiet HU wymaga kwantyzacji równoważnej na permutację i psuje
  zbieżność. Podłogi ogona (szum PI-FP) nie zdejmie fp_tol ani krótki budżet
  (słabszy solver): converged=False (e60) to wynik; rozstrzyga regeneracja (74).
- ε ex-post warstwy DAG-u to suma długów warstw za nią (start 97,5%): rozłóż
  na etapowe i odziedziczone, znajdź próg wiążący (47: tolerancja, nie sufit).
- `pytest.raises(Błąd)` bez `match` nie odróżnia strażnika od potknięcia
  piętro niżej (57: czytnik bez kontroli slotów v2 przeżył bramkę — audyt).
- Stała suma żetonów ≠ dobre rozliczenie: rangi {wygrany, reszta} w
  `award_allin` przeżyły w 4 miejscach (71: 3, `_three_way` — sprint B); nowe
  rozliczenie gra seedem inną trajektorię: szukaj od nowa, nie przybijaj jej.
- Zdania porównawcze i słowa ilościowe sprawdzaj jak liczby (47); raport dryfu
  grepuje KAŻDĄ wartość zmienionej asercji w obu zapisach („5 770"/„5770") po
  dokumentach stanu, nie tylko wyniki komend (71); „zmierzone" przy progu =
  statystyka zbioru asercji, nie mediana zbioru z zerami (74: ~7×, nie ~40×).
- Zero na artefakcie bramki ≠ zero na siatce produkcyjnej: krok siatki bywa
  przyczyną pudła (55 pkt 6: 0 przy kroku 50, 94 przy 2); zmiana modelu rusza
  po cichu liczby bez asercji (minimum, sufit) — łapie to sonda artefaktu (74).
- Openfold: miara FP nie maleje monotonicznie z N (3x 2/4: dołek przy 128), a
  miara w tolerancji ≠ stałe liczby (open 3x 28,9% → 33,9%, 128 → 512): N =
  punkt, OD którego miara zostaje w tolerancji (`stable_checkpoint`); N rusza
  też 3bet ciasnej książki areny (spot z openu) — „bit w bit" to zbieg (73).

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

# Pamięć operacyjna ról produktu Poker

Nośnik stanu między sesjami czatu ról (architekt / koder / audytor).
Nie jest źródłem statusu produktu — to wyłącznie `docs/CURRENT_STATE.md`.
Tu wyłącznie to, czego repo nie wie. Kopia faktu dostępnego w repo jest
błędem; linkuj.

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

- 2026-08-08 arch: F2 audytu POKER-5 — księgowość żetonów w `_view` (betting)
  równoległa do projekcji; unifikacja przy kontrakcie w `poker.betting`.
- 2026-08-10 arch: F1 audytu POKER-22 — equity-przeciw-polu zduplikowane;
  API w preflop_equity osobnym kontraktem (dotyka abstrakcji artefaktu).

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

- 2026-08-08 operator: autoryzacja stała — main podąża za headem
  integracyjnym po każdym komplecie audytów; wykonuje architekt.
- 2026-08-09 operator: mandat autonomii — na drodze b4/GTO+explo
  architekt kwalifikuje i zatwierdza kontrakty bez pytania (skala,
  prostota architektury); do operatora wracają tylko naruszenia
  niezmienników, nowe produkty/gałęzie i zmiany jego decyzji.

## PUŁAPKI — koszt odkrycia > koszt linii

- Zamknięcie zadania aktualizuje też „Następny krok" w CURRENT_STATE
  (dryf: POKER-2/8/25, nagłówek 31/32/33) — jednym commitem.
- Regeneracja artefaktu unieważnia pomiary przy nim, a przepis oparty na
  domyślnych narzędzia kłamie po zmianie domyślnej — bramka milczy o obu
  (24; B4: każda opcja jawnie, parsowana testem). Zgodny sha256 nie chroni
  pomiarów konsumenta: ROI i liczniki BF/BG/BH zależą też od areny (70/71).
- ARCHITEKT: próg ilościowy po budżecie z repo (19/24; 47: najpierw krzywa);
  cel-pomiar bez asercji = liczby bez dowodu (42/43); acceptance = lista (5).
- Moduł w allowed_paths ≠ pusty: konsument poza allowed_paths =
  OBJECTION, nie zadanie (POKER-42).
- Asercja werdyktu produkcyjnego, mianownik na replice modelu ani
  monotoniczność z jednej pary punktów nie chronią zachowania (35/37/40).
- Tabela permutacji w złą stronę przeżywa testy transpozycji (inwolucje),
  psują ją 3-cykle; kotwicz KAŻDĄ oś i tablicę (46: wt2_fold, AA 0,917→0,083).
- ε ex-post warstwy DAG-u to suma długów warstw za nią (start 97,5%): rozłóż
  na etapowe i odziedziczone, znajdź próg wiążący (47: tolerancja, nie sufit).
- `pytest.raises(Błąd)` bez `match` nie odróżnia strażnika od potknięcia
  piętro niżej (57: czytnik bez kontroli slotów v2 przeżył bramkę — audyt).
- Stała suma żetonów ≠ dobre rozliczenie: rangi {wygrany, reszta} dla
  `award_allin` przeżyły w 4 miejscach (3 naprawił 71, `_three_way` — sprint
  B). Po zmianie rozliczenia seed scenariusza testu gra inną trajektorię —
  szukaj seeda od nowa, nie przybijaj nowej po cichu (71: 10x seed 9 → 90).
- Zdania porównawcze i słowa ilościowe sprawdzaj jak liczby (47: poprawne
  liczby, fałszywe zdanie o nich); raport dryfu grepuje KAŻDĄ wartość
  zmienionej asercji w obu zapisach („5 770"/„5770") po dokumentach stanu, nie
  tylko wyniki komend (71 r1 pominął 16 w CURRENT_STATE + PRZEKAZANIE:381).
- Zero na artefakcie bramki ≠ zero na siatce produkcyjnej: krok siatki
  bywa przyczyną pudła (POKER-55 pkt 6 — 0 przy kroku 50, 94 przy 2).
- Openfold: miara FP nie maleje monotonicznie z N (3x 2/4: dołek przy 128), a
  miara w tolerancji ≠ stałe liczby (open 3x 28,9% → 33,9%, 128 → 512): N =
  punkt, OD którego miara zostaje w tolerancji (`stable_checkpoint`); N rusza
  też 3bet ciasnej książki areny (spot z openu) — „bit w bit" to zbieg (73).

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

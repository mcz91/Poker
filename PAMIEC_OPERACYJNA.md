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

- 2026-08-08 arch: tylko tu: F2 POKER-1 — odstępstwo decyzją operatora;
  regeneracja equity ≈40 min/4 rdzenie (POKER-12).
- 2026-08-28 arch: gałąź integracyjna =
  `claude/poker-project-architecture-jw6ukd` (dfmo3y nieaktywna);
  weryfikacja niezależna (czysty venv 3.13) przed scaleniem. Gałęzi
  koderów POKER-26/27/28 brak na zdalnym. Raporty researchu drogi
  Pluribusa żyją w transkrypcie sesji architekta (decyzja 25 streszcza).

## WĄTKI — otwarte, bez TaskSpec

- 2026-08-08 arch: F2 informacyjny audytu POKER-5 — księgowość żetonów
  w `_view` (betting) równoległa do projekcji; rozważyć unifikację przy
  najbliższym kontrakcie dotykającym `poker.betting`.
- 2026-08-10 arch: F1 audytu POKER-22 — formuła equity-przeciw-polu
  zduplikowana; publiczne API w preflop_equity osobnym kontraktem
  (refaktor dotyka abstrakcji, od której zależy artefakt).

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
- Regeneracja artefaktu unieważnia pomiary przy nim, a bramka tego nie
  łapie (POKER-24: 20 607→20 971 infosetów).
- Frozen dataclass ≠ izolacja — niezaufany agent za granicę procesu.
- ARCHITEKT: kryterium ilościowe po oszacowaniu budżetu z repo (19/24;
  wzorzec 47: zmierz krzywą, potem próg); cel-pomiar bez asercji =
  liczby bez dowodu (42/43); acceptance to checklista (5).
- Moduł w allowed_paths ≠ pusty: konsument poza allowed_paths =
  OBJECTION, nie zadanie (POKER-42).
- Asercja werdyktu produkcyjnego, mianownik na replice modelu ani
  monotoniczność z jednej pary punktów nie chronią zachowania (35/37/40).
- Tabela permutacji w złą stronę przeżywa testy na transpozycjach
  i kolapsach (inwolucje) — psują się dopiero 3-cykle. Kotwicz każdą oś
  i KAŻDĄ tablicę osobno: wt2_fold został bez kotwicy, dwie mutacje osi
  przeżywają 343 testy, equity AA leci 0,917→0,083 (POKER-46, audyt).
- ε ex-post warstwy DAG-u to suma długów warstw za nią (stan startowy
  97,5%) — rozłóż ε na etapowe i odziedziczone i znajdź próg wiążący
  (POKER-47: tolerancja, nie sufit iteracji — wbrew diagnozie arch.).
- Koszt po drabince w jednym biegu: zeruj zegar na restart (POKER-47).
- Dowód skryptem w scratchpadzie nie chroni następnego biegu: liczba
  w dokumencie = niezmiennik w teście.
- Zdania porównawcze i słowa ilościowe („monotonicznie") sprawdzaj na
  artefakcie tak jak liczby — POKER-47 miał obok siebie poprawne liczby
  i fałszywe zdanie o nich (audyt).
- mypy widzi tylko `files` z pyproject (od POKER-49: src, tests,
  tools/blueprint) — kod w pozostałych `tools/` przechodzi tylko ruff
  i pytest; „bramka zielona" ≠ „typy sprawdzone" poza tym zbiorem.

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

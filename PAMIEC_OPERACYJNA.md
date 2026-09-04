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
- 2026-08-28 arch: gałąź integracyjna =
  `claude/poker-project-architecture-jw6ukd`; weryfikacja niezależna
  przed scaleniem; gałęzi koderów 26/27/28 brak; raporty researchu
  w transkrypcie sesji architekta (decyzja 25 streszcza).
- 2026-09-04 arch: artefakty produkcyjne żyją w scratchpadzie sesji
  `…/scratchpad/prod/` (tensor + grid2 + blueprint.bpk — ten ostatni
  to wejście POKER-52); regeneracja = AC–AH i BA z CURRENT_STATE.

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
- Regeneracja artefaktu unieważnia pomiary przy nim, a bramka tego
  nie łapie (POKER-24).
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
- Horyzont nie ma checkpointu per cykl — restart w trakcie kosztuje
  wszystkie policzone cykle (POKER-50: 16,2 rdzenio-h); jednostką
  wznowienia jest dopiero warstwa.
- Dowód skryptem w scratchpadzie nie chroni następnego biegu: liczba
  w dokumencie = niezmiennik w teście.
- Zdania porównawcze i słowa ilościowe („monotonicznie") sprawdzaj na
  artefakcie tak jak liczby — POKER-47 miał obok siebie poprawne liczby
  i fałszywe zdanie o nich (audyt).
- Książka 0/1 nie testuje strumienia rng — dodatkowy pobór przeżywa test
  „port nie zmienia przebiegu" (POKER-52: 0/30 vs 8/30 na mieszanej; audyt).

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

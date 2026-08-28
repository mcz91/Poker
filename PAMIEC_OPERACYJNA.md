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
  koderów POKER-26/27/28 brak na zdalnym; research drogi Pluribusa
  w toku, decyzja przed pierwszym kontraktem treningu.

## WĄTKI — otwarte, bez TaskSpec

- 2026-08-08 arch: F2 informacyjny audytu POKER-5 — księgowość żetonów
  w `_view` (betting) równoległa do projekcji; rozważyć unifikację przy
  najbliższym kontrakcie dotykającym `poker.betting`.
- 2026-08-10 arch: F1 audytu POKER-22 — formuła equity-przeciw-polu
  zduplikowana; publiczne API w preflop_equity osobnym kontraktem
  (refaktor dotyka abstrakcji, od której zależy artefakt).
- 2026-08-28 arch: spin_arena ma własny rozgrywacz obok
  poker.betting/table (audyt POKER-42; świadomie poza kontraktami
  44/45) — kwalifikacja przed każdą rozbudową spin_arena.

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

- 2026-08-08 operator: autoryzacja stała — main podąża za headem
  integracyjnym po każdym komplecie audytów; wykonuje architekt.
- 2026-08-09 operator: mandat autonomii — na drodze b4/GTO+explo
  architekt kwalifikuje i zatwierdza kontrakty bez pytania (skala,
  prostota architektury); do operatora wracają tylko naruszenia
  niezmienników, nowe produkty/gałęzie i zmiany jego decyzji.

## PUŁAPKI — koszt odkrycia > koszt linii

- Zamknięcie zadania i zatwierdzenie TaskSpeca N+1 aktualizuje też
  „Następny krok" w CURRENT_STATE — dryf przy POKER-2/8/25 i nagłówek
  przy POKER-31/32/33; numer i opis jednym commitem.
- Regeneracja artefaktu unieważnia pomiary przy nim w CURRENT_STATE,
  a bramka tego nie łapie (POKER-24: 20 607→20 971 infosetów).
- Kryterium acceptance wyliczające zakres czytaj jak checklistę
  asercji — deklaracja ≠ dowód (POKER-5: turn/river bez asercji).
- Frozen dataclass ≠ izolacja: testy przecieku INV-P3/P4 dowodzą
  szczelności API, nie bezpieczeństwa — izolację niezaufanego agenta
  stawiać na granicy procesu (adapter, INV-P7).
- Asercja pod `if` w teście deterministycznym to uśpiona ochrona —
  przybijaj wynik bezwarunkowo (POKER-7).
- Artefakt-moduł Pythona: sufit ~5 MB; koszt bramki dominuje
  `ast.parse` w testach architektury, nie mypy (POKER-24).
- ARCHITEKT: kryterium ilościowe wyłącznie po oszacowaniu budżetu
  z danych repo (POKER-19, POKER-24); liczba w dokumencie wymaga
  komendy odtwarzającej i liczby iteracji; kontrakt z celem-pomiarem
  bez asercji pomiaru produkuje liczby bez dowodu (POKER-42/43).
- Moduł w allowed_paths ≠ pusty: przed przepisaniem policz konsumentów
  grepem; konsument poza allowed_paths = OBJECTION: INCOMPLETE, nie
  zadanie (POKER-42 skasował arenę POKER-13).
- Ręcznie budowane stany $EV gubią żetony (stacki po blindach jako
  wkłady, całe stacki wołających), a „suma = pula" na wektorach ICM to
  tożsamość — niezmiennikiem jest suma żetonów terminala (POKER-30–33).
- Asercja werdyktu produkcyjnego, mianownik na replice modelu
  i monotoniczność z jednej pary punktów nie chronią zachowania
  (POKER-35/37/40; naprawy w POKER-45).

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

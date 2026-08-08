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

- 2026-08-08 arch: gałąź integracyjna = `claude/poker-architecture-dfmo3y`;
  zawiera POKER-1 (`5a74ab9`) i POKER-2 (`bd3473c`), oba zweryfikowane
  niezależnie przez architekta (czysty venv 3.13, pełna bramka zielona,
  stożek zmian w allowed_paths). Do main wchodzi jednym scaleniem po
  audycie.
- 2026-08-08 arch: audyt POKER-1 zamknięty werdyktem FINDINGI
  (końcowe brzmienie u operatora): F1 blokujący (rozjazd bramki) →
  kontrakt POKER-4, wchodzi PO POKER-3 (zależność przez tests/);
  F2 istotny — wada kontraktu POKER-1 (allowed_paths bez pamięci),
  załatana od POKER-2; F3 informacyjny (dryf CURRENT_STATE) —
  sprzątnięty. Gałęzie audytora (ccef820) i kodera (4ac36f1) scalone
  do integracyjnej. Diff POKER-2 czeka na audyt.
- 2026-08-08 arch: POKER-3 (`68df34e`) i POKER-4 (`bd6dd56`) zamknięte,
  zweryfikowane niezależnie (czysty venv 3.13, verification zielone;
  dla POKER-4 także dowód: wstrzyknięty błąd typu w tests/ łapany
  gołym `mypy`) i scalone sekwencyjnie do integracyjnej. Bramka README
  znów pełnoprawna — F1 zmechanizowany testem `tests/test_repo_gate.py`.
- 2026-08-08 koder: audyty POKER-2 (CZYSTY, pełna przestrzeń C(52,5))
  i POKER-3 (OBJECTION: CONFLICT — seed w publicznym HandStarted;
  wykonanie czyste; wątek przejęty przez architekta niżej) zamknięte,
  raporty u operatora. Audyt POKER-5 (diff 14c5b3f..fa6a25c):
  FINDINGI — F1 blokujący (granice kwot bez asercji na turn/river)
  naprawiony testem strażniczym na gałęzi kodera, czeka na scalenie;
  F2 informacyjny (księgowość żetonów w _view równolegle do projekcji
  — rozważyć przy najbliższym kontrakcie w obszarze); silnik
  zweryfikowany symulacją 4000 rozdań bez rozbieżności.
- 2026-08-08 koder: POKER-6 zamknięty na gałęzi kodera (start
  z d21b093, po drodze cherry-pick domknięcia F1 POKER-5); OBJECTION
  audytu POKER-3 zamknięty: seed przeniesiony do DeckSeeded
  (EngineOnly), HandStarted niesie samą konfigurację, test przecieku
  obejmuje pola, repr i serializację widoku. Czeka na scalenie
  i audyt.
- 2026-08-08 arch: audyt POKER-4 (29d65f5..bd6dd56) zamknięty werdyktem
  CZYSTY z reprodukcją dowodów; F1 audytu POKER-1 zamknięty mechanizmem.
  F2 zamknięty decyzją operatora 2026-08-08: odstępstwo uznane (wada
  kontraktu POKER-1, naprawa systemowa od POKER-2). Wszystkie findingi
  audytu POKER-1 zamknięte.
- 2026-08-08 arch: POKER-5 zamknięty (`fa6a25c`), zweryfikowany
  niezależnie (czysty venv 3.13, verification zielone: ruff 0, mypy
  0/17 plików, 92 passed; przegląd logiki licytacji bez zastrzeżeń)
  i scalony do integracyjnej. Audyt POKER-5 w toku świeżym kontekstem.
- 2026-08-08 arch: POKER-6 zatwierdzony
  ([`docs/taskspecs/POKER-6.json`](docs/taskspecs/POKER-6.json)) —
  zamyka OBJECTION audytu POKER-3 (seed) testem przecieku; koder
  startuje ze świeżej sesji z heada integracyjnego, nie z main.

## WĄTKI — otwarte, bez TaskSpec

- 2026-08-08 arch: mono- vs multi-repo dla produktów (pokerroom,
  trener, bot) odroczone do pierwszej kwalifikacji produktu — decyzja
  [`01`](docs/decisions/01-trzy-produkty-jeden-rdzen.md), pkt 3.
(wątek seeda zamknięty w POKER-6: DeckSeeded/EngineOnly + test
przecieku — fakt utrwalony w repo, wpis usunięty protokołem)

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

(pusto — decyzje 01 i 02 utrwalone w `docs/decisions/`; TaskSpeki
w `docs/taskspecs/`)

## PUŁAPKI — koszt odkrycia > koszt linii

- Systemowy `python3` to 3.11 (< wymaganego 3.12); venv stawiaj na
  `python3.13`. Pełną bramkę wylicza `README.md`.
- mypy strict wymaga markera `src/poker/py.typed` — bez niego bramka
  czerwona mimo poprawnych typów.
- `allowed_paths` TaskSpeca musi obejmować `PAMIEC_OPERACYJNA.md`
  (protokoły ról nakazują jej zapis); kolizja kontraktu z protokołem
  = OBJECTION, nie cichy zapis.
- Kryterium acceptance wyliczające zakres („na każdej ulicy", „obu
  przypadków") czytaj jak checklistę asercji: w POKER-5 granice kwot
  miały testy tylko preflop+flop, turn/river zostały bez asercji mimo
  deklaracji pełnego pokrycia w opisie commita — deklaracja ≠ dowód.

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

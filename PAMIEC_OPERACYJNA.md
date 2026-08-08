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
- 2026-08-08 koder: audyt POKER-2 (diff 00dcba7..bd3473c) zamknięty
  werdyktem CZYSTY — wyczerpująca weryfikacja ewaluatora na pełnej
  przestrzeni C(52,5) i 7462 klasach siły; raport u operatora; bez
  nowych PUŁAPEK. Audyt POKER-3 (diff 02331f9..68df34e) w toku świeżym
  kontekstem, werdykt trafi do operatora. Audyt POKER-4 zaległy.

## WĄTKI — otwarte, bez TaskSpec

- 2026-08-08 arch: mono- vs multi-repo dla produktów (pokerroom,
  trener, bot) odroczone do pierwszej kwalifikacji produktu — decyzja
  [`01`](docs/decisions/01-trzy-produkty-jeden-rdzen.md), pkt 3.
- 2026-08-08 arch: `HandStarted` niesie seed i ma widoczność Public
  (`src/poker/events.py`) — seed rekonstruuje całą talię, więc kontrakt
  POKER-5 (widok agenta) MUSI wykluczyć seed z widoku każdego miejsca,
  a test przecieku objąć go wprost; rozważyć widoczność EngineOnly.

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

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

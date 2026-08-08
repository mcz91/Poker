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
- 2026-08-08 arch: POKER-3 zatwierdzony
  ([`docs/taskspecs/POKER-3.json`](docs/taskspecs/POKER-3.json)),
  realizacja nierozpoczęta — koder startuje z heada integracyjnego,
  nie z main; do czasu POKER-4 zieleń dowodzi się wyłącznie komendami
  `verification` TaskSpeca, nie bramką z README.
- 2026-08-08 koder: POKER-3 zamknięty na gałęzi kodera
  `claude/poker-repo-instrukcja-gez88z` (start z 02331f9); czeka na
  scalenie. Audyt POKER-2 uruchomiony świeżym kontekstem, werdykt
  trafi do operatora.

## WĄTKI — otwarte, bez TaskSpec

- 2026-08-08 arch: mono- vs multi-repo dla produktów (pokerroom,
  trener, bot) odroczone do pierwszej kwalifikacji produktu — decyzja
  [`01`](docs/decisions/01-trzy-produkty-jeden-rdzen.md), pkt 3.

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

(pusto — decyzje 01 i 02 utrwalone w `docs/decisions/`; TaskSpeki
w `docs/taskspecs/`)

## PUŁAPKI — koszt odkrycia > koszt linii

- Systemowy `python3` to 3.11 (< wymaganego 3.12); venv stawiaj na
  `python3.13`. Pełną bramkę wylicza `README.md`.
- mypy strict wymaga markera `src/poker/py.typed` — bez niego bramka
  czerwona mimo poprawnych typów.
- Gołe `mypy` (config `packages=["poker"]`) NIE typuje `tests/` — błąd
  typu w testach przechodzi na zielono; do czasu POKER-4 dowodem jest
  wyłącznie `mypy --strict src tests` z `verification` TaskSpeca.
- `allowed_paths` TaskSpeca musi obejmować `PAMIEC_OPERACYJNA.md`
  (protokoły ról nakazują jej zapis); kolizja kontraktu z protokołem
  = OBJECTION, nie cichy zapis.

## DŁUG — DebtRecords czekające na TaskSpec

- 2026-08-08 arch: hatchling (build backend, commit `5a74ab9`) bez
  powodu i planu usunięcia w opisie commita (konstytucja, reguła 9) —
  uzasadnienie utrwalić przy najbliższej zmianie `pyproject.toml`
  (naturalnie: raport POKER-4).

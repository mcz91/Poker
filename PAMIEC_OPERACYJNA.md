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

- 2026-08-08 arch: POKER-1 zamknięty; bramkę 5a74ab9 zweryfikowałem
  niezależnie (czysty venv 3.13: ruff 0, mypy strict src+tests 0,
  1 test passed) — deklaracja kodera potwierdzona. Diff POKER-1 czeka
  na audyt świeżym kontekstem przed scaleniem do main.
- 2026-08-08 arch: gałąź integracyjna = `claude/poker-architecture-dfmo3y`
  (zawiera scaloną gałąź kodera `claude/poker-repo-instrukcja-gez88z`);
  do main wchodzi jednym scaleniem po audycie.
- 2026-08-08 arch: POKER-2 zatwierdzony
  ([`docs/taskspecs/POKER-2.json`](docs/taskspecs/POKER-2.json)) —
  koder startuje z heada gałęzi integracyjnej, nie z main.
- 2026-08-08 koder: POKER-2 zamknięty na gałęzi kodera
  `claude/poker-repo-instrukcja-gez88z` (start z 00dcba7); czeka na
  scalenie do integracyjnej. Audyt POKER-1 uruchomiony świeżym
  kontekstem, werdykt trafi do operatora.

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

## DŁUG — DebtRecords czekające na TaskSpec

(pusto)

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
- 2026-08-08 koder: audyt POKER-1 uruchomiony świeżym kontekstem,
  werdykt trafi do operatora. Diff POKER-2 też czeka na audyt.
- 2026-08-08 arch: POKER-3 zatwierdzony
  ([`docs/taskspecs/POKER-3.json`](docs/taskspecs/POKER-3.json)) —
  koder startuje z heada integracyjnego `bd3473c`, nie z main.

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
- gołe `mypy` (config `packages=["poker"]`) nie widzi `tests/` — błąd
  typu w testach przechodzi na zielono; dowodem jest wyłącznie
  `mypy --strict src tests` z `verification` TaskSpeca.
- TaskSpec bez `PAMIEC_OPERACYJNA.md` w `allowed_paths` konfliktuje
  z protokołem ról (zapis pamięci obowiązkowy); POKER-2 już ją ma —
  pilnuj w każdym następnym.

## DŁUG — DebtRecords czekające na TaskSpec

(pusto)

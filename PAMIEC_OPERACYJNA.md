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

- 2026-08-08 arch: gałąź integracyjna = `claude/poker-architecture-dfmo3y`.
  POKER-1…6 zamknięte, każde zweryfikowane niezależnie przez architekta
  (czysty venv 3.13, verification zielone) i scalone sekwencyjnie;
  statusy i commity w [`docs/README.md`](docs/README.md).
- 2026-08-08 arch: komplet audytów POKER-1…6, wszystkie findingi
  blokujące i OBJECTION zamknięte z dowodami: POKER-1 FINDINGI (F1
  mechanizm test_repo_gate, F2 odstępstwo uznane decyzją operatora,
  F3 sprzątnięty); POKER-2 CZYSTY; POKER-3 OBJECTION seeda zamknięty
  w POKER-6 (DeckSeeded/EngineOnly); POKER-4 CZYSTY; POKER-5 FINDINGI
  (F1 domknięty testem strażniczym af758b8, potwierdzony audytem;
  F2 informacyjny → WĄTKI); POKER-6 CZYSTY (F1 informacyjny →
  PUŁAPKA o granicy gwarancji). Main zsynchronizowany z headem
  integracyjnym fast-forwardem za jawną autoryzacją operatora
  2026-08-08.
- 2026-08-08 arch: POKER-7 zamknięty (`462576d` + domknięcie audytu
  `4a01775`), zweryfikowany niezależnie (czysty venv 3.13, verification
  zielone: ruff 0, mypy 0/23 plików, 114 passed) i scalony do
  integracyjnej. Audyt POKER-7: F1 informacyjny naprawiony, 960 meczów
  weryfikacji niezależnej bez naruszeń — komplet audytów POKER-1…7.
- 2026-08-08 arch: POKER-8 zatwierdzony
  ([`docs/taskspecs/POKER-8.json`](docs/taskspecs/POKER-8.json)) —
  koder startuje ze świeżej sesji z heada integracyjnego, nie z main.

## WĄTKI — otwarte, bez TaskSpec

- 2026-08-08 arch: mono- vs multi-repo dla produktów (pokerroom,
  trener, bot) odroczone do pierwszej kwalifikacji produktu — decyzja
  [`01`](docs/decisions/01-trzy-produkty-jeden-rdzen.md), pkt 3.
- 2026-08-08 arch: F2 informacyjny audytu POKER-5 — księgowość żetonów
  w `_view` (betting) równoległa do projekcji; rozważyć unifikację przy
  najbliższym kontrakcie dotykającym `poker.betting`.

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

- 2026-08-08 operator: autoryzacja stała — main podąża za headem
  gałęzi integracyjnej fast-forwardem po każdym komplecie audytów
  scalonych zadań; wykonuje architekt bez pytania.

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
- Frozen dataclass ≠ izolacja: object.__setattr__/__delattr__
  i introspekcja ramek (sys._getframe) omijają każdą czysto-pythonową
  „szczelność" w procesie; testy przecieku INV-P3/P4 dowodzą
  szczelności API, nie bezpieczeństwa — izolację niezaufanego agenta
  stawiać na granicy procesu (adapter, INV-P7).
- Asercja pod `if` w teście deterministycznym (np. `if reason is BUST:
  assert…`) to uśpiona ochrona: przy przybitym seedzie przebieg jest
  jeden — przybijaj wynik bezwarunkowo, inaczej regresja zmieniająca
  przebieg przechodzi na zielono (POKER-7, test stacka poniżej blindu).

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

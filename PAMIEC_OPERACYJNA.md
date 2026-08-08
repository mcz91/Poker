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
  POKER-1…7 zamknięte i scalone sekwencyjnie, każde zweryfikowane
  niezależnie (czysty venv 3.13, verification zielone); komplet audytów
  POKER-1…7 domknięty z dowodami (OBJECTION seeda z POKER-3 zamknięty
  w POKER-6; F1 POKER-5 testem af758b8; F1 POKER-7 naprawiony, 960
  meczów bez naruszeń); main = head integracyjny (ff za autoryzacją
  stałą). Statusy i commity: [`docs/README.md`](docs/README.md).
- 2026-08-08 arch: POKER-8 zatwierdzony
  ([`docs/taskspecs/POKER-8.json`](docs/taskspecs/POKER-8.json)) —
  koder startuje ze świeżej sesji z heada integracyjnego, nie z main.
- 2026-08-08 arch: projekt kroku 8 na gałęzi
  `claude/poker-interface-design-17xgxr`: decyzja 03 + szkice
  POKER-9/POKER-10 (bez `approved` — nie zatwierdzam własnych
  TaskSpeców). Przekazanie POKER-9 koderowi dopiero po zieleni
  POKER-8 i zatwierdzeniu operatora; POKER-10 po zieleni POKER-9.

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

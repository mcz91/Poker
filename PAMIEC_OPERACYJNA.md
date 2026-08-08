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
  każde zadanie weryfikowane niezależnie przed scaleniem (czysty venv
  3.13); statusy i commity w [`docs/README.md`](docs/README.md).
- 2026-08-08 arch: komplet audytów POKER-1…7 zamknięty; fakty tylko
  tu: F2 audytu POKER-1 — odstępstwo uznane decyzją operatora; audyt
  POKER-7 potwierdzony 960 meczami niezależnymi.
- 2026-08-08 arch: audyty POKER-8/9/11/12 zaległe; main dosunięty do
  e0b0f2b jednorazowym poleceniem operatora — stała autoryzacja
  (komplet audytów) dalej obowiązuje.
- 2026-08-08 arch: POKER-12: pełna regeneracja macierzy equity ≈40 min
  na 4 rdzeniach — test reprodukcji bierze 2 pary.
- 2026-08-08 arch: POKER-17 (hardening F1) zatwierdzony — koder
  startuje ze świeżej sesji z heada integracyjnego (`31ce370`),
  nie z main; werdykty 15/16 w indeksie i opisie commita scalającego.
- 2026-08-08 koder: POKER-17 zrealizowany ze startu `9831691` na
  gałęzi `claude/new-session-aazf0r`; czeka na audyt.

## WĄTKI — otwarte, bez TaskSpec

- 2026-08-08 arch: mono- vs multi-repo dla produktów (pokerroom,
  trener, bot) odroczone do pierwszej kwalifikacji produktu — decyzja
  [`01`](docs/decisions/01-trzy-produkty-jeden-rdzen.md), pkt 3.
- 2026-08-08 arch: F2 informacyjny audytu POKER-5 — księgowość żetonów
  w `_view` (betting) równoległa do projekcji; rozważyć unifikację przy
  najbliższym kontrakcie dotykającym `poker.betting`.
- 2026-08-08 arch: pomiar referencyjny b4.2: clone vs rule −316.25
  BB/100, CI [−534.35, −98.16] (20 par×100 rozdań, seed 7) — podstawa
  b4.3; test wolny (rekomendacja audytu) rozstrzygnąć przy b4.3.

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

- 2026-08-08 operator: autoryzacja stała — main podąża za headem
  gałęzi integracyjnej fast-forwardem po każdym komplecie audytów
  scalonych zadań; wykonuje architekt bez pytania.

## PUŁAPKI — koszt odkrycia > koszt linii

- Zatwierdzenie TaskSpeca N+1 aktualizuje też „Następny krok"
  w `CURRENT_STATE.md` — dryf indeks↔stan powtórzył się przy POKER-2
  (`00dcba7`) i POKER-8 (`b18dace`); oba dokumenty jednym commitem.
- mypy strict wymaga markera `src/poker/py.typed` — bez niego bramka
  czerwona mimo poprawnych typów.
- Wygenerowany moduł danych w `src/` nosi pełny przepis regeneracji
  we własnych metadanych (jak equity POKER-12); przepis tylko w opisie
  commita = artefakt nieodtwarzalny z repo (wagi POKER-16, F1 audytu).
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

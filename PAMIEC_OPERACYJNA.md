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
  weryfikacja niezależna (czysty venv 3.13) przed każdym scaleniem.
- 2026-08-08 arch: audyty POKER-1…7 komplet (tylko tu: F2 POKER-1 —
  odstępstwo decyzją operatora; POKER-7: 960 meczów); POKER-8/9/11/12
  zaległe, main na e0b0f2b — stała autoryzacja obowiązuje.
- 2026-08-08 arch: regeneracja macierzy equity ≈40 min/4 rdzenie (POKER-12).
- 2026-08-10 arch: POKER-20/21 scalone po audycie (statusy w indeksie);
  POKER-22 (c2a) zatwierdzony — koder ze świeżej sesji z heada.
- 2026-08-10 koder: POKER-22 (na `092b761`) i na jego szczycie
  POKER-23 na `claude/new-session-aazf0r`; integracja 22 przed 23.
  POKER-23 na autoryzację z czatu — kopia kontraktu w repo bez pola
  `approved`, do ostemplowania. Trening MCCFR: ~2 min 20 s na 1000
  iteracji przy stackach 100, więc bieg kontrolny bierze stacki 12.

## WĄTKI — otwarte, bez TaskSpec

- 2026-08-08 arch: F2 informacyjny audytu POKER-5 — księgowość żetonów
  w `_view` (betting) równoległa do projekcji; rozważyć unifikację przy
  najbliższym kontrakcie dotykającym `poker.betting`.
- 2026-08-10 arch: F1 audytu POKER-21 — kod stołu to licznik;
  najbliższy kontrakt sieciowy: kod losowy z seedowanego RNG serwera.

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

- 2026-08-08 operator: autoryzacja stała — main podąża za headem
  gałęzi integracyjnej fast-forwardem po każdym komplecie audytów
  scalonych zadań; wykonuje architekt bez pytania.
- 2026-08-09 operator: mandat autonomii — na drodze b4/GTO+explo
  architekt kwalifikuje i zatwierdza kontrakty bez pytania (skala,
  prostota architektury); do operatora wracają tylko naruszenia
  niezmienników, nowe produkty/gałęzie i zmiany jego decyzji.

## PUŁAPKI — koszt odkrycia > koszt linii

- Zatwierdzenie TaskSpeca N+1 aktualizuje też „Następny krok"
  w `CURRENT_STATE.md` — dryf indeks↔stan powtórzył się przy POKER-2
  (`00dcba7`) i POKER-8 (`b18dace`); oba dokumenty jednym commitem.
- mypy strict wymaga markera `src/poker/py.typed` — bez niego bramka
  czerwona mimo poprawnych typów.
- Determinizm bajt w bajt artefaktu trenowanego zależnością zakłada
  ten sam build tej zależności — nieprzypięty `numpy>=2.0` może
  czerwienić testy pochodzenia/reprodukcji po aktualizacji (POKER-19);
  przypnij wersję w extras albo utrwal założenie w decyzji.
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
- socket.makefile duplikuje deskryptor: zamknięcie samego gniazda bez
  pliku nie wysyła FIN — readline po drugiej stronie wisi (POKER-21).

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

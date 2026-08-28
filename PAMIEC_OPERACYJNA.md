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
  Tylko tu: F2 POKER-1 — odstępstwo decyzją operatora; regeneracja
  equity ≈40 min/4 rdzenie (POKER-12).
- 2026-08-28 arch: linia Spin `poker-43-field` (POKER-30–43, decyzje
  10–23) niescalona i bez śladu audytów — main nie podąża bez ich
  kompletu. Gałęzi koderów 26/27/28 brak; POKER-27 warunkowy (dec. 18).

## WĄTKI — otwarte, bez TaskSpec

- 2026-08-08 arch: F2 informacyjny audytu POKER-5 — księgowość żetonów
  w `_view` (betting) równoległa do projekcji; rozważyć unifikację przy
  najbliższym kontrakcie dotykającym `poker.betting`.
- 2026-08-10 arch: F1 audytu POKER-22 — formuła equity-przeciw-polu
  zduplikowana; publiczne API w preflop_equity osobnym kontraktem
  (refaktor dotyka abstrakcji, od której zależy artefakt).

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

- 2026-08-08 operator: autoryzacja stała — main podąża za headem
  integracyjnym po każdym komplecie audytów; wykonuje architekt.
- 2026-08-09 operator: mandat autonomii — na drodze b4/GTO+explo
  architekt kwalifikuje i zatwierdza kontrakty bez pytania (skala,
  prostota architektury); do operatora wracają tylko naruszenia
  niezmienników, nowe produkty/gałęzie i zmiany jego decyzji.

## PUŁAPKI — koszt odkrycia > koszt linii

- Zatwierdzenie TaskSpeca N+1 i każde zamknięcie zadania aktualizuje
  też „Następny krok" w `CURRENT_STATE.md` — dryf powtórzył się przy
  POKER-2, POKER-8 i POKER-25; oba dokumenty jednym commitem.
- mypy strict wymaga markera `src/poker/py.typed` — bez niego bramka
  czerwona mimo poprawnych typów.
- Regeneracja artefaktu unieważnia pomiary opisane przy nim
  w `CURRENT_STATE.md`, a bramka tego nie łapie (testy pilnują tylko
  `INFOSETS == len(STRATEGY)`): POKER-24 podmienił strategię
  (20 607→20 971 infosetów), zostawiając wyniki areny sprzed podmiany.
- Kryterium acceptance wyliczające zakres („na każdej ulicy") czytaj
  jak checklistę asercji: w POKER-5 turn/river zostały bez asercji mimo
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
- Artefakt jako moduł Pythona ma sufit ~5 MB (przy 20 MB bramka rośnie
  z 23 s do 57 s); koszt zdominowany przez `pytest` — `ast.parse`
  artefaktu 5x w testach architektury, nie przez mypy (POKER-24).
- ARCHITEKT: kryterium ilościowe (skala, próg, limit czasu) wpisuj do
  kontraktu wyłącznie po oszacowaniu budżetu z danych repo — druga
  instancja klasy (POKER-19 F1, POKER-24 OBJECTION); trzecia to
  `BLOCKED` wg reguły 7 konstytucji.

## DŁUG — DebtRecords czekające na TaskSpec

(pusto — uzasadnienie hatchling utrwalone w raporcie commita POKER-4)

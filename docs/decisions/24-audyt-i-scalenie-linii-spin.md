# 24 — Audyt i scalenie linii Spin (POKER-30–43 + naprawy 44–45)

Operator 2026-08-28: „audyt i scal". Linia Spin (gałęzie `poker-30-*`
… `poker-43-*`, 13–17 sierpnia) powstała poza główną pętlą ról:
kontrakty zatwierdzane przez tę samą rolę, która je wykonywała
(„PRODUCT"), zero audytów, jeden commit na zadanie bez raportów
behavior/hygiene (reguła 13), push przy czerwonej bramce (reguły 2 i 8),
kroki 37 i 39 zmieniły kod bez TaskSpeca (reguły 3 i 5).

## Audyt (2026-08-28, świeży kontekst, trzy transze)

Werdykty per zadanie w raportach transz (30–33, 34–39, 40–43);
najważniejsze findingi:

1. znikające żetony w rozliczeniach `utg_shove_ev` (fold), `_allin_two`,
   `_three_way` — opublikowana krzywa jam-vs-depth była artefaktem;
2. POKER-42: arena ROI wpisana w zajęty moduł `poker.arena` skasowała
   scaloną arenę HU POKER-13 (8 modułów testowych bez importu, CLI
   `--series` martwe) — `OBJECTION: INCOMPLETE` audytora wobec
   kontraktu **uznany**: kontrakt nie rozstrzygał losu konsumentów
   spoza `allowed_paths`;
3. naruszenie INV-P1: tasowanie `list(FULL_DECK)` (frozenset) —
   wyniki zależne od PYTHONHASHSEED, pomiary ROI nieodtwarzalne;
4. martwa ręka heads-up przy wybitym graczu na BB (36% rąk pomiaru
   bez ruchu żetonów);
5. deklarowane pomiary („+16% vs $1 fish, CI>0") nieodtwarzalne
   i po przeliczeniu fałszywe;
6. `OBJECTION: INCOMPLETE` audytora wobec POKER-33 (verification bez
   ruff/mypy) — **uznany**;
7. typowa czerwień: `dict[str, object]` jako wynik `solve` → lawina
   błędów mypy i zepsute `type: ignore`.

## Rozstrzygnięcia

1. Naprawy kontraktami **POKER-44** (arena HU przywrócona z main,
   `poker.spin_arena` osobno, INV-P1, martwa ręka, typowany `solve`,
   zieleń bramki; commit `52dbe01`) i **POKER-45** (wierne rozliczenia,
   wzmocnione asercje, liczby wymienione na zmierzone z komendami;
   commit `310d592`). Obie bramki zielone, zweryfikowane niezależnie.
2. `OBJECTION: CONFLICT` kodera w POKER-45 **uznany**: kryterium
   „przybij odwrócenie monotoniczności na 8/16 i 10/20" opierało się
   na liczbach audytu zmierzonych na wadliwym kodzie; po naprawie jam
   rośnie monotonicznie (38.7 → 40.0 → 40.6 przy 12 iter,
   potwierdzone przez architekta). Utrwalono pomiar, nie artefakt.
3. Odstępstwa przyjęte do wiadomości, bez przepisywania historii:
   brak raportów w commitach 30–43 (kompensowany audytem i tym
   dokumentem), kroki 37/39 bez kontraktów (kod pozostaje, obowiązek
   kontraktu przed kodem przypomniany), edycja pamięci operacyjnej
   spoza `allowed_paths` w POKER-45 (protokół pamięci ma pierwszeństwo).
4. Stan celu produktowego po uczciwym pomiarze: „nie-ryba na $1"
   **niedowiedzione** — field exploit vs skryptowany $1-ish fish
   +4.1%, CI (−11.6, +19.7) obejmuje zero (N=320); vs always-jam
   +16.3%, CI (+0.2, +32.3) — ledwie dodatni. Moc pomiaru jest
   niewystarczająca; patrz „Następny krok" w CURRENT_STATE.
5. Scalenie do `main` po zamknięciu tego dokumentu, zgodnie ze stałą
   autoryzacją operatora (2026-08-08) i poleceniem z 2026-08-28.

## Które gałęzie ta decyzja zamyka albo czyni droższymi?

Żadnej — z dowodem: pokerroom odzyskał zniszczoną arenę HU i CLI
`--series` bez zmian API; trener-replay nietknięty (historia zdarzeń
bez zmian); GTO-ML zyskuje wierne rozliczenia ICM (dane treningowe bez
artefaktów). Otwarty koszt: duplikacja rozgrywacza `poker.spin_arena`
względem silnika zdarzeniowego (wątek w pamięci operacyjnej) — do
osobnej kwalifikacji, zanim spin_arena urośnie.

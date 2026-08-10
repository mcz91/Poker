# Decyzja 07 — c2: równowaga przez seedowany MCCFR na abstrakcji; mieszanie bez stanu

Status: obowiązuje · 2026-08-10 · decyzja architekta w ramach mandatu
autonomii operatora (2026-08-09)

## Kontekst

Trzy punkty pomiarowe klonowania przy tej samej arenie (20 par × 100
rozdań, seed 7): klon liniowy −316.25 i −281.30 (cechy v2, korpus
3,9×), MLP −347.62 BB/100 vs rule; MLP vs klon liniowy — CI obejmuje
zero. Wniosek zweryfikowany audytem POKER-19: sufit wyznacza sygnał
uczący (nauczyciel), nie cechy, dane ani architektura modelu. Krok c2
decyzji [`06`](06-b43-zaleznosci-w-narzedziach-droga-gto-explo.md):
uczenie ponad nauczyciela.

## Decyzja

1. **Metoda c2: Monte Carlo CFR (external sampling) w self-play na
   abstrakcji gry.** Minimalizacja żalu zbiega do przybliżonej
   równowagi (kierunek „GTO") bez nauczyciela i bez sieci —
   najprostsza metoda o znanych gwarancjach zbieżności. Trening
   w `tools/` (numpy dozwolony, decyzja 06), w całości seedowany
   i deterministyczny.
2. **Abstrakcja jest jawnym, wersjonowanym modułem produktu** (czysty
   stdlib, bez I/O): karty → kubełki equity (preflop z istniejących
   169 klas; postflop kubełki z ewaluatora i equity Monte Carlo
   z seedem), akcje → skończony zbiór (fold / check-call / bet pół
   puli / bet pula / all-in — parametry, INV-P6). Mapowanie
   widok → infoset wyłącznie z informacji widocznych z miejsca
   (INV-P3); wersja abstrakcji jest częścią pochodzenia artefaktu.
3. **Artefakt strategii: tabela infoset → rozkład akcji** jako
   wygenerowane dane z pełnym przepisem pochodzenia (wzorzec
   POKER-17) i dwustopniowym dowodem odtwarzalności (decyzja 06,
   pkt 3: mały łańcuch kontrolny w bramce, pełna regeneracja jedną
   komendą poza nią). Liczba iteracji jest parametrem skali.
4. **Strategia mieszana bez stanu.** Równowaga wymaga mieszania
   akcji; agent strategii losuje akcję **deterministyczną funkcją
   (seed agenta, widok)** — stabilne haszowanie pól widoku, bez RNG
   trzymanego między wywołaniami. Decyzja pozostaje czystą funkcją
   widoku i parametru konstrukcji (INV-P4, bezstanowość z decyzji
   05 pkt 3 zachowana), ten sam widok i seed dają tę samą akcję
   (INV-P8, replay i testy bez zmian), a różne rozdania dają różne
   losowania. To jest „osobna decyzja o strategii losowej"
   zapowiedziana w non_goals POKER-8.
5. **Plastry c2**, każdy własnym kontraktem: **(c2a)** abstrakcja
   kart i akcji z testami własności (pełne pokrycie wejść,
   determinizm, granica informacyjna); **(c2b)** trener MCCFR
   w `tools/` + artefakt strategii + agent tabelowy w rejestrze CLI,
   pomiar w arenie vs wszyscy dotychczasowi agenci; **(c2c)** skala
   treningu (iteracje, wznowienia, koszt) — dopiero po działającym
   c2b i jego pomiarze.
6. **Miarą c2 jest arena.** Oczekiwanie wobec c2b: wynik vs rule
   istotnie lepszy od klonów (wyjście ponad sufit klonowania);
   brak poprawy → wracamy do metody nową decyzją, nie do strojenia
   w ciemno.

## Którą gałąź (pokerroom / trener / GTO-ML) ta decyzja zamyka albo czyni droższą?

Żadnej nie zamyka. **GTO-ML**: kontrakt wykonawczy drogi; ryzykiem
jest jakość abstrakcji ograniczająca jakość równowagi — mitygacja:
abstrakcja wersjonowana i wymienialna bez zmiany portu `Agent`
i formatu artefaktu. **Trener**: tanieje — rozkłady akcji per infoset
to gotowy substrat podpowiedzi i analizy odchyleń. **Pokerroom**:
neutralna — wszystko za portem `Agent`; mieszanie bez stanu nie
wnosi zegara ani globalnej losowości do silnika (INV-P1).

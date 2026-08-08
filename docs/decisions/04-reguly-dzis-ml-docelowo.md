# Decyzja 04 — Etap (b): proste reguły dziś, silnik GTO/explo na ML docelowo

Status: obowiązuje · 2026-08-08 · decyzja operatora (architekt
rekomendował klasyczny solver push/fold — operator wybrał drogę ML;
odrzucona rekomendacja odnotowana dla historii rozumowania)

## Kontekst

Etap (b) kierunku bot (decyzja
[`03`](03-kierunek-bot-interfejs-czlowieka.md)) wymaga wskazania drogi
do silnego agenta. Operator rozstrzygnął: **bez klasycznego solvera** —
w horyzoncie bliskim grają proste, czytelne reguły decyzyjne
(rozwijane z dzisiejszego `RuleAgent`), a docelowym silnikiem jest
**model uczony na historiach rozdań (ML), grający w duchu GTO
z warstwą eksploatacji**. To jest dokładnie gałąź „bot / GTO z ML"
z decyzji 01, wchodząca tym samym portem Agent (INV-P4, INV-P8:
model ML to nie LLM; inferencja deterministyczna).

## Decyzja

1. Podetapy drogi, każdy własnym kontraktem:
   - **(b1)** macierz equity all-in 169 klas preflop jako dane w repo
     (POKER-12, zatwierdzony) — cecha wejściowa i dla lepszych reguł,
     i dla przyszłego ML;
   - **(b2)** arena porównawcza agentów: mecze A vs B na dużej liczbie
     rozdań z lustrzanymi seedami (duplicate) i wynikiem w BB/100
     z przedziałem ufności — bo zarówno warianty reguł, jak i przyszłe
     modele trzeba mierzyć, zanim się je uzna za lepsze;
   - **(b3)** masowa generacja danych self-play (partie eksportów
     historii) jako korpus treningowy;
   - **(b4)** ML właściwe: trening offline (narzędzia poza pętlą gry),
     deterministyczna inferencja w agencie portem Agent — osobna
     kwalifikacja, bo wymaga pierwszych zależności poza standard
     library (reguła 9 konstytucji: powód + plan usunięcia)
     i decyzji o formacie modelu w repo.
2. Ulepszenia agentów regułowych są dozwolone w każdej chwili, ale
   wyłącznie z pomiarem w arenie (b2) — „lepszy" znaczy wygrywa
   w arenie, nie „wygląda lepiej".
3. Eksploatacja (warstwa explo) wchodzi po pierwszym mierzalnym
   modelu bazowym — jej zysk mierzy arena przeciw agentom o znanych
   słabościach.

## Którą gałąź (pokerroom / trener / GTO-ML) ta decyzja zamyka albo czyni droższą?

Żadnej nie zamyka. Bot/GTO-ML: otwiera wprost — to jego droga. Trener:
tanieje (arena i korpus self-play to gotowa infrastruktura analizy).
Pokerroom: neutralny — wszystko za portem Agent i w narzędziach,
silnik nietknięty. Ryzyko tej drogi: ML bez baseline'u o znanej
jakości trudniej uczciwie ocenić niż solver z policzalną
exploitability — mitygacja: arena (b2) z rygorem statystycznym jest
warunkiem wejścia ML, a klasyczny solver pozostaje otwartą opcją
powrotu, gdyby pomiary ML rozczarowały.

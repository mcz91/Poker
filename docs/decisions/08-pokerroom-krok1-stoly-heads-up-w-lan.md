# Decyzja 08 — Otwarcie gałęzi pokerroom: krok 1 to stoły heads-up w sieci lokalnej

Status: obowiązuje · 2026-08-10 · decyzja operatora (zamówienie: „gra
w kilka osób na różnych urządzeniach w lokalnej sieci") + architektura
kroku w ramach mandatu autonomii

## Kontekst

To pierwsze zamówienie funkcji gałęzi pokerroom (decyzja
[`01`](01-trzy-produkty-jeden-rdzen.md)): ludzie przy stole, wiele
urządzeń, sieć. Silnik licytacji jest heads-up przez jawne
uproszczenie INV-P5 (side potów nie ma), a granice INV-P4/P7 były
projektowane dokładnie na ten moment: sieć wchodzi jako adapter,
człowiek portem `Agent`, silnik zostaje nietknięty.

## Decyzja

1. **Mono-repo, adapter-first.** Pokerroom rusza w tym repozytorium
   jako warstwa adapterów nad nietkniętym silnikiem; osobne
   repozytorium produktu dopiero, gdy pokerroom wymusi własny cykl
   wydań — to rozstrzyga (w tym zakresie) wątek odroczony w decyzji
   01, pkt 3.
2. **Krok 1 — serwer wielu stołów heads-up w LAN (POKER-21):**
   jeden proces serwera (stdlib: TCP + typowany, wersjonowany
   protokół JSON Lines) prowadzi równolegle wiele niezależnych
   stołów po 2 graczy; gracze na innych urządzeniach łączą się
   klientem terminalowym, tworzą stół (kod stołu) albo dołączają
   kodem; możliwy stół człowiek vs agent z rejestru. „Kilka osób"
   w kroku 1 znaczy: wiele par przy wielu stołach jednocześnie.
3. **Separacja informacji na granicy procesu.** Serwer jest
   autorytatywny: do klienta wychodzi wyłącznie serializacja jego
   `PlayerView` i zdarzenia widoczne z jego miejsca — INV-P3
   egzekwowane tam, gdzie PUŁAPKA o izolacji każe: na granicy
   procesu, nie w strukturach Pythona; test przecieku bada pełny
   strumień bajtów do klienta.
4. **Multiway przy jednym stole — jawnie poza krokiem 1.** Więcej
   niż 2 osoby przy jednym stole wymaga zniesienia uproszczenia
   INV-P5 w maszynie licytacji (side poty, showdown wielostronny) —
   to osobna kwalifikacja silnika, uruchamiana zamówieniem
   operatora, nie krokiem sieciowym.
5. **Granica zaufania kroku 1:** sieć lokalna zaufana; kod stołu
   jest jedyną kontrolą dostępu; bez szyfrowania, kont
   i uwierzytelniania; bez timerów decyzji (silnik bez zegara,
   INV-P1 — limity czasu to przyszła funkcja adaptera). Internet
   i twardsze zaufanie — osobna kwalifikacja.
6. **Priorytet:** zamówienie operatora ma pierwszeństwo przed
   autonomicznym planem — kolejność integracji: POKER-20 →
   POKER-21 (pokerroom krok 1) → c2a (decyzja 07).

## Którą gałąź (pokerroom / trener / GTO-ML) ta decyzja zamyka albo czyni droższą?

- **pokerroom**: otwiera wprost pierwszym działającym krokiem;
  architektura serwera stołów jest N-miejscowa w protokole
  (zdarzenia i eksport już są N-miejscowe), więc przyszły multiway
  wymienia silnik pod spodem, nie protokół;
- **trener**: tanieje — historie stołów ludzkich eksportowane
  istniejącym formatem to przyszłe dane replay/analizy prawdziwych
  graczy;
- **GTO-ML**: opóźniony o jeden kontrakt (koszt priorytetu
  operatora, świadomy); nic nie jest zamknięte — c2a wchodzi zaraz
  po kroku 1, a stoły LAN dadzą kiedyś arenę człowiek vs model.

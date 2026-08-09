# Decyzja 06 — b4.3: zależności ML w narzędziach, inferencja w stdlib, droga do GTO+explo na skalę

Status: obowiązuje · 2026-08-09 · decyzja architekta w ramach mandatu
autonomii operatora (2026-08-09: „max autonomiczne działanie,
z nastawieniem na skalę, GTO+explo, keep it simple while complex" —
mandat utrwalony w pamięci operacyjnej, sekcja DECYZJE Z CZATU)

## Kontekst

Warunek decyzji [`05`](05-b4-plastrami-dane-baseline-zaleznosci.md)
dla b4.3 jest spełniony dwoma punktami pomiarowymi przy zamrożonej
rodzinie modelu (POKER-16: −316.25 BB/100 vs rule; POKER-18 z cechami
v2 i korpusem 3,9×: −281.30, przedziały ufności nakładają się) —
sufit wyznacza podejście, nie dane. Cel produktu pozostaje: silnik
GTO z warstwą eksploatacji (decyzja
[`04`](04-reguly-dzis-ml-docelowo.md)), grający portem `Agent`.

## Decyzja

1. **Granica zależności — prostota przy złożoności.** Pakiet produktu
   (`src/poker/`) pozostaje bezzależnościowy na stałe: inferencja
   każdego agenta to czysty stdlib nad wygenerowanym modułem danych
   wag z kompletnym przepisem pochodzenia (mechanizm POKER-17).
   Zależności ML żyją wyłącznie w `tools/` (trening) i w extras
   deweloperskich (testy reprodukcji). Pierwsza zależność: **numpy**
   — powód: trening sieci na korpusach o skali jest niewykonalny
   w czystym Pythonie w koszcie bramki; plan usunięcia: ograniczenie
   do `tools/` i extras — wymiana lub usunięcie nie dotyka pakietu
   produktu (reguła 9 konstytucji, egzekwowana per commit kodera).
2. **Plastry drogi do GTO+explo**, każdy z pomiarem w arenie:
   - **(c1)** — POKER-19: MLP-klon na danych v2 — trzeci punkt
     pomiarowy izolujący zmienną „model" (czy nieliniowość rusza
     sufit klonowania);
   - **(c2)** — uczenie ponad nauczyciela: self-play w stronę
     równowagi (rdzeń „GTO") — metoda (styl regret-based / neural
     self-play) dostanie osobną kwalifikację i dokument decyzji po
     pomiarze c1;
   - **(c3)** — warstwa eksploatacyjna po pierwszym mierzalnym
     modelu bazowym (decyzja 04, pkt 3), mierzona w arenie przeciw
     agentom o znanych słabościach.
3. **Skala kontra bramka.** Szybka bramka jest prawem. Dowody
   odtwarzalności artefaktów trenowanych na skali są dwustopniowe
   (wzorzec macierzy equity POKER-12): w bramce deterministyczna
   reprodukcja małego łańcucha kontrolnego; pełna regeneracja
   artefaktu produkcyjnego jedną udokumentowaną komendą jako
   uruchamiany jawnie proces poza bramką. Pomiary referencyjne
   pełnej mocy (długie serie areny) żyją jako jawnie uruchamiane
   komendy z przybitymi seedami, dokumentowane w CURRENT_STATE —
   to zamyka wątek „testu wolnego" z audytu POKER-15/16.
4. **Determinizm bez wyjątków.** Trening z zależnościami podlega tym
   samym prawom co dotąd: seedowana inicjalizacja, deterministyczny
   przebieg, ten sam wsad → bajt w bajt ten sam artefakt; INV-P8
   (zero LLM, deterministyczna inferencja) bez zmian.

## Którą gałąź (pokerroom / trener / GTO-ML) ta decyzja zamyka albo czyni droższą?

Żadnej nie zamyka. **GTO-ML**: otwiera wprost — to jego kontrakt
wykonawczy; ryzyko, że i MLP-klon utknie przy nauczycielu, jest
wkalkulowane: wtedy c1 kupuje dowód, że następny koszt to sygnał
uczący (c2), nie architektura. **Trener**: neutralna-otwierająca —
narzędzia treningowe i pomiarowe są jego przyszłą infrastrukturą
analizy; granica „inferencja w stdlib" trzyma produkt lekkim.
**Pokerroom**: neutralna — wszystko za portem `Agent`; pakiet
produktu bez zależności pozostaje tani w osadzeniu w dowolnym
przyszłym środowisku wielostołowym.

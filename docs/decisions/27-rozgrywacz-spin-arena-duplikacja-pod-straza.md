# 27 — Rozgrywacz spin_arena: duplikacja uzasadniona, ale pod strażą

Audyt POKER-42 (F8) wskazał, że `poker.spin_arena` prowadzi własny
rozgrywacz ręki (talia, licytacja, showdown) obok silnika zdarzeniowego
`poker.betting`/`poker.table` — i że zduplikowana logika rozjechała się
z oryginałem, zawierając błędy, których oryginał nie miał (martwa ręka
HU, tasowanie frozensetu). Kontrakty POKER-44/45 naprawiły błędy, ale
świadomie zostawiły samą duplikację do kwalifikacji architekta. Ten
dokument ją rozstrzyga.

## Dlaczego duplikat w ogóle istnieje

Silnik zdarzeniowy nie umie rozegrać ręki Spina: `HeadsUpHand` wymaga
dokładnie N=2 (jawne uproszczenie INV-P5), a Spin to licytacja
trzyosobowa z side potami. Jedyną drogą usunięcia duplikatu jest
maszyna licytacji multiway w silniku — czyli decyzja otwierająca
gałąź pokerroom-multiway, której nikt nie zamówił i która dotyka
rdzenia produktu (zdarzenia, projekcja, widoki, testy replay).
Wniosek: dziś wybór nie brzmi „duplikat albo czystość", tylko
„duplikat pod strażą albo wielka przebudowa rdzenia bez zamówienia".

## Decyzja

1. **Duplikat zostaje** — jako świadomy, ograniczony kompromis, nie
   jako precedens. Uzasadnienie kosztowe: rozgrywacz obsługuje
   wyłącznie preflopowe drzewo Spina i jest w całości pod testami
   (suma żetonów, martwa ręka, determinizm międzyprocesowy).
2. **Zakres rozgrywacza jest zamrożony** na obecne drzewo akcji
   (jam/fold, open 2.2x, 3bet-jam, call). Każde rozszerzenie —
   flop, nowe sizingi, więcej ulic — wymaga NAJPIERW kwalifikacji
   multiway silnika, nie kolejnej dobudówki w arenie. To jest granica
   architektury, nie preferencja.
3. **Rozliczenia tylko przez wspólne prymitywy.** Rozgrywacz nie ma
   prawa mieć drugiej implementacji rozliczeń — wypłaty idą przez
   `poker.spin.award_allin` i pochodne (dziś tak jest; ta decyzja
   czyni to wymogiem).
4. **Kotwica krzyżowa z silnikiem.** Tam, gdzie oba światy umieją
   rozegrać tę samą sytuację — ręka heads-up po foldzie trzeciego
   gracza — test porównuje rozliczenie rozgrywacza spin_arena
   z `HeadsUpHand` przy identycznych decyzjach. Wchodzi najpóźniej
   z następnym kontraktem dotykającym rozgrywacza (nie z POKER-48,
   którego celem jest moc pomiaru, nie poprawność rozgrywki).

## Którą gałąź ta decyzja zamyka albo czyni droższą?

Żadnej nie zamyka. Pokerroom-multiway pozostaje otwarty — pkt 2 czyni
go wręcz jawną bramką dla każdego wzrostu Spina poza preflop, więc
decyzja o nim zapadnie wtedy, gdy będzie miała zamawiającego, a nie
przypadkiem w arenie. Trener i GTO-ML nietknięte. Koszt jawny: do
czasu multiway każda zmiana reguł rozgrywki wymaga dyscypliny
„najpierw prymitywy w poker.spin, potem konsument w arenie".

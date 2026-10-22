# hu_gto — solver fazy heads-up Spin & Go

Narzędzie do **nauki i analizy offline** fazy HU Spina: SB = button vs BB, chipEV bez ante
(dla Spinów winner-takes-all chipEV = $EV), stack efektywny w bb. Składa się z solvera
preflop (DCFR na 169 klasach), klienta solvera postflop (b-inary postflop-solver przez
sterownik `hupf`), pętli punktu stałego preflop ↔ postflop i narzędzia zapytań `spin_gto.py`.

**Nie do użycia w trakcie gry na salach.** Narzędzie nie ma I/O stołów, a konsultowanie
solvera w czasie rozdania łamie regulaminy RTA sal. Tylko analiza po sesji i nauka.

## Stan jakości (uczciwie)

Są dwie pętle preflop ↔ postflop. `integ/run_fp.py` to pętla spike'u (iteracja punktu stałego
na uboższym drzewie); z jej rundy R4 pochodzą dane narzędzia `spin_gto.py` i liczby tej sekcji.
`integ/run_fpa.py` to jej następca (fictitious play na drzewie `gw_tree`, sekcja „Fictitious
play”); liczby jakości dla niego podaje sekcja „Pilot FP 15 bb”, gdy pilot jest policzony.

Liczby niżej to pomiary z etapu spike (2026-10-19…20, 4 rdzenie), chyba że oznaczono
„wniosek”. Dane, na których je zmierzono (rundy pętli, cache solve'ów), nie są w repo —
regeneruje je `integ/run_fp.py` (sekcja „Pętla”). Skrypty pomiarów są w `integ/` i `tool/`.

| Część | Stan | Liczby |
|---|---|---|
| Push/fold (drzewo jam/fold) | **zgodny z HRC** | max \|Δ\| 0,52 pp na siatce 1–25 bb co 0,5 bb; przy 6/8/10/15/20/25 bb agregaty SB jam / BB call ≤ 0,07 pp; per ręka przy 10/15/20/25 bb ≤ 0,5 pp |
| Pełny preflop (limp / raise / iso / 3bet-jam) | **NIE jest bliski GTO** | luka best response profilu R4 w modelu z liśćmi przeliczonymi solverem: 0,099 / 0,168 bb/rękę przy 15 / 20 bb na flopach pętli, 0,124 / 0,203 na 12 flopach spoza próbki (`integ/crit_oos.py`); cel ≤ 0,01 bb/rękę przekroczony 10–20 razy |
| Zbieżność pętli preflop ↔ postflop | **brak (2-cykl)** | R3→R4 zmienia częstości o 10,8–12,9 pp; runda R5 policzona na zakresach R4 wraca do R3 (\|Δ root\| ≤ 3,1 pp przy 15 bb) |
| Charty 13×13 per ręka | **niewiarygodne** | artefakty próbki 12 flopów (przy 15 bb wszystkie ręce z 7 lub T grają raise 2x); naruszenia dominacji w węźle BB vs 2x: 242 / 134 / 188 par przy 10 / 15 / 20 bb (`integ/dom.py`); akcja najlepsza na innej próbce flopów zgodna w 52–73% kombinacji |
| Agregaty vs GTO Wizard | odchyłki poza szumem | BB vs min-raise przy 20 bb pasuje 38–39% (GW 21%); BB jamuje vs limp 21–28% (GW 9–11%); limp SB przy 10 bb 49% (średnia bootstrapu, R4 55,9%) wobec 62–65% (GW, Gecko) |

Dlaczego tak (zmierzone objawy, przyczyna częściowo wnioskiem):

- Luka 1,5–1,9e-5 bb/rękę raportowana przez solver preflop to tylko warunek stopu DCFR w grze
  z modelem liścia, nie jakość rozwiązania.
- Model liścia jest addytywny, `R = E + a_sb[h] − a_bb[v]`, i nie zależy od składu zakresu,
  więc preflop wybiera skrajne, prawie czyste podziały („bang-bang”), a przeliczenie postflopu
  na nowych zakresach je karze — stąd 2-cykl. Błąd ekstrapolacji modelu: 0,03–0,08 bb/rękę
  przy przebudowie zakresu SB, bias +0,17–0,19 bb dla SB w pulach podbitych.
- Liście liczone są tanim drzewem `flopsmall` (turn/river tylko all-in) na 12 flopach z poprawką
  drzewa policzoną raz na 4 flopach; SE EV klasy w liściu 0,11–0,54 bb, a u ok. 50% kombinacji
  SB przy 15 bb \|EV limp − EV raise\| < 0,1 bb — rozstrzygnięcie per ręka leży w szumie.
- Drzewo preflop jest uboższe niż w referencjach (jeden rozmiar iso 3,5 bb, brak małego 3betu);
  że stąd biorą się odchyłki BB, to wniosek, nie pomiar.

Czasy (zmierzone):

- preflop z booka: p50 9 ms (pełne wywołanie CLI ok. 0,2 s); głębokość spoza siatki 10/15/20 bb
  liczy się na żywo w 1–3 s;
- flop na żywo: 18–189 s (4 wątki, n = 6, p50 54 s), trudne spoty 15–20 bb 164–249 s (2 wątki) —
  **nie jest interaktywny**, a biblioteki flopów nie ma;
- turn z flopem w cache: 0,3–1,6 s; turn na nowym flopie = flop + turn (165–252 s);
- river: < 0,1 s.

Ograniczenia narzędzia: działa na drzewie i danych pętli spike'u (R4 z `run_fp.py`), wyników
fictitious play jeszcze nie eksportuje; rozmiary spoza drzewa preflop (np. open 3x,
iso ≠ 3,5 bb) kończą się błędem; postflop rozmiar człowieka jest **po cichu** mapowany na
najbliższy rozmiar drzewa
(overbet 150–400% liczony jak bet 50–66%); EV wypisywane z dokładnością 0,001 bb bez SE.

## Układ

```
preflop/   hu_preflop.py (solver + CLI), run_table.py (tabela 1–25 bb), gen_equity.py,
           equity_eval7_1M.npy (macierz equity all-in 169×169, pochodzenie niżej)
postflop/  hupf_py/ (klient Pythona: karty, próbki flopów, agregacja per klasa, pipeline, live)
           hupf/ (sterownik Rust, AGPL-3.0: main.rs, Cargo.*, min_bet.patch, build.sh) + NOTICE
integ/     fp.py (klocki pętli), run_fp.py (pętla spike'u), report.py, export_tool_data.py,
           flopsample.py, analysis_extra.py, deviations.py, crit_oos.py, dom.py (pomiary);
           fpa.py + run_fpa.py + report_fpa.py (fictitious play, następca run_fp.py)
tool/      spin_gto.py (zapytania), bench_latency.py
```

Środowisko: venv repo z extras `train` (numpy) i pakietem `poker`
(`python -m pip install -e ".[dev,train]"`). Skrypty uruchamia się ścieżką do pliku
(`python tools/hu_gto/...`); moduły siostrzane ładują się z katalogu skryptu.

## Sterownik postflop `hupf` (opcjonalny program zewnętrzny)

```bash
tools/hu_gto/postflop/hupf/build.sh        # git + cargo; ok. 16 s na 4 rdzeniach
# binarka: tools/hu_gto/postflop/hupf/target/release/hupf  (inną wskazuje HUPF_BIN)
```

Skrypt pobiera b-inary/postflop-solver w commicie `9d1509fe5077d019825f833eed04b16d342dfda1`
do `hupf/vendor/` (poza gitem), nakłada `min_bet.patch` (najmniejszy bet = 1 bb) i buduje
`cargo build --release --locked`. Obejścia, zmierzone na rustc/cargo 1.97:

- `RUSTFLAGS=-A dangerous_implicit_autorefs` — kod upstream z 2023 r. łamie tę lintę, którą
  nowszy rustc zgłasza jako błąd kompilacji (3 miejsca w `action_tree.rs`);
- `HUPF_OFFLINE=1` dodaje `--offline` na maszynie z wypełnionym rejestrem cargo i bez dostępu
  do crates.io; wersje i tak przypina `Cargo.lock`.

Bez binarki działa cały preflop, a testy wymagające `hupf` są pomijane z komunikatem.

## Uruchomienie

Preflop (sekundy):

```bash
python tools/hu_gto/preflop/hu_preflop.py 10 --leaf jamfold --node root --action jam
python tools/hu_gto/preflop/hu_preflop.py 15 --leaf eqr      # placeholder EQR 1,05/0,85
python tools/hu_gto/preflop/run_table.py /tmp/hu_table       # 1–25 bb × 3 warianty liścia
```

Postflop dla jednej linii (zakresy zastępcze albo `--sb-range/--bb-range`, 169 lub 1326 wag;
flop na żywo liczy minuty, pipeline na 30 flopach zmierzono na 33 min dla raise2x_call 15 bb
i 86 min dla limp_check 15 bb na 2 wątkach, częściowo w konkurencji o CPU):

```bash
cd tools/hu_gto/postflop
python -m hupf_py.live --board Ks7d2c --pot 2 --stack 14 --line limp_check
python -m hupf_py.pipeline --line raise2x_call --stack 15 --flops 30 --threads 2
```

Pętla punktu stałego (ok. 85 min na 4 rdzeniach, 4 procesy × 1 wątek; cache ok. 52 MB).
Każdy solve postflop trafia do cache (`integ/out/cache`, klucz = sha1 zadania), więc po
przerwaniu wystarczy uruchomić ją ponownie — policzone joby są odczytywane, nie liczone:

```bash
setsid nohup python tools/hu_gto/integ/run_fp.py 12 4 10 15 20 > /tmp/run_fp.stdout 2>&1 &
python tools/hu_gto/integ/report.py 4            # tabela częstości, zbieżność, charty
python tools/hu_gto/integ/export_tool_data.py    # ostatnia runda -> tool/data
```

`FP_OUT` przenosi katalog rund i cache. Domyślne parametry odtwarzają ustawienia spike'u
(K2 = 12 flopów lofi, K_HI = 4, poprawka drzewa w rundzie 2, limit R4). Pełnej regeneracji
od zera w repo nie powtórzono; na rundach spike'u `report.py`, `dom.py`, `analysis_extra.py`
i `export_tool_data.py` z repo dały pliki identyczne z wynikami spike'u.

Pomiary jakości (po pętli): `analysis_extra.py` (luka przeliczona R0–R3, jackknife),
`deviations.py out/round3.pkl 15 20` (odchylenia), `crit_oos.py 15 20` (luka R4 na flopach
spoza próbki; liczy nowe solve'y), `dom.py` (naruszenia dominacji).

## Fictitious play (`integ/fpa.py`, `integ/run_fpa.py`)

Następca pętli `run_fp.py`, która kręci się w 2-cyklu. Runda r przy profilu uśrednionym R̄_r:

1. postflop liczy wszystkie liście nie-all-in R̄_r (bez pożyczania między głębokościami) tanim
   drzewem `flopsmall` na **świeżym** bloku flopów (`flopsample.herd_blocks`: każdy blok to
   herding do cech całej populacji, bloki rozłączne);
2. **luka held-out** = luka best response R̄_r w modelu dopasowanym tylko do tego bloku (żaden
   model, z którego powstał R̄_r, nie widział tych flopów); wartości klas są wobec ustalonej
   strategii postflop rywala, więc to luka w sensie BR (rywal stały preflop i postflop);
   eksploatacja samego postflopu (solve'y do 1% puli) nie jest w niej liczona;
3. model puli M̄_r = średnia modeli addytywnych z rund z wagami k + 1 (FP na modelach liścia;
   szum próbki maleje, bo pula widzi wszystkie bloki), R_{r+1} = równowaga preflop w M̄_r,
   R̄_{r+1} = średnia R_0..R_{r+1} z wagami k + 1 w sensie realizacji (FP na profilach).

Estymator wielowierności: w rundzie `--hifi-round` blok ma `--hifi-flops` (domyślnie 30)
flopów i dla liści o SPR > 1,5 liczy też drzewo produkcyjne (`low1rf` / `l1rf` wg SPR);
poprawka D = EV_prod − EV_tanie (wygładzona po cechach klas) wchodzi do modelu wszystkich rund.
Liście o SPR ≤ 1,5 (pule po iso 5–6 bb i po małym 3becie) zostają na tanim drzewie: oba drzewa
mają tam na turnie i riverze praktycznie tylko check / all-in; D dla nich jest mierzona na
`--spr-check-flops` flopach i raportowana, ale nie stosowana. Po ostatniej rundzie:
luka R̄_final na osobnym bloku held-out (`--holdout`, cały i połówki — szum pomiaru),
zgodność akcji najlepszej per klasa model puli vs model held-out, bias modelu per liść
(SE jackknife po flopach), naruszenia dominacji, porównanie z referencjami o porównywalnym
drzewie (GW-AI 10/16/20 bb, biblioteka GW 20 bb, Gecko 10 bb).

Drzewo `hu_preflop.gw_tree(S)`: open 2x i 2,5x na każdej głębokości, BB vs limp
check / iso 2,5 i 4 bb (S < 13), 3 i 5 (13 ≤ S < 18), 3 i 6 (S ≥ 18) / jam, mały 3bet do 2,5×
openu vs open przy S ≥ 13 (SB: fold / call / 4bet-jam).

Wygładzanie empirycznym Bayesem (`fpa.shrink`, opcja `--smooth`) jest domyślnie wyłączone —
uzasadnienie liczbami w sekcji pilota.

Test na grze zabawkowej (`tests/test_hu_gto_fpa.py`, postflop zależny od zakresu SB): iteracja
bez uśredniania wpada w 2-cykl (open SB 0 ↔ 74%, luka 0,31–0,35 bb/rękę), FP zbiega
(po 8 rundach luka < 0,002 bb/rękę, zmiana R̄ między rundami 6–8 < 2 pp).

```bash
cd tools/hu_gto/integ
setsid nohup python run_fpa.py --depths 15 --rounds 9 --out OUT > OUT.stdout 2>&1 &
python report_fpa.py OUT          # tabela rund i wynik held-out końcowego
python compare_smooth.py OUT      # model puli surowy vs EB na bloku held-out (z cache)
```

Checkpointy: każdy solve postflop w `OUT/cache` (klucz sha1 zadania), stan po rundzie w
`OUT/state.json` i `OUT/fpa_round<r>.pkl`; postęp w `OUT/run.log`. Wznowienie = ta sama komenda
(także z większym `--rounds`): preflop jest deterministyczny, policzone solve'y są czytane
z cache.

Zapytania (po eksporcie danych; flop na żywo liczy minuty):

```bash
python tools/hu_gto/tool/spin_gto.py --depth 15 --line "SB limp" --hand AJo
python tools/hu_gto/tool/spin_gto.py --depth 15 --line "SB limp, BB check" --board Ks7d2c --hand Kd8c
python tools/hu_gto/tool/spin_gto.py --depth 15 \
    --line "SB limp, BB check; BB check, SB bet, BB call" --board Ks7d2c5h --hand Kh9h
```

Akcje preflop rozdziela przecinek (`SB fold|limp|raise 2|raise 2.5|jam`, `BB check|iso|jam|call|fold`),
ulice postflop średnik (`<SB|BB> check|bet X|raise X|call|fold|allin`, X w bb albo `X%` puli);
`--hand` to ręka gracza, który ma ruch.

## Macierz equity `preflop/equity_eval7_1M.npy`

- To nie strategia: equity all-in klasy wiersza przeciw klasie kolumny (wygrana + pół splitu),
  169×169 float64, kolejność klas jak `poker.preflop.ALL_CLASSES`.
- Wygenerowana przez `gen_equity.py`: `python gen_equity.py 1000000 2 equity_eval7_1M.npy`
  (eval7 0.1.11, MIT; 1e6 prób Monte Carlo na parę, SE ok. 0,05 pp; 657,6 s na 2 procesach).
- Ziarna nie ma: eval7 seeduje swój generator czasem przy imporcie, więc regeneracja daje
  macierz różną w granicach błędu MC, nie bitowo równą.
- sha256 `33f8ed9d2f3e2520e546160138a892a47755fe127c620a2af56901bb80f3346a` (sprawdza test).
- Wobec macierzy repo `poker.preflop_equity` (2048 prób/parę): RMS 1,01 pp, max 4,09 pp.
- eval7 nie jest zależnością repo — tylko do regeneracji, w osobnym venv
  (`pip install eval7==0.1.11`).

## Artefakty

Booki, rundy pętli (`round*.pkl`), cache solve'ów i dane narzędzia nie wchodzą do repo
(decyzja 30); `.gitignore` w tym katalogu wyklucza `integ/out/`, `postflop/out/`,
`tool/data/`, `tool/cache/`, `postflop/hupf/vendor/` i `postflop/hupf/target/`.

## Licencje

`postflop/hupf/` (sterownik, łatka, skrypt budowania) jest na AGPL-3.0-or-later jako pochodna
b-inary postflop-solver — szczegóły w `postflop/NOTICE`. Reszta `tools/hu_gto` (w tym klient
`hupf_py`) uruchamia `hupf` jako osobny proces i wymienia z nim tekst/JSON; ma licencję repo.

## Testy

`tests/test_hu_gto_preflop.py`, `test_hu_gto_postflop.py`, `test_hu_gto_integ.py`,
`test_hu_gto_fpa.py`, `test_hu_gto_tool.py` (ok. 40 s). Bez binarki `hupf` pomijane są 4 testy uruchamiające
sterownik, bez eval7 — 1 test generatora macierzy. Kod `tools/hu_gto` jest poza
`mypy` strict (jak reszta `tools/` poza `tools/blueprint`); typowane są testy.

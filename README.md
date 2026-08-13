# Poker

Stół heads-up (1v1) No-Limit Hold'em z agentami o podpinanej,
deterministycznej logice — bez LLM w pętli decyzyjnej. Produkt pod
kontrolą Foundry (`mcz91/foundry`); obowiązuje
[konstytucja wykonawców](https://github.com/mcz91/foundry/blob/main/CONSTITUTION.md)
z tego repozytorium.

**Bieżący stan, granice i następny krok:**
[`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md);
indeks dokumentacji: [`docs/README.md`](docs/README.md).

## Uruchomienie meczu

```bash
python -m poker.adapters.cli --seed 7 --hands 50 --export mecz.json
```

Argumenty (wszystkie z wartościami domyślnymi): `--small-blind 1`,
`--big-blind 2`, `--stack 100 100`, `--button 0`, `--hands 100`,
`--seed 0`, `--agent0 rule`, `--agent1 rule` (dostępny wariant progów
`rule-aggressive`), `--export PLIK` (bez eksportu, gdy pominięty).
Wynik meczu trafia na standardowe wyjście, a pełna historia rozdań —
do wersjonowanego pliku JSON, identycznego bajt w bajt dla tych samych
argumentów.

### Gra człowieka z botem

```bash
python -m poker.adapters.cli --human 0 --agent1 rule --seed 7
```

`--human MIEJSCE` (0 albo 1, domyślnie brak) zastępuje agenta
wskazanego miejsca decyzjami z klawiatury. Przed każdą decyzją terminal
pokazuje wyłącznie widok twojego miejsca: karty własne, board, pulę,
stacki, jawne akcje i granice legalnych akcji; decyzję wpisujesz jako
`fold`, `check`, `call`, `bet KWOTA` albo `raise KWOTA`. Wejście
nielegalne albo nieparsowalne dostaje komunikat i ponowne pytanie, bez
śladu w historii rozdania; koniec strumienia wejścia przerywa mecz
z niezerowym kodem wyjścia. Rozstrzygnięcie każdego rozdania (fold albo
showdown) terminal pokazuje natychmiast po jego zakończeniu, a po meczu
dodatkowo w zbiorczym przebiegu rozdań. Karty bota i seed pozostają
niewidoczne do showdownu; po nim widać odkryte karty. Eksport historii
działa tą samą flagą `--export`.

### Gra w sieci lokalnej (pokerroom, krok 1)

```bash
python -m poker.adapters.cli --serve 7777            # serwer stołów
python -m poker.adapters.cli --connect 192.168.0.10:7777 \
  --opponent human --hands 50 --seed 7               # tworzy stół, drukuje kod
python -m poker.adapters.cli --connect 192.168.0.10:7777 --join K7M2QRXB
```

Jeden serwer (`--serve PORT`, nasłuch na `--serve-host`, domyślnie
0.0.0.0) prowadzi wiele niezależnych stołów heads-up. Klient z innego
urządzenia tworzy stół (dostaje kod; konfiguracja meczu tymi samymi
flagami co mecz lokalny) albo dołącza kodem (`--join`); `--opponent`
`human` czeka na drugiego gracza, nazwa agenta z rejestru gra od razu.
Mecz rusza po skompletowaniu dwóch graczy; do klienta wychodzi
wyłącznie widok jego miejsca (ta sama dyscyplina co w terminalu
lokalnym — INV-P3 na granicy procesu, pod testem pełnego strumienia
bajtów). Protokół to typowane, wersjonowane JSON Lines — nieznana
wersja jest odrzucana po obu stronach. Rozłączenie gracza kończy jego
stół komunikatem dla przeciwnika, bez wpływu na pozostałe stoły.
`--export-dir KATALOG` na serwerze zapisuje historie zakończonych
stołów w formacie eksportu. Sieć lokalna jest zaufana (decyzja 08):
kod stołu to jedyna kontrola dostępu — dlatego jest losowy, nie
kolejny: osiem znaków z alfabetu bez znaków mylących
(`ABCDEFGHJKMNPQRSTUVWXYZ23456789`), czyli ~39,6 bita. `--serve-seed`
przybija sekwencję kodów (odtwarzalna między uruchomieniami, przydatne
w testach); pominięty daje kody nieodtwarzalne. To utrudnia trafienie
w cudzy stół, ale nie jest zabezpieczeniem kryptograficznym.

### Arena porównawcza agentów

```bash
python -m poker.adapters.cli --series 100 --hands 200 --seed 7 \
  --agent0 rule --agent1 rule-aggressive
```

`--series PARY` (domyślnie brak) rozgrywa serię PAR meczów agent0 vs
agent1 na lustrzanych rozdaniach (duplicate): każdy seed meczu grany
jest dwukrotnie z zamianą miejsc, więc obie strony dostają te same
karty, a wynik pary jest sumą obu przebiegów. Raport na stdout: wynik
agenta0 w BB/100, odchylenie standardowe po parach i 95% przedział
ufności; ten sam seed serii daje identyczny raport. Konfiguracja
serii to te same flagi co mecz (`--small-blind`, `--big-blind`,
`--stack`, `--button`, `--hands`, `--seed`); `--series` wyklucza
`--human` i `--export`.

### Korpus self-play

```bash
python -m poker.adapters.cli --corpus korpus/ --matches 1000 --seed 7 \
  --jobs 4 --agent0 rule --agent1 rule
```

`--corpus KATALOG` (domyślnie brak) generuje `--matches` meczów
(domyślnie 100) agent0 vs agent1 na seedach pochodnych deterministycznie
od `--seed`; każdy mecz to osobny plik w formacie eksportu, obok
powstaje `manifest.json` z własną wersją, konfiguracją meczu, nazwami
agentów, seedem, liczbą meczów i listą plików. Ten sam seed
i konfiguracja dają korpus identyczny bajt w bajt, niezależnie od
`--jobs` (domyślnie 1). Katalog docelowy musi być pusty — korpus
niczego nie nadpisuje. `--corpus` wyklucza `--human`, `--export`
i `--series`.

### Zbiór przykładów decyzyjnych

```bash
python -m poker.adapters.cli --dataset zbior.json --from-corpus korpus/
```

`--dataset PLIK` (domyślnie brak) przekształca korpus self-play
wskazany przez `--from-corpus` w jeden typowany plik JSON z jawnym
polem wersji zbioru: dla każdej decyzji agenta (blindy nie są
decyzjami) cechy liczbowe wyprowadzone wyłącznie z widoku miejsca
decydującego w chwili decyzji (granica informacyjna decyzji 05 —
karty przeciwnika, seedy i zdarzenia silnika nie wchodzą żadnym
kanałem) oraz etykieta: typ akcji i kwota. Zestaw i kolejność cech v1
dokumentuje moduł `poker.encoding` (`FEATURE_NAMES`). Ten sam korpus
daje plik identyczny bajt w bajt; istniejący plik wyjściowy to błąd.
`--dataset` wyklucza pozostałe tryby CLI.

### Baseline behavior clone

Regeneracja zatwierdzonych wag od zera, wyłącznie z tego repozytorium
(sekwencja zgodna ze stałymi `CORPUS_*` i hiperparametrami w module
wag; dowód dwustopniowy decyzji 06: w bramce deterministyczna
reprodukcja małego łańcucha kontrolnego, pełna regeneracja poniższymi
komendami poza bramką):

```bash
python -m poker.adapters.cli --corpus korpus-wag/ --matches 100 \
  --seed 7 --agent0 rule --agent1 rule-aggressive
python tools/train_behavior_clone.py --from-corpus korpus-wag/
```

Narzędzie treningu wykonuje łańcuch korpus → zbiór → trening w całości
z manifestu korpusu (czysty stdlib, wieloklasowa regresja logistyczna
na typ akcji) i zapisuje wagi jako wygenerowany moduł
`src/poker/clone_weights.py` z kompletnym przepisem pochodzenia
(parametry korpusu, wersja zbioru, hiperparametry, liczba przykładów).
Hiperparametry z udokumentowanymi domyślnymi: `--learning-rate 0.1`,
`--epochs 100`; trening jest w pełni deterministyczny — ten sam korpus
i hiperparametry dają bajt w bajt identyczny moduł. Agent `clone`
(rejestr CLI) gra deterministyczną inferencją portem Agent: model
wybiera typ akcji, kwoty v1 to minimum legalne, typ niedostępny ma
deterministyczny fallback (check → call → fold) — nigdy nie zwraca
decyzji nielegalnej. Pomiar w arenie:

```bash
python -m poker.adapters.cli --series 20 --hands 100 --seed 7 \
  --agent0 clone --agent1 rule
```

### Strategia MCCFR (self-play)

```bash
python tools/train_mccfr.py --iterations 1000 --seed 7 \
  --averaging linear --checkpoint checkpoint.json --checkpoint-every 100
python tools/train_mccfr.py --iterations 1000 --seed 7 \
  --averaging linear --checkpoint checkpoint.json --resume
python -m poker.adapters.cli --series 20 --hands 100 --seed 7 \
  --agent0 mccfr --agent1 rule
```

Trener MCCFR (external sampling) gra self-play na abstrakcji c2a
i zapisuje uśrednioną strategię jako moduł `src/poker/strategy_table.py`
z pełnym przepisem pochodzenia (wersja abstrakcji, seed, iteracje,
sposób uśredniania, parametry kubełków i rozmiarów zakładów).
Domyślne uśrednianie jest liniowe (`--averaging linear`: waga iteracji
t, Linear CFR). `--averaging uniform` przywraca klasyczne sumowanie
jednostajne — do porównań A/B. Trening jest w całości seedowany —
losowość iteracji zależy wyłącznie od pary (seed, numer
iteracji), więc ta sama komenda odtwarza artefakt bajt w bajt, a bieg
przerwany i wznowiony z `--checkpoint ... --resume` daje wynik
identyczny z biegiem ciągłym o tej samej łącznej liczbie iteracji
(pod testami; dowód dwustopniowy decyzji 06). Bez `--resume` istniejący
checkpoint jest nadpisywany od zera. Bieg 1000 iteracji przy stackach
100 trwa ok. 1,5 min; koszt rośnie liniowo z iteracjami, a rozmiar
artefaktu ~n^0,65. Standard library wystarczył — numpy, dozwolony
w `tools/`, nie był potrzebny.

Agent `mccfr` (rejestr CLI, gra też przez serwer LAN) liczy infoset
z widoku, bierze rozkład z artefaktu i losuje akcję **bez stanu**:
deterministyczną funkcją seeda konstrukcji i widoku (blake2b), więc ten
sam widok i seed zawsze dają tę samą akcję — replay i lustro areny
działają bez zmian. Infoset spoza artefaktu ma fallback check-call
(a bez niego fold).

## Dane equity preflop

Macierz equity all-in 169×169 klas preflop żyje w repozytorium jako
wygenerowany moduł `src/poker/preflop_equity_data.py` (Monte Carlo;
metoda, seed i liczba prób w metadanych modułu). Regeneracja:

```bash
python tools/generate_preflop_equity.py
```

Parametry `--seed 12`, `--trials 2048`, `--jobs 4` i `--output` mają
wartości domyślne zgodne z utrwaloną macierzą; ten sam seed i liczba
prób odtwarzają identyczne dane.

## ICM i Spin & Go

`poker.icm` liczy $EV turnieju modelem Malmuth–Harville (stdlib).
Winner-take-all (2×/3× Spin) jest tożsamy z udziałem żetonów.
`poker.spin` trzyma start 25 bb, wypłaty 2×/3×/10× i rozliczenie
all-in jam/fold 3-max. To nie otwiera licytacji multiway
(`HeadsUpHand` zostaje przy dwóch miejscach).

### MLP-klon (trening z numpy, inferencja stdlib)

```bash
python -m poker.adapters.cli --corpus korpus-wag/ --matches 100 \
  --seed 7 --agent0 rule --agent1 rule-aggressive
python tools/train_mlp_clone.py --from-corpus korpus-wag/
python -m poker.adapters.cli --series 20 --hands 100 --seed 7 \
  --agent0 mlp-clone --agent1 clone
```

Narzędzie treningu MLP wymaga extras `train` (numpy — wyłącznie
w `tools/` i testach reprodukcji; pakiet produktu i inferencja agenta
`mlp-clone` to czysty stdlib, decyzja 06). Wersja numpy jest
przypięta w pyproject: bitowa identyczność regeneracji artefaktów
trenowanych zależnością jest gwarantowana dla przypiętej wersji —
inny build może dawać inne bity przy tej samej matematyce. Architektura
i hiperparametry z udokumentowanymi domyślnymi: `--hidden 16`,
`--activation relu`, `--learning-rate 0.05`, `--epochs 300`,
`--seed 0`. Trening jest deterministyczny (seedowana inicjalizacja,
pełny batch): ten sam korpus, architektura, hiperparametry i seed
odtwarzają moduł `src/poker/mlp_weights.py` bajt w bajt — pełna
regeneracja komendami powyżej (dowód dwustopniowy: w bramce
deterministyczna reprodukcja małego łańcucha kontrolnego).

## Instalacja i pełna bramka

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,train]"
ruff check .
mypy
pytest
```

## Prompty ról

1. [`PROMPT_POKER_ARCHITEKT.md`](PROMPT_POKER_ARCHITEKT.md) — kwalifikuje
   „czy budować", specyfikuje TaskSpeki `POKER-N`, strzeże niezmienników
   INV-P1…P8 i otwartych gałęzi rozwoju (pokerroom, trener, GTO/ML);
2. [`PROMPT_POKER_KODER.md`](PROMPT_POKER_KODER.md) — realizuje dokładnie
   jeden TaskSpec pod pełną bramką;
3. [`PROMPT_POKER_AUDYTOR.md`](PROMPT_POKER_AUDYTOR.md) — audytuje diff
   na świeżym kontekście i wydaje werdykt.

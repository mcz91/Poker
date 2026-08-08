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
z niezerowym kodem wyjścia. Karty bota i seed pozostają niewidoczne do
showdownu; po nim przebieg rozdań pokazuje odkryte karty. Eksport
historii działa tą samą flagą `--export`.

## Instalacja i pełna bramka

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
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

# Colab na ThinkPadzie

Ten sam notes co na S9+, inny pulpit. Cel pierwszej sesji: dym `smoke`.

Notes:
https://colab.research.google.com/github/mcz91/Poker/blob/grok/poker-53-aivat/tools/blueprint/colab/train_gto.ipynb

Gałąź: `grok/poker-53-aivat`. Runtime CPU. GPU off.

## 0. Zanim otworzysz Colaba

- Zasilacz. Nie na baterii.
- Chrome (nie Firefox do pierwszego dymu — mniej dziwactw z Drive).
- Sen: pokrywa może być przymknięta tylko jeśli system **nie usypia**.
  - Windows: Zasilanie → Zamknięcie pokrywy → Nic nie rób (przy zasilaczu).
  - Linux: `HandleLidSwitch=ignore` albo nie zamykaj.
- Nie przełączaj sieci w pół komórki (VPN on/off zrywa websocket).

## 1. Colab

1. Wejdź w notes z linku wyżej. Zaloguj to samo Google co Drive.
2. Runtime → Change runtime type → Hardware accelerator **None**.
   High-RAM jeśli jest. Sprawdź pasek: RAM/dysk, **nie** T4/A100/L4.
3. Connect. Zielona kropka.

## 2. Dym (15 min)

Komórka 1 — `PROFILE = "smoke"`. Uruchom. Pozwól na Drive.

Komórka 2 — uruchom. Poczekaj na JSON:

```
status, profile=smoke, config_hash, horizon_cycles, layers
```

Zapisz `config_hash`. Komórki 3 nie ruszaj.

## 3. Test resume

Runtime → Restart session.

Komórka 1. Komórka 2. `config_hash` **identyczny**.
Inny hash = zły tensor, zły profil albo pusty OUT.

To zamyka wieczór. WTA nie startuj o 4 rano.

## 4. Później: WTA

W komórce 1: `PROFILE = "wta25"`.
`POKER_TENSOR` = `/content/drive/MyDrive/poker-gto/PROD/tensor`
(katalog musi już leżeć na Drive — repo go nie ma).

Komórka 2, `--session-hours 9`. Zostaw ThinkPada na zasilaczu.
Rano: Restart session → 1 → 2. Ten sam hash, przyrost `layers` / `horizon_cycles`.

Pack (komórka 3) tylko przy `status=done`.

## 5. Gdy coś pada

| objaw | co |
|---|---|
| T4 w pasku | Runtime → None, Restart |
| `No such file: colab_run.py` | clone nie z `grok/poker-53-aivat` |
| `allow-fresh` na istniejącym OUT | notes sam to ogarnie; nie dopisuj flagi |
| inny `config_hash` | nie packuj; sprawdź profil i tensor |
| sesja umarła po śnie | to jest OK; Drive ma manifest; komórka 2 wznawia |

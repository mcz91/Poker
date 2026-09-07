# Colab — rdzeń GTO, checklista na sesję

Runtime: CPU + High-RAM. GPU off. Python 3.12+. Gałąź `grok/poker-53-aivat`.

## Wieczór / rano — kolejność

1. Notes `train_gto.ipynb`, `PROFILE = "smoke"`.
2. Komórka 1 (clone + Drive). Tensor dymu = `tools/blueprint/control/tensor` w repo.
3. Komórka 2 (`--session-hours 0.25`). Ma skończyć `done` albo `aborted-session` z manifestem na Drive.
4. Restart runtime, znowu komórka 1 i 2 — bez ręcznego `--allow-fresh`. Status ma pokazać ten sam `config_hash`.
5. Dopiero potem `PROFILE = "wta25"` i tensor z Drive (`PROD/tensor`). Budżet 9 h ściany, 2–3 sesje.

Nie startuj `wta25` bez zielonego dymu. Domyślny `GridConfig.grid_step` to 5; produkcja to 2 — dlatego profil jest wymagany.

## Profile

| profil | krok | prizes | po co |
|---|---|---|---|
| `smoke` | kontrolny | łańcuch | dym, resume |
| `tdeep` | 2 | 0.8, 0.2, 0 | T-DEEP 10x |
| `wta25` | 2 | 1, 0, 0 | P-7 |

## Pułapki

- `!` widzi zmienne **shell**, nie Pythona — notes ładuje ścieżki do `os.environ`.
- Fuse sesji tnie **po** cyklu/warstwie, nie w środku. 9 h, nie 11.
- `identity` to katalog PROD (32 pliki), nie `OUT` solvera.
- Artefakt zostaje na Drive, nie w `git push`.

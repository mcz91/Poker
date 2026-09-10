# Colab — rdzeń GTO, checklista na sesję

Python 3.12+. Gałąź `grok/poker-53-aivat`.

Dwa tory, nie jeden:

| tor | hardware | co wolno |
|---|---|---|
| **świadek** | CPU High-RAM | testy, dym, resume, oficjalny `.bpk` |
| **piec** | GPU (później) | tylko po bramce vs świadek; sam nie packuje produktu |

GPU nie startuje, dopóki `smoke` na CPU nie jest zielony. Decyzja 29: GPU = pilotaż walidowany wobec CPU, nie źródło bitów.

## Wieczór / rano — tylko świadek

1. Runtime **CPU + High-RAM**, GPU off. Notes `train_gto.ipynb`, `PROFILE = "smoke"`.
2. Komórka 1 (clone + Drive). Tensor dymu = `tools/blueprint/control/tensor`.
3. Komórka 2 (`--session-hours 0.25`). `done` albo `aborted-session` + manifest na Drive.
4. Restart → komórki 1–2. Ten sam `config_hash`.
5. Stop. To jest test runnera, nie P-7.

## Później — trening

Najpierw nadal CPU: `wta25`, tensor z Drive, 9 h ściany, 2–3 sesje. To jest kandydat na produkt.

Tor GPU (gdy będzie backend):

1. Ten sam `--profile` i ten sam tensor.
2. Świadek CPU liczy **łańcuch kontrolny + jedną warstwę** produkcyjną.
3. Piec GPU liczy to samo.
4. Bramka: `config_hash` identyczny; sha256 `layer_*.npz` / `boundary.npz` identyczne.
5. Różnica bitów = GPU odpada, pack idzie ze świadka.
6. Zgoda bitów na wycinku **nie** otwiera milcząco całego P-7 na GPU — dopiero osobny kontrakt backendu.

Nie ma dziś `cupy` w solverze. „Guess na GPU” = plan bramki, nie flaga w notesie.

## Profile

| profil | krok | prizes | po co | tor |
|---|---|---|---|---|
| `smoke` | kontrolny | łańcuch | dym, resume | tylko CPU |
| `tdeep` | 2 | 0.8, 0.2, 0 | T-DEEP 10x | świadek CPU; GPU po bramce |
| `wta25` | 2 | 1, 0, 0 | P-7 | j.w. |

## Pułapki

- `!` widzi shell, nie Pythona — ścieżki w `os.environ`.
- Fuse tnie po cyklu/warstwie. 9 h, nie 11.
- `identity` = katalog PROD, nie `OUT`.
- Artefakt na Drive, nie w `git push`.
- Colab zmienia model GPU między sesjami — dlatego świadek jest CPU.

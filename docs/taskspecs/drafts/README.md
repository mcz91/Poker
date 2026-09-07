# Szkice TaskSpeców — NIEZATWIERDZONE

Kolejka mapy [decyzji 29](../../decisions/29-tier-first-fundament-gto-mapa-po-researchu.md)
pkt 5, zeszkicowana przez architekta i **niezatwierdzona**. Szkic nie ma
pola `approved` — dopóki go nie ma, koder go nie realizuje.

Ścieżka zatwierdzenia: architekt czyta szkic w świeżym kontekście, uzupełnia
kryteria ilościowe o budżet zmierzony z repo (wzorzec 47: najpierw krzywa,
potem próg), dopisuje `approved` i przenosi plik poziom wyżej, do
`docs/taskspecs/POKER-N.json`.

| plik | rola w mapie | koszt [rdzenio-h] |
|---|---|---:|
| `POKER-58.szkic.json` | P-3: domknięcie warstw 1–5 przez osiągalność łańcucha dokładnego | 2–10 |
| `POKER-59.szkic.json` | P-4: checkpoint horyzontu per cykl | ~1 |
| `POKER-53.szkic.json` | P-5: AIVAT w przestrzeni nagród (wersja przeskalowana decyzją 29) | ~5 |
| `POKER-60.szkic.json` | P-6: trzy sondy błędu modelu (bramka STOP) | ~24 |
| `POKER-69.szkic.json` | runner Colab rdzenia GTO (decyzja 31) — przed P-7 | 0 |

Wzorzec zatwierdzonego kontraktu: `docs/taskspecs/POKER-57.json`.

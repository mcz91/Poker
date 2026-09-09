# 31 — Call w slocie 3, checkdown (wierność 0); WTA na starym drzewie nie

Status: obowiązuje. 2026-09-10. Po dymie Colab i POKER-60.

## Decyzja

1. **Następny kontrakt GTO to drzewo, nie kolejny solve.** P-6(a) zapalił
   krok 1 siatki (flip 4% + import 16/16 > 5e−4 na kontroli). STOP decyzji
   29 pkt 5 dopuszcza wtedy krok 1. Nie wydajemy 252 rdzenio-h na siatkę
   kroku 1, która nadal nie umie callować. Audyt A1 stoi: 17 liści
   fold/showdown, SLOT_MID przy otwarciu to 3bet/jam, nie flat.
2. **Czwarta akcja = call, slot 3.** Format v2 już ma `DERIVED_SLOT_V2 = 3`
   z dopełnienia. Dziś jest zerem. Poszerzenie nie rusza magii `.bpk`.
   First-in zostaje fold / open 2.2x / jam (decyzja 20) — bez limpa UTG.
   Call tylko **vs open** (BB vs T, BB vs U po foldzie T, T vs U potem BB).
3. **Wierność 0: liść call = checkdown** (`sd` przez `_settle`). Bez
   postflopu. Drabina 1/2 (checkdown znany błąd → embedding) = osobny
   kontrakt po dymie nowego drzewa.
4. **Łańcuch kontrolny zamrożony.** `_tree_3max` / `_LEAF_DEFS_3` bez
   zmian, dopóki `tree_id` nie wejdzie za flagą. Spike (POKER-68) liczy
   liście i koszt; wiring = POKER-68b.

## Spike (liczby wiążące)

3-max: 17 → **23** liście (+6: 4× sd 2-way, 1× sd 3-way, 1× fold).
HU: 6 → **7**. Iloraz liści 23/17 ≈ 1,35. Koszt `deep` (arytmetyka +
strumień, decyzja 29): **1,6×**. Squeeze (T call U, BB działa) = 4 z 6
nowych liści. Extra 3-way przy C=169: ~55 MiB payloadu — asercja < 80 MiB.

## Mapa sprintów (do RTA)

| sprint | kontrakt | co | nie |
|---|---|---|---|
| S12 | POKER-68 | spike + ten rekord | wiring, solve |
| S13 | POKER-68b | drzewo za `tree_id`, dym kontroli | WTA 65 h |
| S14 | P-7 | WTA@25bb **na nowym drzewie** | T-DEEP 80/20 |
| S15 | P-11 | DBR HU-first | DBR 3p przed HU |
| S16 | — | lookup RTA z `.bpk` | search w runtime |

Krok 1 siatki i P-6(b,c) zostają w kolejce **za** S13: taniej mierzyć
kwantyzację na drzewie, które jest grą.

## Czego nie robimy

MCCFR, sieci, GPU jako referencja, UTG limp, postflop w S12/S13,
przebudowa v2, ruszanie `src/poker` poza czytelnikiem gdy slot 3
dostanie masę (S13).

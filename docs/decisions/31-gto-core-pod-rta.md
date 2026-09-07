# 31. Rdzeń GTO jako podłoże RTA; explo później

Status: obowiązuje. Autor: architekt, 2026-09-07.
Zlecenie operatora: docelowo bot RTA; teraz focus na rdzeniu GTO,
na który wejdzie warstwa eksploatacyjna.

## 1. Co jest produktem teraz

Produkt bieżącej linii to **rdzeń GTO**: rodzina artefaktów `.bpk`
(lookup strategii per stan/miejsce/węzeł) liczona offline na CPU,
odtwarzalna bajt w bajt, mierzona ex-post ε i areną.

Runtime bota — także przyszłego RTA — to **odczyt tablicy**, nie search
w trakcie ręki. To już jest w kodzie (`blueprint_reader`,
`blueprint_agent`, stdlib, zero numpy). Decyzja 29 pkt 4 zostaje:
search w czasie rzeczywistym w produkcie jest odrzucony. RTA nie
otwiera tej decyzji — RTA ma być szybkim konsumentem artefaktu,
nie drugim solverem.

## 2. Warstwy i kolejność

```
RTA (później)     — I/O stołu, timing, wybór artefaktu po multiplikatorze
explo (później)   — seat-restricted DBR, trzy tablice V hero, P_max z krzywej
rdzeń GTO (teraz) — T-DEEP istniejący → WTA@25bb → T-MODAL po kill-checku
przyrząd          — AIVAT, sondy STOP, Colab runner, checkpointy
```

Warstwa explo **nakłada się na rdzeń**, nie zastępuje go: `n=0` w DBR
to czysty blueprint. Bez zmierzonego rdzenia nie ma czego ograniczać
bramką `ε_DBR ≤ ε_blueprint`.

## 3. Co to znaczy „łatwy do wytrenowania w Colabie”

Trening = bieg `tools/blueprint/solve_grid.py` + packer, nie sieć.
Colab jest runnerem CPU z dyskiem trwałym (Drive). Sesja pada;
jednostką wznowienia jest cykl horyzontu (POKER-59) i warstwa
(POKER-50). GPU nie jest ścieżką referencyjną artefaktu.

Kontrakt opakowania: szkic POKER-69. Bez niego każdy bieg produkuje
prozę setupu zamiast artefaktu.

## 4. Zakres sprintów do RTA

Otwieramy wyłącznie to, co buduje rdzeń albo przyrząd rdzenia:

- Colab runner (POKER-69)
- AIVAT (P-53) — moc pomiaru, nie strategia
- sondy STOP (P-60) — czy w ogóle wolno kolejny solve
- WTA@25bb (P-7) — pierwszy artefakt właściwej gry
- T-MODAL (P-8) — tylko po przeżyciu kill-checku i potwierdzeniu tabeli

Nie otwieramy w tej fazie: P-10…P-13 (brak korpusu HH i brak rdzenia
modalnego), P-14 (drzewo zamrożone), search/RTA I/O, sieci.

## 5. Definicja „rdzeń gotowy na explo / RTA”

1. Artefakt `.bpk` v2 z fingerprintem przebiegu.
2. `verify_identity` zielone na katalogu biegu.
3. Ex-post ε maks pod progiem wysyłkowym 1e−3 (dziś T-DEEP: 4,72e−4).
4. Agent `blueprint` gra z pliku bez fallbacku poza zmierzonym
   (licznik POKER-55); RTA użyje tego samego czytnika.
5. Colab umie ten bieg wznowić i dokończyć po restarcie sesji.

Punkt 5 jest twardym wymaganiem treningu. Punkty 1–4 już prawie stoją
na T-DEEP; brakuje WTA/T-MODAL i runnera.

## 6. Czego ta decyzja nie zmienia

Niezmienniki INV-P1…P8, decyzje 25–30, zakaz Jensena, zakaz GPU jako
źródła bitów, zakaz publikacji artefaktu, drzewo zamrożone do P-14.

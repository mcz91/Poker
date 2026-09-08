# Colab na Galaxy Tab S9+

Cel wieczoru: dym `smoke` (15 min), nie WTA. Runtime **CPU**. GPU off.

Colab liczy w chmurze. Tablet jest pulpitem. Sen ekranu / zabicie Chrome
zrywa sesję częściej niż na laptopie.

## 0. Sprzęt

- Chrome (nie Samsung Internet — Colab pada na WebView).
- Konto Google z Drive.
- Najlepiej **DeX + klawiatura**. Bez DeX też przejdzie, gorzej się edytuje.
- Ustawienia → Ekran → limit 10 min albo „zostaw włączony” na czas dymu.
- Nie przełączaj na inną ciężką apkę na 15 min. Android uśpi kartę.

## 1. Runtime

1. Otwórz [colab.research.google.com](https://colab.research.google.com).
2. Plik → Otwórz notes → GitHub → `mcz91/Poker` → gałąź `grok/poker-53-aivat`
   → `tools/blueprint/colab/train_gto.ipynb`.
   Albo wklej raw URL notesu z tej gałęzi.
3. Menu Runtime → Change runtime type:
   - Hardware accelerator: **None** (CPU).
   - Jeśli jest High-RAM — włącz.
4. Połącz (Connect). Poczekaj na zieloną kropkę. Ma pisać RAM, nie T4/A100.

## 2. Komórki — kolejność, nic nie dopisuj

Komórka 1: clone gałęzi + Drive. Zostaw `PROFILE = "smoke"`.
Pierwszy raz pozwoli na Drive — zaakceptuj.

Komórka 2: solve 0,25 h. Ma wypisać JSON `status` + `config_hash`.
Zostaw tablet odblokowany.

Komórka 3 **nie ruszaj**, dopóki `status` nie jest `done`.

## 3. Restart (to jest test)

1. Runtime → Restart session (albo zamknij i wejdź od nowa w ten sam notes).
2. Komórka 1 jeszcze raz (Drive już jest).
3. Komórka 2 jeszcze raz — **bez** ręcznego `--allow-fresh` (notes sam
   sprawdzi manifest na Drive).
4. `config_hash` ma być **identyczny**. Inny hash = zły tensor albo zły profil.

## 4. Gdy dym jest zielony

Dopiero wtedy `PROFILE = "wta25"` i tensor z
`/content/drive/MyDrive/poker-gto/PROD/tensor`.
WTA to 2–3 sesje po 9 h. Na tablecie: DeX, ładowarka, nie minimalizuj Chrome.
Fuse i tak zetnie po cyklu koło 9 h — rano ta sama komórka 2.

## 5. Czego nie robić na S9+

- Runtime GPU „bo szybciej” — psuje dym (inne bity, inna karta po restarcie).
- Samsung Internet.
- `git push` artefaktu.
- `identity` na katalogu `OUT` solvera — to jest na PROD (32 pliki).
- WTA przed zielonym `smoke`.

## 6. Jeśli komórka 1 padnie

Typowe na tablecie:

- `git clone` timeout — odpal komórkę 1 jeszcze raz.
- `pip install` woła o restart runtime — Restart, znowu 1, nie 2.
- Drive `mount` pyta o kod — zaloguj to samo konto co Colab.
- `No such file: colab_run.py` — jesteś na `main`, nie na
  `grok/poker-53-aivat`. W komórce 1 ma być `git clone --branch grok/poker-53-aivat`.

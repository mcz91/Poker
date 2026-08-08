# Pamięć operacyjna ról Poker

Nośnik stanu między sesjami ról (architekt / koder / audytor) produktu
Poker. Protokół identyczny z `PAMIEC_OPERACYJNA.md` w `mcz91/foundry`:
czytaj na starcie sesji, nadpisz swoje wpisy przed zamknięciem; limit
80 linii; format `RRRR-MM-DD rola: fakt`; fakt utrwalony w repo → usuń
wpis; linkuj zamiast kopiować.

## STAN — praca w locie

- 2026-08-08 arch: POKER-1 zatwierdzony
  ([`docs/taskspecs/POKER-1.json`](docs/taskspecs/POKER-1.json)) —
  następny ruch należy do kodera; kolejny TaskSpec (karty i ewaluator
  rąk) dopiero po zielonej bramce POKER-1.

## WĄTKI — otwarte, bez TaskSpec

- 2026-08-08 arch: mono- vs multi-repo dla produktów (pokerroom,
  trener, bot) odroczone do pierwszej kwalifikacji produktu — decyzja
  [`01`](docs/decisions/01-trzy-produkty-jeden-rdzen.md), pkt 3.

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

(pusto — decyzje 01 i 02 utrwalone w `docs/decisions/`)

## PUŁAPKI — koszt odkrycia > koszt linii

(pusto)

## DŁUG — DebtRecords czekające na TaskSpec

(pusto)

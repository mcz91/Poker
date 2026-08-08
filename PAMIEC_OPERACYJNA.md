# Pamięć operacyjna ról Poker

Nośnik stanu między sesjami ról (architekt / koder / audytor) produktu
Poker. Protokół identyczny z `PAMIEC_OPERACYJNA.md` w `mcz91/foundry`:
czytaj na starcie sesji, nadpisz swoje wpisy przed zamknięciem; limit
80 linii; format `RRRR-MM-DD rola: fakt`; fakt utrwalony w repo → usuń
wpis; linkuj zamiast kopiować.

## STAN — praca w locie

- 2026-08-08 arch: POKER-1 (szkielet + bramka) w
  [`docs/taskspecs/POKER-1.json`](docs/taskspecs/POKER-1.json), status
  szkic (`approved: null`) — czeka na dwie decyzje operatora: język
  (rekomendacja: Python ≥3.12) i zatwierdzenie TaskSpec. Koder nie
  startuje przed zatwierdzeniem.

## WĄTKI — otwarte, bez TaskSpec

(pusto)

## DECYZJE Z CZATU — obowiązują, niezmechanizowane

- 2026-08-08 arch: TaskSpeki produktu żyją w `docs/taskspecs/POKER-N.json`
  według `schemas/task-spec.schema.json` z `mcz91/foundry`; dokumenty
  decyzji — numerowane pliki w `docs/`, indeks powstaje w POKER-1.

## PUŁAPKI — koszt odkrycia > koszt linii

(pusto)

## DŁUG — DebtRecords czekające na TaskSpec

(pusto)

# Decyzja 02 — Język rdzenia: Python ≥3.12

Status: obowiązuje · 2026-08-08 · decyzja operatora na rekomendację
architekta

## Decyzja

Rdzeń produktu (silnik, historia zdarzeń, kontrakt agenta) oraz bramka
repozytorium powstają w Pythonie ≥3.12, z toolchainem wspólnym
z Foundry: `ruff` (lint), `mypy --strict` (typy), `pytest` (testy).
Standard library first — zależności wykonawcze poza narzędziami bramki
wymagają powodu i planu usunięcia (konstytucja, reguła 9).

## Uzasadnienie

- wspólna bramka i narzędzia z `mcz91/foundry` — zero kosztu nauki
  i jedna dyscyplina jakości między repozytoriami;
- najtańsza przyszła gałąź bota autonomicznego (ekosystem ML);
- wydajność interpretera wystarcza dla deterministycznego silnika
  heads-up; nikt w horyzoncie bieżącym nie zamówił przepustowości.

## Którą gałąź ta decyzja zamyka albo czyni droższą?

Żadnej nie zamyka. Bot/ML tanieje (ekosystem). Trener neutralny.
Pokerroom: gdyby kiedyś wymagał wysokiej przepustowości sieciowej,
granica INV-P7 (silnik za adapterami) pozwala wymienić krawędzie —
a w ostateczności przepisać rdzeń przy zachowaniu kontraktów i historii
zdarzeń jako prawdy (INV-P2); koszt takiej wymiany rośnie, co uznajemy
świadomie za akceptowalny, bo dziś niepotrzebny do opłacenia.

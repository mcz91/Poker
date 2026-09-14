# 31. Nauka, nie modele komercyjne: własna linia tabelaryczna, a brak środków rozwiązany darmowym computem i darmowym pomiarem

Status: **PROJEKT — czeka na zatwierdzenie operatora.** Autor: doradca
na zlecenie operatora (sesja audytu), 2026-09-13.
Podstawa: delegacja operatora 2026-09-13 („Zrób research w necie. Nauka
i modele komercyjne. Wybierz. Nie mamy środków na testy") po audycie kodu
z 2026-09-12 ([`docs/AUDYT_KODU_2026-09-12.md`](../AUDYT_KODU_2026-09-12.md)).
Research: źródła pierwotne z 2026-09-13 (arXiv, dokumentacja GitHub i Oracle,
strony cenowe producentów, kod klientów API); każde twierdzenie ma numer
i link w pkt 9. Gdzie źródło pierwotne było niedostępne, stoi `BRAK`
i źródło wtórne jest tak nazwane. Kontekst: decyzje
[04](04-reguly-dzis-ml-docelowo.md), [07](07-c2-mccfr-na-abstrakcji-strategia-mieszana.md),
[22](22-arena-roi.md), [25](25-blueprint-po-dagu-zegara-pifp-cfrplus.md),
[29](29-tier-first-fundament-gto-mapa-po-researchu.md),
[30](30-dystrybucja-artefaktu-i-odblokowanie-p7.md).

## 0. Wybór w jednym zdaniu

**Nauka** — zostaje własna linia tabelaryczna klasy Pluribusa (decyzje 25/29),
**żaden model komercyjny nie wchodzi do produktu**; komercja służy wyłącznie
jako **darmowy miernik zewnętrzny**; a zdanie „nie mamy środków na testy"
rozwiązuje się nie zakupem, lecz trzema darmowymi dźwigniami, które
istnieją dziś i pasują do tego repozytorium co do konstrukcji: (1) runnery
GitHub Actions publicznego repozytorium jako compute solvera, (2) GTO
Wizard Benchmark + Slumbot jako pomiar HU z AIVAT, (3) otwarty korpus
hand histories jako dane do zbudowania maszynerii eksploatacji.
Jedynym kosztem mapy z decyzji 29 stają się godziny ludzkie.

## 1. Dlaczego nie model komercyjny jako mózg bota

Sprawdzone produkty i ceny (2026-09): HRC Classic 16,66 $/mies. · 39,99 $/kw.
· 119,90 $/rok (stacki do 30 bb, 50 tys. węzłów), HRC Pro 49,99 $/mies. ·
359,90 $/rok [S1]; ICMIZER Basic ~79,99 $/rok, Pro ~159,99 $/rok (3-way
Spin & Go, tryb cEV; źródło wtórne, strona producenta odmówiła dostępu — `BRAK`
ceny pierwotnej) [S2]; GTO Wizard Starter 26 $, Premium 44 $, Elite 116 $/mies.
(wtórne; cennik za logowaniem — `BRAK`) [S3]; PioSOLVER Pro 450 €, Edge 800 €
jednorazowo (wtórne) [S4]; MonkerSolver 499 € (wtórne) [S4]. Żaden z nich nie
jest wyborem, bo:

1. **Nieosadzalne.** Produkt potrzebuje polityki na KAŻDYM stanie DAG-u
   zegara (tysiące stanów × 169 klas × 3 miejsca), nie „rozwiązań do
   nauki". Systematyczne wyciąganie rozwiązań to użycie klasy scrapingu,
   którego regulaminy zakazują wprost — GTO Wizard: „Users are prohibited
   from using automated requests or scripts within the Service" [S5],
   a w benchmarku: zakaz „scrape, harvest, or systematically query the API
   to extract the underlying strategy" [S6].
2. **Repozytorium jest PUBLICZNE** (`"private": false`, sprawdzone API
   2026-09-13; potwierdza decyzję 30). Każde osadzenie cudzych danych
   w repo jest ich republikacją. Decyzja 30 zakazuje publikacji nawet
   WŁASNEGO artefaktu.
3. **INV-P8**: żadne wywołanie sieciowe w logice agenta — wykluczone
   „pytanie API w czasie gry".
4. **Zła gra.** PioSOLVER/MonkerSolver/GTO Wizard liczą chipEV cash HU i 6-max
   przy stałej głębokości; decyzja 25 udowodniła, że równowaga turniejowa
   po DAG-u zegara różni się od nich do 9,4× w węzłach po dwóch agresjach.
   Jedyne narzędzie komercyjne we WŁAŚCIWEJ grze (3-max ICM push/fold
   z symulacją dalszej gry) to HRC — i ono też jest narzędziem do nauki,
   nie polityką.
5. **Koszt jest cykliczny**, a przesłanka operatora brzmi „nie mamy środków".

**Co komercja daje za darmo i co bierzemy:** GTO Wizard Benchmark (pkt 3),
Slumbot (pkt 3) oraz — gdyby kiedykolwiek pojawiły się środki — HRC Pro
(359,90 $/rok) jako próbkowy sanity-check pierwszych akcji Spina, w roli
przewidzianej już przez decyzję 25 („sanity-check, nie ground truth").
Otwarte solvery (TexasSolver, postflop-solver) odpadają niezależnie od ceny:
AGPL-3.0 wobec licencji `Proprietary` w `pyproject.toml`, rozwój zawieszony,
i liczą postflop cash HU — nie naszą grę [S7].

## 2. Dlaczego nie „nauka" w wersji neuronowej ani LLM

Świeże liczby z 2026 potwierdzają obalenia z decyzji 25/29, więc katalog
odrzuceń nie wymaga rewizji:

- **AlphaHoldem** (AAAI 2022) — najtańszy opublikowany agent neuronowy
  bijący Slumbota: +111,56 mbb/h vs Slumbot i +16,91 mbb/h vs reimplementację
  DeepStacka na 200 000 rąk; trening **3 dni na 8×TITAN V + 64 rdzenie CPU**
  (wersja GPU: 4·10³ CPU-h + 580 GPU-h; wersja CPU: 5·10⁴ CPU-h + 210 GPU-h);
  inferencja 2,9 ms **na GPU** [S8]. Sama inferencja łamie runtime stdlib,
  a trening to ~25–300× cała mapa decyzji 29.
- **GTO Wizard AI** — +19,4 ± 4,1 bb/100 vs Slumbot na 150 000 rąk;
  „self-play RL over hundreds of millions of hands", compute nieujawniony
  [S9]. Punkt odniesienia, nie droga.
- **LLM-y** — na tym samym benchmarku: GPT-5.3 XHigh −16 ± 3, GPT-5.4
  −17,8 ± 3,7, Claude Opus 4.6 −20,4 ± 8,6, Gemini 3.1 Pro −30,8 ± 4,5 bb/100
  (po 5 000 rąk; koszt API badania 5 207,72 $), Grok 4 −60 bb/100 [S9, S10];
  nawet z ręcznie zbudowaną biblioteką umiejętności (PokerSkill, maj 2026)
  −57 ± 21 mbb/rękę [S11]. INV-P8 wyklucza je z osobna.
- **Szybsze warianty CFR** (DDCFR, ICLR 2024 spotlight; Deep PDCFR+, AAAI 2026)
  [S12, S13] — dotyczą gier dwuosobowych o sumie zerowej; nasza gra etapowa
  jest 3-osobowa, końcówka HU kosztuje 0,029 rdzenio-h, a prawo nasycenia
  z decyzji 29 (ε = 4,72e−4 → 0,14 pp ROI przy 3× wobec CI areny 1,46 pp)
  mówi, że szybsza zbieżność kupuje dokładność poniżej rozdzielczości
  pomiaru. **Algorytm zostaje bez zmian.**
- Nowość warta odnotowania, nie działania: **CS-RNR** (30 lipca 2026) —
  eksploatacja z certyfikatem bezpieczeństwa liczonym na faktycznie granej
  strategii i harmonogramem pewności z sekwencji ufności [S14]. Skala
  eksperymentów: Leduc, Liar's Dice. Wzorzec certyfikatu może zasilić
  projekt bramki P-11 (decyzja 29 pkt 3B) — po tym, jak P-11 dostanie dane.

## 3. Dźwignia 1 — compute za zero: runnery GitHub Actions publicznego repozytorium

Fakty (źródła pierwotne): „GitHub Actions usage is free for self-hosted
runners and for public repositories that use standard GitHub-hosted runners"
[S15]; zmiana cennika z 2026 tego nie dotyka — „Runner usage in public
repositories will remain free" [S16]; runner publicznego repozytorium ma
**4 vCPU, 16 GiB RAM** (od 2023-12-01, etykiety `ubuntu-*`) [S17]; limity:
**6 h na job**, 35 dni na workflow, **20 równoległych jobów** w planie Free
[S18]. Repozytorium jest publiczne (pkt 1.2). Dziś repozytorium **nie ma ani
jednego workflow** — nawet bramka nie chodzi na GitHubie (brak katalogu
`.github/`).

Rachunek (założenia jawne): mapa decyzji 29 to ~172 rdzenio-h dolnego
oszacowania (fixture `mode_census`), P-7 (WTA@25bb) 64,3 rdzenio-h, T-MODAL
17,8. Przyjmując 1 vCPU ≈ ½–1 rdzenia z pomiaru fixture'a (vCPU to wątek,
nie rdzeń), jeden job daje 12–24 rdzenio-h, a 20 równoległych jobów —
240–480 rdzenio-h na 6 godzin ściennych. **Cała mapa mieści się w jednej
dobie ściennej za 0 zł**, pod warunkiem shardingu po warstwach DAG-u (stany
w warstwie są niezależne — decyzja 25 pkt 5) i checkpointów co warstwę
(bieg jest wznawialny bajt w bajt — POKER-50; P-4 z mapy staje się
warunkiem wstępnym, nie opcją).

Warunki brzegowe, bez których ta dźwignia jest zakazana:

1. **Decyzja 30.** Artefakt workflow w publicznym repozytorium może pobrać
   każdy zalogowany użytkownik GitHuba — czyli upload strategii jako
   artefaktu **jest publikacją**. Każdy checkpoint i każdy wynik biegu
   wychodzi z runnera **wyłącznie zaszyfrowany** kluczem trzymanym
   w sekretach Actions (klucz ma tylko operator), albo idzie bezpośrednio
   do prywatnego magazynu operatora. Logi nie drukują strategii ani
   wartości V.
2. **Determinizm.** Tylko runnery x64 — darmowe runnery arm64 [S19] łamią
   bitową identyczność artefaktów numpy (decyzja 25, PUŁAPKA POKER-19).
   Pierwszy workflow nie liczy nic nowego: odtwarza łańcuch kontrolny
   i porównuje sha256 z `tools/blueprint/control/prod_identity.json`
   (decyzja 30 pkt 2). Rozjazd = STOP i BLOCKED, nie „inny build".
3. **Regulamin.** GitHub zakazuje na runnerach hostowanych „any other
   activity unrelated to the production, testing, deployment, or
   publication of the software project associated with the repository"
   [S20]. Generowanie artefaktu strategii TEGO produktu jest produkcją tego
   projektu — to lektura obronna, nie gwarancja. Dyscyplina: biegi wiązane
   z konkretnym kontraktem POKER-N i tagiem, nigdy pętla ciągła, nigdy
   praca na cudze zlecenie. Ryzyko jawne: zmiana interpretacji przez
   GitHub kończy dźwignię — wtedy wraca plan Colab.
4. `BRAK`: plan konta GitHub operatora (Free = 20 równoległych jobów;
   Pro = 40) — do potwierdzenia przed projektem workflow.

Alternatywy darmowe, zmierzone i słabsze: Oracle Always Free po cięciu
z 2026-06-15 to **2 OCPU / 12 GB ARM** (1 500 OCPU-h/mies.) [S21, S22] —
ARM łamie determinizm, 2 rdzenie dają 172 rdzenio-h w ~86 h ściennych;
zaleta: prywatna maszyna, więc bez problemu publikacji — **plan zapasowy**
dla biegów, których szyfrowanie na Actions okaże się kłopotliwe. Colab
free: „notebooks can run for at most 12 hours", ToS wymaga interaktywności
i zakazuje „running distributed computing workers" [S23] — pozostaje tym,
czym był w decyzji 29 (runner z checkpointami), ale nie jest już
pierwszym wyborem. Kaggle: `BRAK` aktualnego źródła pierwotnego limitów
CPU (strona dokumentacji nie oddaje treści bez JS; źródło wtórne z 2019
mówi o 9 h sesji) — nie liczymy na nie.

## 4. Dźwignia 2 — pomiar za zero: zewnętrzny miernik HU z AIVAT

Audyt (5.1) pokazał, że arena BB/100 nie mierzy tempa wygrywania (mediana
1 rozdanie na mecz). Zamiast budować przyrząd od nowa dla linii HU, bierzemy
gotowy, cudzy i darmowy:

- **GTO Wizard Benchmark** (arXiv 2603.23660, 24 marca 2026): publiczne
  REST API, HUNL, **blindy 50/100, stacki 200 bb, reset co rękę**, klucz
  API na wniosek („We will review your request, and if approved, you will
  receive your key via email"), limit **100 000 rąk/użytkownika/miesiąc**,
  AIVAT: „threefold reduction in standard deviation, resulting in the same
  statistical significance with 10 times less data"; klient Pythona
  publiczny (`gtowizard-ai/researcher-api-client`), agent gra **lokalnie**
  przez protokół `PokerAgent` [S6, S9, S24, S25]. Cena: strona i README nie
  podają żadnej — `BRAK` pierwotnego zdania „free"; dostęp jest uznaniowy
  i odwoływalny.
- **Slumbot** — darmowe API (`/api/new_hand`, `/api/act`), `STACK_SIZE =
  20000`, blindy 50/100, logowanie opcjonalne [S26]; mistrz ACPC 2018, punkt
  odniesienia literatury (GTO Wizard AI +19,4 bb/100, AlphaHoldem +111,56
  mbb/h).

Zgodność z niezmiennikami: klient HTTP żyje w `tools/` (jak `run_arena.py`),
agent pozostaje czystą funkcją `PlayerView → Decision` — to dokładnie wzorzec
adaptera LAN. Regulamin benchmarku dopuszcza ocenę, zakazuje **uczenia
i kalibracji** czegokolwiek na danych benchmarku i wyciągania strategii
[S6] — więc: żadnego DBR z tych rąk, żadnego korpusu z tych rąk, żadnej
regeneracji artefaktu „po wynikach benchmarku".

Granica uczciwości: to **HU cash 200 bb**, nie Spin. Nasza linia HU (c2, stacki
50 bb, rozmiary `half`/`pot`) dostanie tam liczbę bardzo ujemną — i to jest
właściwy, zewnętrzny wyrok dla linii c2 zamiast wewnętrznej areny, która
wyroku wydać nie umie. **Dla Spina 3-max nie istnieje żaden zewnętrzny
miernik** (oba benchmarki są HU) — tam obowiązują naprawy przyrządu
z audytu (5.1, 5.3) i AIVAT w przestrzeni nagród (P-5 POKER-53).

## 5. Dźwignia 3 — dane za zero: otwarty korpus dla maszynerii eksploatacji

Decyzja 29 pkt 6 blokuje P-10..P-13 na „korpusie realnych hand histories
od operatora". Istnieje otwarty korpus (MIT): `uoftcprg/phh-dataset` —
**21 605 687 rzeczywistych rąk NLHE ludzi** (HandHQ, 1–23 lipca 2009:
PartyPoker 8 298 718, PokerStars 3 092 698, Full Tilt 1 299 503, Absolute
1 270 658, iPoker, Ongame), logi ACPC HUNL bot-vs-bot (3,6 mln w 2009 →
156,9 mln w 2016–17), logi ACPC **3-osobowe limit** (13,1 mln 2009 … 5,76 mln
2014), 10 000 rąk Pluribusa [S27, S28]. **Nie ma w nim Spin & Go.**

Co to odblokowuje, a czego nie: odblokowuje **budowę i test maszynerii**
P-10 (builder modelu populacyjnego, licznik decyzji niezmapowanych) i P-11
(DBR w końcówce HU) na prawdziwych ludzkich decyzjach zamiast na własnych
skryptach. Nie odblokowuje żadnego twierdzenia o polu: cash 2009 ≠ Spin 2026,
a decyzja 29 zakazuje raportowania pola „z własnych skryptów" jako realnego —
ten zakaz rozciąga się na ten korpus co do joty. Blokada P-12/P-13 (pole
Spin) **pozostaje** przy operatorze.

## 6. Kolejność prac za zero złotych (zmienia mapę decyzji 29 wyłącznie co do kolejności i nośnika)

1. **Przyrząd przed pomiarem** (0 rdzenio-h): audyt 5.1 — arena HU raportuje
   statystykę zdefiniowaną dla meczów kończących się bustem (odsetek
   wygranych meczów, jak w audycie) albo resetuje stosy co rozdanie;
   audyt 5.3 — `play_spin` odmawia punktowania turnieju z powodem
   `"guard"`; P-5 AIVAT (POKER-53).
2. **Bramka i łańcuch kontrolny na Actions** (≈0 rdzenio-h solvera):
   pierwszy workflow = `ruff`/`mypy`/`pytest` + odtworzenie łańcucha
   kontrolnego + porównanie sha256 z `prod_identity.json`. Dopiero zgodność
   bitowa otwiera pkt 4.
3. **P-4 checkpoint horyzontu** (POKER-59, ~1 rdzenio-h) — warunek 6-godzinnego
   limitu joba.
4. **P-7 kill-check WTA@25bb** (POKER-61, 64,3 rdzenio-h) na Actions
   z szyfrowaniem artefaktów — najtańsza falsyfikacja tezy tierowej,
   odblokowana decyzją 30. Wynik rozstrzyga, czy P-8/P-9 w ogóle powstają.
5. **Miernik zewnętrzny HU** (0 rdzenio-h): `tools/` klient benchmarku
   GTO Wizard i Slumbota nad agentami z rejestru; jedna liczba z AIVAT dla
   `rule`, `mccfr`, `clone`, `mlp-clone`. Los linii c2 rozstrzyga ta liczba,
   nie arena.
6. **Maszyneria eksploatacji na otwartym korpusie** (P-10/P-11 co do
   mechaniki), bez twierdzeń o polu.

Bramka STOP z decyzji 29 (P-15) obowiązuje bez zmian: żaden bieg poza P-7
nie startuje bez pomiaru wyzwalającego — darmowy compute nie jest
wyzwalaczem.

## 7. Wejścia operatorskie (nic nie kupujemy, ale trzy rzeczy tylko operator może dać)

1. Zatwierdzenie tej decyzji i plan konta GitHub (pkt 3.4).
2. Wniosek o klucz API GTO Wizard Benchmark (formularz; decyzja uznaniowa
   po ich stronie) — Slumbot klucza nie wymaga.
3. Potwierdzenie tabeli tierów (P-8) i realny korpus Spin (P-12/P-13) —
   bez zmian wobec decyzji 29/30; ta decyzja ich nie zastępuje.

## 8. Czego ta decyzja nie robi

Nie zmienia architektury, algorytmu solvera, abstrakcji ani niezmienników;
nie otwiera drzewa (P-14 nadal wymaga własnego rekordu); nie zwalnia z bramki
STOP; nie uchyla zakazu publikacji artefaktu (wzmacnia go o szyfrowanie);
nie wprowadza żadnej zależności do pakietu `poker` (klienci HTTP i workflow
żyją w `tools/` i `.github/`); nie uznaje korpusu 2009 za pole; nie
przesądza, że GitHub Actions pozostanie darmowe — pkt 3.3 nazywa to
ryzykiem i wskazuje plan zapasowy.

## 9. Źródła (dostęp 2026-09-13)

- [S1] HRC — cennik: <https://www.holdemresources.net/hrc/pricing>
- [S2] ICMIZER — recenzja z cenami (wtórne): <https://www.vip-grinders.com/poker-tools/icmizer-review/>; <https://www.gipsyteam.com/poker/software/icmizer-3>
- [S3] GTO Wizard — ceny (wtórne, wrzesień 2026): <https://www.preflopwizard.app/blog/gto-wizard-alternative>
- [S4] PioSOLVER/MonkerSolver — ceny (wtórne): <https://www.vip-grinders.com/poker-tools/piosolver-review/>; <https://pokerfuse.com/learn-poker/tools/poker-solvers/>
- [S5] GTO Wizard — regulamin: <https://gtowizard.com/terms/>
- [S6] GTO Wizard Benchmark — regulamin: <https://gtowizard.com/benchmark/terms>
- [S7] TexasSolver (AGPL-3.0): <https://github.com/bupticybee/TexasSolver>; postflop-solver (AGPL-3.0): <https://github.com/b-inary/postflop-solver>
- [S8] AlphaHoldem, AAAI 2022: <https://ojs.aaai.org/index.php/AAAI/article/view/20394> (PDF: <https://cdn.aaai.org/ojs/20394/20394-13-24407-1-2-20220628.pdf>)
- [S9] GTO Wizard Benchmark, arXiv 2603.23660: <https://arxiv.org/abs/2603.23660>
- [S10] PokerNews, 2026-04: <https://www.pokernews.com/news/2026/04/gto-wizard-ai-outperforms-gpt-5-and-grok-4-in-new-benchmark-51020.htm>
- [S11] PokerSkill, arXiv 2605.30094: <https://arxiv.org/abs/2605.30094>
- [S12] DDCFR, ICLR 2024: <https://openreview.net/forum?id=6PbvbLyqT6>; kod: <https://github.com/rpSebastian/DDCFR>
- [S13] Deep (Predictive) Discounted CFR, arXiv 2511.08174 (AAAI 2026): <https://arxiv.org/abs/2511.08174>
- [S14] CS-RNR, arXiv 2607.28520: <https://arxiv.org/abs/2607.28520>
- [S15] GitHub — billing Actions: <https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions>
- [S16] GitHub Changelog 2025-12-16: <https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/>
- [S17] GitHub Blog — runnery 4 vCPU dla open source: <https://github.blog/news-insights/product-news/github-hosted-runners-double-the-power-for-open-source/>
- [S18] GitHub — limity Actions: <https://docs.github.com/en/actions/reference/limits>
- [S19] GitHub Changelog 2025-01-16 — arm64 dla repozytoriów publicznych: <https://github.blog/changelog/2025-01-16-linux-arm64-hosted-runners-now-available-for-free-in-public-repositories-public-preview/>
- [S20] GitHub Terms for Additional Products and Features (Actions): <https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features>
- [S21] Oracle — Always Free Resources: <https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm>
- [S22] InfoQ, 2026-07: <https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/>
- [S23] Google Colab FAQ: <https://research.google.com/colaboratory/faq.html>
- [S24] GTO Wizard Benchmark — strona: <https://gtowizard.com/benchmark/>; leaderboard: <https://benchmark.gtowizard.com/>
- [S25] Klient API: <https://github.com/gtowizard-ai/researcher-api-client>
- [S26] Slumbot: <https://slumbot.com/>; klient referencyjny: <https://github.com/Gongsta/Poker-AI/blob/main/slumbot/slumbot_api.py>
- [S27] phh-dataset (MIT): <https://github.com/uoftcprg/phh-dataset>
- [S28] Zenodo 17136841 (v3, wrzesień 2025): <https://zenodo.org/records/17136841>
- [S29] Pluribus — koszt blueprintu (~144 $, 8 dni; Science 2019 via Wikipedia): <https://en.wikipedia.org/wiki/Pluribus_(poker_bot)>

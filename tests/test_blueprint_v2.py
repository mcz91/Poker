"""Testy formatu `.bpk` v2 (POKER-57): sufity v1 zdjęte, dwie nowe sekcje.

v1 ma trzy twarde sufity: maskę osiągalności w uint16 (16 węzłów), dwa
zapisane sloty akcji (trzy akcje) i kwantyzację uint8 (zeruje ogony
mieszania). v2 zdejmuje wszystkie trzy i dokłada ex-post ε per stan oraz
marginesy indyferencji per infoset. Testy POKER-51 zostają nietknięte
w `test_blueprint_pilot.py` — v1 ma być bajt w bajt tym samym plikiem co
przed tym kontraktem, i to też jest tu asercją.

Artefakt kontrolny liczy się na miejscu (ten sam wycinek produkcyjny co
w POKER-51), a ex-post i marginesy dolicza się do niego, bo obie sekcje
opisują bieg, a nie plik.
"""

import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
BLUEPRINT = REPO / "tools" / "blueprint"
CONTROL_DIR = BLUEPRINT / "control"


def _load(name: str) -> Any:
    """Ładuje moduł z tools/blueprint pod nazwą stem — jak testy reprodukcji."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _import_reader() -> Any:
    from poker import blueprint_reader

    return blueprint_reader


# Krok kwantyzacji uint16: jeden poziom skali 65 535. Metoda największych reszt
# trzyma sumę dokładnie, więc błąd pojedynczego prawdopodobieństwa jest mniejszy
# od kroku — to granica round-tripu, nie próg dobrany do wyniku.
QUANT_STEP_U16 = 1.0 / 65535.0

# Sufity bajtów przeczytanych ze strumienia na JEDEN odczyt z artefaktu
# kontrolnego v2 (190 stanów, 4 klasy). Zmierzone `bench --sweep` i wpisane
# z zapasem na inną wersję zlib, a nie na inny sposób odczytu — tak jak
# sufity v1 w POKER-51. Blok v2 jest większy od v1 (uint16 i trzeci slot),
# więc sufit stanu jest wyższy niż 160 B z POKER-51.
# Zmierzone najgorsze przypadki na całym artefakcie: 180 B na stan, 56 B na V,
# 42 B na ε, 97 B na marginesy; sufity mają ~1,4x zapasu, tyle samo co sufity
# v1 w POKER-51 (116 -> 160 B).
CONTROL_V2_STATE_READ_MAX_BYTES = 260
CONTROL_V2_VALUE_READ_MAX_BYTES = 72
CONTROL_V2_EPS_READ_MAX_BYTES = 60
CONTROL_V2_MARGIN_READ_MAX_BYTES = 140

# Margines akcji dominującej w konstrukcji jam/fold WTA: próg z zapasem pod
# zmierzoną wartością (patrz blok POKER-57 w docs/CURRENT_STATE.md), a nie
# liczba dobrana do wyniku.
MARGIN_DOMINANT_MIN = 0.05

# Infosety artefaktu kontrolnego: 22 stany-warstwy × żywe węzły × 4 klasy.
CONTROL_INFOSETS = 416
# Z tego DECYZJAMI (co najmniej dwie legalne akcje) jest 376 — reszta to węzły
# osiągalne o jednej akcji. Rozkład marginesów artefaktu kontrolnego cytuje blok
# POKER-57 w docs/CURRENT_STATE.md, więc stoi tu jako niezmiennik.
CONTROL_MARGIN_INFOSETS = 376
CONTROL_MARGIN_MAX = 0.3027213513851166
CONTROL_MARGIN_MEDIAN = 0.07704192772507668
# Margines akcji dominującej w konstrukcji jam/fold WTA, klasa AA — liczba
# zmierzona, próg MARGIN_DOMINANT_MIN ma wobec niej dziesięciokrotny zapas.
MARGIN_AA_JAMFOLD_WTA = 0.5239
# Korzeń UTG artefaktu kontrolnego: AA MIESZA (0,898 open / 0,101 jam) przy
# marginesie 0,011568, a KK gra niemal czysto przy marginesie 0,000981.
CONTROL_ROOT_MARGIN_AA = 0.011567593552172184
CONTROL_ROOT_MARGIN_KK = 0.0009811840718612075


class _CountingStream:
    """Strumień liczący przeczytane bajty — dowód, że odczyt stanu nie czyta całości."""

    def __init__(self, handle: Any) -> None:
        self._handle = handle
        self.read_bytes = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        return int(self._handle.seek(offset, whence))

    def read(self, size: int = -1) -> bytes:
        chunk: bytes = self._handle.read(size)
        self.read_bytes += len(chunk)
        return chunk


@pytest.fixture(scope="module")
def v2_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Bieg kontrolny z DOLICZONYM ex-post i marginesami — wejście sekcji v2."""
    sg = _load("solve_grid")
    cc = _load("control_chain")
    ex = _load("expost")
    mg = _load("margins")
    out_dir = tmp_path_factory.mktemp("v2") / "solve"
    manifest = sg.solve(cc.control_config(), CONTROL_DIR / "tensor", out_dir)
    expost = ex.run_expost(out_dir, jobs=1)
    margins = mg.run_margins(out_dir, jobs=1)
    return {
        "out_dir": out_dir,
        "manifest": manifest,
        "sg": sg,
        "expost": expost,
        "margins": margins,
    }


@pytest.fixture(scope="module")
def packed_v2(v2_run: dict[str, Any], tmp_path_factory: pytest.TempPathFactory) -> Path:
    pk = _load("pack_blueprint")
    packed = tmp_path_factory.mktemp("v2file") / "control_v2.bpk"
    pk.pack(v2_run["out_dir"], packed, version=2)
    return packed


def test_naglowek_v2_zapowiada_sloty_sekcje_i_kwantyzacje(
    v2_run: dict[str, Any], packed_v2: Path
) -> None:
    """Nagłówek v2: wersja 2, uint16 domyślnie, cztery sloty (trzy zapisane), flagi sekcji.

    Pola v2 leżą w rezerwie v1, więc nagłówek nadal ma 128 bajtów — to jest
    powód, dla którego czytnik jednej wersji nie musi zgadywać rozmiaru.
    """
    br = _import_reader()
    pk = _load("pack_blueprint")
    head = packed_v2.read_bytes()[: br.HEADER_SIZE]
    assert head[:8] == br.MAGIC
    slots, stored, flags = br.HEADER_V2_STRUCT.unpack_from(head, br.HEADER_V2_OFFSET)
    assert (slots, stored) == (4, 3)
    assert flags == br.FLAG_EPSILON | br.FLAG_MARGINS
    with packed_v2.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        assert reader.format_version == br.FORMAT_VERSION_V2 == 2
        assert reader.quant_bits == pk.DEFAULT_QUANT_BITS_V2 == 16
        assert reader.n_slots == br.N_SLOTS_V2 == 4
        assert reader.config_hash == v2_run["manifest"]["config_hash"]
        assert reader.file_length == packed_v2.stat().st_size
        meta = json.loads(reader.meta_bytes())
        layers = reader.layers
    assert meta["format"] == {
        "version": 2,
        "quant_bits": 16,
        "levels": 65535,
        "stored_slots": [0, 1, 2],
        "derived_slot": 3,
        "method": "largest-remainder",
        "sections": ["epsilon", "margins"],
        "margin_levels": 255,
    }
    # Odcisk przebiegu (POKER-56) jest w metadanych v2 tak samo jak w v1 —
    # konsument pyta o „jaką grę opisuje ten plik" jednym polem.
    br.check_fingerprint(meta["fingerprint"], v2_run["manifest"]["fingerprint"])
    # Warstwa brzegowa niesie samo V: ani strategii, ani ε (ex-post jej nie liczy).
    assert [(info.has_policy, info.has_epsilon, info.has_margins) for info in layers] == [
        (True, True, True), (True, True, True), (False, False, False)
    ]


def test_konwerter_v2_daje_bajt_w_bajt_ten_sam_plik(
    v2_run: dict[str, Any], tmp_path: Path
) -> None:
    """Determinizm zapisu obowiązuje v2 tak samo jak v1 — z sekcjami włącznie."""
    pk = _load("pack_blueprint")
    first, second = tmp_path / "a.bpk", tmp_path / "b.bpk"
    summary = pk.pack(v2_run["out_dir"], first, version=2)
    pk.pack(v2_run["out_dir"], second, version=2)
    assert first.read_bytes() == second.read_bytes()
    assert summary["bytes"] == first.stat().st_size
    assert summary["sections"] == ["epsilon", "margins"]
    assert not list(tmp_path.glob("*.tmp"))


def test_v1_nie_zauwazyl_ze_powstalo_v2(v2_run: dict[str, Any], tmp_path: Path) -> None:
    """Plik v1 z biegu z sekcjami jest bajt w bajt plikiem v1 z biegu bez nich.

    v1 nie ma miejsca na ε ani marginesy i nie udaje, że ma: nie wchodzą do
    pliku ani do bloku metadanych, więc artefakt produkcyjny spakowany po
    POKER-57 ma ten sam sha co przed. Pola opisu formatu v1 zostają dokładnie
    tymi sześcioma, które opisał POKER-51.
    """
    pk = _load("pack_blueprint")
    af = _load("artifacts")
    br = _import_reader()
    stripped = tmp_path / "bez_sekcji"
    stripped.mkdir()
    for path in v2_run["out_dir"].iterdir():
        if path.name not in ("expost.npz", "margins.npz",
                             "expost_report.json", "margins_report.json"):
            (stripped / path.name).write_bytes(path.read_bytes())
    with_sections = tmp_path / "z.bpk"
    without = tmp_path / "bez.bpk"
    summary = pk.pack(v2_run["out_dir"], with_sections)
    pk.pack(stripped, without)
    assert with_sections.read_bytes() == without.read_bytes()
    assert summary["sections"] == []
    with with_sections.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        assert reader.format_version == br.FORMAT_VERSION == 1
        assert reader.quant_bits == pk.DEFAULT_QUANT_BITS == 8
        meta = json.loads(reader.meta_bytes())
    assert sorted(meta["format"]) == [
        "derived_slot", "levels", "method", "quant_bits", "stored_slots", "version"
    ]
    assert af.sha256_file(with_sections) == af.sha256_file(without)


def test_v2_round_trip_rozkladow_w_granicach_kroku_uint16(
    v2_run: dict[str, Any], packed_v2: Path
) -> None:
    """Wszystkie węzły i wszystkie klasy: cztery sloty, suma 1, błąd < krok uint16.

    W v1 slot jamu wynikał z dopełnienia; w v2 jest ZAPISANY, a z dopełnienia
    wynika slot czwarty — którego dzisiejsze drzewo nie ma, więc jest zerem.
    To jest miejsce na czwartą akcję w formacie, a nie akcja w drzewie.
    """
    br = _import_reader()
    sg = v2_run["sg"]
    layers = sg.load_layers(v2_run["out_dir"])
    checked = 0
    with packed_v2.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        for hand, layer in layers.items():
            for position, row in enumerate(layer["states"].tolist()):
                stacks = (int(row[0]), int(row[1]), int(row[2]))
                block = reader.state(hand, stacks)
                live = np.flatnonzero(layer["sigma"][position].sum(axis=(1, 2)) > 0.0)
                assert block.nodes() == tuple(int(node) for node in live)
                for node in block.nodes():
                    expected = layer["sigma"][position, node]
                    for klass, got in enumerate(block.policy_table(node)):
                        assert len(got) == 4
                        assert got[br.DERIVED_SLOT_V2] == 0.0
                        assert abs(sum(got) - 1.0) < 1e-9
                        for slot in range(3):
                            assert abs(got[slot] - float(expected[klass, slot])) < QUANT_STEP_U16
                        checked += 1
                    assert sum(block.quantized(node, 0)) == block.levels
    # Wszystkie infosety artefaktu kontrolnego (stan × żywy węzeł × klasa) —
    # liczba jest w bloku POKER-57, więc jest tu niezmiennikiem, a nie progiem.
    assert checked == CONTROL_INFOSETS


def test_czwarty_slot_wynika_z_dopelnienia_a_nie_z_zera() -> None:
    """Slot z dopełnienia niesie RESZTĘ skali, a nie zero — inaczej v2 to v1 z gorszą maską.

    W dzisiejszym drzewie czwarty slot jest zerem, bo trzy zapisane sumują się
    do pełnej skali; ten test jest o regule, nie o dzisiejszych danych, więc
    składa blok, w którym reszta jest niezerowa. Bez tego „czwarty slot"
    przeszedłby każdą asercję na artefakcie, będąc stałym zerem.
    """
    br = _import_reader()
    levels = (1 << 16) - 1
    stored = np.array([[10000, 12000], [20000, 21000], [30000, 31000]], dtype="<u2")
    block = br.StateBlock(
        hand=0, stacks=(1, 1, 1), node_mask=1, n_classes=2, quant_bits=16,
        payload=stored.tobytes(), n_slots=4,
    )
    assert block.n_stored == 3
    assert block.quantized(0, 0) == (10000, 20000, 30000, levels - 60000)
    assert block.quantized(0, 1) == (12000, 21000, 31000, levels - 64000)
    assert abs(sum(block.policy(0, 0)) - 1.0) < 1e-12
    v1_block = br.StateBlock(
        hand=0, stacks=(1, 1, 1), node_mask=1, n_classes=2, quant_bits=16,
        payload=stored[:2].tobytes(),
    )
    assert v1_block.n_stored == 2
    assert v1_block.quantized(0, 0) == (10000, 20000, levels - 30000)


def test_v2_wartosci_v_wracaja_bajtowo_dokladnie(
    v2_run: dict[str, Any], packed_v2: Path
) -> None:
    """Tablica V jest nieskompresowanym float64 także w v2 — kwantyzacja jej nie dotyka."""
    br = _import_reader()
    af = _load("artifacts")
    sg = v2_run["sg"]
    layers = sg.load_layers(v2_run["out_dir"])
    boundary = af.read_npz(v2_run["out_dir"] / "boundary.npz")
    with packed_v2.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        for hand, layer in layers.items():
            for position, row in enumerate(layer["states"].tolist()):
                stacks = (int(row[0]), int(row[1]), int(row[2]))
                assert reader.value(hand, stacks) == tuple(layer["v"][position].tolist())
        horizon = max(info.hand for info in reader.layers)
        for position, row in enumerate(boundary["states"].tolist()):
            stacks = (int(row[0]), int(row[1]), int(row[2]))
            assert reader.value(horizon, stacks) == tuple(boundary["v"][position].tolist())


def test_v2_epsilon_zgodne_co_do_wartosci_z_raportem_expost(
    v2_run: dict[str, Any], packed_v2: Path
) -> None:
    """ε w pliku to ta sama liczba co w `expost_report`, zapisana we float32.

    Bramką wysyłkową profilu ograniczonego (P-13) jest maksimum po żywych
    miejscach — więc to ono musi się zgadzać z raportem, a nie tylko średnia.
    """
    br = _import_reader()
    af = _load("artifacts")
    sg = v2_run["sg"]
    layers = sg.load_layers(v2_run["out_dir"])
    eps_source = af.read_npz(v2_run["out_dir"] / "expost.npz")
    worst = -1.0
    with packed_v2.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        for hand, layer in layers.items():
            source = eps_source[f"eps_{hand:02d}"]
            for position, row in enumerate(layer["states"].tolist()):
                stacks = (int(row[0]), int(row[1]), int(row[2]))
                got = reader.epsilon(hand, stacks)
                for seat in range(3):
                    assert got[seat] == float(np.float32(source[position, seat]))
                    if stacks[seat] > 0:
                        worst = max(worst, got[seat])
    assert worst == float(np.float32(v2_run["expost"]["epsilon_max"]))


def test_raport_marginesow_artefaktu_kontrolnego(v2_run: dict[str, Any]) -> None:
    """Rozkład marginesów artefaktu kontrolnego — liczby cytowane w dokumencie.

    376 decyzji z 416 infosetów: reszta to węzły osiągalne, w których drzewo
    zostawia jedną legalną akcję. Najmniejszy margines jest o cztery rzędy
    wielkości mniejszy od największego — pole ma sens tylko dlatego, że tak
    właśnie wygląda ten rozkład.
    """
    report = v2_run["margins"]
    assert report["n_infosets"] == CONTROL_MARGIN_INFOSETS
    assert report["margin_max"] == pytest.approx(CONTROL_MARGIN_MAX, rel=1e-9)
    assert report["margin_median"] == pytest.approx(CONTROL_MARGIN_MEDIAN, rel=1e-9)
    assert report["pool"] == 1.0


def test_mieszanie_w_sigma_nie_jest_dowodem_obojetnosci(v2_run: dict[str, Any]) -> None:
    """Komórka mieszana ma tu WIĘKSZY margines niż komórka niemal czysta.

    σ artefaktu to średnia najlepszych odpowiedzi PI-FP, więc niesie masę
    akcji, która była najlepsza wcześnie — mieszanie NIE implikuje
    obojętności. Gdyby implikowało, pole marginesu byłoby wyprowadzalne
    z rozkładu i nie musiałoby leżeć w pliku; ten test jest dowodem, że nie
    jest, i stoi na artefakcie, a nie na intuicji.
    """
    sg = _load("solve_grid")
    cc = _load("control_chain")
    af = _load("artifacts")
    classes = cc.control_classes()
    aces = classes.index(cc.class_index("AA"))
    kings = classes.index(cc.class_index("KK"))
    sigma = af.read_npz(v2_run["out_dir"] / "layer_00.npz")["sigma"][0, sg.N_U_ROOT]
    margin = af.read_npz(v2_run["out_dir"] / "margins.npz")["margin_00"][0, sg.N_U_ROOT]
    assert 0.05 < float(sigma[aces, sg.SLOT_JAM]) < 0.15
    assert float(sigma[kings, sg.SLOT_MID]) > 0.99
    assert float(margin[aces]) == pytest.approx(CONTROL_ROOT_MARGIN_AA, rel=1e-6)
    assert float(margin[kings]) == pytest.approx(CONTROL_ROOT_MARGIN_KK, rel=1e-6)
    assert float(margin[aces]) > float(margin[kings])


def test_v2_marginesy_wracaja_w_swojej_skali_i_z_wlasna_maska(
    v2_run: dict[str, Any], packed_v2: Path
) -> None:
    """Marginesy: zapis zgrubny (uint8 na skali stanu), odczyt dokładnie ten zapis.

    Maska marginesów jest WĘŻSZA od maski strategii — węzeł z jedną legalną
    akcją nie jest decyzją, więc nie ma marginesu zamiast mieć margines zero.
    """
    br = _import_reader()
    af = _load("artifacts")
    sg = v2_run["sg"]
    layers = sg.load_layers(v2_run["out_dir"])
    source = af.read_npz(v2_run["out_dir"] / "margins.npz")
    narrower = 0
    with packed_v2.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        for hand, layer in layers.items():
            values = source[f"margin_{hand:02d}"]
            decision = source[f"decision_{hand:02d}"]
            for position, row in enumerate(layer["states"].tolist()):
                stacks = (int(row[0]), int(row[1]), int(row[2]))
                block = reader.margins(hand, stacks)
                strategy = reader.state(hand, stacks)
                live = values[position][decision[position]]
                # Oczekiwanie liczone TU, z reguły opisanej w dokumencie —
                # a nie funkcją konwertera, bo wtedy porównywalibyśmy zapis
                # z jego własną repliką (PUŁAPKA replik z POKER-51).
                expected_scale = float(np.float32(live.max()))
                assert block.scale == expected_scale
                assert block.nodes() == tuple(
                    int(node) for node in np.flatnonzero(decision[position])
                )
                narrower += len(strategy.nodes()) - len(block.nodes())
                for node in block.nodes():
                    for klass in range(block.n_classes):
                        exact = float(values[position, node, klass])
                        expected_q = int(exact / expected_scale * br.MARGIN_LEVELS + 0.5)
                        assert block.quantized(node, klass) == expected_q
                        assert block.margin(node, klass) == (
                            expected_q * block.scale / br.MARGIN_LEVELS
                        )
                        assert abs(block.margin(node, klass) - exact) <= (
                            block.scale / (2 * br.MARGIN_LEVELS) + 1e-9
                        )
    assert narrower > 0


def _shuffled_run_v2(source: Path, target: Path, seed: int) -> int:
    """Kopia biegu z przetasowanymi wierszami warstw ORAZ obu sekcji v2.

    ε i marginesy są indeksowane porządkiem wierszy warstwy, a nie kluczem
    stanu, więc konwerter musi je przenumerować tą samą permutacją, którą
    sortuje klucze. Solver dzisiaj emituje stany posortowane, więc pominięcie
    tego przenumerowania niczego by nie zepsuło — do pierwszego artefaktu
    o innym porządku, gdzie ε trafiłoby pod cudzy stan.
    """
    af = _load("artifacts")
    manifest = json.loads((source / "solve_manifest.json").read_text())
    target.mkdir(parents=True, exist_ok=True)
    rng = np.random.Generator(np.random.PCG64(seed))
    orders: dict[int, np.ndarray] = {}
    files = {int(key): manifest["layers"][key]["file"] for key in manifest["layers"]}
    shuffled = 0
    for hand, name in sorted(files.items()):
        arrays = af.read_npz(source / name)
        order = rng.permutation(arrays["states"].shape[0])
        orders[hand] = order
        if list(order) != sorted(order):
            shuffled += 1
        af.write_npz(target / name, {key: value[order] for key, value in arrays.items()})
        manifest["layers"][str(hand)]["sha256"] = af.sha256_file(target / name)
    boundary = af.read_npz(source / manifest["boundary"]["file"])
    af.write_npz(target / manifest["boundary"]["file"], boundary)
    manifest["boundary"]["sha256"] = af.sha256_file(target / manifest["boundary"]["file"])
    for name, prefixes in (("expost.npz", ("eps",)), ("margins.npz", ("margin", "decision"))):
        arrays = af.read_npz(source / name)
        af.write_npz(target / name, {
            key: value[orders[int(key.split("_")[1])]]
            if key.split("_")[0] in prefixes else value
            for key, value in arrays.items()
        })
    af.write_json(target / "solve_manifest.json", manifest)
    return shuffled


def test_sekcje_v2_ida_za_stanem_a_nie_za_wierszem(
    v2_run: dict[str, Any], packed_v2: Path, tmp_path: Path
) -> None:
    """Przetasowany bieg daje te same ε i marginesy pod tymi samymi stanami."""
    pk = _load("pack_blueprint")
    br = _import_reader()
    shuffled_dir = tmp_path / "shuffled"
    assert _shuffled_run_v2(v2_run["out_dir"], shuffled_dir, seed=57) >= 1
    packed = tmp_path / "shuffled_v2.bpk"
    pk.pack(shuffled_dir, packed, version=2)
    seen = 0
    with packed.open("rb") as handle, packed_v2.open("rb") as origin:
        reader = br.BlueprintReader(handle)
        reference = br.BlueprintReader(origin)
        for info in reader.layers:
            keys = [reader.state_key(info.hand, index) for index in range(info.n_states)]
            assert keys == sorted(keys)
            for stacks in keys:
                if not info.has_epsilon:
                    continue
                assert reader.epsilon(info.hand, stacks) == reference.epsilon(info.hand, stacks)
                block = reader.margins(info.hand, stacks)
                origin_block = reference.margins(info.hand, stacks)
                assert block.node_mask == origin_block.node_mask
                assert block.scale == origin_block.scale
                assert block.payload == origin_block.payload
                seen += 1
    assert seen == 22


def test_margines_zna_obojetnosc_i_dominacje(v2_run: dict[str, Any]) -> None:
    """Konstrukcja: gra o stałej wypłacie → margines 0; jam z AA na krótkim stacku → duży.

    Pierwszy przypadek jest obojętnością Z KONSTRUKCJI, a nie zaobserwowaną:
    przy wypłatach (1/3, 1/3, 1/3) i takiej samej kontynuacji każda akcja daje
    dokładnie tyle samo, więc różnica dwóch najlepszych musi zniknąć w szumie
    arytmetyki f32. Drugi jest dominacją z konstrukcji: w drzewie jam/fold
    2-osobowym przy wypłatach WTA klasa AA nie ma czym przegrać przez fold.

    Mieszanie w σ artefaktu NIE jest dowodem obojętności i dlatego nie jest tu
    kryterium: σ to średnia najlepszych odpowiedzi PI-FP, więc niesie masę
    akcji, która była najlepsza wcześnie — i właśnie po to jest to pole.
    """
    sg = _load("solve_grid")
    cc = _load("control_chain")
    mg = _load("margins")
    tensors = sg.load_tensors(CONTROL_DIR / "tensor", cc.control_classes())
    n_classes = tensors.count

    def uniform(problem: Any) -> dict[int, np.ndarray]:
        sigma = {}
        for node_id in problem.nodes:
            allowed = problem.allowed[node_id]
            matrix = np.zeros((n_classes, 3), dtype=np.float32)
            for slot in allowed:
                matrix[:, slot] = 1.0 / len(allowed)
            sigma[node_id] = matrix
        return sigma

    flat = sg.GridConfig(prizes=(1 / 3, 1 / 3, 1 / 3), classes=cc.control_classes(),
                         total_chips=cc.control_config().total_chips,
                         start_stacks=cc.control_config().start_stacks,
                         grid_step=cc.control_config().grid_step)
    stacks = tuple(flat.start_stacks)
    problem, _, _ = sg.build_stage_problem(
        tensors, flat, stacks, 0, 1, 2,
        lambda target: np.full(3, 1 / 3, dtype=np.float64),
    )
    margin, decision = mg.state_margins(problem, uniform(problem), sg.N_NODES)
    assert decision.any()
    assert float(np.max(np.abs(margin[decision]))) < 1e-6

    wta = sg.GridConfig(prizes=(1.0, 0.0, 0.0), classes=cc.control_classes(),
                        total_chips=cc.control_config().total_chips,
                        start_stacks=cc.control_config().start_stacks,
                        grid_step=cc.control_config().grid_step)
    hu_stacks = (0, wta.total_chips // 2, wta.total_chips - wta.total_chips // 2)
    problem, _, mode = sg.build_stage_problem(
        tensors, wta, hu_stacks, 0, 6, 12,
        lambda target: np.asarray(
            [target[seat] / wta.total_chips for seat in range(3)], dtype=np.float64
        ),
    )
    assert mode == "hu-jamfold"
    margin, decision = mg.state_margins(problem, uniform(problem), sg.N_NODES)
    classes = cc.control_classes()
    aces = classes.index(cc.class_index("AA"))
    worst_class = classes.index(cc.class_index("72o"))
    assert margin[sg.H_ROOT, aces] > MARGIN_DOMINANT_MIN
    assert margin[sg.H_ROOT, aces] == pytest.approx(MARGIN_AA_JAMFOLD_WTA, rel=1e-3)
    # Jam z AA i fold z 72o to dwie DOMINACJE, nie dominacja i obojętność —
    # zdanie porównawcze między nimi byłoby zdaniem o niczym, więc go nie ma:
    # obie mają być duże, bo w obu alternatywa jest wyraźnie gorsza.
    assert margin[sg.H_ROOT, worst_class] > MARGIN_DOMINANT_MIN


def test_v2_zdejmuje_sufit_szesnastu_wezlow(v2_run: dict[str, Any], tmp_path: Path) -> None:
    """Bieg o 17 węzłach: v1 odmawia (maska uint16), v2 pakuje i czyta węzeł 16.

    To jest sufit, który blokował KAŻDE poszerzenie drzewa (dziś 14 węzłów +
    4 sloty HU). Test jest na artefakcie, a nie na stałej: warstwy kontrolne
    dostają siedemnasty węzeł skopiowany z zerowego.
    """
    pk = _load("pack_blueprint")
    af = _load("artifacts")
    br = _import_reader()
    wide = tmp_path / "wide"
    wide.mkdir()
    manifest = json.loads((v2_run["out_dir"] / "solve_manifest.json").read_text())
    for path in v2_run["out_dir"].glob("*.npz"):
        # Marginesy zostają: mierzymy sufit MASKI, a sekcja marginesów o innej
        # liczbie węzłów niż warstwa jest osobnym błędem i ma osobny test.
        if path.name == "margins.npz":
            continue
        arrays = af.read_npz(path)
        if "sigma" in arrays:
            sigma = arrays["sigma"]
            grown = np.zeros((sigma.shape[0], 17, sigma.shape[2], sigma.shape[3]),
                             dtype=sigma.dtype)
            grown[:, : sigma.shape[1]] = sigma
            grown[:, 16] = sigma[:, 0]
            arrays["sigma"] = grown
        af.write_npz(wide / path.name, arrays)
    for entry in manifest["layers"].values():
        entry["sha256"] = af.sha256_file(wide / entry["file"])
    manifest["boundary"]["sha256"] = af.sha256_file(wide / manifest["boundary"]["file"])
    af.write_json(wide / "solve_manifest.json", manifest)

    with pytest.raises(ValueError, match="sufit v1"):
        pk.pack(wide, tmp_path / "wide_v1.bpk")
    with pytest.raises(ValueError, match="węzłów, a warstwa biegu"):
        af.write_npz(wide / "margins.npz",
                     af.read_npz(v2_run["out_dir"] / "margins.npz"))
        pk.pack(wide, tmp_path / "wide_v2_zla_sekcja.bpk", version=2)
    (wide / "margins.npz").unlink()
    packed = tmp_path / "wide_v2.bpk"
    summary = pk.pack(wide, packed, version=2)
    assert summary["n_nodes"] == 17
    with packed.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        info = reader.layers[0]
        key = reader.state_key(info.hand, 0)
        block = reader.state(info.hand, key)
        assert block.has_node(16)
        assert block.policy(16, 0) == block.policy(0, 0)


def test_czytnik_odrzuca_obca_wersje_i_v1_przestemplowane_na_v2(
    v2_run: dict[str, Any], packed_v2: Path, tmp_path: Path
) -> None:
    """Wersja spoza obsługiwanych leci błędem, a v1 z podmienioną wersją też.

    Plik v1 przestemplowany na 2 nie jest plikiem v2: pola v2 leżą w rezerwie
    v1, więc zapowiada zero slotów akcji. To jest powód odmowy — nie
    przypadkowe potknięcie się na cudzym katalogu warstw.
    """
    pk = _load("pack_blueprint")
    br = _import_reader()
    v1 = tmp_path / "control.bpk"
    pk.pack(v2_run["out_dir"], v1)
    raw_v1 = v1.read_bytes()
    raw_v2 = packed_v2.read_bytes()
    cases = {
        "v1 przestemplowane na v2": raw_v1[:8] + (2).to_bytes(2, "little") + raw_v1[10:],
        "wersja 3": raw_v2[:8] + (3).to_bytes(2, "little") + raw_v2[10:],
        "magia": b"XXXXXXXX" + raw_v2[8:],
        "kwantyzacja": raw_v2[:10] + (7).to_bytes(2, "little") + raw_v2[12:],
        "obcięty nagłówek": raw_v2[: br.HEADER_SIZE - 1],
    }
    for label, payload in cases.items():
        with pytest.raises(br.BlueprintFormatError):
            br.BlueprintReader(io.BytesIO(payload))
        assert issubclass(br.BlueprintFormatError, ValueError), label


def test_brak_sekcji_jest_jawny_a_nie_cichym_zerem(
    v2_run: dict[str, Any], packed_v2: Path, tmp_path: Path
) -> None:
    """Plik v1 i warstwa brzegowa nie mają ε ani marginesów — i mówią to wyjątkiem."""
    pk = _load("pack_blueprint")
    br = _import_reader()
    v1 = tmp_path / "control.bpk"
    pk.pack(v2_run["out_dir"], v1)
    with v1.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        stacks = tuple(v2_run["manifest"]["config"]["start_stacks"])
        with pytest.raises(br.SectionMissing):
            reader.epsilon(0, stacks)
        with pytest.raises(br.SectionMissing):
            reader.margins(0, stacks)
    with packed_v2.open("rb") as handle:
        reader = br.BlueprintReader(handle)
        horizon = max(info.hand for info in reader.layers)
        boundary_key = reader.state_key(horizon, 0)
        with pytest.raises(br.SectionMissing):
            reader.epsilon(horizon, boundary_key)
        with pytest.raises(br.SectionMissing):
            reader.margins(horizon, boundary_key)
        with pytest.raises(br.LayerNotFound):
            reader.epsilon(horizon + 7, boundary_key)
        with pytest.raises(br.StateNotFound):
            reader.epsilon(0, (1, 1, 1))
    assert issubclass(br.SectionMissing, LookupError)
    for other in (br.NodeUnreachable, br.PolicyMissing, br.StateNotFound, br.LayerNotFound):
        assert not issubclass(other, br.SectionMissing)
        assert not issubclass(br.SectionMissing, other)


def test_odczyt_v2_nie_czyta_calego_pliku(v2_run: dict[str, Any], packed_v2: Path) -> None:
    """Sufity bajtów na jeden odczyt: stan, V, ε i marginesy — z zapasem na zlib."""
    br = _import_reader()
    with packed_v2.open("rb") as handle:
        counting = _CountingStream(handle)
        reader = br.BlueprintReader(counting)
        info = reader.layers[1]
        key = reader.state_key(info.hand, info.n_states - 1)
        counting.read_bytes = 0
        reader.seat_value(info.hand, key, 0)
        value_bytes = counting.read_bytes
        counting.read_bytes = 0
        block = reader.state(info.hand, key)
        block.policy(min(block.nodes()), 0)
        state_bytes = counting.read_bytes
        counting.read_bytes = 0
        reader.epsilon(info.hand, key)
        eps_bytes = counting.read_bytes
        counting.read_bytes = 0
        margins = reader.margins(info.hand, key)
        margins.margin(min(margins.nodes()), 0)
        margin_bytes = counting.read_bytes
    assert value_bytes <= CONTROL_V2_VALUE_READ_MAX_BYTES
    assert state_bytes <= CONTROL_V2_STATE_READ_MAX_BYTES
    assert eps_bytes <= CONTROL_V2_EPS_READ_MAX_BYTES
    assert margin_bytes <= CONTROL_V2_MARGIN_READ_MAX_BYTES
    assert state_bytes < packed_v2.stat().st_size // 4


def test_sweep_v2_mierzy_wszystkie_sekcje(packed_v2: Path) -> None:
    """`bench --sweep` na v2 przemiela też ε i marginesy — maksimum, nie percentyl próbki."""
    pk = _load("pack_blueprint")
    report = pk.bench(packed_v2, samples=32, sweep=True)["sweep"]
    assert report["state_bytes_max"] <= CONTROL_V2_STATE_READ_MAX_BYTES
    assert report["value_bytes_max"] <= CONTROL_V2_VALUE_READ_MAX_BYTES
    assert report["eps_bytes_max"] <= CONTROL_V2_EPS_READ_MAX_BYTES
    assert report["margin_bytes_max"] <= CONTROL_V2_MARGIN_READ_MAX_BYTES
    assert report["state_reads"] == report["eps_reads"] == report["margin_reads"]


def test_round_trip_v2_przez_requantize_zachowuje_sloty(
    v2_run: dict[str, Any], tmp_path: Path
) -> None:
    """`requantize` v2 wraca CZYTNIKIEM: kopia biegu ma trzy sloty i błąd < krok uint16."""
    pk = _load("pack_blueprint")
    af = _load("artifacts")
    sg = v2_run["sg"]
    out = tmp_path / "q16"
    summary = pk.requantize_run(v2_run["out_dir"], out, tmp_path / "q16.bpk", version=2)
    assert summary["quant_bits"] == 16
    source = sg.load_layers(v2_run["out_dir"])
    copy = sg.load_layers(out)
    for hand, layer in source.items():
        assert copy[hand]["sigma"].shape == layer["sigma"].shape
        delta = np.abs(copy[hand]["sigma"] - layer["sigma"])
        assert float(delta.max()) < QUANT_STEP_U16
        assert np.array_equal(copy[hand]["v"], layer["v"])
    manifest = af.read_json(out / "solve_manifest.json")
    assert manifest["requantized"]["format_version"] == 2
    assert manifest["requantized"]["quant_bits"] == 16

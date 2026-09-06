"""Czytnik binarnego artefaktu blueprintu (POKER-51) — czysty stdlib.

Format `.bpk` opisuje bajt po bajcie `docs/CURRENT_STATE.md` (blok POKER-51);
tu jest jego jedyny czytnik po stronie produktu. Trzy decyzje kształtują to
API:

1. **Dostęp swobodny.** Stan czyta się bez ładowania i dekompresji całości:
   binarne wyszukiwanie klucza w tablicy stanów warstwy, potem jeden blok
   zlib tego stanu. Wartość V czyta się jeszcze taniej — tablica V jest
   nieskompresowana, więc pojedyncza liczba to `seek` + osiem bajtów.
2. **Silnik nie wykonuje I/O** (INV-P7, `test_silnik_nie_wykonuje_io`).
   Czytnik nie otwiera plików: dostaje otwarty strumień binarny i tylko po
   nim skacze. Otwarcie pliku należy do adaptera albo narzędzia.
   Z tego samego powodu blok metadanych wraca jako bajty — JSON parsuje
   konsument, bo `json` jest importem zabronionym w silniku.
3. **Nieosiągalność jest jawna.** Węzeł spoza maski osiągalności nie ma
   rozkładu — odczyt podnosi `NodeUnreachable`, nigdy nie zwraca cichego
   rozkładu zerowego ani równego. To jest kontrakt dla fallbacku agenta.
4. **Fingerprint przebiegu sprawdza się jawnie** (POKER-56). Artefakt nie
   mówi sam z siebie, JAKĄ grę policzył: kształt wypłat, żetony, zegar i krok
   siatki żyją w metadanych, a konsument ma własne oczekiwania. Rodzina
   blueprintów per tier (decyzja 29) sprawia, że pomyłka o jeden plik jest
   cicha — te same warstwy, ta sama siatka, inna gra. `check_fingerprint`
   RZUCA przy pierwszej różnicy, zamiast pozwolić grać dalej.
5. **Dwie wersje formatu, jeden czytnik** (POKER-57). v1 zdejmuje się bajt
   w bajt jak dotąd; v2 zdejmuje trzy sufity v1 (maska osiągalności uint32
   zamiast uint16, cztery sloty akcji zamiast trzech, kwantyzacja uint16
   domyślnie) i dokłada dwie sekcje opcjonalne: ex-post ε per stan i miejsce
   oraz marginesy indyferencji per infoset. Sekcji NIEOBECNEJ nie udaje się
   zerami — odczyt podnosi `SectionMissing`, jak każda inna nieobecność
   w tym API. Spec bajtowa: blok POKER-57 w `docs/CURRENT_STATE.md`.
"""

import struct
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

MAGIC = b"POKERBP1"
# Wersja domyślna zapisu: v1 (POKER-51). v2 (POKER-57) zapisuje się jawnie,
# a czytnik obsługuje obie — artefakt produkcyjny zostaje v1, dopóki nie
# przepakuje go osobna decyzja.
FORMAT_VERSION = 1
FORMAT_VERSION_V2 = 2
SUPPORTED_VERSIONS = (FORMAT_VERSION, FORMAT_VERSION_V2)

HEADER_SIZE = 128
LAYER_RECORD_SIZE = 48
LAYER_RECORD_SIZE_V2 = 80
BLOCK_INDEX_SIZE = 16
STATE_KEY_SIZE = 6
VALUE_RECORD_SIZE = 24
EPS_RECORD_SIZE = 12
SEATS = 3

# Sloty akcji artefaktu: 0 = fold, 1 = środkowy (open/call/3bet), 2 = jam.
# v1 zapisuje dwa pierwsze, trzeci wynika z dopełnienia do pełnej skali.
STORED_SLOTS = (0, 1)
DERIVED_SLOT = 2
N_SLOTS = 3
# v2 ma cztery sloty: trzy zapisane, czwarty z dopełnienia. Dzisiejsze drzewo
# ma trzy akcje, więc slot 3 jest w nim zerem — miejsce jest w formacie, a nie
# w drzewie (poszerzenie drzewa to osobny rekord decyzyjny, P-14).
STORED_SLOTS_V2 = (0, 1, 2)
DERIVED_SLOT_V2 = 3
N_SLOTS_V2 = 4

# Skala marginesu indyferencji: uint8 na skali stanu (float32 w bloku).
# Zapis jest ZGRUBNY z wyboru (decyzja 29 pkt 3): pole ma odpowiadać na
# pytanie „czy ta komórka jest bliska obojętności", a nie nieść EV.
MARGIN_LEVELS = 255

# Flagi nagłówka v2: które sekcje opcjonalne plik w ogóle niesie.
# O pojedynczej warstwie rozstrzyga jej rekord katalogu, nie flaga.
FLAG_EPSILON = 1
FLAG_MARGINS = 2

# Układ bajtowy formatu — jedno źródło prawdy dzielone z konwerterem w tools/blueprint.
# `HEADER_STRUCT` to wspólne 104 bajty obu wersji; v2 dokłada `HEADER_V2_STRUCT`
# pod offsetem 104, w rezerwie v1 (dlatego nagłówek nadal ma 128 B).
HEADER_STRUCT = struct.Struct("<8sHHIII QQQ QQQ 32s")
HEADER_V2_OFFSET = 104
HEADER_V2_STRUCT = struct.Struct("<HHI")
LAYER_STRUCT = struct.Struct("<IIBB6x QQQQ")
LAYER_V2_STRUCT = struct.Struct("<IIBBBB4x QQQQ QQQ8x")
BLOCK_INDEX_STRUCT = struct.Struct("<QII")
STATE_KEY_STRUCT = struct.Struct("<3h")
VALUE_ROW_STRUCT = struct.Struct("<3d")
VALUE_ONE_STRUCT = struct.Struct("<d")
EPS_ROW_STRUCT = struct.Struct("<3f")
MASK_STRUCT = struct.Struct("<H")
MASK_V2_STRUCT = struct.Struct("<I")
MARGIN_HEAD_STRUCT = struct.Struct("<If")


class ByteSource(Protocol):
    """Czego czytnik naprawdę potrzebuje od strumienia: skoku i odczytu.

    Węższe niż `BinaryIO`, bo dzięki temu legalnym wejściem jest też otoczka
    licząca bajty albo bufor w pamięci — a właśnie na otoczce liczącej stoi
    dowód, że odczyt jednego stanu nie czyta całego pliku.
    """

    def seek(self, offset: int, whence: int = 0, /) -> int: ...

    def read(self, size: int = -1, /) -> bytes: ...


class BlueprintError(Exception):
    """Wspólny nadtyp błędów artefaktu blueprintu."""


class BlueprintFormatError(BlueprintError, ValueError):
    """Plik nie jest artefaktem blueprintu albo jest niespójny."""


class BlueprintLookupError(BlueprintError, LookupError):
    """Pytanie o coś, czego artefakt nie zawiera."""


class LayerNotFound(BlueprintLookupError):
    """Numer ręki spoza warstw artefaktu."""


class StateNotFound(BlueprintLookupError):
    """Wektor stacków spoza siatki stanów tej warstwy — stan nieosiągalny."""


class NodeUnreachable(BlueprintLookupError):
    """Węzeł, którego artefakt w tym stanie nie opisuje.

    W bloku strategii znaczy „poza maską osiągalności" (drzewo gry etapowej
    tam nie dochodzi). W bloku marginesów (v2) znaczy dodatkowo „nie ma tu
    czego mierzyć": węzeł osiągalny, ale z jedną legalną akcją nie jest
    decyzją, a margines zero byłby o nim nieprawdą.
    """


class PolicyMissing(BlueprintLookupError):
    """Warstwa niesie wyłącznie V (warunek brzegowy) — nie ma w niej strategii."""


class SectionMissing(BlueprintLookupError):
    """Sekcja opcjonalna (ε per stan, marginesy) nie jest w tym pliku ani warstwie.

    Rozróżnialna od `NodeUnreachable` i `PolicyMissing` z tego samego powodu,
    dla którego tamte są rozróżnialne między sobą: „nie policzono" to co innego
    niż „policzono zero", a konsument bramkujący wysyłkę profilu ograniczonego
    (P-13) musi te dwa przypadki rozdzielić.
    """


class FingerprintMismatch(BlueprintError, ValueError):
    """Artefakt opisuje inny przebieg niż ten, którego oczekuje konsument."""


# Rodzaj profilu w artefakcie: równowagowy blueprint tieru albo profil
# ograniczony miejscem (Data-Biased Response, decyzja 29 pkt 3B) — te dwa
# nigdy nie są wymienne, bo V z DBR nie zasila AIVAT.
PROFILE_BLUEPRINT = "blueprint"
PROFILE_DBR = "dbr"

# Konwencja hero: jedna tablica V wspólna dla wszystkich miejsc (blueprint)
# albo trzy tablice indeksowane miejscem hero (DBR, nigdy zmiksowana).
HERO_SYMMETRIC = "symmetric"
HERO_SEAT_RESTRICTED = "seat-restricted"


def _canonical(value: Any) -> Any:
    """Porównywalna postać wartości: listy JSON-a i krotki Pythona to to samo."""
    if isinstance(value, (list, tuple)):
        return tuple(_canonical(item) for item in value)
    return value


def run_fingerprint(
    *,
    prizes: object,
    total_chips: int,
    levels: object,
    hands_per_level: int,
    grid_step: int,
    profile: str = PROFILE_BLUEPRINT,
    hero: str = HERO_SYMMETRIC,
    **extra: object,
) -> dict[str, Any]:
    """Odcisk przebiegu: co trzeba wiedzieć, żeby NIE pomylić artefaktów.

    Słownik jest rozszerzalny (`extra`) — kolejne kontrakty dokładają pola,
    a `check_fingerprint` porównuje tylko to, o co pyta konsument, więc nowe
    pole nie unieważnia starych oczekiwań. `levels` to ROZWINIĘTE poziomy
    blindów, nigdy `None`: dwa biegi o tej samej siatce i innym zegarze to dwie
    różne gry.
    """
    out: dict[str, Any] = {
        "prizes": _canonical(prizes),
        "total_chips": total_chips,
        "levels": _canonical(levels),
        "hands_per_level": hands_per_level,
        "grid_step": grid_step,
        "profile": profile,
        "hero": hero,
    }
    out.update({key: _canonical(value) for key, value in extra.items()})
    return out


def check_fingerprint(
    actual: Mapping[str, Any] | None, expected: Mapping[str, Any]
) -> None:
    """Fingerprint artefaktu wobec oczekiwań konsumenta — wyjątek przy pierwszej różnicy.

    Klucz, którego artefakt nie niesie, jest różnicą tak samo jak wartość inna:
    „nie wiem, jaką grę czytam" nie może kończyć się cichym graniem. Z tego
    samego powodu `None` (artefakt spakowany przed POKER-56, gdzie naturalnym
    wywołaniem jest `meta.get("fingerprint")`) jest różnicą, a nie błędem typu:
    inaczej wypadałby poza `except FingerprintMismatch` konsumenta.
    """
    if actual is None:
        raise FingerprintMismatch(
            "artefakt nie niesie odcisku przebiegu, a konsument oczekuje "
            f"{ {key: _canonical(expected[key]) for key in sorted(expected)} }"
        )
    for key in sorted(expected):
        want = _canonical(expected[key])
        if key not in actual:
            raise FingerprintMismatch(
                f"fingerprint artefaktu nie niesie pola {key!r}, a konsument oczekuje {want!r}"
            )
        have = _canonical(actual[key])
        if have != want:
            raise FingerprintMismatch(
                f"fingerprint artefaktu: {key} = {have!r}, konsument oczekuje {want!r}"
            )


@dataclass(frozen=True)
class LayerInfo:
    """Opis warstwy: numer ręki, liczba stanów i które sekcje warstwa niesie."""

    hand: int
    n_states: int
    has_policy: bool
    has_epsilon: bool = False
    has_margins: bool = False


@dataclass(frozen=True)
class _LayerRecord:
    hand: int
    n_states: int
    has_policy: bool
    states_offset: int
    values_offset: int
    index_offset: int
    eps_offset: int = 0
    margin_index_offset: int = 0


@dataclass(frozen=True)
class StateBlock:
    """Rozpakowany blok jednego stanu: maska osiągalności i skwantowane rozkłady.

    `payload` to bajty bloku bez maski (uint16 w v1, uint32 w v2); węzły leżą
    w nim rosnąco po numerze, każdy jako `n_slots - 1` kolumn po `n_classes`
    wartości (slot 0, potem 1, w v2 jeszcze 2). Kolejność kolumnowa, nie
    przeplot — sąsiadujące wartości tego samego slotu są podobne, więc zlib
    pakuje je ciaśniej.
    """

    hand: int
    stacks: tuple[int, int, int]
    node_mask: int
    n_classes: int
    quant_bits: int
    payload: bytes
    n_slots: int = N_SLOTS

    @property
    def levels(self) -> int:
        """Największa wartość skwantowana — pełne prawdopodobieństwo 1,0."""
        return (1 << self.quant_bits) - 1

    @property
    def n_stored(self) -> int:
        """Ile slotów leży w bloku: wszystkie oprócz ostatniego (ten z dopełnienia)."""
        return self.n_slots - 1

    def has_node(self, node: int) -> bool:
        return bool(self.node_mask >> node & 1) if node >= 0 else False

    def nodes(self) -> tuple[int, ...]:
        return tuple(node for node in range(self.node_mask.bit_length()) if self.has_node(node))

    def _column_offset(self, node: int) -> int:
        if not self.has_node(node):
            raise NodeUnreachable(
                f"węzeł {node} poza maską osiągalności stanu {self.stacks} ręki {self.hand}"
            )
        rank = (self.node_mask & ((1 << node) - 1)).bit_count()
        return rank * self.n_stored * self.n_classes * (self.quant_bits // 8)

    def _raw(self, offset: int) -> int:
        if self.quant_bits == 8:
            return self.payload[offset]
        return int.from_bytes(self.payload[offset : offset + 2], "little")

    def quantized(self, node: int, klass: int) -> tuple[int, ...]:
        """Surowe wartości skwantowane: zapisane sloty, ostatni z dopełnienia.

        Krotka ma tyle pozycji, ile format ma slotów akcji (v1: 3, v2: 4) —
        slot z dopełnienia jest zawsze ostatni, więc numery slotów 0..2 znaczą
        w obu wersjach to samo i konsument v1 czyta v2 bez przeliczania.
        """
        if not 0 <= klass < self.n_classes:
            raise BlueprintLookupError(f"klasa {klass} poza zakresem 0..{self.n_classes - 1}")
        width = self.quant_bits // 8
        base = self._column_offset(node)
        stored = tuple(
            self._raw(base + (slot * self.n_classes + klass) * width)
            for slot in range(self.n_stored)
        )
        return (*stored, self.levels - sum(stored))

    def policy(self, node: int, klass: int) -> tuple[float, ...]:
        """Rozkład akcji (fold, środkowy, jam, [rezerwa v2]) po dekwantyzacji."""
        scale = float(self.levels)
        return tuple(value / scale for value in self.quantized(node, klass))

    def policy_table(self, node: int) -> tuple[tuple[float, ...], ...]:
        """Rozkłady wszystkich klas węzła — ta sama droga co `policy`, nie jej kopia.

        Osobna, „szybsza" pętla dekwantyzacji byłaby drugą implementacją
        dopełnienia trzeciego slotu, której testy na `policy` już by nie
        chroniły; koszt jednej dodatkowej maski na klasę jest tego wart.
        """
        return tuple(self.policy(node, klass) for klass in range(self.n_classes))


@dataclass(frozen=True)
class MarginBlock:
    """Marginesy indyferencji jednego stanu: o ile najlepsza akcja bije drugą.

    Wartość jest w jednostkach SUMY WEKTORA WYPŁAT (tych samych co ε) i jest
    WARUNKOWA: to różnica EV dwóch najlepszych akcji na jedną rękę klasy, która
    tę decyzję podejmuje — nie ważona tym, jak często przeciwnicy do węzła
    dochodzą. Zapis jest zgrubny (uint8 na skali stanu), bo pole ma rozstrzygać
    „czy ta komórka jest bliska obojętności", a nie zastępować EV.

    Maska jest WĘŻSZA niż maska strategii: węzeł, w którym drzewo zostawia
    jedną legalną akcję, nie ma marginesu (nie ma wyboru), a nie margines zero.
    """

    hand: int
    stacks: tuple[int, int, int]
    node_mask: int
    n_classes: int
    scale: float
    payload: bytes

    def has_node(self, node: int) -> bool:
        return bool(self.node_mask >> node & 1) if node >= 0 else False

    def nodes(self) -> tuple[int, ...]:
        return tuple(node for node in range(self.node_mask.bit_length()) if self.has_node(node))

    def _offset(self, node: int, klass: int) -> int:
        if not self.has_node(node):
            raise NodeUnreachable(
                f"węzeł {node} nie jest decyzją stanu {self.stacks} ręki {self.hand} "
                "(poza maską osiągalności albo jedna legalna akcja) — brak marginesu"
            )
        if not 0 <= klass < self.n_classes:
            raise BlueprintLookupError(f"klasa {klass} poza zakresem 0..{self.n_classes - 1}")
        rank = (self.node_mask & ((1 << node) - 1)).bit_count()
        return rank * self.n_classes + klass

    def quantized(self, node: int, klass: int) -> int:
        """Surowa wartość skwantowana marginesu (0..MARGIN_LEVELS)."""
        return self.payload[self._offset(node, klass)]

    def margin(self, node: int, klass: int) -> float:
        """Margines indyferencji infosetu po dekwantyzacji skalą stanu."""
        return self.quantized(node, klass) * self.scale / MARGIN_LEVELS

    def margin_table(self, node: int) -> tuple[float, ...]:
        """Marginesy wszystkich klas węzła — tą samą drogą co `margin`, nie jej kopią."""
        return tuple(self.margin(node, klass) for klass in range(self.n_classes))


class BlueprintReader:
    """Odczyt swobodny artefaktu blueprintu z otwartego strumienia binarnego."""

    def __init__(self, stream: ByteSource) -> None:
        self._stream = stream
        stream.seek(0)
        raw = stream.read(HEADER_SIZE)
        if len(raw) < HEADER_SIZE:
            raise BlueprintFormatError("plik krótszy niż nagłówek artefaktu blueprintu")
        (
            magic,
            self.format_version,
            self.quant_bits,
            self.n_classes,
            n_layers,
            self.n_nodes,
            self._meta_offset,
            self._meta_zlib_length,
            self._meta_raw_length,
            layer_dir_offset,
            self.n_states_total,
            self.file_length,
            config_hash,
        ) = HEADER_STRUCT.unpack(raw[: HEADER_STRUCT.size])
        if magic != MAGIC:
            raise BlueprintFormatError(f"zła magia artefaktu: {magic!r}")
        if self.format_version not in SUPPORTED_VERSIONS:
            raise BlueprintFormatError(
                f"wersja formatu {self.format_version} spoza obsługiwanych {SUPPORTED_VERSIONS}"
            )
        if self.quant_bits not in (8, 16):
            raise BlueprintFormatError(f"nieobsługiwana kwantyzacja {self.quant_bits} bitów")
        self.config_hash = config_hash.hex()
        self.n_slots = N_SLOTS
        self.flags = 0
        record_size, record_struct = LAYER_RECORD_SIZE, LAYER_STRUCT
        if self.format_version == FORMAT_VERSION_V2:
            # Pola v2 leżą w rezerwie v1, więc plik v1 z przestemplowaną wersją
            # ma tu zera i wywraca się TUTAJ, na nieznanej liczbie slotów —
            # a nie po cichu, na cudzym układzie katalogu warstw.
            n_slots, n_stored, self.flags = HEADER_V2_STRUCT.unpack_from(raw, HEADER_V2_OFFSET)
            if (n_slots, n_stored) != (N_SLOTS_V2, N_SLOTS_V2 - 1):
                raise BlueprintFormatError(
                    f"nagłówek v2 zapowiada {n_slots} slotów akcji ({n_stored} zapisanych), "
                    f"a format v2 ma {N_SLOTS_V2} ({N_SLOTS_V2 - 1} zapisanych)"
                )
            self.n_slots = n_slots
            record_size, record_struct = LAYER_RECORD_SIZE_V2, LAYER_V2_STRUCT
        self._layers: dict[int, _LayerRecord] = {}
        stream.seek(layer_dir_offset)
        directory = stream.read(n_layers * record_size)
        if len(directory) != n_layers * record_size:
            raise BlueprintFormatError("katalog warstw urwany")
        for index in range(n_layers):
            fields = record_struct.unpack_from(directory, index * record_size)
            if self.format_version == FORMAT_VERSION_V2:
                (
                    hand, n_states, has_policy, seats, has_eps, has_margins,
                    states_offset, values_offset, index_offset,
                    _blocks_offset,  # początek obszaru bloków — czytnik idzie indeksem
                    eps_offset, margin_index_offset, _margin_blocks_offset,
                ) = fields
            else:
                (
                    hand, n_states, has_policy, seats,
                    states_offset, values_offset, index_offset, _blocks_offset,
                ) = fields
                has_eps = has_margins = 0
                eps_offset = margin_index_offset = 0
            if seats != SEATS:
                raise BlueprintFormatError(f"warstwa {hand} opisuje {seats} miejsc, nie {SEATS}")
            self._layers[hand] = _LayerRecord(
                hand=hand,
                n_states=n_states,
                has_policy=bool(has_policy),
                states_offset=states_offset,
                values_offset=values_offset,
                index_offset=index_offset,
                eps_offset=eps_offset if has_eps else 0,
                margin_index_offset=margin_index_offset if has_margins else 0,
            )

    @property
    def layers(self) -> tuple[LayerInfo, ...]:
        return tuple(
            LayerInfo(
                record.hand,
                record.n_states,
                record.has_policy,
                bool(record.eps_offset),
                bool(record.margin_index_offset),
            )
            for record in sorted(self._layers.values(), key=lambda item: item.hand)
        )

    def meta_bytes(self) -> bytes:
        """Blok metadanych (JSON UTF-8) po dekompresji — parsowanie po stronie konsumenta."""
        self._stream.seek(self._meta_offset)
        payload = zlib.decompress(self._stream.read(self._meta_zlib_length))
        if len(payload) != self._meta_raw_length:
            raise BlueprintFormatError("blok metadanych ma inną długość niż zapowiada nagłówek")
        return payload

    def _layer(self, hand: int) -> _LayerRecord:
        record = self._layers.get(hand)
        if record is None:
            raise LayerNotFound(f"artefakt nie ma warstwy ręki {hand}")
        return record

    def _position(self, record: _LayerRecord, stacks: tuple[int, int, int]) -> int:
        """Binarne wyszukiwanie klucza stanu — bez czytania całej tablicy warstwy."""
        low, high = 0, record.n_states - 1
        stream = self._stream
        while low <= high:
            middle = (low + high) // 2
            stream.seek(record.states_offset + middle * STATE_KEY_SIZE)
            key = STATE_KEY_STRUCT.unpack(stream.read(STATE_KEY_SIZE))
            if key == stacks:
                return middle
            if key < stacks:
                low = middle + 1
            else:
                high = middle - 1
        raise StateNotFound(f"stan {stacks} nie należy do warstwy ręki {record.hand}")

    def state_key(self, hand: int, position: int) -> tuple[int, int, int]:
        """Klucz stanu warstwy po pozycji — wyliczenie siatki bez czytania całej tablicy."""
        record = self._layer(hand)
        if not 0 <= position < record.n_states:
            raise BlueprintLookupError(
                f"pozycja {position} poza warstwą ręki {hand} ({record.n_states} stanów)"
            )
        self._stream.seek(record.states_offset + position * STATE_KEY_SIZE)
        key = STATE_KEY_STRUCT.unpack(self._stream.read(STATE_KEY_SIZE))
        return (key[0], key[1], key[2])

    def has_state(self, hand: int, stacks: tuple[int, int, int]) -> bool:
        """Czy artefakt ma ten stan — predykat ZGRUBNY, bez rozróżniania przyczyny.

        Zwraca `False` tak samo dla stanu spoza siatki warstwy, jak i dla ręki
        spoza horyzontu artefaktu. Fallback agenta (POKER-52), który musi te
        przypadki rozdzielić, pyta przez `value`/`state` i czyta wyjątek:
        `StateNotFound` to co innego niż `LayerNotFound`, a `NodeUnreachable`
        i `PolicyMissing` to jeszcze co innego.
        """
        try:
            self._position(self._layer(hand), stacks)
        except BlueprintLookupError:
            return False
        return True

    def value(self, hand: int, stacks: tuple[int, int, int]) -> tuple[float, float, float]:
        """Wartość stanu per miejsce w pełnej precyzji (float64)."""
        record = self._layer(hand)
        position = self._position(record, stacks)
        self._stream.seek(record.values_offset + position * VALUE_RECORD_SIZE)
        return VALUE_ROW_STRUCT.unpack(self._stream.read(VALUE_RECORD_SIZE))

    def seat_value(self, hand: int, stacks: tuple[int, int, int], seat: int) -> float:
        """Pojedyncza wartość V — osiem bajtów spod wyliczonego offsetu."""
        if not 0 <= seat < SEATS:
            raise BlueprintLookupError(f"miejsce {seat} poza zakresem 0..{SEATS - 1}")
        record = self._layer(hand)
        position = self._position(record, stacks)
        self._stream.seek(record.values_offset + position * VALUE_RECORD_SIZE + seat * 8)
        return float(VALUE_ONE_STRUCT.unpack(self._stream.read(8))[0])

    def state(self, hand: int, stacks: tuple[int, int, int]) -> StateBlock:
        """Blok jednego stanu: maska osiągalności i skwantowane rozkłady akcji."""
        record = self._layer(hand)
        if not record.has_policy:
            raise PolicyMissing(
                f"warstwa ręki {hand} niesie wyłącznie V (warunek brzegowy) — brak strategii"
            )
        position = self._position(record, stacks)
        stream = self._stream
        stream.seek(record.index_offset + position * BLOCK_INDEX_SIZE)
        offset, zlib_length, raw_length = BLOCK_INDEX_STRUCT.unpack(stream.read(BLOCK_INDEX_SIZE))
        stream.seek(offset)
        payload = zlib.decompress(stream.read(zlib_length))
        if len(payload) != raw_length:
            raise BlueprintFormatError(
                f"blok stanu {stacks} warstwy {hand} ma inną długość niż zapowiada indeks"
            )
        mask_struct = MASK_V2_STRUCT if self.format_version == FORMAT_VERSION_V2 else MASK_STRUCT
        (node_mask,) = mask_struct.unpack_from(payload, 0)
        n_stored = self.n_slots - 1
        expected = (
            mask_struct.size
            + node_mask.bit_count() * n_stored * self.n_classes * (self.quant_bits // 8)
        )
        if raw_length != expected:
            raise BlueprintFormatError(
                f"blok stanu {stacks} warstwy {hand}: {raw_length} B przy masce {node_mask:#010x}"
            )
        return StateBlock(
            hand=hand,
            stacks=stacks,
            node_mask=node_mask,
            n_classes=self.n_classes,
            quant_bits=self.quant_bits,
            payload=payload[mask_struct.size :],
            n_slots=self.n_slots,
        )

    def policy(
        self, hand: int, stacks: tuple[int, int, int], node: int, klass: int
    ) -> tuple[float, ...]:
        """Rozkład akcji jednego węzła i jednej klasy — skrót na `state().policy`."""
        if not 0 <= node < self.n_nodes:
            raise BlueprintLookupError(f"węzeł {node} poza zakresem 0..{self.n_nodes - 1}")
        return self.state(hand, stacks).policy(node, klass)

    def epsilon(self, hand: int, stacks: tuple[int, int, int]) -> tuple[float, float, float]:
        """Ex-post ε stanu per miejsce (float32) — sekcja v2, `SectionMissing` gdy jej nie ma.

        Ta sama liczba co w `expost_report` biegu i w tych samych jednostkach
        (udział SUMY WEKTORA WYPŁAT), tyle że dostępna per stan bez ładowania
        raportu — to jest bramka wysyłkowa profilu ograniczonego (P-13).
        """
        record = self._layer(hand)
        if not record.eps_offset:
            raise SectionMissing(
                f"warstwa ręki {hand} nie niesie sekcji ex-post ε "
                "(plik v1 albo bieg bez raportu ex-post)"
            )
        position = self._position(record, stacks)
        self._stream.seek(record.eps_offset + position * EPS_RECORD_SIZE)
        row = EPS_ROW_STRUCT.unpack(self._stream.read(EPS_RECORD_SIZE))
        return (row[0], row[1], row[2])

    def margins(self, hand: int, stacks: tuple[int, int, int]) -> MarginBlock:
        """Marginesy indyferencji stanu — sekcja v2, `SectionMissing` gdy jej nie ma."""
        record = self._layer(hand)
        if not record.margin_index_offset:
            raise SectionMissing(
                f"warstwa ręki {hand} nie niesie sekcji marginesów indyferencji "
                "(plik v1 albo bieg bez policzonych marginesów)"
            )
        position = self._position(record, stacks)
        stream = self._stream
        stream.seek(record.margin_index_offset + position * BLOCK_INDEX_SIZE)
        offset, zlib_length, raw_length = BLOCK_INDEX_STRUCT.unpack(stream.read(BLOCK_INDEX_SIZE))
        stream.seek(offset)
        payload = zlib.decompress(stream.read(zlib_length))
        if len(payload) != raw_length:
            raise BlueprintFormatError(
                f"blok marginesów stanu {stacks} warstwy {hand} ma inną długość niż indeks"
            )
        node_mask, scale = MARGIN_HEAD_STRUCT.unpack_from(payload, 0)
        expected = MARGIN_HEAD_STRUCT.size + node_mask.bit_count() * self.n_classes
        if raw_length != expected:
            raise BlueprintFormatError(
                f"blok marginesów stanu {stacks} warstwy {hand}: {raw_length} B "
                f"przy masce {node_mask:#010x}"
            )
        return MarginBlock(
            hand=hand,
            stacks=stacks,
            node_mask=node_mask,
            n_classes=self.n_classes,
            scale=scale,
            payload=payload[MARGIN_HEAD_STRUCT.size :],
        )

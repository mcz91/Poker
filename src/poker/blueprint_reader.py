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
"""

import struct
import zlib
from dataclasses import dataclass
from typing import Protocol

MAGIC = b"POKERBP1"
FORMAT_VERSION = 1

HEADER_SIZE = 128
LAYER_RECORD_SIZE = 48
BLOCK_INDEX_SIZE = 16
STATE_KEY_SIZE = 6
VALUE_RECORD_SIZE = 24
SEATS = 3

# Sloty akcji artefaktu: 0 = fold, 1 = środkowy (open/call/3bet), 2 = jam.
# Zapisane są dwa pierwsze, trzeci wynika z dopełnienia do pełnej skali.
STORED_SLOTS = (0, 1)
DERIVED_SLOT = 2

# Układ bajtowy formatu — jedno źródło prawdy dzielone z konwerterem w tools/blueprint.
HEADER_STRUCT = struct.Struct("<8sHHIII QQQ QQQ 32s")
LAYER_STRUCT = struct.Struct("<IIBB6x QQQQ")
BLOCK_INDEX_STRUCT = struct.Struct("<QII")
STATE_KEY_STRUCT = struct.Struct("<3h")
VALUE_ROW_STRUCT = struct.Struct("<3d")
VALUE_ONE_STRUCT = struct.Struct("<d")


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
    """Węzeł spoza maski osiągalności stanu — artefakt nie ma tam strategii."""


class PolicyMissing(BlueprintLookupError):
    """Warstwa niesie wyłącznie V (warunek brzegowy) — nie ma w niej strategii."""


@dataclass(frozen=True)
class LayerInfo:
    """Opis warstwy: numer ręki, liczba stanów i czy niesie strategię."""

    hand: int
    n_states: int
    has_policy: bool


@dataclass(frozen=True)
class _LayerRecord:
    hand: int
    n_states: int
    has_policy: bool
    states_offset: int
    values_offset: int
    index_offset: int


@dataclass(frozen=True)
class StateBlock:
    """Rozpakowany blok jednego stanu: maska osiągalności i skwantowane rozkłady.

    `payload` to bajty bloku bez dwubajtowej maski; węzły leżą w nim rosnąco
    po numerze, każdy jako dwie kolumny po `n_classes` wartości (slot 0, potem
    slot 1). Kolejność kolumnowa, nie przeplot — sąsiadujące wartości tego
    samego slotu są podobne, więc zlib pakuje je ciaśniej.
    """

    hand: int
    stacks: tuple[int, int, int]
    node_mask: int
    n_classes: int
    quant_bits: int
    payload: bytes

    @property
    def levels(self) -> int:
        """Największa wartość skwantowana — pełne prawdopodobieństwo 1,0."""
        return (1 << self.quant_bits) - 1

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
        return rank * 2 * self.n_classes * (self.quant_bits // 8)

    def _raw(self, offset: int) -> int:
        if self.quant_bits == 8:
            return self.payload[offset]
        return int.from_bytes(self.payload[offset : offset + 2], "little")

    def quantized(self, node: int, klass: int) -> tuple[int, int, int]:
        """Surowe wartości skwantowane (dwie zapisane, trzecia z dopełnienia)."""
        if not 0 <= klass < self.n_classes:
            raise BlueprintLookupError(f"klasa {klass} poza zakresem 0..{self.n_classes - 1}")
        width = self.quant_bits // 8
        base = self._column_offset(node)
        first = self._raw(base + klass * width)
        second = self._raw(base + (self.n_classes + klass) * width)
        return (first, second, self.levels - first - second)

    def policy(self, node: int, klass: int) -> tuple[float, float, float]:
        """Rozkład akcji (fold, środkowy, jam) po dekwantyzacji."""
        scale = float(self.levels)
        first, second, third = self.quantized(node, klass)
        return (first / scale, second / scale, third / scale)

    def policy_table(self, node: int) -> tuple[tuple[float, float, float], ...]:
        """Rozkłady wszystkich klas węzła — ta sama droga co `policy`, nie jej kopia.

        Osobna, „szybsza" pętla dekwantyzacji byłaby drugą implementacją
        dopełnienia trzeciego slotu, której testy na `policy` już by nie
        chroniły; koszt jednej dodatkowej maski na klasę jest tego wart.
        """
        return tuple(self.policy(node, klass) for klass in range(self.n_classes))


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
        if self.format_version != FORMAT_VERSION:
            raise BlueprintFormatError(
                f"wersja formatu {self.format_version} != {FORMAT_VERSION} obsługiwana"
            )
        if self.quant_bits not in (8, 16):
            raise BlueprintFormatError(f"nieobsługiwana kwantyzacja {self.quant_bits} bitów")
        self.config_hash = config_hash.hex()
        self._layers: dict[int, _LayerRecord] = {}
        stream.seek(layer_dir_offset)
        directory = stream.read(n_layers * LAYER_RECORD_SIZE)
        if len(directory) != n_layers * LAYER_RECORD_SIZE:
            raise BlueprintFormatError("katalog warstw urwany")
        for index in range(n_layers):
            (
                hand,
                n_states,
                has_policy,
                seats,
                states_offset,
                values_offset,
                index_offset,
                _blocks_offset,  # początek obszaru bloków — czytnik idzie indeksem
            ) = LAYER_STRUCT.unpack_from(directory, index * LAYER_RECORD_SIZE)
            if seats != SEATS:
                raise BlueprintFormatError(f"warstwa {hand} opisuje {seats} miejsc, nie {SEATS}")
            self._layers[hand] = _LayerRecord(
                hand=hand,
                n_states=n_states,
                has_policy=bool(has_policy),
                states_offset=states_offset,
                values_offset=values_offset,
                index_offset=index_offset,
            )

    @property
    def layers(self) -> tuple[LayerInfo, ...]:
        return tuple(
            LayerInfo(record.hand, record.n_states, record.has_policy)
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
        (node_mask,) = struct.unpack_from("<H", payload, 0)
        expected = 2 + node_mask.bit_count() * 2 * self.n_classes * (self.quant_bits // 8)
        if raw_length != expected:
            raise BlueprintFormatError(
                f"blok stanu {stacks} warstwy {hand}: {raw_length} B przy masce {node_mask:#06x}"
            )
        return StateBlock(
            hand=hand,
            stacks=stacks,
            node_mask=node_mask,
            n_classes=self.n_classes,
            quant_bits=self.quant_bits,
            payload=payload[2:],
        )

    def policy(
        self, hand: int, stacks: tuple[int, int, int], node: int, klass: int
    ) -> tuple[float, float, float]:
        """Rozkład akcji jednego węzła i jednej klasy — skrót na `state().policy`."""
        if not 0 <= node < self.n_nodes:
            raise BlueprintLookupError(f"węzeł {node} poza zakresem 0..{self.n_nodes - 1}")
        return self.state(hand, stacks).policy(node, klass)

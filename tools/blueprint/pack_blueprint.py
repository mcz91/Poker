"""Konwerter artefaktu solvera (npz + manifest) do formatu binarnego `.bpk` (POKER-51).

Format opisuje bajt po bajcie `docs/CURRENT_STATE.md` (blok POKER-51), a czyta
go `poker.blueprint_reader` w czystym stdlib. Tu jest strona zapisu — wolno jej
używać numpy, bo narzędzia żyją poza pakietem produktu.

Zapis jest deterministyczny: ten sam katalog biegu daje bajt w bajt ten sam
plik. Nie ma w nim znaczników czasu ani nazw tymczasowych; metadane to
kanoniczny JSON (`sort_keys`, bez spacji), a bloki stanów pakuje zlib o stałym
poziomie. Plik powstaje jako `.tmp` obok celu i wchodzi na miejsce przez
`os.replace` — jak reszta artefaktów pilota.

Kwantyzacja rozkładu akcji: metoda największych reszt na trzech slotach do
sumy `2**bits - 1`. Suma jest zachowana dokładnie, więc trzeci slot wynika
z dopełnienia i nie trzeba go zapisywać; błąd pojedynczego prawdopodobieństwa
jest mniejszy niż jeden krok kwantyzacji. KOREKTA JEDNOSTKOWA (decyzja
z 2026-08-29): ten błąd żyje w przestrzeni prawdopodobieństw, a nie w ε
(udziale puli) — koszt kwantyzacji mierzy `expost` na artefakcie przepuszczonym
przez `requantize`, nie ten szacunek.

Uruchomienie (venv z extras train):

    python tools/blueprint/pack_blueprint.py pack --run KATALOG --out plik.bpk
    python tools/blueprint/pack_blueprint.py requantize --run KATALOG --out KATALOG2
    python tools/blueprint/pack_blueprint.py bench --file plik.bpk [--sweep]
"""

import argparse
import importlib.util
import io
import json
import os
import random
import shutil
import sys
import time
import zlib
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

from poker.blueprint_reader import (
    BLOCK_INDEX_SIZE,
    BLOCK_INDEX_STRUCT,
    DERIVED_SLOT,
    FORMAT_VERSION,
    HEADER_SIZE,
    HEADER_STRUCT,
    LAYER_RECORD_SIZE,
    LAYER_STRUCT,
    MAGIC,
    SEATS,
    STORED_SLOTS,
    BlueprintReader,
)


def _sibling(name: str) -> ModuleType:
    """Moduł siostrzany z tools/blueprint — tools nie jest pakietem (jak testy reprodukcji)."""
    module = sys.modules.get(name)
    if module is not None:
        return module
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"brak modułu siostrzanego {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


artifacts = _sibling("artifacts")

DEFAULT_QUANT_BITS = 8
ZLIB_LEVEL = 9
# Kwantyzacja liczona porcjami węzłów: pełna warstwa produkcyjna w float64 to
# setki MB na tablicę pośrednią, a porcja tej wielkości mieści się w pamięci.
CHUNK_NODES = 2048


def quantize_chunk(sigma: np.ndarray, levels: int) -> np.ndarray:
    """Metoda największych reszt na ostatniej osi: suma dokładnie `levels`, błąd < 1 krok.

    Zaokrąglanie slot po slocie nie zachowuje sumy, więc trzeciego slotu nie
    dałoby się odtworzyć z dopełnienia. Reszty rozdziela stabilny porządek
    malejących części ułamkowych — remis rozstrzyga numer slotu, żeby wynik
    nie zależał od implementacji sortowania.
    """
    total = sigma.sum(axis=-1, keepdims=True)
    if not bool(np.all(total > 0.0)):
        raise ValueError("rozkład akcji w węźle maski osiągalności ma zerową sumę")
    scaled = np.asarray(sigma, dtype=np.float64) / total * levels
    base = np.floor(scaled)
    remainder = np.clip(levels - base.sum(axis=-1), 0, sigma.shape[-1]).astype(np.int64)
    order = np.argsort(-(scaled - base), axis=-1, kind="stable")
    rank = np.empty_like(order)
    np.put_along_axis(rank, order, np.arange(sigma.shape[-1]), axis=-1)
    quantized: np.ndarray = (base + (rank < remainder[..., None])).astype(np.int64)
    if not bool(np.all(quantized.sum(axis=-1) == levels)):
        raise ValueError("kwantyzacja nie zachowała sumy skali")
    return quantized


def reachable_nodes(sigma: np.ndarray) -> np.ndarray:
    """Maska osiągalności (stan, węzeł): solver zapisał tam rozkład, czy same zera.

    Węzeł, do którego drzewo gry etapowej nie dochodzi, ma w artefakcie same
    zera — i takim zostaje. Rozróżnienie „brak strategii" od „strategia zerowa"
    robi maska, nie wartość; bez niej czytnik musiałby zgadywać z zer.
    """
    return np.asarray(sigma.sum(axis=(2, 3)) > 0.0)


def quantize_layer(sigma: np.ndarray, levels: int) -> tuple[np.ndarray, np.ndarray]:
    """Skwantowane rozkłady warstwy (N, węzły, klasy, 3) i maska osiągalności (N, węzły).

    Kwantyzowane są wyłącznie węzły z maski — reszta zostaje zerami i nigdy
    nie trafia do pliku. Porcjami po węzłach, bo tablice pośrednie float64
    pełnej warstwy produkcyjnej to setki megabajtów.
    """
    live = reachable_nodes(sigma)
    flat = sigma.reshape(sigma.shape[0] * sigma.shape[1], sigma.shape[2], sigma.shape[3])
    out = np.zeros(flat.shape, dtype=np.int64)
    positions = np.flatnonzero(live.reshape(-1))
    for start in range(0, len(positions), CHUNK_NODES):
        take = positions[start : start + CHUNK_NODES]
        out[take] = quantize_chunk(flat[take], levels)
    return out.reshape(sigma.shape), live


def node_mask(live_row: np.ndarray) -> int:
    """Wiersz maski osiągalności jednego stanu jako bity uint16 formatu."""
    mask = 0
    for node in range(live_row.shape[0]):
        if bool(live_row[node]):
            mask |= 1 << node
    return mask


def _pad(sink: io.BufferedIOBase, alignment: int = 8) -> None:
    remainder = sink.tell() % alignment
    if remainder:
        sink.write(b"\x00" * (alignment - remainder))


def _layer_sources(run_dir: Path, manifest: dict[str, Any]) -> list[tuple[int, Path, bool]]:
    """Warstwy artefaktu rosnąco po ręce: warstwy solvera, na końcu warunek brzegowy.

    Warunek brzegowy wchodzi jako warstwa o numerze `n_hands` bez strategii —
    niesie samo V, którego potrzebują AIVAT i trener na horyzoncie.
    """
    sources: list[tuple[int, Path, bool]] = []
    for key in sorted(manifest["layers"], key=int):
        sources.append((int(key), run_dir / manifest["layers"][key]["file"], True))
    boundary = manifest["boundary"]
    horizon = max(hand for hand, _, _ in sources) + 1
    sources.append((horizon, run_dir / boundary["file"], False))
    return sources


def _check_source_hashes(manifest: dict[str, Any], sources: list[tuple[int, Path, bool]],
                         run_dir: Path) -> dict[str, str]:
    """Sha256 pakowanych plików skonfrontowane z manifestem biegu — pochodzenie nie kłamie."""
    declared: dict[str, str] = {
        manifest["layers"][key]["file"]: manifest["layers"][key]["sha256"]
        for key in manifest["layers"]
    }
    declared[manifest["boundary"]["file"]] = manifest["boundary"]["sha256"]
    digests: dict[str, str] = {}
    for _, path, _ in sources:
        digest = artifacts.sha256_file(path)
        if digest != declared[path.name]:
            raise ValueError(
                f"{path.name}: sha256 pliku różni się od manifestu biegu — artefakt niespójny"
            )
        digests[path.name] = digest
    digests["solve_manifest.json"] = artifacts.sha256_file(run_dir / "solve_manifest.json")
    return digests


def pack(run_dir: Path, out_path: Path, quant_bits: int = DEFAULT_QUANT_BITS) -> dict[str, Any]:
    """Artefakt solvera → plik `.bpk`; zwraca podsumowanie zapisu."""
    if quant_bits not in (8, 16):
        raise ValueError(f"nieobsługiwana kwantyzacja {quant_bits} bitów")
    manifest = artifacts.read_json(run_dir / "solve_manifest.json")
    if manifest["status"] != "done":
        raise ValueError("format pakuje wyłącznie zakończony bieg solvera")
    sources = _layer_sources(run_dir, manifest)
    digests = _check_source_hashes(manifest, sources, run_dir)
    levels = (1 << quant_bits) - 1
    dtype = np.uint8 if quant_bits == 8 else np.dtype("<u2")
    n_classes = len(manifest["config"]["classes"])

    meta = {
        "artifact": "blueprint-binary",
        "format": {
            "version": FORMAT_VERSION,
            "quant_bits": quant_bits,
            "levels": levels,
            "stored_slots": list(STORED_SLOTS),
            "derived_slot": DERIVED_SLOT,
            "method": "largest-remainder",
        },
        "run_manifest": manifest,
        "source_sha256": digests,
        "boundary_hand": sources[-1][0],
    }
    meta_raw = json.dumps(meta, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    meta_blob = zlib.compress(meta_raw, ZLIB_LEVEL)

    tmp = out_path.with_name(out_path.name + ".tmp")
    n_states_total = 0
    n_nodes = 0
    records: list[tuple[int, int, bool, int, int, int, int]] = []
    with tmp.open("wb") as sink:
        sink.write(b"\x00" * HEADER_SIZE)
        meta_offset = sink.tell()
        sink.write(meta_blob)
        _pad(sink)
        layer_dir_offset = sink.tell()
        sink.write(b"\x00" * (len(sources) * LAYER_RECORD_SIZE))
        for hand, path, has_policy in sources:
            data = artifacts.read_npz(path)
            states = np.ascontiguousarray(data["states"], dtype="<i2")
            order = np.lexsort((states[:, 2], states[:, 1], states[:, 0]))
            states = states[order]
            values = np.ascontiguousarray(data["v"], dtype="<f8")[order]
            if states.shape[1] != SEATS or values.shape[1] != SEATS:
                raise ValueError(f"{path.name}: warstwa nie opisuje {SEATS} miejsc")
            n_states = states.shape[0]
            n_states_total += n_states
            _pad(sink)
            states_offset = sink.tell()
            sink.write(states.tobytes())
            _pad(sink)
            values_offset = sink.tell()
            sink.write(values.tobytes())
            index_offset = blocks_offset = 0
            if has_policy:
                sigma = np.ascontiguousarray(data["sigma"])[order]
                n_nodes = sigma.shape[1]
                raw, live = quantize_layer(sigma, levels)
                masks = [node_mask(live[position]) for position in range(n_states)]
                quantized = raw.astype(dtype)
                # (stan, węzeł, slot, klasa) — slot całą kolumną, bo sąsiednie
                # klasy jednego slotu są podobne i zlib pakuje je ciaśniej.
                stored = quantized[..., list(STORED_SLOTS)]
                columns = np.ascontiguousarray(stored.transpose(0, 1, 3, 2))
                flat = columns.reshape(n_states, n_nodes, 2 * n_classes).view(np.uint8)
                blocks: list[bytes] = []
                for position in range(n_states):
                    mask = masks[position]
                    parts = [mask.to_bytes(2, "little")]
                    for node in range(n_nodes):
                        if mask >> node & 1:
                            parts.append(flat[position, node].tobytes())
                    blocks.append(b"".join(parts))
                _pad(sink)
                index_offset = sink.tell()
                sink.write(b"\x00" * (n_states * BLOCK_INDEX_SIZE))
                _pad(sink)
                blocks_offset = sink.tell()
                index = bytearray()
                for block in blocks:
                    compressed = zlib.compress(block, ZLIB_LEVEL)
                    index += BLOCK_INDEX_STRUCT.pack(sink.tell(), len(compressed), len(block))
                    sink.write(compressed)
                end = sink.tell()
                sink.seek(index_offset)
                sink.write(bytes(index))
                sink.seek(end)
            records.append(
                (hand, n_states, has_policy, states_offset, values_offset,
                 index_offset, blocks_offset)
            )
        file_length = sink.tell()
        sink.seek(layer_dir_offset)
        for record in records:
            sink.write(LAYER_STRUCT.pack(record[0], record[1], int(record[2]), SEATS,
                                   record[3], record[4], record[5], record[6]))
        sink.seek(0)
        sink.write(
            HEADER_STRUCT.pack(
                MAGIC, FORMAT_VERSION, quant_bits, n_classes, len(records), n_nodes,
                meta_offset, len(meta_blob), len(meta_raw), layer_dir_offset,
                n_states_total, file_length, bytes.fromhex(manifest["config_hash"]),
            )
        )
    os.replace(tmp, out_path)
    return {
        "file": str(out_path),
        "bytes": file_length,
        "n_layers": len(records),
        "n_states": n_states_total,
        "n_classes": n_classes,
        "n_nodes": n_nodes,
        "quant_bits": quant_bits,
        "bytes_per_state": round(file_length / max(n_states_total, 1), 1),
        "config_hash": manifest["config_hash"],
    }


def requantize_run(run_dir: Path, out_dir: Path, packed: Path,
                   quant_bits: int = DEFAULT_QUANT_BITS) -> dict[str, Any]:
    """Kopia biegu z rozkładami przepuszczonymi przez format — wejście dla `expost`.

    Strategie wracają CZYTNIKIEM stdlib, nie powtórzeniem kwantyzacji w numpy:
    mierzony ma być koszt formatu, a nie koszt jego repliki (PUŁAPKA replik).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = pack(run_dir, packed, quant_bits=quant_bits)
    manifest = artifacts.read_json(run_dir / "solve_manifest.json")
    shutil.copy2(run_dir / manifest["boundary"]["file"], out_dir / manifest["boundary"]["file"])
    with packed.open("rb") as handle:
        reader = BlueprintReader(handle)
        for key in sorted(manifest["layers"], key=int):
            hand = int(key)
            path = run_dir / manifest["layers"][key]["file"]
            data = artifacts.read_npz(path)
            sigma = np.zeros(data["sigma"].shape, dtype=np.float32)
            for position, row in enumerate(data["states"].tolist()):
                block = reader.state(hand, (int(row[0]), int(row[1]), int(row[2])))
                for node in block.nodes():
                    sigma[position, node] = np.asarray(
                        block.policy_table(node), dtype=np.float32
                    )
            arrays = dict(data)
            arrays["sigma"] = sigma
            target = out_dir / path.name
            artifacts.write_npz(target, arrays)
            manifest["layers"][key]["sha256"] = artifacts.sha256_file(target)
    manifest["requantized"] = {
        "source_run": str(run_dir.resolve()),
        "format_version": FORMAT_VERSION,
        "quant_bits": quant_bits,
        "packed_sha256": artifacts.sha256_file(packed),
    }
    artifacts.write_json(out_dir / "solve_manifest.json", manifest)
    return summary


# Kryterium blokujące POKER-51: przyrost maksymalnego ε po round-tripie przez
# format nie większy niż ta część wartości surowej. Przekroczenie oznacza
# podniesienie precyzji (uint16) i ponowny pomiar, a nie poluzowanie progu.
QUANT_EPS_LIMIT_SHARE = 0.10


def quantization_cost(raw: dict[str, Any], quantized: dict[str, Any]) -> dict[str, Any]:
    """Koszt kwantyzacji w ε z dwóch raportów TEGO SAMEGO narzędzia ex-post.

    Mierzona jest różnica maksymalnego ε: obie strony mają tę samą tablicę V
    (format przenosi ją w pełnej precyzji), więc różnica to czysty przyrost
    wartości najlepszej odpowiedzi przeciw skwantowanemu profilowi. Wartość
    ujemna znaczy, że kwantyzacja tego artefaktu nie kosztowała nic.
    """
    delta = quantized["epsilon_max"] - raw["epsilon_max"]
    share = delta / raw["epsilon_max"]
    return {
        "raw_epsilon_max": raw["epsilon_max"],
        "raw_epsilon_median": raw["epsilon_median"],
        "quant_epsilon_max": quantized["epsilon_max"],
        "quant_epsilon_median": quantized["epsilon_median"],
        "delta_epsilon_max": delta,
        "delta_share": share,
        "limit_share": QUANT_EPS_LIMIT_SHARE,
        "ok": share <= QUANT_EPS_LIMIT_SHARE,
        "states": raw["states"],
    }


class _CountingStream:
    """Strumień liczący przeczytane bajty — miara „ile odczyt naprawdę bierze z pliku"."""

    def __init__(self, handle: Any) -> None:
        self._handle = handle
        self.read_bytes = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        return int(self._handle.seek(offset, whence))

    def read(self, size: int = -1) -> bytes:
        chunk: bytes = self._handle.read(size)
        self.read_bytes += len(chunk)
        return chunk


def sweep_read_bytes(path: Path) -> dict[str, Any]:
    """Bajty przeczytane na jeden odczyt, przemiał po WSZYSTKICH stanach artefaktu.

    Czas zależy od obciążenia maszyny, liczba bajtów nie — więc to ona jest
    powtarzalną miarą dostępu swobodnego. Próbka losowa daje percentyle,
    ale maksimum zna wyłącznie pełny przemiał (stany różnią się liczbą
    żywych węzłów, a bloki kompresują się różnie).
    """
    state_bytes: list[int] = []
    value_bytes: list[int] = []
    with path.open("rb") as handle:
        counting = _CountingStream(handle)
        reader = BlueprintReader(counting)
        for info in reader.layers:
            for position in range(info.n_states):
                key = reader.state_key(info.hand, position)
                counting.read_bytes = 0
                reader.seat_value(info.hand, key, 0)
                value_bytes.append(counting.read_bytes)
                if not info.has_policy:
                    continue
                counting.read_bytes = 0
                block = reader.state(info.hand, key)
                block.policy(min(block.nodes()), 0)
                state_bytes.append(counting.read_bytes)
    state_bytes.sort()
    value_bytes.sort()
    return {
        "state_reads": len(state_bytes),
        "state_bytes_max": state_bytes[-1],
        "state_bytes_median": state_bytes[len(state_bytes) // 2],
        "state_bytes_p95": state_bytes[int(len(state_bytes) * 0.95)],
        "value_reads": len(value_bytes),
        "value_bytes_max": value_bytes[-1],
        "value_bytes_median": value_bytes[len(value_bytes) // 2],
    }


def bench(path: Path, samples: int = 2000, seed: int = 51,
          sweep: bool = False) -> dict[str, Any]:
    """Czas odczytu jednego stanu i jednej wartości V — liczba raportowana, nie progowana.

    Próg ustali konsument w POKER-52; tu mierzymy, ile kosztuje dostęp swobodny
    do gotowego pliku. Losowanie jest deterministyczne (stały seed), więc dwa
    uruchomienia biorą te same stany i różnią się wyłącznie zegarem. `sweep`
    dokłada pełny przemiał bajtów po wszystkich stanach — wolniejszy, ale
    powtarzalny co do liczby i znający maksimum, a nie tylko percentyl próbki.
    """
    rng = random.Random(seed)
    state_times: list[float] = []
    value_times: list[float] = []
    with path.open("rb") as handle:
        reader = BlueprintReader(handle)
        policy_layers = [info for info in reader.layers if info.has_policy]
        draws = [
            (info.hand, rng.randrange(info.n_states))
            for info in (rng.choice(policy_layers) for _ in range(samples))
        ]
        keys = [(hand, reader.state_key(hand, position)) for hand, position in draws]
        for hand, stacks in keys:
            started = time.perf_counter()
            block = reader.state(hand, stacks)
            block.policy(min(block.nodes()), 0)
            state_times.append(time.perf_counter() - started)
            started = time.perf_counter()
            reader.seat_value(hand, stacks, 0)
            value_times.append(time.perf_counter() - started)
        file_bytes = reader.file_length
    state_times.sort()
    value_times.sort()
    report = {
        "file": str(path),
        "bytes": file_bytes,
        "samples": samples,
        "state_median_us": round(state_times[len(state_times) // 2] * 1e6, 1),
        "state_p95_us": round(state_times[int(len(state_times) * 0.95)] * 1e6, 1),
        "value_median_us": round(value_times[len(value_times) // 2] * 1e6, 1),
        "value_p95_us": round(value_times[int(len(value_times) * 0.95)] * 1e6, 1),
    }
    if sweep:
        report["sweep"] = sweep_read_bytes(path)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    packer = commands.add_parser("pack")
    packer.add_argument("--run", type=Path, required=True)
    packer.add_argument("--out", type=Path, required=True)
    packer.add_argument("--bits", type=int, default=DEFAULT_QUANT_BITS, choices=(8, 16))
    requant = commands.add_parser("requantize")
    requant.add_argument("--run", type=Path, required=True)
    requant.add_argument("--out", type=Path, required=True)
    requant.add_argument("--packed", type=Path, default=None)
    requant.add_argument("--bits", type=int, default=DEFAULT_QUANT_BITS, choices=(8, 16))
    timing = commands.add_parser("bench")
    timing.add_argument("--file", type=Path, required=True)
    timing.add_argument("--samples", type=int, default=2000)
    timing.add_argument("--seed", type=int, default=51)
    timing.add_argument("--sweep", action="store_true",
                        help="przemiał bajtów po wszystkich stanach (maksimum, nie percentyl)")
    return parser


def main(argv: Any = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "pack":
        summary = pack(args.run, args.out, quant_bits=args.bits)
    elif args.command == "bench":
        summary = bench(args.file, samples=args.samples, seed=args.seed,
                        sweep=args.sweep)
    else:
        packed = args.packed if args.packed is not None else args.out / "blueprint.bpk"
        packed.parent.mkdir(parents=True, exist_ok=True)
        summary = requantize_run(args.run, args.out, packed, quant_bits=args.bits)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

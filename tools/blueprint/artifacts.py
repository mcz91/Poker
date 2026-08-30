"""Deterministyczny, atomowy zapis artefaktów pilota blueprintu (POKER-46).

`np.savez` wpisuje do zipa bieżący czas, więc dwa identyczne biegi dają różne
bajty — a kontrakt wymaga wznowienia bajt w bajt. Dlatego własny zapis .npz:
wpisy zip ze stałą datą (1980-01-01) i payloadem w formacie .npy; plik
powstaje jako tmp w tym samym katalogu i wchodzi na miejsce przez
`os.replace` (atomowo w obrębie systemu plików). Format pozostaje zwykłym
.npz — czyta go każdy `np.load`.
"""

import hashlib
import io
import json
import os
import platform
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

_EPOCH = (1980, 1, 1, 0, 0, 0)


def write_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name in sorted(arrays):
            payload = io.BytesIO()
            np.lib.format.write_array(payload, np.ascontiguousarray(arrays[name]))
            info = zipfile.ZipInfo(f"{name}.npy", date_time=_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, payload.getvalue())
    os.replace(tmp, path)


def read_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as data:
        return {name: data[name] for name in data.files}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"manifest nie jest obiektem JSON: {path}")
    return payload


def cpu_model() -> str:
    """Model CPU do manifestu pochodzenia: /proc/cpuinfo (Linux), inaczej platform."""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()

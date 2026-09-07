"""Runner Colab dla rdzenia GTO (POKER-69, decyzja 31).

Trzy kroki: katalog wyjścia → solve z resume i bezpiecznikiem ściany
sesji → pack v2. GPU nie liczy artefaktu. Domyślny budżet sesji: 10 h
ściany (2 h zapasu przed zabiciem runtime Colaba).

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
      python tools/blueprint/colab_run.py solve \\
        --tensor TENSOR --out OUT --session-hours 10 --jobs 4 --allow-fresh

    python tools/blueprint/colab_run.py pack --run OUT --bpk OUT/blueprint_v2.bpk

    python tools/blueprint/colab_run.py identity --dir PROD
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

FORBIDDEN_GPU = ("cupy", "cudf", "pycuda")


def _sibling(name: str) -> ModuleType:
    module = sys.modules.get(name)
    if module is not None:
        return module
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"brak modułu {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def assert_cpu_only() -> None:
    loaded = [name for name in FORBIDDEN_GPU if name in sys.modules]
    if loaded:
        raise RuntimeError(
            "artefakt GTO liczy się na CPU — wyrzuć "
            + ", ".join(loaded)
            + " (decyzja 29 pkt 4, POKER-69)"
        )


def _prizes(raw: str) -> tuple[float, float, float]:
    parts = tuple(float(part) for part in raw.split(","))
    if len(parts) != 3:
        raise SystemExit("--prizes wymaga trzech wartości")
    return parts[0], parts[1], parts[2]


def run_solve(
    tensor: Path,
    out: Path,
    *,
    session_hours: float = 10.0,
    jobs: int = 1,
    allow_fresh: bool = False,
    prizes: str = "0.8,0.2,0.0",
    grid_step: int | None = None,
    control: bool = False,
) -> dict[str, Any]:
    """Solve z resume. Pusty katalog wymaga --allow-fresh."""
    assert_cpu_only()
    solve_grid = _sibling("solve_grid")
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "solve_manifest.json"
    if not manifest_path.exists() and not allow_fresh:
        raise SystemExit(
            f"{out} nie ma solve_manifest.json — nowy bieg wymaga --allow-fresh"
        )
    if control:
        config = _sibling("control_chain").control_config(jobs=jobs)
    else:
        defaults = solve_grid.GridConfig()
        config = solve_grid.GridConfig(
            prizes=_prizes(prizes),
            grid_step=defaults.grid_step if grid_step is None else grid_step,
            jobs=jobs,
        )
    deadline = time.perf_counter() + session_hours * 3600.0
    manifest = solve_grid.solve(
        config, tensor, out, session_deadline=deadline
    )
    return {
        "status": manifest["status"],
        "config_hash": manifest["config_hash"],
        "boundary": manifest.get("boundary") is not None,
        "layers": len(manifest.get("layers") or {}),
        "horizon_cycles": (manifest.get("horizon") or {}).get("cycles_done", 0),
    }


def run_pack(run_dir: Path, bpk: Path, bits: int = 16) -> dict[str, Any]:
    assert_cpu_only()
    packer = _sibling("pack_blueprint")
    bpk.parent.mkdir(parents=True, exist_ok=True)
    return packer.pack(run_dir, bpk, quant_bits=bits, version=2)


def run_identity(catalog: Path) -> int:
    verify = _sibling("verify_identity")
    return int(verify.main(["--dir", str(catalog)]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    solve = sub.add_parser("solve", help="solver z resume i bezpiecznikiem sesji")
    solve.add_argument("--tensor", type=Path, required=True)
    solve.add_argument("--out", type=Path, required=True)
    solve.add_argument("--session-hours", type=float, default=10.0)
    solve.add_argument("--jobs", type=int, default=1)
    solve.add_argument("--allow-fresh", action="store_true")
    solve.add_argument("--prizes", default="0.8,0.2,0.0")
    solve.add_argument("--grid-step", type=int, default=None)
    solve.add_argument(
        "--control",
        action="store_true",
        help="wycinek łańcucha kontrolnego (kotwica config_hash)",
    )
    pack = sub.add_parser("pack", help="pack v2 z katalogu biegu")
    pack.add_argument("--run", type=Path, required=True)
    pack.add_argument("--bpk", type=Path, required=True)
    pack.add_argument("--bits", type=int, default=16)
    identity = sub.add_parser("identity", help="tożsamość katalogu PROD")
    identity.add_argument("--dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "solve":
        report = run_solve(
            args.tensor,
            args.out,
            session_hours=args.session_hours,
            jobs=args.jobs,
            allow_fresh=args.allow_fresh,
            prizes=args.prizes,
            grid_step=args.grid_step,
            control=args.control,
        )
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["status"] in {"done", "partial", "aborted-session"} else 1
    if args.command == "pack":
        print(json.dumps(run_pack(args.run, args.bpk, bits=args.bits), ensure_ascii=False))
        return 0
    return run_identity(args.dir)


if __name__ == "__main__":
    raise SystemExit(main())

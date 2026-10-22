"""Thin Python client for the Rust `hupf` driver (one-shot `solve` or persistent `serve`)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .cards import BB_CHIPS

ROOT = Path(__file__).resolve().parent.parent
HUPF = Path(os.environ.get("HUPF_BIN", ROOT / "hupf" / "target" / "release" / "hupf"))
BUILD_SCRIPT = ROOT / "hupf" / "build.sh"

# Tree presets: per-street (bet, raise) strings, same for both players.
# Bet floor = 1 bb is enforced inside the patched solver (MIN_BET), so "33%" in a 2 bb pot
# becomes a 1 bb bet; the strings below already avoid sub-bb sizes in limped pots.
TREES: dict[str, dict] = {
    "checkdown": {
        "flop": ("", ""),
        "turn": ("", ""),
        "river": ("", ""),
        "add_allin_threshold": 0.0,
    },
    # low SPR (<= ~4): one size + all-in per street, raise = all-in
    "low1": {"flop": ("33%, a", "a"), "turn": ("66%, a", "a"), "river": ("75%, a", "a")},
    # low SPR with a non-all-in flop raise (3x): low1 without it distorts check-raising (measured on
    # raise2x_call 15 bb: IP c-bet 97.9% vs 59.6% in the rich tree on Ks7d2c)
    "low1rf": {"flop": ("33%, a", "3x, a"), "turn": ("66%, a", "a"), "river": ("75%, a", "a")},
    # limped-pot candidates (SPR 7-12)
    "flopsmall": {"flop": ("50%, a", "a"), "turn": ("a", ""), "river": ("a", "")},
    "l1": {"flop": ("50%, a", "a"), "turn": ("66%, a", "a"), "river": ("75%, a", "a")},
    "l1r": {"flop": ("50%, a", "3x, a"), "turn": ("66%, a", "3x, a"), "river": ("75%, a", "a")},
    "l1rf": {"flop": ("50%, a", "3x, a"), "turn": ("66%, a", "a"), "river": ("75%, a", "a")},
    "l1r3": {"flop": ("50%, a", "3x"), "turn": ("66%, a", "3x"), "river": ("75%, a", "a")},
    "l2": {
        "flop": ("50%, 100%, a", "a"),
        "turn": ("50%, 100%, a", "a"),
        "river": ("50%, 100%, a", "a"),
    },
    "rich": {
        "flop": ("50%, 100%, a", "3x, a"),
        "turn": ("50%, 100%, a", "3x, a"),
        "river": ("50%, 100%, a", "3x, a"),
    },
}


def _fmt(v: np.ndarray) -> str:
    return " ".join("0" if x == 0 else f"{x:.6g}" for x in np.clip(v, 0.0, 1.0))


def job_text(
    board: str,
    pot_bb: float,
    stack_bb: float,
    range_oop: np.ndarray,
    range_ip: np.ndarray,
    tree: str | dict = "l1",
    target_pct: float = 0.5,
    max_iter: int = 1000,
    check_every: int = 10,
    compress: bool = False,
    node_depth: int = 1,
    node_combos: bool = True,
    want_ev: bool = True,
    export: str | None = None,
    max_mem_gb: float = 5.0,
    tag: str | None = None,
    extra: dict | None = None,
) -> str:
    t = TREES[tree] if isinstance(tree, str) else tree
    lines = [
        f"board {board}",
        f"pot {int(round(pot_bb * BB_CHIPS))}",
        f"stack {int(round(stack_bb * BB_CHIPS))}",
        f"min_bet {BB_CHIPS}",
        f"target_pct {target_pct}",
        f"max_iter {max_iter}",
        f"check_every {check_every}",
        f"compress {int(compress)}",
        f"node_depth {node_depth}",
        f"node_combos {int(node_combos)}",
        f"want_ev {int(want_ev)}",
        f"max_mem_gb {max_mem_gb}",
    ]
    for street in ("flop", "turn", "river"):
        b, r = t[street]
        lines.append(f"{street}_bet {b}")
        lines.append(f"{street}_raise {r}")
    for k in (
        "add_allin_threshold",
        "force_allin_threshold",
        "merging_threshold",
        "turn_donk",
        "river_donk",
    ):
        if k in t:
            lines.append(f"{k} {t[k]}")
    if export:
        lines.append(f"export {export}")
    if tag:
        lines.append(f"tag {tag}")
    for k, v in (extra or {}).items():
        lines.append(f"{k} {v}")
    lines.append(f"range_oop {_fmt(range_oop)}")
    lines.append(f"range_ip {_fmt(range_ip)}")
    return "\n".join(lines) + "\n"


def binary() -> Path:
    """The driver is an optional external program (AGPL, built separately), so a missing binary
    is reported with the build command instead of a bare OSError from subprocess."""
    if not HUPF.is_file():
        raise FileNotFoundError(f"hupf driver not found: {HUPF} (build it with {BUILD_SCRIPT})")
    return HUPF


def solve(threads: int = 2, **kw) -> dict:
    text = job_text(**kw)
    tmp_root = ROOT / "out" / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp_root) as d:
        jp, op = Path(d) / "job.txt", Path(d) / "out.json"
        jp.write_text(text + f"out {op}\n")
        env = dict(os.environ, RAYON_NUM_THREADS=str(threads))
        subprocess.run([str(binary()), "solve", str(jp)], check=True, env=env)
        res = json.loads(op.read_text())
    if not res.get("ok"):
        raise RuntimeError(res.get("error"))
    return res


class Server:
    """Persistent `hupf serve` process for live queries (no process start per query)."""

    def __init__(self, threads: int = 2):
        env = dict(os.environ, RAYON_NUM_THREADS=str(threads))
        self.p = subprocess.Popen(
            [str(binary()), "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=1,
        )

    def query(self, **kw) -> dict:
        assert self.p.stdin and self.p.stdout
        self.p.stdin.write(job_text(**kw) + "END\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def close(self) -> None:
        if self.p.stdin:
            self.p.stdin.write("QUIT\n")
            self.p.stdin.close()
        self.p.wait()

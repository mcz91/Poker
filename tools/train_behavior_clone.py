"""Trening baseline'u behavior clone: zbiór POKER-15 -> moduł wag Pythona.

Uruchomienie (z korzenia repozytorium, w venv z zainstalowanym pakietem):

    python tools/train_behavior_clone.py --dataset zbior.json

Hiperparametry z udokumentowanymi domyślnymi: --learning-rate 0.1,
--epochs 100. Trening jest w pełni deterministyczny (bez losowości),
więc ten sam zbiór i hiperparametry dają bajt w bajt identyczny moduł.
"""

import argparse
import sys
from pathlib import Path

from poker.adapters.dataset import read_dataset
from poker.clone_training import render_weights_module, train_clone


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, required=True,
                        help="plik zbioru przykładów decyzyjnych (POKER-15)")
    parser.add_argument("--learning-rate", type=float, default=0.1,
                        help="krok uczenia (domyślnie 0.1)")
    parser.add_argument("--epochs", type=int, default=100,
                        help="liczba epok pełnego batcha (domyślnie 100)")
    parser.add_argument("--output", type=Path, default=Path("src/poker/clone_weights.py"),
                        help="ścieżka generowanego modułu wag")
    args = parser.parse_args(argv)
    examples = read_dataset(args.dataset)
    model = train_clone(examples, learning_rate=args.learning_rate, epochs=args.epochs)
    args.output.write_text(render_weights_module(model), encoding="utf-8")
    print(f"zapisano: {args.output} ({model.examples} przykładów)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

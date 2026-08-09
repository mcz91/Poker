"""Trening MLP-klona (c1, decyzja 06): korpus -> zbiór -> trening numpy -> wagi stdlib.

Uruchomienie (z korzenia repozytorium, w venv z extras `train`):

    python tools/train_mlp_clone.py --from-corpus <katalog-korpusu>

numpy żyje wyłącznie w tym narzędziu i w extras deweloperskich —
pakiet produktu i inferencja agenta pozostają czystym stdlib
(decyzja 06). Trening jest deterministyczny: seedowana inicjalizacja
wag (PCG64), pełny batch bez tasowania, stałe epoki i krok — ten sam
korpus, architektura, hiperparametry i seed dają bajt w bajt
identyczny moduł wag. Domyślne hiperparametry: --hidden 16,
--activation relu, --learning-rate 0.05, --epochs 300, --seed 0.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

from poker.adapters.corpus import CorpusManifest, read_corpus
from poker.clone_training import ACTION_ORDER
from poker.encoding import DATASET_VERSION, FEATURE_NAMES, encode_hand

Layer = tuple[np.ndarray, np.ndarray]


def train_mlp(
    inputs: np.ndarray,
    targets: np.ndarray,
    hidden: tuple[int, ...],
    activation: str,
    learning_rate: float,
    epochs: int,
    seed: int,
) -> list[Layer]:
    rng = np.random.Generator(np.random.PCG64(seed))
    sizes = [inputs.shape[1], *hidden, len(ACTION_ORDER)]
    layers: list[Layer] = [
        (
            rng.normal(0.0, np.sqrt(2.0 / fan_in), size=(fan_out, fan_in)),
            np.zeros(fan_out),
        )
        for fan_in, fan_out in zip(sizes[:-1], sizes[1:], strict=True)
    ]
    count = inputs.shape[0]
    one_hot = np.zeros((count, len(ACTION_ORDER)))
    one_hot[np.arange(count), targets] = 1.0
    for _ in range(epochs):
        activations = [inputs]
        pre: list[np.ndarray] = []
        for index, (weights, bias) in enumerate(layers):
            z = activations[-1] @ weights.T + bias
            pre.append(z)
            if index < len(layers) - 1:
                activations.append(np.maximum(z, 0.0) if activation == "relu" else np.tanh(z))
        shifted = pre[-1] - pre[-1].max(axis=1, keepdims=True)
        exps = np.exp(shifted)
        probabilities = exps / exps.sum(axis=1, keepdims=True)
        delta = (probabilities - one_hot) / count
        for index in range(len(layers) - 1, -1, -1):
            weights, bias = layers[index]
            gradient_w = delta.T @ activations[index]
            gradient_b = delta.sum(axis=0)
            if index > 0:
                upstream = delta @ weights
                if activation == "relu":
                    upstream = upstream * (pre[index - 1] > 0.0)
                else:
                    upstream = upstream * (1.0 - np.tanh(pre[index - 1]) ** 2)
                delta = upstream
            layers[index] = (
                weights - learning_rate * gradient_w,
                bias - learning_rate * gradient_b,
            )
    return layers


def render_mlp_module(
    layers: list[Layer],
    means: np.ndarray,
    scales: np.ndarray,
    manifest: CorpusManifest,
    hidden: tuple[int, ...],
    activation: str,
    learning_rate: float,
    epochs: int,
    seed: int,
    examples: int,
) -> str:
    architecture = (len(FEATURE_NAMES), *hidden, len(ACTION_ORDER))
    config = manifest.match_config
    lines = [
        '"""Wygenerowane wagi MLP-klona (POKER-19) — nie edytować ręcznie.',
        "",
        "Pełny przepis pochodzenia żyje w stałych poniżej; regeneracja od zera",
        "wyłącznie z tego repozytorium:",
        "",
        "    python -m poker.adapters.cli --corpus <katalog> \\",
        f"        --matches {manifest.matches} --seed {manifest.seed} \\",
        f"        --agent0 {manifest.agents[0]} --agent1 {manifest.agents[1]}",
        "    python tools/train_mlp_clone.py --from-corpus <katalog>",
        "",
        "Warstwy gęste w kolejności od wejścia; wiersz wag na neuron, ostatnia",
        "waga wiersza to bias; aktywacja ACTIVATION między warstwami ukrytymi;",
        "cechy w kolejności poker.encoding.FEATURE_NAMES standaryzowane przez",
        "(x - mean) / scale.",
        '"""',
        "",
        f"DATASET_VERSION = {DATASET_VERSION}",
        f"ARCHITECTURE = {architecture!r}",
        f"ACTIVATION = {activation!r}",
        f"LEARNING_RATE = {learning_rate!r}",
        f"EPOCHS = {epochs}",
        f"INIT_SEED = {seed}",
        f"EXAMPLES = {examples}",
        f"ACTIONS = {ACTION_ORDER!r}",
        "",
        f"CORPUS_AGENTS = {manifest.agents!r}",
        f"CORPUS_MATCHES = {manifest.matches}",
        f"CORPUS_SEED = {manifest.seed}",
        f"CORPUS_SMALL_BLIND = {config.small_blind}",
        f"CORPUS_BIG_BLIND = {config.big_blind}",
        f"CORPUS_STACKS = {config.stacks!r}",
        f"CORPUS_BUTTON = {config.button}",
        f"CORPUS_HAND_LIMIT = {config.hand_limit}",
        "",
        "FEATURE_MEANS: tuple[float, ...] = (",
        *(f"    {float(value)!r}," for value in means),
        ")",
        "",
        "FEATURE_SCALES: tuple[float, ...] = (",
        *(f"    {float(value)!r}," for value in scales),
        ")",
        "",
        "LAYERS: tuple[tuple[tuple[float, ...], ...], ...] = (",
    ]
    for weights, bias in layers:
        lines.append("    (")
        for row, row_bias in zip(weights, bias, strict=True):
            lines.append("        (")
            lines.extend(f"            {float(value)!r}," for value in row)
            lines.append(f"            {float(row_bias)!r},")
            lines.append("        ),")
        lines.append("    ),")
    lines.append(")")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-corpus", type=Path, required=True, metavar="KATALOG",
                        help="katalog korpusu źródłowego (manifest + pliki meczów)")
    parser.add_argument("--hidden", type=int, nargs="+", default=[16],
                        help="rozmiary warstw ukrytych (domyślnie 16)")
    parser.add_argument("--activation", choices=("relu", "tanh"), default="relu",
                        help="aktywacja warstw ukrytych (domyślnie relu)")
    parser.add_argument("--learning-rate", type=float, default=0.05,
                        help="krok uczenia (domyślnie 0.05)")
    parser.add_argument("--epochs", type=int, default=300,
                        help="liczba epok pełnego batcha (domyślnie 300)")
    parser.add_argument("--seed", type=int, default=0,
                        help="seed inicjalizacji wag (domyślnie 0)")
    parser.add_argument("--output", type=Path, default=Path("src/poker/mlp_weights.py"),
                        help="ścieżka generowanego modułu wag")
    args = parser.parse_args(argv)
    manifest, matches = read_corpus(args.from_corpus)
    examples = [
        example
        for histories in matches
        for history in histories
        for example in encode_hand(history)
    ]
    raw = np.array([example.features for example in examples], dtype=np.float64)
    means = raw.mean(axis=0)
    scales = raw.std(axis=0)
    scales[scales == 0.0] = 1.0
    inputs = (raw - means) / scales
    targets = np.array(
        [ACTION_ORDER.index(example.action.value) for example in examples], dtype=np.int64
    )
    layers = train_mlp(
        inputs,
        targets,
        hidden=tuple(args.hidden),
        activation=args.activation,
        learning_rate=args.learning_rate,
        epochs=args.epochs,
        seed=args.seed,
    )
    args.output.write_text(
        render_mlp_module(
            layers,
            means,
            scales,
            manifest,
            hidden=tuple(args.hidden),
            activation=args.activation,
            learning_rate=args.learning_rate,
            epochs=args.epochs,
            seed=args.seed,
            examples=len(examples),
        ),
        encoding="utf-8",
    )
    print(f"zapisano: {args.output} ({len(examples)} przykładów)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

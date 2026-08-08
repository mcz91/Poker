"""Trening behavior clone (b4.2): wieloklasowa regresja logistyczna w czystym stdlib.

Deterministyczny pełny batch bez losowości: wagi startują od zer,
przykłady w kolejności zbioru, stała liczba epok i stały krok uczenia —
ten sam zbiór i hiperparametry dają identyczny model. Cechy są
standaryzowane (średnia i odchylenie z populacji zbioru; odchylenie 0
zastępuje skala 1), a parametry standaryzacji wchodzą do modułu wag,
bo inferencja musi liczyć dokładnie tę samą transformację.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import exp, sqrt

from poker.encoding import DATASET_VERSION, FEATURE_NAMES, DecisionExample

ACTION_ORDER: tuple[str, ...] = ("fold", "check", "call", "bet", "raise")


@dataclass(frozen=True, slots=True)
class CorpusProvenance:
    """Kompletny przepis korpusu źródłowego wag — dane wejściowe regeneracji artefaktu."""

    agents: tuple[str, str]
    matches: int
    seed: int
    small_blind: int
    big_blind: int
    stacks: tuple[int, ...]
    button: int
    hand_limit: int


@dataclass(frozen=True, slots=True)
class CloneModel:
    feature_means: tuple[float, ...]
    feature_scales: tuple[float, ...]
    weights: tuple[tuple[float, ...], ...]
    examples: int
    learning_rate: float
    epochs: int


def train_clone(
    examples: Sequence[DecisionExample], learning_rate: float, epochs: int
) -> CloneModel:
    if not examples:
        raise ValueError("trening wymaga co najmniej jednego przykładu")
    if learning_rate <= 0 or epochs < 1:
        raise ValueError("krok uczenia musi być dodatni, a liczba epok co najmniej 1")
    dimensions = len(FEATURE_NAMES)
    count = len(examples)

    means = [0.0] * dimensions
    for example in examples:
        for index, value in enumerate(example.features):
            means[index] += value / count
    scales = [0.0] * dimensions
    for example in examples:
        for index, value in enumerate(example.features):
            scales[index] += (value - means[index]) ** 2 / count
    for index in range(dimensions):
        scales[index] = sqrt(scales[index]) if scales[index] > 0 else 1.0

    inputs = [
        [(value - means[index]) / scales[index] for index, value in enumerate(ex.features)]
        + [1.0]
        for ex in examples
    ]
    targets = [ACTION_ORDER.index(example.action.value) for example in examples]

    classes = len(ACTION_ORDER)
    weights = [[0.0] * (dimensions + 1) for _ in range(classes)]
    for _ in range(epochs):
        gradient = [[0.0] * (dimensions + 1) for _ in range(classes)]
        for row, target in zip(inputs, targets, strict=True):
            scores = [sum(w * x for w, x in zip(weights[k], row, strict=True))
                      for k in range(classes)]
            peak = max(scores)
            exps = [exp(score - peak) for score in scores]
            total = sum(exps)
            for k in range(classes):
                error = exps[k] / total - (1.0 if k == target else 0.0)
                row_gradient = gradient[k]
                for index, x in enumerate(row):
                    row_gradient[index] += error * x / count
        for k in range(classes):
            for index in range(dimensions + 1):
                weights[k][index] -= learning_rate * gradient[k][index]

    return CloneModel(
        feature_means=tuple(means),
        feature_scales=tuple(scales),
        weights=tuple(tuple(row) for row in weights),
        examples=count,
        learning_rate=learning_rate,
        epochs=epochs,
    )


def render_weights_module(model: CloneModel, provenance: CorpusProvenance) -> str:
    lines = [
        '"""Wygenerowane wagi behavior clone (POKER-16/17) — nie edytować ręcznie.',
        "",
        "Pełny przepis pochodzenia żyje w stałych CORPUS_* i hiperparametrach",
        "poniżej; regeneracja od zera wyłącznie z tego repozytorium:",
        "",
        "    python -m poker.adapters.cli --corpus <katalog> \\",
        f"        --matches {provenance.matches} --seed {provenance.seed} \\",
        f"        --agent0 {provenance.agents[0]} --agent1 {provenance.agents[1]}",
        "    python tools/train_behavior_clone.py --from-corpus <katalog>",
        "",
        "Wieloklasowa regresja logistyczna na typ akcji; wiersz wag na klasę",
        "w kolejności ACTIONS, ostatnia waga wiersza to bias; cechy w kolejności",
        "poker.encoding.FEATURE_NAMES standaryzowane przez (x - mean) / scale.",
        '"""',
        "",
        f"DATASET_VERSION = {DATASET_VERSION}",
        f"LEARNING_RATE = {model.learning_rate!r}",
        f"EPOCHS = {model.epochs}",
        f"EXAMPLES = {model.examples}",
        f"ACTIONS = {ACTION_ORDER!r}",
        "",
        f"CORPUS_AGENTS = {provenance.agents!r}",
        f"CORPUS_MATCHES = {provenance.matches}",
        f"CORPUS_SEED = {provenance.seed}",
        f"CORPUS_SMALL_BLIND = {provenance.small_blind}",
        f"CORPUS_BIG_BLIND = {provenance.big_blind}",
        f"CORPUS_STACKS = {provenance.stacks!r}",
        f"CORPUS_BUTTON = {provenance.button}",
        f"CORPUS_HAND_LIMIT = {provenance.hand_limit}",
        "",
        "FEATURE_MEANS: tuple[float, ...] = (",
        *(f"    {value!r}," for value in model.feature_means),
        ")",
        "",
        "FEATURE_SCALES: tuple[float, ...] = (",
        *(f"    {value!r}," for value in model.feature_scales),
        ")",
        "",
        "WEIGHTS: tuple[tuple[float, ...], ...] = (",
    ]
    for row in model.weights:
        lines.append("    (")
        lines.extend(f"        {value!r}," for value in row)
        lines.append("    ),")
    lines.append(")")
    return "\n".join(lines) + "\n"

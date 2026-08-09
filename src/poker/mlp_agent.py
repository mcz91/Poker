"""Agent MLP-klon (c1, decyzja 06): inferencja czystym stdlib nad wygenerowanymi wagami.

Forward pass sieci z modułu wag (warstwy gęste, aktywacja z metadanych,
ostatnia waga wiersza to bias), wejście standaryzowane jak w treningu.
Model wybiera wyłącznie typ akcji (argmax po ACTIONS, przy remisie
pierwszy w kolejności); kwoty i fallback to reguła v1 z POKER-16
(`decision_for_action`). Zero pamięci między wywołaniami, zero I/O,
zero zależności poza standard library (INV-P4, INV-P8, decyzja 06).
"""

from dataclasses import dataclass
from math import sumprod, tanh

from poker.agent import Decision
from poker.clone_agent import decision_for_action
from poker.encoding import view_features
from poker.events import ActionType
from poker.mlp_weights import ACTIONS, ACTIVATION, FEATURE_MEANS, FEATURE_SCALES, LAYERS
from poker.views import PlayerView


@dataclass(frozen=True, slots=True)
class MlpCloneAgent:
    def decide(self, view: PlayerView) -> Decision:
        action = ActionType(ACTIONS[_predicted_class(view_features(view))])
        return decision_for_action(action, view)


def _activate(value: float) -> float:
    if ACTIVATION == "relu":
        return value if value > 0.0 else 0.0
    return tanh(value)


def _predicted_class(features: tuple[int, ...]) -> int:
    x = [
        (value - mean) / scale
        for value, mean, scale in zip(features, FEATURE_MEANS, FEATURE_SCALES, strict=True)
    ]
    last = len(LAYERS) - 1
    for index, layer in enumerate(LAYERS):
        outputs = [sumprod(row[:-1], x) + row[-1] for row in layer]
        x = outputs if index == last else [_activate(value) for value in outputs]
    best_class, best_score = 0, float("-inf")
    for index, score in enumerate(x):
        if score > best_score:
            best_class, best_score = index, score
    return best_class

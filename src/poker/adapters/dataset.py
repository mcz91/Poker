"""Plik zbioru przykładów decyzyjnych (b4.1): ekstrakcja z korpusu, zapis i odczyt (adapter)."""

import json
from dataclasses import dataclass
from pathlib import Path

from poker.adapters.corpus import MANIFEST_NAME, read_corpus
from poker.encoding import DATASET_VERSION, FEATURE_NAMES, DecisionExample, encode_hand
from poker.events import ActionType


@dataclass(frozen=True, slots=True)
class DatasetReport:
    examples: int
    hands: int
    matches: int
    path: Path


def extract_dataset(corpus_directory: Path, output: Path) -> DatasetReport:
    if not (corpus_directory / MANIFEST_NAME).is_file():
        raise ValueError(f"brak manifestu korpusu w {corpus_directory}")
    if output.exists():
        raise ValueError(f"plik wyjściowy istnieje: {output} — zbiór nie nadpisuje")
    _, matches = read_corpus(corpus_directory)
    examples: list[DecisionExample] = []
    hands = 0
    for histories in matches:
        hands += len(histories)
        for history in histories:
            examples.extend(encode_hand(history))
    document = {
        "dataset_version": DATASET_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "examples": [
            {
                "seat": example.seat,
                "features": list(example.features),
                "action": example.action.value,
                "amount": example.amount,
            }
            for example in examples
        ],
    }
    output.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return DatasetReport(
        examples=len(examples), hands=hands, matches=len(matches), path=output
    )


def read_dataset(path: Path) -> tuple[DecisionExample, ...]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("zbiór przykładów musi być obiektem JSON")
    if raw.get("dataset_version") != DATASET_VERSION:
        raise ValueError(f"nieobsługiwana wersja zbioru: {raw.get('dataset_version')!r}")
    if raw.get("feature_names") != list(FEATURE_NAMES):
        raise ValueError("zestaw cech w pliku niezgodny z FEATURE_NAMES tej wersji")
    examples_doc = raw.get("examples")
    if not isinstance(examples_doc, list):
        raise ValueError("pole 'examples' zbioru musi być listą")
    return tuple(_example_from(item) for item in examples_doc)


def _example_from(value: object) -> DecisionExample:
    if not isinstance(value, dict):
        raise ValueError("przykład zbioru musi być obiektem JSON")
    seat = value.get("seat")
    amount = value.get("amount")
    action = value.get("action")
    features = value.get("features")
    if not isinstance(seat, int) or isinstance(seat, bool):
        raise ValueError("pole 'seat' przykładu musi być liczbą całkowitą")
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise ValueError("pole 'amount' przykładu musi być liczbą całkowitą")
    if not isinstance(action, str):
        raise ValueError("pole 'action' przykładu musi być tekstem")
    if not isinstance(features, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in features
    ):
        raise ValueError("pole 'features' przykładu musi być listą liczb całkowitych")
    return DecisionExample(
        seat=seat, features=tuple(features), action=ActionType(action), amount=amount
    )

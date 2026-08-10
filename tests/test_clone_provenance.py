"""Pochodzenie wag klona liniowego (POKER-17/20): dowód dwustopniowy decyzji 06.

W bramce: deterministyczna reprodukcja małego łańcucha kontrolnego
(korpus → zbiór → trening) z seedem różnicującym. Pełna regeneracja
produkcyjnych wag jedną sekwencją komend z README żyje poza bramką
(wzorzec MLP z POKER-19); jej wynik bajt w bajt weryfikuje koder
w raporcie zadania zmieniającego artefakt.
"""

from pathlib import Path

from poker import clone_weights
from poker.adapters.corpus import generate_corpus
from poker.adapters.dataset import extract_dataset, read_dataset
from poker.clone_training import (
    CloneModel,
    CorpusProvenance,
    render_weights_module,
    train_clone,
)
from poker.table import MatchConfig


def test_metadane_pochodzenia_sa_kompletne_i_typowane() -> None:
    assert clone_weights.CORPUS_AGENTS == ("rule", "rule-aggressive")
    assert clone_weights.CORPUS_MATCHES > 30  # istotnie większy korpus niż b4.2
    assert isinstance(clone_weights.CORPUS_SEED, int)
    assert clone_weights.CORPUS_SMALL_BLIND >= 1
    assert clone_weights.CORPUS_BIG_BLIND >= 1
    assert len(clone_weights.CORPUS_STACKS) == 2
    assert clone_weights.CORPUS_BUTTON in (0, 1)
    assert clone_weights.CORPUS_HAND_LIMIT >= 1


def _kontrolny_lancuch(tmp_path: Path, nazwa: str, seed: int) -> tuple[str, CloneModel]:
    config = MatchConfig(
        small_blind=clone_weights.CORPUS_SMALL_BLIND,
        big_blind=clone_weights.CORPUS_BIG_BLIND,
        stacks=clone_weights.CORPUS_STACKS,
        button=clone_weights.CORPUS_BUTTON,
        hand_limit=5,
    )
    generate_corpus(
        tmp_path / nazwa,
        config=config,
        agent_names=clone_weights.CORPUS_AGENTS,
        matches=2,
        seed=seed,
    )
    extract_dataset(tmp_path / nazwa, tmp_path / f"{nazwa}.json")
    examples = read_dataset(tmp_path / f"{nazwa}.json")
    model = train_clone(
        examples, learning_rate=clone_weights.LEARNING_RATE, epochs=3
    )
    provenance = CorpusProvenance(
        agents=clone_weights.CORPUS_AGENTS,
        matches=2,
        seed=seed,
        small_blind=config.small_blind,
        big_blind=config.big_blind,
        stacks=config.stacks,
        button=config.button,
        hand_limit=config.hand_limit,
    )
    return render_weights_module(model, provenance), model


def test_kontrolny_lancuch_deterministyczny_z_seedem_roznicujacym(tmp_path: Path) -> None:
    first_text, first_model = _kontrolny_lancuch(tmp_path, "a", seed=5)
    second_text, second_model = _kontrolny_lancuch(tmp_path, "b", seed=5)
    assert first_text.encode("utf-8") == second_text.encode("utf-8")
    assert first_model == second_model
    other_text, other_model = _kontrolny_lancuch(tmp_path, "c", seed=6)
    assert first_text != other_text
    assert first_model.weights != other_model.weights  # różnią się wagi, nie tylko metadane

"""Test pochodzenia wag (POKER-17): pełny łańcuch z metadanych artefaktu, bajt w bajt."""

from pathlib import Path

from poker import clone_weights
from poker.adapters.corpus import generate_corpus
from poker.adapters.dataset import extract_dataset, read_dataset
from poker.clone_training import CorpusProvenance, render_weights_module, train_clone
from poker.table import MatchConfig

WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "src" / "poker" / "clone_weights.py"


def test_metadane_pochodzenia_sa_kompletne_i_typowane() -> None:
    assert clone_weights.CORPUS_AGENTS == ("rule", "rule-aggressive")
    assert clone_weights.CORPUS_MATCHES > 30  # istotnie większy korpus niż b4.2
    assert isinstance(clone_weights.CORPUS_SEED, int)
    assert clone_weights.CORPUS_SMALL_BLIND >= 1
    assert clone_weights.CORPUS_BIG_BLIND >= 1
    assert len(clone_weights.CORPUS_STACKS) == 2
    assert clone_weights.CORPUS_BUTTON in (0, 1)
    assert clone_weights.CORPUS_HAND_LIMIT >= 1


def test_pelny_lancuch_z_metadanych_odtwarza_modul_bajt_w_bajt(tmp_path: Path) -> None:
    config = MatchConfig(
        small_blind=clone_weights.CORPUS_SMALL_BLIND,
        big_blind=clone_weights.CORPUS_BIG_BLIND,
        stacks=clone_weights.CORPUS_STACKS,
        button=clone_weights.CORPUS_BUTTON,
        hand_limit=clone_weights.CORPUS_HAND_LIMIT,
    )
    generate_corpus(
        tmp_path / "korpus",
        config=config,
        agent_names=clone_weights.CORPUS_AGENTS,
        matches=clone_weights.CORPUS_MATCHES,
        seed=clone_weights.CORPUS_SEED,
        jobs=2,  # zawartość niezależna od liczby procesów — pod testem korpusu
    )
    extract_dataset(tmp_path / "korpus", tmp_path / "zbior.json")
    examples = read_dataset(tmp_path / "zbior.json")
    assert len(examples) == clone_weights.EXAMPLES
    model = train_clone(
        examples,
        learning_rate=clone_weights.LEARNING_RATE,
        epochs=clone_weights.EPOCHS,
    )
    provenance = CorpusProvenance(
        agents=clone_weights.CORPUS_AGENTS,
        matches=clone_weights.CORPUS_MATCHES,
        seed=clone_weights.CORPUS_SEED,
        small_blind=clone_weights.CORPUS_SMALL_BLIND,
        big_blind=clone_weights.CORPUS_BIG_BLIND,
        stacks=clone_weights.CORPUS_STACKS,
        button=clone_weights.CORPUS_BUTTON,
        hand_limit=clone_weights.CORPUS_HAND_LIMIT,
    )
    rendered = render_weights_module(model, provenance)
    committed = WEIGHTS_PATH.read_text(encoding="utf-8")
    assert rendered.encode("utf-8") == committed.encode("utf-8")

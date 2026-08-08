"""Korpus self-play: odtwarzalna generacja historii meczów w formacie eksportu (adapter)."""

import json
import random
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path

from poker.adapters.export import deserialize_match_history, serialize_match_history
from poker.adapters.registry import agent_registry
from poker.events import HandEvent
from poker.table import MatchConfig, play_match

MANIFEST_VERSION = 1
MANIFEST_NAME = "manifest.json"

_MatchTask = tuple[int, int, MatchConfig, tuple[str, str]]
MatchHistories = tuple[tuple[HandEvent, ...], ...]


@dataclass(frozen=True, slots=True)
class CorpusManifest:
    match_config: MatchConfig
    agents: tuple[str, str]
    seed: int
    matches: int
    files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CorpusReport:
    matches: int
    hands: int
    directory: Path


def corpus_match_seeds(seed: int, matches: int) -> tuple[int, ...]:
    """Seedy meczów pochodne od seeda korpusu — jawny kontrakt odtwarzalności."""
    rng = random.Random(seed)
    return tuple(rng.getrandbits(64) for _ in range(matches))


def _match_file_name(index: int) -> str:
    return f"match-{index:06d}.json"


def _generate_match(task: _MatchTask) -> tuple[int, str, int]:
    index, seed, config, agent_names = task
    registry = agent_registry()
    result = play_match(
        config, seed=seed, agents=(registry[agent_names[0]], registry[agent_names[1]])
    )
    return index, serialize_match_history(result.histories), result.hands_played


def generate_corpus(
    directory: Path,
    config: MatchConfig,
    agent_names: tuple[str, str],
    matches: int,
    seed: int,
    jobs: int = 1,
) -> CorpusReport:
    if matches < 1:
        raise ValueError(f"korpus wymaga co najmniej jednego meczu: {matches}")
    if jobs < 1:
        raise ValueError(f"liczba procesów roboczych musi być dodatnia: {jobs}")
    registry = agent_registry()
    unknown = [name for name in agent_names if name not in registry]
    if unknown:
        raise ValueError(f"nieznane nazwy agentów: {unknown}; dostępne: {sorted(registry)}")
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError(f"katalog docelowy niepusty: {directory} — korpus nie nadpisuje")

    tasks: list[_MatchTask] = [
        (index, match_seed, config, agent_names)
        for index, match_seed in enumerate(corpus_match_seeds(seed, matches))
    ]
    if jobs == 1:
        outcomes = [_generate_match(task) for task in tasks]
    else:
        with Pool(jobs) as pool:
            outcomes = list(pool.imap_unordered(_generate_match, tasks))

    total_hands = 0
    for index, text, hands in outcomes:
        (directory / _match_file_name(index)).write_text(text, encoding="utf-8")
        total_hands += hands
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "match_config": {
            "small_blind": config.small_blind,
            "big_blind": config.big_blind,
            "stacks": list(config.stacks),
            "button": config.button,
            "hand_limit": config.hand_limit,
        },
        "agents": list(agent_names),
        "seed": seed,
        "matches": matches,
        "files": [_match_file_name(index) for index in range(matches)],
    }
    (directory / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return CorpusReport(matches=matches, hands=total_hands, directory=directory)


def read_corpus(directory: Path) -> tuple[CorpusManifest, tuple[MatchHistories, ...]]:
    raw: object = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("manifest korpusu musi być obiektem JSON")
    if raw.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError(
            f"nieobsługiwana wersja manifestu korpusu: {raw.get('manifest_version')!r}"
        )
    config_doc = raw["match_config"]
    if not isinstance(config_doc, dict):
        raise ValueError("pole match_config manifestu musi być obiektem JSON")
    manifest = CorpusManifest(
        match_config=MatchConfig(
            small_blind=_int_of(config_doc, "small_blind"),
            big_blind=_int_of(config_doc, "big_blind"),
            stacks=tuple(_int_list_of(config_doc, "stacks")),
            button=_int_of(config_doc, "button"),
            hand_limit=_int_of(config_doc, "hand_limit"),
        ),
        agents=_agent_pair_of(raw),
        seed=_int_of(raw, "seed"),
        matches=_int_of(raw, "matches"),
        files=tuple(_str_list_of(raw, "files")),
    )
    histories = tuple(
        deserialize_match_history((directory / name).read_text(encoding="utf-8"))
        for name in manifest.files
    )
    return manifest, histories


def _int_of(doc: dict[str, object], key: str) -> int:
    value = doc.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"pole {key!r} manifestu musi być liczbą całkowitą")
    return value


def _int_list_of(doc: dict[str, object], key: str) -> list[int]:
    value = doc.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise ValueError(f"pole {key!r} manifestu musi być listą liczb całkowitych")
    return value


def _str_list_of(doc: dict[str, object], key: str) -> list[str]:
    value = doc.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"pole {key!r} manifestu musi być listą tekstów")
    return value


def _agent_pair_of(doc: dict[str, object]) -> tuple[str, str]:
    names = _str_list_of(doc, "agents")
    if len(names) != 2:
        raise ValueError(f"pole 'agents' manifestu musi mieć 2 nazwy, ma {len(names)}")
    return names[0], names[1]

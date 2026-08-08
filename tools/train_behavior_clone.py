"""Trening baseline'u behavior clone: korpus POKER-14 -> moduł wag z przepisem pochodzenia.

Uruchomienie (z korzenia repozytorium, w venv z zainstalowanym pakietem):

    python tools/train_behavior_clone.py --from-corpus <katalog-korpusu>

Łańcuch korpus -> zbiór -> trening wykonuje się w całości z manifestu
korpusu, więc przepis pochodzenia w module wag (stałe CORPUS_*) jest
z konstrukcji zgodny z danymi treningu. Hiperparametry z udokumentowanymi
domyślnymi: --learning-rate 0.1, --epochs 100. Trening jest w pełni
deterministyczny — ten sam korpus i hiperparametry dają bajt w bajt
identyczny moduł.
"""

import argparse
import sys
from pathlib import Path

from poker.adapters.corpus import read_corpus
from poker.clone_training import CorpusProvenance, render_weights_module, train_clone
from poker.encoding import encode_hand


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-corpus", type=Path, required=True, metavar="KATALOG",
                        help="katalog korpusu źródłowego (manifest + pliki meczów)")
    parser.add_argument("--learning-rate", type=float, default=0.1,
                        help="krok uczenia (domyślnie 0.1)")
    parser.add_argument("--epochs", type=int, default=100,
                        help="liczba epok pełnego batcha (domyślnie 100)")
    parser.add_argument("--output", type=Path, default=Path("src/poker/clone_weights.py"),
                        help="ścieżka generowanego modułu wag")
    args = parser.parse_args(argv)
    manifest, matches = read_corpus(args.from_corpus)
    examples = [
        example
        for histories in matches
        for history in histories
        for example in encode_hand(history)
    ]
    model = train_clone(examples, learning_rate=args.learning_rate, epochs=args.epochs)
    provenance = CorpusProvenance(
        agents=manifest.agents,
        matches=manifest.matches,
        seed=manifest.seed,
        small_blind=manifest.match_config.small_blind,
        big_blind=manifest.match_config.big_blind,
        stacks=manifest.match_config.stacks,
        button=manifest.match_config.button,
        hand_limit=manifest.match_config.hand_limit,
    )
    args.output.write_text(render_weights_module(model, provenance), encoding="utf-8")
    print(f"zapisano: {args.output} ({model.examples} przykładów)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

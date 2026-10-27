"""Autocomplete: complete the last word being typed, using edge n-grams.

Every word in the corpus is broken into its prefixes ("index" -> i, in, ind, inde, index),
and each prefix points at the words it can complete, counted by how often they occur:

    "in": {"index": 9, "inverted": 4, "information": 1}

So suggesting is a single dictionary lookup per keystroke. Suggestions use the original
words rather than their stems: "indexing" is a better completion than "index".
"""

from collections import Counter
from collections.abc import Iterable

from searchengine.analysis.ngrams import edge_ngrams
from searchengine.analysis.stopwords import STOP_WORDS
from searchengine.analysis.tokenizer import tokenize


class Suggester:
    def __init__(self, max_prefix: int = 20) -> None:
        self.max_prefix = max_prefix
        self.prefixes: dict[str, Counter[str]] = {}

    def add(self, text: str) -> None:
        for word in tokenize(text):
            if len(word) < 2 or word in STOP_WORDS:
                continue
            for prefix in edge_ngrams(word, 1, self.max_prefix):
                self.prefixes.setdefault(prefix, Counter())[word] += 1

    def add_all(self, texts: Iterable[str]) -> None:
        for text in texts:
            self.add(text)

    def suggest(self, typed: str, limit: int = 5) -> list[str]:
        """Complete the last word of `typed`, keeping the words before it."""
        if not typed.strip() or typed[-1].isspace():
            return []
        words = typed.split()
        before, partial = typed[: len(typed) - len(words[-1])], tokenize(words[-1])
        if len(partial) != 1:
            return []
        candidates = self.prefixes.get(partial[0][: self.max_prefix], Counter())
        ranked = sorted(
            (item for item in candidates.items() if item[0].startswith(partial[0])),
            key=lambda item: (-item[1], item[0]),
        )
        return [before + word for word, _ in ranked[:limit]]

"""Inverted index: maps each term to the documents (and positions) where it appears.

    postings = {
        "search": {0: [3, 17], 9: [0]},   # term -> doc id -> positions
        "index":  {6: [1]},
    }

Looking up a term is a single dict access instead of scanning every document, which is
why search engines beat SQL `LIKE '%term%'`. Positions are the term's offsets in the
analyzed term list, so phrase queries can check that words appear next to each other.
Document lengths are kept for relevance scoring (BM25 favours shorter documents).
"""

from collections.abc import Iterable
from typing import Any


class InvertedIndex:
    def __init__(self) -> None:
        self.postings: dict[str, dict[int, list[int]]] = {}
        self.lengths: dict[int, int] = {}

    def add(self, doc_id: int, terms: Iterable[str]) -> None:
        """Index a document's analyzed terms, replacing any earlier version of it."""
        if doc_id in self.lengths:
            self.remove(doc_id)
        length = 0
        for position, term in enumerate(terms):
            self.postings.setdefault(term, {}).setdefault(doc_id, []).append(position)
            length += 1
        self.lengths[doc_id] = length

    def remove(self, doc_id: int) -> None:
        if self.lengths.pop(doc_id, None) is None:
            return
        for term in [t for t, docs in self.postings.items() if doc_id in docs]:
            del self.postings[term][doc_id]
            if not self.postings[term]:
                del self.postings[term]

    def postings_for(self, term: str) -> dict[int, list[int]]:
        return self.postings.get(term, {})

    def doc_freq(self, term: str) -> int:
        """Number of documents containing the term."""
        return len(self.postings.get(term, {}))

    def term_freq(self, term: str, doc_id: int) -> int:
        """Number of times the term appears in one document."""
        return len(self.postings.get(term, {}).get(doc_id, []))

    @property
    def doc_count(self) -> int:
        return len(self.lengths)

    @property
    def avg_length(self) -> float:
        return sum(self.lengths.values()) / len(self.lengths) if self.lengths else 0.0

    def __contains__(self, term: str) -> bool:
        return term in self.postings

    def __len__(self) -> int:
        """Number of distinct terms (the vocabulary size)."""
        return len(self.postings)

    def to_dict(self) -> dict[str, Any]:
        return {"postings": self.postings, "lengths": self.lengths}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InvertedIndex":
        """Rebuild from `to_dict()` output, including after a JSON round trip (string keys)."""
        index = cls()
        index.postings = {
            term: {int(doc_id): list(positions) for doc_id, positions in docs.items()}
            for term, docs in data["postings"].items()
        }
        index.lengths = {int(doc_id): length for doc_id, length in data["lengths"].items()}
        return index

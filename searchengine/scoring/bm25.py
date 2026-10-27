"""BM25 relevance scoring, plus field boosting.

For each query term t found in document d:

    idf(t)      = ln(1 + (N - df + 0.5) / (df + 0.5))         rare terms count more
    score(t, d) = idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d) / avg_len))

- tf (term frequency) helps, but with diminishing returns: k1 controls how fast it saturates.
- Long documents are penalised: b controls how much (0 = ignore length, 1 = full).
- Each field (title, body, ...) is scored separately, multiplied by its boost, then summed,
  so a match in a short, boosted title outranks the same word buried in a long body.

Statistics are gathered across all segments, so scores are comparable between them.
"""

import heapq
import math
from collections.abc import Iterable, Mapping
from functools import cache

from searchengine.index.inverted_index import InvertedIndex
from searchengine.query.parser import And, Or, Phrase, Query, Term

K1 = 1.2
B = 0.75


def idf(doc_freq: int, doc_count: int) -> float:
    return math.log(1 + (doc_count - doc_freq + 0.5) / (doc_freq + 0.5))


def bm25(tf: int, doc_length: int, avg_length: float, term_idf: float, k1: float = K1, b: float = B) -> float:
    if tf == 0:
        return 0.0
    length_ratio = doc_length / avg_length if avg_length else 1.0
    return term_idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length_ratio))


def query_terms(query: Query | None) -> list[tuple[str, str | None]]:
    """The (term, field) pairs that should add to a document's score; NOT clauses don't."""
    if isinstance(query, Term):
        return [(query.text, query.field)]
    if isinstance(query, Phrase):
        return [(term, query.field) for term in query.terms]
    if isinstance(query, And | Or):
        return [pair for child in query.children for pair in query_terms(child)]
    return []  # Not, or an empty query


class BM25:
    def __init__(
        self,
        indexes: Mapping[str, Iterable[InvertedIndex]],
        boosts: Mapping[str, float] | None = None,
        k1: float = K1,
        b: float = B,
    ) -> None:
        """`indexes` maps each field to its inverted index in every segment."""
        self.indexes = {name: list(segment_indexes) for name, segment_indexes in indexes.items()}
        self.boosts = dict(boosts or {})
        self.k1 = k1
        self.b = b
        self.doc_count = {f: sum(i.doc_count for i in idx) for f, idx in self.indexes.items()}
        self.avg_length = {
            f: sum(sum(i.lengths.values()) for i in idx) / self.doc_count[f] if self.doc_count[f] else 0.0
            for f, idx in self.indexes.items()
        }
        self.idf = cache(self._idf)

    def _idf(self, field: str, term: str) -> float:
        doc_freq = sum(index.doc_freq(term) for index in self.indexes[field])
        return idf(doc_freq, self.doc_count[field])

    def score(
        self,
        doc_id: int,
        segment: Mapping[str, InvertedIndex],
        terms: Iterable[tuple[str, str | None]],
    ) -> float:
        """Score one document, given its segment's per-field indexes and the query terms."""
        total = 0.0
        for term, only_field in terms:
            for field, index in segment.items():
                if only_field is not None and field != only_field:
                    continue
                tf = index.term_freq(term, doc_id)
                if tf:
                    raw = bm25(
                        tf,
                        index.lengths[doc_id],
                        self.avg_length[field],
                        self.idf(field, term),
                        self.k1,
                        self.b,
                    )
                    total += raw * self.boosts.get(field, 1.0)
        return total


def top_k(scores: Mapping[int, float], k: int) -> list[tuple[int, float]]:
    """Highest scores first; ties go to the lower (older) document id."""
    return heapq.nsmallest(k, scores.items(), key=lambda item: (-item[1], item[0]))

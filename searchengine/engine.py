"""Engine: the black box that ties analysis, indexing, querying and scoring together.

    with Engine("index", boosts={"title": 2.0}, facet_fields=["category"]) as engine:
        engine.index({"title": "Stop words", "body": "...", "category": "text-analysis"})
        results = engine.search('stemming OR "inverted index"', filters={"category": "concepts"})

A search runs in four stages:
  1. parse   the query string into a tree (Term/Phrase/And/Or/Not)
  2. match   evaluate the tree per segment with set operations on the postings,
             checking positions for phrases, then drop deleted and filtered-out docs
  3. facet   count category/tag values over every match
  4. rank    score matches with BM25 (field boosts applied) and keep the top `limit`

Changes are buffered in memory until commit() (or leaving the `with` block) writes them.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from searchengine.analysis import analyze
from searchengine.document import Document
from searchengine.facets import Filters, facet_counts, matches_filters
from searchengine.index.inverted_index import InvertedIndex
from searchengine.index.segments import Manifest, Segment, SegmentStore
from searchengine.query.parser import Not, Or, Phrase, Query, Term, parse
from searchengine.scoring.bm25 import BM25, query_terms, top_k


@dataclass
class Hit:
    doc: Document
    score: float


@dataclass
class SearchResults:
    query: Query | None
    total: int
    hits: list[Hit]
    facets: dict[str, list[tuple[str, int]]] = field(default_factory=dict)


class Engine:
    def __init__(
        self,
        directory: str | Path,
        fields: Iterable[str] = ("title", "body"),
        boosts: Mapping[str, float] | None = None,
        facet_fields: Iterable[str] = (),
        segment_size: int = 1000,
    ) -> None:
        """Open the index in `directory`. Settings only apply when creating a new index;
        an existing index keeps the settings stored in its manifest."""
        manifest = Manifest(
            fields=list(fields),
            boosts=dict(boosts or {}),
            facet_fields=list(facet_fields),
            segment_size=segment_size,
        )
        self.store = SegmentStore(directory, manifest)

    @property
    def manifest(self) -> Manifest:
        return self.store.manifest

    # -- writing ----------------------------------------------------------------

    def index(self, fields: Mapping[str, Any]) -> int:
        """Add a document and return its new id."""
        doc = Document(self.store.allocate_id(), dict(fields))
        self.store.add(doc, {name: analyze(doc.text(name)) for name in self.manifest.fields})
        return doc.id

    def index_many(self, docs: Iterable[Mapping[str, Any]]) -> list[int]:
        return [self.index(fields) for fields in docs]

    def delete(self, doc_id: int) -> bool:
        return self.store.delete(doc_id)

    def commit(self) -> None:
        self.store.save()

    def compact(self) -> None:
        self.store.compact()
        self.store.save()

    def __enter__(self) -> "Engine":
        return self

    def __exit__(self, exc_type: object, *_: object) -> None:
        if exc_type is None:
            self.commit()

    # -- reading ----------------------------------------------------------------

    def get(self, doc_id: int) -> Document | None:
        return self.store.get(doc_id)

    @property
    def doc_count(self) -> int:
        return self.store.doc_count

    def search(
        self,
        text: str,
        limit: int = 10,
        filters: Filters | None = None,
        default_operator: str = "AND",
    ) -> SearchResults:
        """Search the index. An empty query (or only stop words) matches every document,
        which is handy for browsing by facet filters alone."""
        query = parse(text, default_operator)
        filters = filters or {}

        matches: dict[int, Segment] = {}
        for segment in self.store.segments:
            ids = _evaluate(query, segment) if query is not None else set(segment.docs)
            for doc_id in ids:
                if not self.store.is_deleted(doc_id) and matches_filters(segment.docs[doc_id], filters):
                    matches[doc_id] = segment

        facets = facet_counts((s.docs[i] for i, s in matches.items()), self.manifest.facet_fields)

        scorer = BM25(
            {name: [s.indexes[name] for s in self.store.segments] for name in self.manifest.fields},
            self.manifest.boosts,
        )
        terms = query_terms(query)
        scores = {doc_id: scorer.score(doc_id, s.indexes, terms) for doc_id, s in matches.items()}
        hits = [Hit(matches[doc_id].docs[doc_id], score) for doc_id, score in top_k(scores, limit)]
        return SearchResults(query, len(matches), hits, facets)


# -- query evaluation ---------------------------------------------------------


def _evaluate(query: Query, segment: Segment) -> set[int]:
    """The ids in `segment` matching `query` (deleted docs are filtered by the caller)."""
    if isinstance(query, Term):
        return set().union(*(index.postings_for(query.text) for index in _fields(segment, query.field)))
    if isinstance(query, Phrase):
        return set().union(*(_phrase_matches(index, query.terms) for index in _fields(segment, query.field)))
    if isinstance(query, Not):
        return set(segment.docs) - _evaluate(query.child, segment)
    if isinstance(query, Or):
        return set().union(*(_evaluate(child, segment) for child in query.children))
    # And: intersect the positive clauses, then subtract the NOT clauses
    positive = [c for c in query.children if not isinstance(c, Not)]
    negative = [c.child for c in query.children if isinstance(c, Not)]
    result = set(segment.docs)
    for child in positive:
        result &= _evaluate(child, segment)
    for child in negative:
        result -= _evaluate(child, segment)
    return result


def _fields(segment: Segment, only: str | None) -> list[InvertedIndex]:
    if only is None:
        return list(segment.indexes.values())
    return [segment.indexes[only]] if only in segment.indexes else []


def _phrase_matches(index: InvertedIndex, terms: tuple[str, ...]) -> set[int]:
    """Docs where the terms appear at consecutive positions."""
    postings = [index.postings_for(term) for term in terms]
    candidates = set(postings[0]).intersection(*postings[1:])
    return {
        doc_id
        for doc_id in candidates
        if any(
            all(start + offset in set(p[doc_id]) for offset, p in enumerate(postings))
            for start in postings[0][doc_id]
        )
    }

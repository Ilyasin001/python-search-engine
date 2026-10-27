import json
from pathlib import Path

import pytest

from searchengine.analysis import analyze
from searchengine.index.inverted_index import InvertedIndex
from searchengine.query.parser import parse
from searchengine.scoring.bm25 import BM25, bm25, idf, query_terms, top_k

SAMPLE = json.loads((Path(__file__).parent.parent / "data" / "sample_docs.json").read_text(encoding="utf-8"))


def test_idf_favours_rare_terms():
    assert idf(1, 100) > idf(10, 100) > idf(90, 100) > 0


def test_term_frequency_saturates():
    one, two, ten, hundred = (bm25(tf, 10, 10, 1.0) for tf in (1, 2, 10, 100))
    assert one < two < ten < hundred
    assert two - one > hundred - ten  # diminishing returns
    assert hundred < 1.0 * (1.2 + 1)  # never exceeds idf * (k1 + 1)


def test_shorter_documents_score_higher():
    assert bm25(1, 5, 10, 1.0) > bm25(1, 10, 10, 1.0) > bm25(1, 50, 10, 1.0)


def test_b_zero_ignores_length():
    assert bm25(1, 5, 10, 1.0, b=0) == bm25(1, 50, 10, 1.0, b=0)


def test_zero_tf_scores_nothing():
    assert bm25(0, 5, 10, 1.0) == 0.0


def test_query_terms_skip_negations():
    assert query_terms(parse('title:stemming "inverted index" -segment')) == [
        ("stem", "title"),
        ("invert", None),
        ("index", None),
    ]
    assert query_terms(None) == []


def test_top_k_orders_by_score_then_id():
    assert top_k({3: 1.0, 1: 2.0, 2: 1.0, 4: 0.5}, 3) == [(1, 2.0), (2, 1.0), (3, 1.0)]


def two_field_segment(docs: dict[int, tuple[str, str]]) -> dict[str, InvertedIndex]:
    segment = {"title": InvertedIndex(), "body": InvertedIndex()}
    for doc_id, (title, body) in docs.items():
        segment["title"].add(doc_id, analyze(title))
        segment["body"].add(doc_id, analyze(body))
    return segment


def stats(segment: dict[str, InvertedIndex]) -> dict[str, list[InvertedIndex]]:
    return {field: [index] for field, index in segment.items()}


def test_boost_multiplies_a_fields_contribution():
    segment = two_field_segment({1: ("stemming", "words"), 2: ("words", "stemming")})
    terms = [("stem", None)]
    plain = BM25(stats(segment))
    boosted = BM25(stats(segment), boosts={"title": 3.0})
    assert plain.score(1, segment, terms) == pytest.approx(plain.score(2, segment, terms))
    assert boosted.score(1, segment, terms) == pytest.approx(3 * boosted.score(2, segment, terms))


def test_field_restricted_term_only_scores_that_field():
    segment = two_field_segment({1: ("stemming", "stemming")})
    scorer = BM25(stats(segment))
    both = scorer.score(1, segment, [("stem", None)])
    title_only = scorer.score(1, segment, [("stem", "title")])
    assert 0 < title_only < both


def test_stats_are_shared_across_segments():
    first = two_field_segment({1: ("index", "w1 w2 w3 w4")})
    second = two_field_segment({2: ("segment", "w5 w6")})
    scorer = BM25({f: [first[f], second[f]] for f in ("title", "body")})
    assert scorer.doc_count == {"title": 2, "body": 2}
    assert scorer.avg_length["body"] == 3.0
    assert scorer.idf("title", "index") == idf(1, 2)


def test_ranks_the_sample_corpus_sensibly():
    segment = two_field_segment({d["id"]: (d["title"], d["body"]) for d in SAMPLE})
    scorer = BM25(stats(segment), boosts={"title": 2.0})
    terms = query_terms(parse("stemming"))
    scores = {doc_id: scorer.score(doc_id, segment, terms) for doc_id in segment["body"].lengths}
    best_id, _ = top_k({i: s for i, s in scores.items() if s > 0}, 1)[0]
    assert SAMPLE[best_id]["title"] == "Stemming words to their roots"

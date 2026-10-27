import json
from pathlib import Path

from searchengine.document import Document
from searchengine.facets import facet_counts, filter_docs, matches_filters

DOCS = [
    Document(1, {"category": "concepts", "tags": ["fundamentals", "search"]}),
    Document(2, {"category": "concepts", "tags": ["fundamentals"]}),
    Document(3, {"category": "text-analysis", "tags": ["analysis", "fundamentals"]}),
    Document(4, {"category": "scoring", "tags": ["analysis"]}),
    Document(5, {"title": "no facets at all"}),
]


def test_counts_single_and_multi_valued_fields():
    assert facet_counts(DOCS, ["category", "tags"]) == {
        "category": [("concepts", 2), ("scoring", 1), ("text-analysis", 1)],
        "tags": [("fundamentals", 3), ("analysis", 2), ("search", 1)],
    }


def test_duplicate_values_in_one_doc_count_once():
    doc = Document(1, {"tags": ["a1", "a1"]})
    assert facet_counts([doc], ["tags"]) == {"tags": [("a1", 1)]}


def test_limit_keeps_the_most_common():
    assert facet_counts(DOCS, ["tags"], limit=1) == {"tags": [("fundamentals", 3)]}


def test_unknown_field_gives_empty_counts():
    assert facet_counts(DOCS, ["colour"]) == {"colour": []}


def test_filter_by_one_value():
    assert [d.id for d in filter_docs(DOCS, {"category": "concepts"})] == [1, 2]
    assert [d.id for d in filter_docs(DOCS, {"tags": "analysis"})] == [3, 4]


def test_values_in_one_field_are_ored():
    assert [d.id for d in filter_docs(DOCS, {"category": ["concepts", "scoring"]})] == [1, 2, 4]


def test_different_fields_are_anded():
    assert [d.id for d in filter_docs(DOCS, {"category": "concepts", "tags": "search"})] == [1]


def test_no_filters_match_everything():
    assert matches_filters(DOCS[4], {})
    assert not matches_filters(DOCS[4], {"category": "concepts"})


def test_drill_down_on_the_sample_corpus():
    path = Path(__file__).parent.parent / "data" / "sample_docs.json"
    docs = [Document(d["id"], d) for d in json.loads(path.read_text(encoding="utf-8"))]
    counts = dict(facet_counts(docs, ["category"])["category"])
    assert sum(counts.values()) == len(docs)
    narrowed = filter_docs(docs, {"category": "text-analysis"})
    assert len(narrowed) == counts["text-analysis"]
    assert facet_counts(narrowed, ["category"]) == {"category": [("text-analysis", len(narrowed))]}

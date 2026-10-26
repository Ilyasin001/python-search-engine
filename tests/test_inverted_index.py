import json

from searchengine.analysis import analyze
from searchengine.index.inverted_index import InvertedIndex


def build() -> InvertedIndex:
    index = InvertedIndex()
    index.add(1, analyze("Search engines use an inverted index"))
    index.add(2, analyze("The index maps each term to documents"))
    index.add(3, analyze("Searching and indexing documents, then searching again"))
    return index


def test_postings_record_documents_and_positions():
    index = build()
    assert index.postings_for("index") == {1: [4], 2: [0], 3: [1]}
    assert index.postings_for("search") == {1: [0], 3: [0, 3]}
    assert index.postings_for("missing") == {}


def test_frequencies_and_lengths():
    index = build()
    assert index.doc_freq("search") == 2
    assert index.term_freq("search", 3) == 2
    assert index.term_freq("search", 2) == 0
    assert index.lengths == {1: 5, 2: 5, 3: 5}
    assert index.doc_count == 3
    assert index.avg_length == 5.0


def test_contains_and_vocabulary_size():
    index = build()
    assert "document" in index
    assert "the" not in index  # stop word, never indexed
    assert len(index) == len(index.postings)


def test_remove_cleans_up_empty_terms():
    index = build()
    index.remove(1)
    assert index.postings_for("index") == {2: [0], 3: [1]}
    assert "engin" not in index
    assert 1 not in index.lengths
    index.remove(99)  # unknown ids are ignored


def test_re_adding_a_document_replaces_it():
    index = build()
    index.add(2, analyze("Completely new text"))
    assert 2 not in index.postings_for("index")
    assert index.postings_for("text") == {2: [2]}
    assert index.lengths[2] == 3


def test_json_round_trip():
    index = build()
    restored = InvertedIndex.from_dict(json.loads(json.dumps(index.to_dict())))
    assert restored.postings == index.postings
    assert restored.lengths == index.lengths

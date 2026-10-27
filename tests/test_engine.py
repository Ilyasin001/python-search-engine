import json
from pathlib import Path

import pytest

from searchengine.engine import Engine

SAMPLE = json.loads((Path(__file__).parent.parent / "data" / "sample_docs.json").read_text(encoding="utf-8"))


def new_engine(directory: Path, segment_size: int = 5) -> Engine:
    return Engine(
        directory,
        fields=["title", "body"],
        boosts={"title": 2.0},
        facet_fields=["category", "tags"],
        segment_size=segment_size,
    )


@pytest.fixture
def engine(tmp_path):
    engine = new_engine(tmp_path / "index")
    engine.index_many({k: v for k, v in doc.items() if k != "id"} for doc in SAMPLE)
    return engine


def titles(results) -> list[str]:
    return [hit.doc.fields["title"] for hit in results.hits]


def test_indexes_across_several_segments(engine):
    assert engine.doc_count == len(SAMPLE)
    assert len(engine.store.segments) == 4  # 16 docs, 5 per segment


def test_best_match_first(engine):
    assert titles(engine.search("stemming"))[0] == "Stemming words to their roots"
    results = engine.search("index")
    scores = [hit.score for hit in results.hits]
    assert len(scores) > 1
    assert scores == sorted(scores, reverse=True)
    assert scores[-1] > 0


def test_and_or_not(engine):
    either = engine.search("faceting OR boosting").total
    faceting = engine.search("faceting").total
    boosting = engine.search("boosting").total
    assert either >= max(faceting, boosting)
    assert engine.search("faceting boosting").total <= min(faceting, boosting)
    without = engine.search("index -segment")
    assert all("segment" not in hit.doc.fields["body"].lower() for hit in without.hits)


def test_phrase_requires_adjacent_words(engine):
    phrase = engine.search('"inverted index"')
    loose = engine.search("inverted index")
    assert 0 < phrase.total <= loose.total
    for hit in phrase.hits:
        text = (hit.doc.fields["title"] + " " + hit.doc.fields["body"]).lower()
        assert "inverted index" in text


def test_field_restriction(engine):
    title_only = engine.search("title:index")
    assert title_only.total > 0
    assert all("index" in hit.doc.fields["title"].lower() for hit in title_only.hits)
    assert title_only.total < engine.search("index").total


def test_facets_and_filters(engine):
    everything = engine.search("")
    assert everything.total == len(SAMPLE)
    categories = dict(everything.facets["category"])
    narrowed = engine.search("", filters={"category": "text-analysis"})
    assert narrowed.total == categories["text-analysis"]
    assert narrowed.facets["category"] == [("text-analysis", narrowed.total)]


def test_limit_caps_hits_not_total(engine):
    results = engine.search("", limit=3)
    assert len(results.hits) == 3
    assert results.total == len(SAMPLE)


def test_delete_hides_document(engine):
    top = engine.search("stemming").hits[0].doc
    assert engine.delete(top.id)
    assert engine.get(top.id) is None
    assert top.id not in [hit.doc.id for hit in engine.search("stemming").hits]
    assert not engine.delete(top.id)


def test_commit_and_reopen(engine):
    engine.delete(0)
    engine.commit()
    reopened = Engine(engine.store.directory, fields=["ignored"])
    assert reopened.manifest.fields == ["title", "body"]  # stored settings win
    assert reopened.doc_count == len(SAMPLE) - 1
    assert titles(reopened.search("stemming")) == titles(engine.search("stemming"))


def test_compact_keeps_results(engine):
    engine.delete(3)
    before = titles(engine.search("words"))
    engine.compact()
    assert titles(engine.search("words")) == before
    assert engine.manifest.deleted == []


def test_context_manager_commits(tmp_path):
    with new_engine(tmp_path / "idx") as engine:
        doc_id = engine.index({"title": "Hello", "body": "World"})
    assert Engine(tmp_path / "idx").get(doc_id).fields["title"] == "Hello"


def test_context_manager_skips_commit_on_error(tmp_path):
    with pytest.raises(RuntimeError), new_engine(tmp_path / "idx") as engine:
        engine.index({"title": "Hello"})
        raise RuntimeError
    assert not (tmp_path / "idx").exists()


def test_unknown_field_and_no_matches(engine):
    assert engine.search("colour:red").total == 0
    assert engine.search("zzzzqqq").hits == []

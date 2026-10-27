import json

import pytest

from searchengine.analysis import analyze
from searchengine.document import Document
from searchengine.index.segments import MANIFEST, Manifest, SegmentStore

TEXTS = [
    ("Stop words", "Filler words such as and, the and but"),
    ("Stemming", "Reducing testing and tester to a root"),
    ("Inverted index", "Maps terms to documents and positions"),
    ("Segments", "Smaller index files that make up the index"),
    ("BM25", "Scores documents by term frequency and length"),
]


def add_all(store: SegmentStore) -> None:
    for title, body in TEXTS:
        doc = Document(store.allocate_id(), {"title": title, "body": body})
        store.add(doc, {"title": analyze(title), "body": analyze(body)})


@pytest.fixture
def store(tmp_path):
    store = SegmentStore(tmp_path / "index", Manifest(segment_size=2, boosts={"title": 2.0}))
    add_all(store)
    return store


def files(store: SegmentStore) -> list[str]:
    return sorted(p.name for p in store.directory.iterdir())


def test_documents_fill_segments_in_order(store):
    assert [len(s) for s in store.segments] == [2, 2, 1]
    assert store.doc_count == 5
    assert store.manifest.next_id == 5
    assert store.segments[1].indexes["body"].postings_for("index") == {3: [1, 5]}


def test_save_writes_manifest_and_segments(store):
    store.save()
    assert files(store) == [MANIFEST, "segment_0000.json", "segment_0001.json", "segment_0002.json"]
    manifest = json.loads((store.directory / MANIFEST).read_text(encoding="utf-8"))
    assert manifest["segments"] == ["segment_0000.json", "segment_0001.json", "segment_0002.json"]
    assert manifest["boosts"] == {"title": 2.0}


def test_reopen_restores_everything(store):
    store.save()
    reopened = SegmentStore(store.directory)
    assert reopened.manifest == store.manifest
    assert reopened.get(2) == Document(2, {"title": "Inverted index", "body": TEXTS[2][1]})
    assert reopened.segments[0].indexes["title"].postings_for("stem") == {1: [0]}


def test_save_only_rewrites_changed_segments(store):
    store.save()
    first = store.directory / "segment_0000.json"
    first.write_text(first.read_text(encoding="utf-8") + " ", encoding="utf-8")  # marker
    doc = Document(store.allocate_id(), {"title": "Faceting", "body": "Counts per category"})
    store.add(doc, {"title": analyze("Faceting"), "body": analyze("Counts per category")})
    store.save()
    assert first.read_text(encoding="utf-8").endswith(" ")  # untouched
    assert len(store.segments[-1]) == 2


def test_delete_is_a_tombstone_until_compaction(store):
    assert store.delete(1)
    assert not store.delete(1)
    assert not store.delete(99)
    assert store.get(1) is None
    assert store.is_deleted(1)
    assert store.doc_count == 4
    assert [d.id for d in store.documents()] == [0, 2, 3, 4]
    assert 1 in store.segments[0].docs  # still physically there

    store.save()
    assert SegmentStore(store.directory).is_deleted(1)


def test_compact_removes_deleted_and_merges_segments(store):
    store.delete(1)
    store.delete(2)
    store.save()
    store.compact()
    store.save()
    assert [sorted(s.docs) for s in store.segments] == [[0, 3], [4]]
    assert files(store) == [MANIFEST, "segment_0000.json", "segment_0001.json"]
    assert store.segments[0].indexes["body"].postings_for("stem") == {}
    reopened = SegmentStore(store.directory)
    assert reopened.manifest.deleted == []
    assert [d.id for d in reopened.documents()] == [0, 3, 4]


def test_adding_an_existing_id_is_rejected(store):
    with pytest.raises(ValueError):
        store.add(Document(0, {"title": "dup"}), {"title": ["dup"]})


def test_no_temp_files_left_behind(store):
    store.save()
    assert not list(store.directory.glob("*.tmp"))

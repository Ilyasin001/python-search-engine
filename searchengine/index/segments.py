"""Segments: the index is stored as several smaller files plus a manifest.

    index/
      manifest.json       settings, segment list, next doc id, deleted ids
      segment_0000.json   up to `segment_size` documents + one inverted index per field
      segment_0001.json

Rewriting one giant file on every change doesn't scale. Instead new documents go into
the newest segment and only changed segments are rewritten. Deletes are recorded in the
manifest as "tombstones" and hidden from results; compact() later rewrites the segments
without them and merges small ones together. This is the same idea Lucene uses.
"""

import json
import os
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from searchengine.document import Document
from searchengine.index.inverted_index import InvertedIndex

MANIFEST = "manifest.json"


@dataclass
class Manifest:
    fields: list[str] = field(default_factory=lambda: ["title", "body"])
    boosts: dict[str, float] = field(default_factory=dict)
    facet_fields: list[str] = field(default_factory=list)
    segment_size: int = 1000
    next_id: int = 0
    deleted: list[int] = field(default_factory=list)
    segments: list[str] = field(default_factory=list)


class Segment:
    """A chunk of documents with its own inverted index per searchable field."""

    def __init__(self, name: str, fields: list[str]) -> None:
        self.name = name
        self.docs: dict[int, Document] = {}
        self.indexes: dict[str, InvertedIndex] = {f: InvertedIndex() for f in fields}

    def add(self, doc: Document, terms_by_field: dict[str, list[str]]) -> None:
        self.docs[doc.id] = doc
        for name, index in self.indexes.items():
            index.add(doc.id, terms_by_field.get(name, []))

    def remove(self, doc_id: int) -> None:
        self.docs.pop(doc_id, None)
        for index in self.indexes.values():
            index.remove(doc_id)

    def merge(self, other: "Segment") -> None:
        self.docs.update(other.docs)
        for name, index in self.indexes.items():
            index.merge(other.indexes[name])

    def __len__(self) -> int:
        return len(self.docs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "docs": {doc_id: doc.fields for doc_id, doc in self.docs.items()},
            "indexes": {name: index.to_dict() for name, index in self.indexes.items()},
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "Segment":
        segment = cls(name, [])
        segment.docs = {int(i): Document(int(i), fields) for i, fields in data["docs"].items()}
        segment.indexes = {f: InvertedIndex.from_dict(d) for f, d in data["indexes"].items()}
        return segment


class SegmentStore:
    """Opens the index in `directory`, or starts a new one there with `manifest` settings."""

    def __init__(self, directory: str | Path, manifest: Manifest | None = None) -> None:
        self.directory = Path(directory)
        self._dirty: set[str] = set()
        manifest_path = self.directory / MANIFEST
        if manifest_path.exists():
            self.manifest = Manifest(**json.loads(manifest_path.read_text(encoding="utf-8")))
            self.segments = [self._load_segment(name) for name in self.manifest.segments]
        else:
            self.manifest = manifest or Manifest()
            self.segments = []
        self._deleted = set(self.manifest.deleted)

    # -- writing ----------------------------------------------------------------

    def allocate_id(self) -> int:
        doc_id = self.manifest.next_id
        self.manifest.next_id += 1
        return doc_id

    def add(self, doc: Document, terms_by_field: dict[str, list[str]]) -> None:
        if self._segment_of(doc.id) is not None:
            raise ValueError(f"document {doc.id} is already indexed; delete it and use a new id")
        segment = self.segments[-1] if self.segments else None
        if segment is None or len(segment) >= self.manifest.segment_size:
            segment = Segment(f"segment_{len(self.segments):04d}.json", self.manifest.fields)
            self.segments.append(segment)
        segment.add(doc, terms_by_field)
        self.manifest.next_id = max(self.manifest.next_id, doc.id + 1)
        self._dirty.add(segment.name)

    def delete(self, doc_id: int) -> bool:
        """Tombstone a document. Returns False if it wasn't found."""
        if doc_id in self._deleted or self._segment_of(doc_id) is None:
            return False
        self._deleted.add(doc_id)
        return True

    def compact(self) -> None:
        """Drop tombstoned documents for good and merge undersized segments."""
        for segment in self.segments:
            for doc_id in self._deleted & segment.docs.keys():
                segment.remove(doc_id)
        self._deleted.clear()

        merged: list[Segment] = []
        for segment in self.segments:
            if not segment.docs:
                continue
            if merged and len(merged[-1]) + len(segment) <= self.manifest.segment_size:
                merged[-1].merge(segment)
            else:
                merged.append(segment)
        for number, segment in enumerate(merged):
            segment.name = f"segment_{number:04d}.json"
        self.segments = merged
        self._dirty = {s.name for s in merged}

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        for segment in self.segments:
            if segment.name in self._dirty:
                self._write_json(segment.name, segment.to_dict())
        self._dirty.clear()

        self.manifest.segments = [s.name for s in self.segments]
        self.manifest.deleted = sorted(self._deleted)
        self._write_json(MANIFEST, asdict(self.manifest))

        for path in self.directory.glob("segment_*.json"):
            if path.name not in self.manifest.segments:
                path.unlink()

    # -- reading ----------------------------------------------------------------

    def get(self, doc_id: int) -> Document | None:
        segment = self._segment_of(doc_id)
        return None if segment is None or doc_id in self._deleted else segment.docs[doc_id]

    def is_deleted(self, doc_id: int) -> bool:
        return doc_id in self._deleted

    def documents(self) -> Iterator[Document]:
        for segment in self.segments:
            for doc_id, doc in segment.docs.items():
                if doc_id not in self._deleted:
                    yield doc

    @property
    def doc_count(self) -> int:
        return sum(len(s) for s in self.segments) - len(self._deleted)

    # -- helpers ----------------------------------------------------------------

    def _segment_of(self, doc_id: int) -> Segment | None:
        return next((s for s in self.segments if doc_id in s.docs), None)

    def _load_segment(self, name: str) -> Segment:
        data = json.loads((self.directory / name).read_text(encoding="utf-8"))
        return Segment.from_dict(name, data)

    def _write_json(self, name: str, data: dict[str, Any]) -> None:
        """Write to a temp file, then swap it in, so a crash never leaves a half-written file."""
        path = self.directory / name
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

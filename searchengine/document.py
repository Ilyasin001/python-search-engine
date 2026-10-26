"""Document: the core unit of data in a search engine.

Unlike a normalized database row, a document is a flat text blob paired with
descriptive metadata (title, category, tags, ...).
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    id: int
    fields: dict[str, Any] = field(default_factory=dict)

    def text(self, name: str) -> str:
        value = self.fields.get(name, "")
        return " ".join(value) if isinstance(value, list) else str(value)

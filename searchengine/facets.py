"""Faceting: count results per category/tag for drill-down filtering.

Like the sidebar on a shopping site:

    category                    tags
      concepts (4)                fundamentals (5)
      text-analysis (3)           analysis (3)

Counts are computed over the documents matching the current query, so they always
reflect what clicking a value would return. Selecting values narrows the results:
values within one field are OR'd (concepts or text-analysis), different fields are
AND'd (category=concepts and tags=fundamentals). Facet values are matched exactly,
not analyzed, since they are labels rather than free text.
"""

from collections import Counter
from collections.abc import Iterable, Mapping

from searchengine.document import Document

Filters = Mapping[str, str | Iterable[str]]


def _values(doc: Document, field: str) -> set[str]:
    value = doc.fields.get(field)
    if value is None:
        return set()
    return {str(v) for v in value} if isinstance(value, list) else {str(value)}


def facet_counts(
    docs: Iterable[Document], fields: Iterable[str], limit: int | None = None
) -> dict[str, list[tuple[str, int]]]:
    """Per field, (value, count) pairs, most common first and then alphabetical."""
    fields = list(fields)
    counters = {field: Counter[str]() for field in fields}
    for doc in docs:
        for field in fields:
            counters[field].update(_values(doc, field))
    return {
        field: sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
        for field, counter in counters.items()
    }


def matches_filters(doc: Document, filters: Filters) -> bool:
    for field, wanted in filters.items():
        wanted = {wanted} if isinstance(wanted, str) else set(wanted)
        if not wanted & _values(doc, field):
            return False
    return True


def filter_docs(docs: Iterable[Document], filters: Filters) -> list[Document]:
    return [doc for doc in docs if matches_filters(doc, filters)]

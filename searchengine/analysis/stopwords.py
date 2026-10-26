"""Stop words: high-frequency, low-meaning filler words filtered out of the index.

The list is Lucene's classic English stop set.
"""

from collections.abc import Iterable

STOP_WORDS: frozenset[str] = frozenset(
    """
    a an and are as at be but by for if in into is it no not of on or such
    that the their then there these they this to was will with
    """.split()
)


def is_stop_word(term: str) -> bool:
    return term in STOP_WORDS


def remove_stop_words(tokens: Iterable[str], stop_words: frozenset[str] = STOP_WORDS) -> list[str]:
    return [t for t in tokens if t not in stop_words]

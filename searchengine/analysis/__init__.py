"""Text analysis: turn raw text into a stream of index terms.

tokenize -> lowercase -> remove stop words -> stem (or n-gram for autocomplete)
"""

from searchengine.analysis.stemmer import stem
from searchengine.analysis.stopwords import STOP_WORDS
from searchengine.analysis.tokenizer import tokenize


def analyze(text: str, stop_words: frozenset[str] = STOP_WORDS, stemming: bool = True) -> list[str]:
    """The standard analyzer chain used for both indexing and querying."""
    terms = [t for t in tokenize(text) if t not in stop_words]
    return [stem(t) for t in terms] if stemming else terms

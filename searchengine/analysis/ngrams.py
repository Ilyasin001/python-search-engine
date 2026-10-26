"""N-grams and edge n-grams: character windows for autocomplete and fuzzy matching.

- n-grams slide a fixed-size window across a word:  "search", 3 -> sea, ear, arc, rch
  They match on fragments, which helps with typos and languages a stemmer doesn't cover.
- edge n-grams grow from the start of a word:        "search", 2..4 -> se, sea, sear
  Indexing these lets a partial query ("sea") match whole words, which powers autocomplete.
"""


def ngrams(word: str, n: int) -> list[str]:
    if n < 1:
        raise ValueError("n must be at least 1")
    return [word[i : i + n] for i in range(len(word) - n + 1)]


def edge_ngrams(word: str, min_n: int = 1, max_n: int = 10) -> list[str]:
    if min_n < 1 or max_n < min_n:
        raise ValueError("need 1 <= min_n <= max_n")
    return [word[:n] for n in range(min_n, min(max_n, len(word)) + 1)]

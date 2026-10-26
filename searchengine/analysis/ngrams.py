"""N-grams and edge n-grams: character windows for autocomplete and fuzzy matching. (Step 4)"""


def ngrams(word: str, n: int) -> list[str]:
    raise NotImplementedError("Step 4: n-grams")


def edge_ngrams(word: str, min_n: int = 1, max_n: int = 10) -> list[str]:
    raise NotImplementedError("Step 4: edge n-grams")

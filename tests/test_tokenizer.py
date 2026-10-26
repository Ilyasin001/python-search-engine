from searchengine.analysis.tokenizer import tokenize


def test_lowercases_and_splits_on_punctuation():
    assert tokenize("Hello, World! Search-engine.") == ["hello", "world", "search", "engine"]


def test_keeps_numbers():
    assert tokenize("BM25 beats LIKE in 2026") == ["bm25", "beats", "like", "in", "2026"]


def test_drops_apostrophes_inside_words():
    assert tokenize("Don't stop") == ["dont", "stop"]
    assert tokenize("it’s") == ["its"]


def test_handles_non_english_text():
    assert tokenize("Café Straße") == ["café", "strasse"]


def test_empty_and_whitespace():
    assert tokenize("") == []
    assert tokenize("   \n\t ") == []

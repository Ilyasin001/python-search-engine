from searchengine.analysis.stopwords import STOP_WORDS, is_stop_word, remove_stop_words
from searchengine.analysis.tokenizer import tokenize


def test_common_filler_words_are_stop_words():
    for word in ("and", "the", "but"):
        assert is_stop_word(word)
    assert not is_stop_word("search")


def test_remove_stop_words_from_tokens():
    tokens = tokenize("The engine and the index")
    assert remove_stop_words(tokens) == ["engine", "index"]


def test_custom_stop_list():
    assert remove_stop_words(["foo", "bar"], frozenset({"foo"})) == ["bar"]


def test_stop_words_are_lowercase():
    assert all(w == w.casefold() for w in STOP_WORDS)

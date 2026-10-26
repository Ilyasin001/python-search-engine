import pytest

from searchengine.analysis.ngrams import edge_ngrams, ngrams


def test_ngrams_slide_a_window():
    assert ngrams("search", 3) == ["sea", "ear", "arc", "rch"]
    assert ngrams("abc", 1) == ["a", "b", "c"]


def test_ngrams_word_shorter_than_n():
    assert ngrams("ab", 3) == []
    assert ngrams("abc", 3) == ["abc"]


def test_ngrams_work_on_non_english_text():
    assert ngrams("東京都", 2) == ["東京", "京都"]


def test_edge_ngrams_grow_from_the_start():
    assert edge_ngrams("search", 2, 4) == ["se", "sea", "sear"]
    assert edge_ngrams("index") == ["i", "in", "ind", "inde", "index"]


def test_edge_ngrams_capped_by_word_length():
    assert edge_ngrams("ab", 1, 5) == ["a", "ab"]
    assert edge_ngrams("a", 2, 5) == []


def test_edge_ngrams_enable_prefix_matching():
    index = {gram: word for word in ("search", "segment", "stem") for gram in edge_ngrams(word, 2)}
    assert index["sea"] == "search"
    assert index["seg"] == "segment"


@pytest.mark.parametrize("n", [0, -1])
def test_ngrams_reject_bad_n(n):
    with pytest.raises(ValueError):
        ngrams("word", n)


@pytest.mark.parametrize(("min_n", "max_n"), [(0, 3), (4, 2)])
def test_edge_ngrams_reject_bad_range(min_n, max_n):
    with pytest.raises(ValueError):
        edge_ngrams("word", min_n, max_n)

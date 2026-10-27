from searchengine.suggest import Suggester


def build() -> Suggester:
    suggester = Suggester()
    suggester.add_all(["the inverted index", "index segments and indexing", "an index", "Information"])
    return suggester


def test_completes_by_frequency_then_alphabetically():
    assert build().suggest("in") == ["index", "indexing", "information", "inverted"]


def test_keeps_earlier_words():
    assert build().suggest("inverted ind") == ["inverted index", "inverted indexing"]


def test_limit():
    assert build().suggest("in", limit=1) == ["index"]


def test_case_insensitive():
    assert build().suggest("INF") == ["information"]


def test_stop_words_are_not_suggested():
    assert "the" not in build().suggest("th")


def test_nothing_to_complete():
    suggester = build()
    assert suggester.suggest("") == []
    assert suggester.suggest("index ") == []  # trailing space: the word is finished
    assert suggester.suggest("zz") == []


def test_prefix_longer_than_max_prefix():
    suggester = Suggester(max_prefix=3)
    suggester.add("internationalization")
    assert suggester.suggest("internat") == ["internationalization"]
    assert suggester.suggest("intern-x") == []

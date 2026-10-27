import pytest

from searchengine.query.parser import And, Not, Or, Phrase, Term, parse


def p(text: str, default_operator: str = "AND") -> str:
    return str(parse(text, default_operator))


def test_single_term_is_analyzed():
    assert parse("Testing") == Term("test")


def test_implicit_and_between_terms():
    assert parse("inverted index") == And((Term("invert"), Term("index")))


def test_default_operator_can_be_or():
    assert parse("inverted index", "OR") == Or((Term("invert"), Term("index")))


def test_phrase():
    assert parse('"Inverted Indexes"') == Phrase(("invert", "index"))


def test_hyphenated_word_becomes_phrase():
    assert parse("search-engine") == Phrase(("search", "engin"))


def test_or_and_precedence():
    assert p("stemming OR ngrams scoring") == "(stem OR (ngram AND score))"
    assert p("a1 b1 OR c1") == "((a1 AND b1) OR c1)"


def test_not_and_minus():
    assert parse("index NOT segment") == And((Term("index"), Not(Term("segment"))))
    assert parse("index -segment") == parse("index NOT segment")
    assert parse("index AND NOT segment") == parse("index NOT segment")


def test_parentheses_group():
    assert p("(bm25 OR tfidf) scoring") == "((bm25 OR tfidf) AND score)"
    assert p("NOT (stop OR stem)") == "NOT (stop OR stem)"


def test_field_prefix():
    assert parse("title:Stemming") == Term("stem", "title")
    assert parse('body:"inverted index"') == Phrase(("invert", "index"), "body")


def test_nested_ands_are_flattened():
    assert parse("a1 AND (b1 AND c1)") == And((Term("a1"), Term("b1"), Term("c1")))


def test_stop_words_are_dropped():
    assert parse("the index of the corpus") == And((Term("index"), Term("corpu")))
    assert parse('"index of the corpus"') == Phrase(("index", "corpu"))
    assert parse("the AND of") is None


def test_lowercase_keywords_are_just_words():
    # "and"/"or"/"not" are stop words, so they vanish rather than acting as operators
    assert parse("cats or dogs") == And((Term("cat"), Term("dog")))


@pytest.mark.parametrize(
    "text",
    ["", "   ", "()", ")", "AND", "OR OR", "NOT", "-", '"', "((("],
)
def test_garbage_gives_empty_query(text):
    assert parse(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("index)", "index"),
        ("(index", "index"),
        ("index AND", "index"),
        ("OR index", "index"),
        ('"unterminated phrase', '"untermin phrase"'),
        ("index NOT", "index"),
    ],
)
def test_lenient_parsing(text, expected):
    assert p(text) == expected


def test_bad_default_operator():
    with pytest.raises(KeyError):
        parse("x", "XOR")

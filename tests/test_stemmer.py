import pytest

from searchengine.analysis import analyze
from searchengine.analysis.stemmer import stem

# Expected outputs from Martin Porter's paper and reference vocabulary.
PORTER_CASES = {
    # step 1a
    "caresses": "caress",
    "ponies": "poni",
    "ties": "ti",
    "caress": "caress",
    "cats": "cat",
    # step 1b
    "feed": "feed",
    "agreed": "agre",
    "plastered": "plaster",
    "bled": "bled",
    "motoring": "motor",
    "sing": "sing",
    "conflated": "conflat",
    "troubled": "troubl",
    "sized": "size",
    "hopping": "hop",
    "tanned": "tan",
    "falling": "fall",
    "hissing": "hiss",
    "fizzed": "fizz",
    "failing": "fail",
    "filing": "file",
    # step 1c
    "happy": "happi",
    "sky": "sky",
    # steps 2-5
    "relational": "relat",
    "conditional": "condit",
    "generalizations": "gener",
    "oscillators": "oscil",
    "electricity": "electr",
    "hopeful": "hope",
    "goodness": "good",
    "effective": "effect",
    "adjustable": "adjust",
    "probate": "probat",
    "rate": "rate",
    "cease": "ceas",
    "controll": "control",
    "roll": "roll",
}


@pytest.mark.parametrize(("word", "expected"), PORTER_CASES.items())
def test_porter_reference_cases(word, expected):
    assert stem(word) == expected


def test_variations_share_a_stem():
    assert {stem(w) for w in ("connect", "connected", "connecting", "connection", "connections")} == {
        "connect"
    }
    assert {stem(w) for w in ("test", "tests", "testing", "tested")} == {"test"}


def test_short_and_non_alpha_tokens_pass_through():
    assert stem("is") == "is"
    assert stem("bm25") == "bm25"
    assert stem("café") == "café"


def test_analyze_runs_the_full_chain():
    assert analyze("The testers are testing the indexes") == ["tester", "test", "index"]
    assert analyze("Testing the index", stemming=False) == ["testing", "index"]

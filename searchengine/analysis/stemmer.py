"""Stemming: reduce words to a root form so variations match (testing, tests -> test).

An implementation of the original Porter (1980) algorithm. A word is viewed as
[C](VC)^m[V], where C/V are runs of consonants/vowels and m is its "measure";
most rules only strip a suffix when the remaining stem is long enough (m > 0, m > 1).
"""

from collections.abc import Callable
from itertools import groupby

_VOWELS = frozenset("aeiou")


def _is_consonant(word: str, i: int) -> bool:
    ch = word[i]
    if ch in _VOWELS:
        return False
    if ch == "y":
        # "y" is a vowel when it follows a consonant (happy), a consonant otherwise (yes, toy).
        return i == 0 or not _is_consonant(word, i - 1)
    return True


def _measure(stem: str) -> int:
    pattern = "".join("c" if _is_consonant(stem, i) else "v" for i in range(len(stem)))
    collapsed = "".join(key for key, _ in groupby(pattern))
    return collapsed.count("vc")


def _has_vowel(stem: str) -> bool:
    return any(not _is_consonant(stem, i) for i in range(len(stem)))


def _ends_double_consonant(word: str) -> bool:
    return len(word) >= 2 and word[-1] == word[-2] and _is_consonant(word, len(word) - 1)


def _ends_cvc(word: str) -> bool:
    """consonant-vowel-consonant ending, where the last consonant is not w, x or y (hop, fil)."""
    return (
        len(word) >= 3
        and _is_consonant(word, len(word) - 3)
        and not _is_consonant(word, len(word) - 2)
        and _is_consonant(word, len(word) - 1)
        and word[-1] not in "wxy"
    )


def _replace_suffix(word: str, rules: list[tuple[str, str]], condition: Callable[[str], bool]) -> str:
    """Apply the rule for the longest matching suffix; stop there even if its condition fails."""
    for suffix, replacement in rules:
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            return stem + replacement if condition(stem) else word
    return word


def _longest_first(rules: dict[str, str]) -> list[tuple[str, str]]:
    return sorted(rules.items(), key=lambda rule: len(rule[0]), reverse=True)


_STEP2 = _longest_first(
    {
        "ational": "ate",
        "tional": "tion",
        "enci": "ence",
        "anci": "ance",
        "izer": "ize",
        "abli": "able",
        "alli": "al",
        "entli": "ent",
        "eli": "e",
        "ousli": "ous",
        "ization": "ize",
        "ation": "ate",
        "ator": "ate",
        "alism": "al",
        "iveness": "ive",
        "fulness": "ful",
        "ousness": "ous",
        "aliti": "al",
        "iviti": "ive",
        "biliti": "ble",
    }
)

_STEP3 = _longest_first(
    {
        "icate": "ic",
        "ative": "",
        "alize": "al",
        "iciti": "ic",
        "ical": "ic",
        "ful": "",
        "ness": "",
    }
)

_STEP4 = _longest_first(
    {
        suffix: ""
        for suffix in (
            "al ance ence er ic able ible ant ement ment ent ion ou ism ate iti ous ive ize".split()
        )
    }
)


def _step1a(word: str) -> str:
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("ies"):
        return word[:-2]
    if word.endswith("ss"):
        return word
    if word.endswith("s"):
        return word[:-1]
    return word


def _step1b(word: str) -> str:
    if word.endswith("eed"):
        return word[:-1] if _measure(word[:-3]) > 0 else word
    for suffix in ("ed", "ing"):
        if word.endswith(suffix) and _has_vowel(word[: -len(suffix)]):
            return _step1b_cleanup(word[: -len(suffix)])
    return word


def _step1b_cleanup(word: str) -> str:
    if word.endswith(("at", "bl", "iz")):
        return word + "e"  # conflat(ed) -> conflate
    if _ends_double_consonant(word) and word[-1] not in "lsz":
        return word[:-1]  # hopp(ing) -> hop
    if _measure(word) == 1 and _ends_cvc(word):
        return word + "e"  # fil(ing) -> file
    return word


def _step1c(word: str) -> str:
    if word.endswith("y") and _has_vowel(word[:-1]):
        return word[:-1] + "i"
    return word


def _step4(word: str) -> str:
    for suffix, _ in _STEP4:
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            keep_ion = suffix != "ion" or stem.endswith(("s", "t"))
            return stem if _measure(stem) > 1 and keep_ion else word
    return word


def _step5(word: str) -> str:
    if word.endswith("e"):
        stem = word[:-1]
        m = _measure(stem)
        if m > 1 or (m == 1 and not _ends_cvc(stem)):
            word = stem
    if _measure(word) > 1 and _ends_double_consonant(word) and word.endswith("l"):
        word = word[:-1]
    return word


def stem(word: str) -> str:
    """Return the Porter stem of a lowercase word. Non-ASCII or non-alphabetic tokens pass through."""
    if len(word) <= 2 or not (word.isascii() and word.isalpha()):
        return word
    word = _step1a(word)
    word = _step1b(word)
    word = _step1c(word)
    word = _replace_suffix(word, _STEP2, lambda s: _measure(s) > 0)
    word = _replace_suffix(word, _STEP3, lambda s: _measure(s) > 0)
    word = _step4(word)
    return _step5(word)

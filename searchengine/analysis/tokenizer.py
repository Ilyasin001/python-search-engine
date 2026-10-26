"""Split raw text into lowercase word tokens.

Words are runs of letters/digits (any language, via a Unicode-aware regex). Apostrophes inside a
word are dropped so "don't" and "dont" produce the same token.
"""

import re

_WORD = re.compile(r"\w+(?:['’]\w+)*")
_APOSTROPHES = str.maketrans("", "", "'’")


def tokenize(text: str) -> list[str]:
    return [m.group().translate(_APOSTROPHES) for m in _WORD.finditer(text.casefold())]

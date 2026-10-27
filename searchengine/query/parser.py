"""Query parser: turn raw user input into a query tree the engine can evaluate.

Supported syntax:

    inverted index            two terms, joined by the default operator (AND)
    "inverted index"          phrase: the terms must appear next to each other
    stemming OR ngrams        either term
    index AND NOT segment     NOT / a leading "-" excludes:  index -segment
    (bm25 OR tfidf) scoring   parentheses group
    title:stemming            restrict a term or phrase to one field

Precedence is NOT > AND > OR. Every term goes through the same analyze() chain used at
index time, so "Testing" becomes "test" and stop words disappear. The parser is lenient,
like a real search box: stray parentheses and dangling operators are ignored.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass

from searchengine.analysis import analyze


@dataclass(frozen=True)
class Term:
    text: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.field}:{self.text}" if self.field else self.text


@dataclass(frozen=True)
class Phrase:
    terms: tuple[str, ...]
    field: str | None = None

    def __str__(self) -> str:
        quoted = '"' + " ".join(self.terms) + '"'
        return f"{self.field}:{quoted}" if self.field else quoted


@dataclass(frozen=True)
class And:
    children: tuple["Query", ...]

    def __str__(self) -> str:
        return "(" + " AND ".join(map(str, self.children)) + ")"


@dataclass(frozen=True)
class Or:
    children: tuple["Query", ...]

    def __str__(self) -> str:
        return "(" + " OR ".join(map(str, self.children)) + ")"


@dataclass(frozen=True)
class Not:
    child: "Query"

    def __str__(self) -> str:
        return f"NOT {self.child}"


Query = Term | Phrase | And | Or | Not

# -- lexer --------------------------------------------------------------------

_TOKEN = re.compile(
    r"""
    (?P<lparen>\() | (?P<rparen>\)) | (?P<neg>-)(?=[^\s-])
    | (?:(?P<field>\w+):)? (?: "(?P<phrase>[^"]*)"? | (?P<word>[^\s()"]+) )
    """,
    re.VERBOSE,
)
_KEYWORDS = {"AND", "OR", "NOT"}


@dataclass(frozen=True)
class _Token:
    kind: str  # "(", ")", "AND", "OR", "NOT", "TEXT"
    node: Query | None = None  # analyzed Term/Phrase for TEXT tokens (None if all stop words)


def _lex(text: str) -> Iterator[_Token]:
    for m in _TOKEN.finditer(text):
        if m["lparen"]:
            yield _Token("(")
        elif m["rparen"]:
            yield _Token(")")
        elif m["neg"]:
            yield _Token("NOT")
        elif m["word"] in _KEYWORDS and not m["field"]:
            yield _Token(m["word"])
        else:
            yield _Token("TEXT", _text_node(m["phrase"] or m["word"] or "", m["field"]))


def _text_node(text: str, field: str | None) -> Query | None:
    """A word that analyzes to several terms (e.g. "search-engine") becomes a phrase."""
    terms = analyze(text)
    field = field.casefold() if field else None
    if not terms:
        return None
    return Term(terms[0], field) if len(terms) == 1 else Phrase(tuple(terms), field)


# -- parser -------------------------------------------------------------------


def _combine(kind: type[And] | type[Or], parts: list[Query | None]) -> Query | None:
    children: list[Query] = []
    for part in parts:
        if isinstance(part, kind):
            children.extend(part.children)  # flatten (a AND (b AND c)) -> (a AND b AND c)
        elif part is not None:
            children.append(part)
    if not children:
        return None
    return children[0] if len(children) == 1 else kind(tuple(children))


class _Parser:
    def __init__(self, tokens: list[_Token], default: type[And] | type[Or]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.default = default

    def peek(self) -> str | None:
        return self.tokens[self.pos].kind if self.pos < len(self.tokens) else None

    def advance(self) -> _Token:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def starts_operand(self) -> bool:
        return self.peek() in ("(", "NOT", "TEXT")

    def parse(self) -> Query | None:
        parts = []
        while self.peek() is not None:
            if self.peek() == ")":  # stray closing paren
                self.advance()
                continue
            parts.append(self.or_expr())
        return _combine(self.default, parts)

    def or_expr(self) -> Query | None:
        parts = [self.and_expr()]
        while self.peek() == "OR" or (self.default is Or and self.starts_operand()):
            if self.peek() == "OR":
                self.advance()
            parts.append(self.and_expr())
        return _combine(Or, parts)

    def and_expr(self) -> Query | None:
        parts = [self.unary()]
        while self.peek() == "AND" or (self.default is And and self.starts_operand()):
            if self.peek() == "AND":
                self.advance()
            parts.append(self.unary())
        return _combine(And, parts)

    def unary(self) -> Query | None:
        kind = self.peek()
        if kind is None or kind == ")":
            return None
        token = self.advance()
        if kind == "NOT":
            child = self.unary()
            return Not(child) if child is not None else None
        if kind == "(":
            node = self.or_expr()
            if self.peek() == ")":
                self.advance()
            return node
        if kind == "TEXT":
            return token.node
        return None  # a misplaced AND/OR, e.g. at the very start


def parse(text: str, default_operator: str = "AND") -> Query | None:
    """Parse a query string. Returns None when nothing searchable is left (e.g. only stop words)."""
    default = {"AND": And, "OR": Or}[default_operator.upper()]
    return _Parser(list(_lex(text)), default).parse()

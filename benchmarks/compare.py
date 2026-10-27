"""Compare this engine with SQL `LIKE`, SQLite FTS5 and Whoosh.

    python -m benchmarks.compare                 # quality on the sample corpus + speed on 10k docs
    python -m benchmarks.compare --docs 50000

Two questions, printed as Markdown:
  1. Quality: on the real sample corpus, what does each approach return for a few queries?
  2. Speed:   on a larger synthetic corpus, how long does indexing and searching take?

Backends:
  - this engine     pure Python, inverted index in JSON segments, BM25
  - SQL LIKE        SQLite in memory, `title LIKE '%word%' OR body LIKE '%word%'`, no ranking
  - SQLite FTS5     SQLite's built-in inverted index (C), porter stemmer, BM25
  - Whoosh          pure-Python search library (pip install -e ".[compare]"); skipped if missing
"""

import argparse
import json
import random
import re
import sqlite3
import statistics
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from searchengine.analysis.stopwords import STOP_WORDS
from searchengine.analysis.tokenizer import tokenize
from searchengine.engine import Engine

SAMPLE = Path(__file__).parent.parent / "data" / "sample_docs.json"
QUALITY_QUERIES = ["stemming", "indexes", "core", '"inverted index"', "search engines"]

Doc = dict[str, str]
Result = tuple[int, list[str]]  # (total matches, top titles)


class Backend:
    name = ""

    def build(self, docs: list[Doc]) -> None:
        raise NotImplementedError

    def search(self, query: str, limit: int = 10) -> Result:
        raise NotImplementedError

    def close(self) -> None:
        pass


class OurEngine(Backend):
    name = "this engine"

    def build(self, docs: list[Doc]) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.engine = Engine(self._tmp.name, boosts={"title": 2.0}, facet_fields=["category"])
        self.engine.index_many(docs)
        self.engine.commit()

    def search(self, query: str, limit: int = 10) -> Result:
        results = self.engine.search(query, limit)
        return results.total, [hit.doc.fields["title"] for hit in results.hits]

    def close(self) -> None:
        self._tmp.cleanup()


class SqlLike(Backend):
    name = "SQL LIKE"

    def build(self, docs: list[Doc]) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE docs (id INTEGER PRIMARY KEY, title TEXT, body TEXT)")
        self.db.executemany(
            "INSERT INTO docs (title, body) VALUES (?, ?)", [(d["title"], d["body"]) for d in docs]
        )
        self.db.commit()

    def search(self, query: str, limit: int = 10) -> Result:
        # Each quoted phrase or bare word must appear somewhere as a substring; no ranking.
        needles = [p or w for p, w in re.findall(r'"([^"]+)"|(\S+)', query)]
        where = " AND ".join("(title LIKE ? OR body LIKE ?)" for _ in needles) or "1"
        params = [f"%{n}%" for n in needles for _ in range(2)]
        total = self.db.execute(f"SELECT COUNT(*) FROM docs WHERE {where}", params).fetchone()[0]
        rows = self.db.execute(f"SELECT title FROM docs WHERE {where} ORDER BY id LIMIT ?", [*params, limit])
        return total, [title for (title,) in rows]


class SqliteFts5(Backend):
    name = "SQLite FTS5"

    def build(self, docs: list[Doc]) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE VIRTUAL TABLE docs USING fts5(title, body, tokenize='porter')")
        self.db.executemany(
            "INSERT INTO docs (title, body) VALUES (?, ?)", [(d["title"], d["body"]) for d in docs]
        )
        self.db.commit()

    def search(self, query: str, limit: int = 10) -> Result:
        total = self.db.execute("SELECT COUNT(*) FROM docs WHERE docs MATCH ?", [query]).fetchone()[0]
        rows = self.db.execute(
            "SELECT title FROM docs WHERE docs MATCH ? ORDER BY bm25(docs, 2.0, 1.0) LIMIT ?", [query, limit]
        )
        return total, [title for (title,) in rows]


class Whoosh(Backend):
    name = "Whoosh"

    def build(self, docs: list[Doc]) -> None:
        from whoosh import fields, index
        from whoosh.analysis import StemmingAnalyzer
        from whoosh.qparser import MultifieldParser

        schema = fields.Schema(
            title=fields.TEXT(stored=True, analyzer=StemmingAnalyzer(), field_boost=2.0),
            body=fields.TEXT(analyzer=StemmingAnalyzer()),
        )
        # Whoosh memory-maps its segment files, which Windows won't delete while mapped.
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.index = index.create_in(self._tmp.name, schema)
        writer = self.index.writer()
        for doc in docs:
            writer.add_document(title=doc["title"], body=doc["body"])
        writer.commit()
        self.parser = MultifieldParser(["title", "body"], schema)
        self.searcher = self.index.searcher()

    def search(self, query: str, limit: int = 10) -> Result:
        results = self.searcher.search(self.parser.parse(query), limit=limit)
        return len(results), [hit["title"] for hit in results]

    def close(self) -> None:
        self.searcher.close()
        self.index.close()
        self._tmp.cleanup()


def available_backends() -> list[type[Backend]]:
    backends: list[type[Backend]] = [OurEngine, SqlLike, SqliteFts5]
    try:
        import whoosh  # noqa: F401
    except ImportError:
        pass
    else:
        backends.append(Whoosh)
    return backends


# -- corpora ------------------------------------------------------------------


def sample_docs() -> list[Doc]:
    return [{k: v for k, v in d.items() if k != "id"} for d in json.loads(SAMPLE.read_text(encoding="utf-8"))]


def synthetic_docs(count: int, seed: int = 42) -> tuple[list[Doc], list[str]]:
    """Random documents whose words follow a Zipf-like distribution over the sample vocabulary,
    so a few words are very common and most are rare, as in real text. Returns the docs and
    the vocabulary ordered from most to least common."""
    rng = random.Random(seed)
    vocabulary = sorted(
        {w for d in sample_docs() for w in tokenize(d["title"] + " " + d["body"]) if w.isalpha()}
    )
    rng.shuffle(vocabulary)
    weights = [1 / rank for rank in range(1, len(vocabulary) + 1)]
    categories = sorted({d["category"] for d in sample_docs()})

    def words(low: int, high: int) -> str:
        return " ".join(rng.choices(vocabulary, weights, k=rng.randint(low, high)))

    docs = [
        {"title": words(3, 6).capitalize(), "body": words(30, 80), "category": rng.choice(categories)}
        for _ in range(count)
    ]
    return docs, vocabulary


def speed_queries(vocabulary: list[str]) -> list[str]:
    content = [w for w in vocabulary if w not in STOP_WORDS and len(w) > 3]
    common, mid, rare = content[0], content[20], content[200 % len(content)]
    return [common, mid, rare, f"{common} {mid}", f'"{content[1]} {content[2]}"']


# -- reports ------------------------------------------------------------------


def timed(fn: Callable[[], object]) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


def quality_report(backends: list[type[Backend]], limit: int = 3) -> str:
    docs = sample_docs()
    built = [b() for b in backends]
    for backend in built:
        backend.build(docs)
    lines = [f"### Quality on the sample corpus ({len(docs)} docs)", ""]
    for query in QUALITY_QUERIES:
        lines += [f"**`{query}`**", "", "| Backend | Matches | Top results |", "|---|---|---|"]
        for backend in built:
            total, titles = backend.search(query, limit)
            lines.append(f"| {backend.name} | {total} | {'; '.join(titles) or '-'} |")
        lines.append("")
    for backend in built:
        backend.close()
    return "\n".join(lines)


def speed_report(backends: list[type[Backend]], count: int, repeat: int, seed: int) -> str:
    docs, vocabulary = synthetic_docs(count, seed)
    queries = speed_queries(vocabulary)
    header = "| Backend | Index time | " + " | ".join(f"`{q}`" for q in queries) + " |"
    lines = [
        f"### Speed on {count:,} synthetic docs",
        "",
        f"Median of {repeat} runs per query, in milliseconds, with the match count in brackets.",
        "",
        header,
        "|---" * (len(queries) + 2) + "|",
    ]
    for backend_type in backends:
        backend = backend_type()
        build_seconds = timed(lambda backend=backend: backend.build(docs))
        cells = []
        for query in queries:
            total, _ = backend.search(query)
            runs = [timed(lambda q=query, backend=backend: backend.search(q)) for _ in range(repeat)]
            cells.append(f"{statistics.median(runs) * 1000:.1f} ({total:,})")
        backend.close()
        lines.append(f"| {backend.name} | {build_seconds:.2f} s | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--docs", type=int, default=10_000, help="synthetic corpus size")
    parser.add_argument("--repeat", type=int, default=5, help="runs per query")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    backends = available_backends()
    if Whoosh not in backends:
        print('> Whoosh not installed; skipping it (pip install -e ".[compare]")\n')
    print(quality_report(backends))
    print()
    print(speed_report(backends, args.docs, args.repeat, args.seed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

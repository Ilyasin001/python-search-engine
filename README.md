# Python Search Engine

A small, educational full-text search engine built step by step in pure Python, based on
Daniel Lindley's talk *"Building A Python-Based Search Engine"*.

It covers the core ideas behind engines like Lucene, Solr, Elasticsearch and Whoosh:
documents, text analysis (stop words, stemming, n-grams), an inverted index stored in
segments, a query parser, BM25 scoring, boosting and faceting.

## Tech stack

| Area      | Choice                                   |
|-----------|------------------------------------------|
| Language  | Python 3.11+                              |
| Engine    | Standard library only (no dependencies)  |
| Storage   | JSON segment files + a manifest          |
| Interface | CLI (`argparse`)                          |
| Tests     | pytest                                    |
| Lint/format | ruff                                    |
| Editor    | VS Code (settings in `.vscode/`)          |

## Project structure

```
searchengine/            the engine package
  document.py            Document: text blob + metadata
  analysis/              tokenizer, stop words, stemmer, n-grams
  index/                 inverted index + on-disk segments
  query/                 query parser
  scoring/               BM25 + boosting
  facets.py              facet counts
  suggest.py             autocomplete via edge n-grams
  engine.py              ties it all together
  cli.py                 command-line interface
benchmarks/compare.py    vs SQL LIKE, SQLite FTS5 and Whoosh
tests/                   pytest suite
data/sample_docs.json    sample corpus (16 docs about search concepts)
docs/ROADMAP.md          the step-by-step build plan
docs/COMPARISON.md       benchmark results and what they show
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"
pytest
python -m searchengine --help
```

## Usage

```bash
# build the index (in ./index) from the sample corpus
python -m searchengine index data/sample_docs.json --fresh

# search: terms, "phrases", AND / OR / NOT (or -word), (grouping), field:term
python -m searchengine search "inverted index"
python -m searchengine search "\"inverted index\" OR stemming -lucene"
python -m searchengine search "title:segments"

# drill down with facet filters; an empty query browses everything
python -m searchengine search "" --filter category=text-analysis

# autocomplete the last word
python -m searchengine suggest "inverted ind"
```

From Python:

```python
from searchengine.engine import Engine

with Engine("index", boosts={"title": 2.0}, facet_fields=["category", "tags"]) as engine:
    engine.index({"title": "Stop words", "body": "Filler words like and, the, but", "category": "analysis"})
    results = engine.search("stop words")
    for hit in results.hits:
        print(hit.score, hit.doc.fields["title"])
```

## How it compares

[docs/COMPARISON.md](docs/COMPARISON.md) benchmarks this engine against SQL `LIKE`,
SQLite FTS5 and Whoosh, covering result quality on the sample corpus and speed on 10k documents.
`LIKE` misses word variants, matches inside other words and can't rank. An inverted index
does work in proportion to the matches rather than the corpus size.

```bash
pip install -e ".[compare]"
python -m benchmarks.compare
```

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

## References

- Daniel Lindley, *Building A Python-Based Search Engine* (talk):
  https://www.youtube.com/watch?v=cY7pE7vX6MU

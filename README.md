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
  engine.py              ties it all together
  cli.py                 command-line interface
tests/                   pytest suite
data/sample_docs.json    sample corpus (16 docs about search concepts)
docs/ROADMAP.md          the step-by-step build plan
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"
pytest
python -m searchengine --help
```

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

## References

- Daniel Lindley, *Building A Python-Based Search Engine* (talk):
  https://www.youtube.com/watch?v=cY7pE7vX6MU

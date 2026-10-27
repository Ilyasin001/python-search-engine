# Roadmap

Each step is one commit (or a small set of commits) pushed to GitHub.

| Step | Topic | Module | Status |
|------|-------|--------|--------|
| 1  | Project scaffold, tech stack, `Document`         | `document.py`, `cli.py`        | done |
| 2  | Tokenizer + stop words                           | `analysis/tokenizer.py`, `analysis/stopwords.py` | done |
| 3  | Stemming (Porter-style)                          | `analysis/stemmer.py`          | done |
| 4  | N-grams and edge n-grams (autocomplete)          | `analysis/ngrams.py`           | done |
| 5  | Inverted index with positions                    | `index/inverted_index.py`      | done |
| 6  | Segments + manifest on disk                      | `index/segments.py`            | done |
| 7  | Query parser (terms, phrases, AND/OR/NOT)        | `query/parser.py`              | done |
| 8  | BM25 scoring + field boosting                    | `scoring/bm25.py`              | done |
| 9  | Faceting (category/tag counts)                   | `facets.py`                    | |
| 10 | Engine API: index, search, delete                | `engine.py`                    | |
| 11 | CLI: `index`, `search`, `suggest` commands       | `cli.py`                       | |
| 12 | Compare against SQL `LIKE` and Whoosh            | `docs/`                        | |

## Glossary

- **Document**: a flat text blob plus metadata (title, tags, attributes).
- **Corpus**: all documents in an index.
- **Engine**: takes a query, returns ranked results.
- **Stop words**: filler words (and, the, but) dropped during analysis.
- **Stemming**: reducing words to a root (testing, tester → test).
- **N-grams / edge n-grams**: character windows; power autocomplete and non-English matching.
- **Inverted index**: term → documents and positions where it appears.
- **Segments**: smaller index files that together make up the full index.
- **Query parser**: turns raw input into structured terms / a query tree.
- **Scoring (BM25)**: ranks documents by term frequency, rarity and length.
- **Faceting**: drill-down filters with counts per category.
- **Boosting**: weighting some fields or documents higher during scoring.

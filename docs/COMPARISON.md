# Comparison: this engine vs SQL `LIKE`, SQLite FTS5 and Whoosh

The talk's argument for a search engine over `LIKE '%term%'` is about both **relevance** and
**speed**. This page tests that claim with [`benchmarks/compare.py`](../benchmarks/compare.py):

| Backend | What it is |
|---|---|
| **this engine** | pure Python, inverted index in JSON segments, Porter stemming, BM25 |
| **SQL LIKE** | SQLite in memory, `title LIKE '%word%' OR body LIKE '%word%'` per word, no ranking |
| **SQLite FTS5** | SQLite's built-in full-text index, written in C, Porter stemming, BM25 |
| **Whoosh** | a pure-Python search library ([whoosh-reloaded](https://github.com/Sygil-Dev/whoosh-reloaded)), stemming, BM25F |

Every backend gives titles a 2x boost. Run it yourself:

```bash
pip install -e ".[compare]"      # adds Whoosh; the engine itself still has no dependencies
python -m benchmarks.compare     # --docs 50000 for a bigger corpus
```

The numbers below come from one run on a 7th-gen Intel laptop CPU, Windows 10, Python 3.15.
Timings vary between machines, so compare the backends with each other rather than reading
the numbers as absolute.

## Results

### Quality on the sample corpus (16 docs)

**`stemming`**

| Backend | Matches | Top results |
|---|---|---|
| this engine | 1 | Stemming words to their roots |
| SQL LIKE | 1 | Stemming words to their roots |
| SQLite FTS5 | 1 | Stemming words to their roots |
| Whoosh | 1 | Stemming words to their roots |

**`indexes`**

| Backend | Matches | Top results |
|---|---|---|
| this engine | 5 | The inverted index; Index segments; The corpus |
| SQL LIKE | 1 | Index segments |
| SQLite FTS5 | 5 | Index segments; The inverted index; The corpus |
| Whoosh | 5 | The inverted index; Index segments; The corpus |

**`core`**

| Backend | Matches | Top results |
|---|---|---|
| this engine | 1 | What is a document |
| SQL LIKE | 3 | What is a document; Scoring with BM25; Boosting important fields |
| SQLite FTS5 | 1 | What is a document |
| Whoosh | 1 | What is a document |

**`"inverted index"`**

| Backend | Matches | Top results |
|---|---|---|
| this engine | 3 | The inverted index; Query parsing; Building a Python search engine |
| SQL LIKE | 3 | The inverted index; Query parsing; Building a Python search engine |
| SQLite FTS5 | 3 | The inverted index; Query parsing; Building a Python search engine |
| Whoosh | 3 | The inverted index; Query parsing; Building a Python search engine |

**`search engines`**

| Backend | Matches | Top results |
|---|---|---|
| this engine | 5 | Building a Python search engine; Whoosh: search in pure Python; Why build in-house search |
| SQL LIKE | 0 | - |
| SQLite FTS5 | 5 | Building a Python search engine; Whoosh: search in pure Python; Why build in-house search |
| Whoosh | 5 | Building a Python search engine; Whoosh: search in pure Python; Why build in-house search |


### Speed on 10,000 synthetic docs

Median of 5 runs per query, in milliseconds, with the match count in brackets.

| Backend | Index time | `rise` | `parsing` | `wading` | `rise parsing` | `"against words"` |
|---|---|---|---|---|---|---|
| this engine | 9.26 s | 47.5 (9,997) | 29.5 (3,267) | 1.8 (387) | 25.7 (3,267) | 104.6 (2,387) |
| SQL LIKE | 0.07 s | 7.3 (9,997) | 12.6 (2,818) | 19.3 (387) | 14.0 (2,818) | 27.4 (2,220) |
| SQLite FTS5 | 0.17 s | 12.3 (9,997) | 3.5 (3,267) | 0.4 (387) | 7.3 (3,267) | 14.6 (2,240) |
| Whoosh | 7.03 s | 113.2 (9,997) | 16.2 (3,267) | 4.7 (387) | 86.0 (3,267) | 576.0 (2,349) |

## What this shows

**`LIKE` matches substrings, not words.** That breaks relevance in both directions:

- *Misses:* `indexes` finds 1 document instead of 5, because "index" and "indexing" don't
  contain the substring "indexes". `search engines` finds nothing, because the corpus says
  "search engine". Stemming fixes both.
- *False hits:* `core` also matches "**s**core" and "**s**coring", so it returns 3 documents
  where only 1 is about the core of something.
- *No ranking:* `LIKE` returns rows in table order. The three real engines agree on what
  matches and rank "The inverted index" first for `indexes`, because the word is in its
  boosted title.

**An inverted index does work in proportion to the matches, not to the corpus.** For the rare
word `wading` (387 of 10,000 docs), `LIKE` still scans every row and takes about 19 ms. This
engine looks up one postings list in 1.8 ms, and FTS5 in 0.4 ms. As the corpus grows,
`LIKE` gets slower for *every* query. The inverted index only slows down for queries
that match a lot.

**Where `LIKE` wins:** a word that appears in nearly every document (`rise` matches 9,997 of
10,000). There, scanning is as cheap as anything, while the engines also have to score and
sort every match. `LIKE` is also near-instant to "index", because it builds no index at all.

**Pure Python vs C.** This engine and Whoosh are in the same league: both take about 7–9 s
to index 10k documents, mostly spent in Python tokenizing and stemming. This engine searches
faster in this run, partly because Whoosh's phrase queries are slow. FTS5 does the same job
in C and is 50x faster to index and 3–10x faster to search. That is the talk's conclusion:
building a search engine in Python is the best way to understand one, but production systems
use Lucene, Solr, Elasticsearch (or FTS5 for small apps).

**Phrase counts differ slightly** (`"against words"`: 2,387 here vs 2,240 in FTS5). This engine
removes stop words *before* recording positions, so "against the words" counts as the phrase
"against words". FTS5 keeps stop words in its positions; Whoosh falls in between.

## Where this engine could get faster

- Cache corpus statistics (document counts, average lengths) between queries instead of
  recomputing them for every search.
- Skip facet counting when nobody asked for facets.
- Use top-k pruning (e.g. WAND) so common terms don't require scoring every matching document.
- Store postings in a compact binary format instead of JSON, to make indexing and loading faster.

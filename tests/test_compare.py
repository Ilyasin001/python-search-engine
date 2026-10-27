"""Smoke tests so the benchmark script keeps working as the engine changes."""

from benchmarks.compare import (
    QUALITY_QUERIES,
    OurEngine,
    SqliteFts5,
    SqlLike,
    available_backends,
    quality_report,
    speed_queries,
    speed_report,
    synthetic_docs,
)


def test_synthetic_corpus_is_reproducible():
    first, vocabulary = synthetic_docs(20, seed=1)
    second, _ = synthetic_docs(20, seed=1)
    assert first == second
    assert len(speed_queries(vocabulary)) == 5


def test_quality_report_covers_every_query():
    report = quality_report([OurEngine, SqlLike, SqliteFts5])
    for query in QUALITY_QUERIES:
        assert f"**`{query}`**" in report


def test_like_matches_substrings_but_engine_matches_words():
    report = quality_report([OurEngine, SqlLike])
    core = report.split("**`core`**")[1].split("**`")[0]
    assert "| this engine | 1 |" in core
    assert "| SQL LIKE | 3 |" in core


def test_speed_report_runs_every_available_backend():
    backends = available_backends()
    report = speed_report(backends, count=30, repeat=1, seed=3)
    for backend in backends:
        assert f"| {backend.name} |" in report

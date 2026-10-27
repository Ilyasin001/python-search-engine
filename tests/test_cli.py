import json
from pathlib import Path

import pytest

from searchengine.cli import main

SAMPLE = Path(__file__).parent.parent / "data" / "sample_docs.json"


@pytest.fixture
def index_dir(tmp_path):
    directory = tmp_path / "index"
    assert main(["--dir", str(directory), "index", str(SAMPLE)]) == 0
    return directory


def run(capsys, *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def test_no_command_prints_help(capsys):
    code, out, _ = run(capsys)
    assert code == 0
    assert "index" in out and "search" in out and "suggest" in out


def test_index_reports_count(tmp_path, capsys):
    code, out, _ = run(capsys, "--dir", str(tmp_path / "idx"), "index", str(SAMPLE))
    assert code == 0
    assert "indexed 16 documents" in out
    assert (tmp_path / "idx" / "manifest.json").exists()


def test_index_appends_unless_fresh(index_dir, capsys):
    _, out, _ = run(capsys, "--dir", str(index_dir), "index", str(SAMPLE))
    assert "(32 total)" in out
    _, out, _ = run(capsys, "--dir", str(index_dir), "index", str(SAMPLE), "--fresh")
    assert "(16 total)" in out


def test_index_jsonl(tmp_path, capsys):
    path = tmp_path / "docs.jsonl"
    path.write_text('{"title": "One"}\n\n{"title": "Two"}\n', encoding="utf-8")
    code, out, _ = run(capsys, "--dir", str(tmp_path / "idx"), "index", str(path))
    assert code == 0 and "indexed 2 documents" in out


def test_search_prints_ranked_hits_and_facets(index_dir, capsys):
    code, out, _ = run(capsys, "--dir", str(index_dir), "search", "inverted index")
    assert code == 0
    assert out.startswith("3 results for (invert AND index)")
    assert "1. The inverted index  [data-structures]" in out
    assert "\ncategory: " in out


def test_search_with_filter_and_limit(index_dir, capsys):
    _, out, _ = run(capsys, "--dir", str(index_dir), "search", "", "-f", "category=text-analysis", "-n", "1")
    assert "(showing the top 1)" in out
    assert "category: text-analysis (" in out


def test_search_any_uses_or(index_dir, capsys):
    _, both, _ = run(capsys, "--dir", str(index_dir), "search", "faceting boosting")
    _, either, _ = run(capsys, "--dir", str(index_dir), "search", "faceting boosting", "--any")
    assert int(either.split()[0]) > int(both.split()[0])


def test_suggest(index_dir, capsys):
    code, out, _ = run(capsys, "--dir", str(index_dir), "suggest", "inverted ind")
    assert code == 0
    assert out.splitlines()[0] == "inverted index"


def test_bad_filter_is_an_error(index_dir, capsys):
    code, _, err = run(capsys, "--dir", str(index_dir), "search", "x", "-f", "category")
    assert code == 1 and "field=value" in err


def test_unreadable_index_suggests_rebuild(tmp_path, capsys):
    directory = tmp_path / "old"
    directory.mkdir()
    (directory / "manifest.json").write_text(json.dumps({"segments": [], "unknown": 1}), encoding="utf-8")
    code, _, err = run(capsys, "--dir", str(directory), "search", "x")
    assert code == 1 and "--fresh" in err


def test_fresh_refuses_to_delete_other_files(tmp_path, capsys):
    directory = tmp_path / "notes"
    directory.mkdir()
    (directory / "important.txt").write_text("keep me", encoding="utf-8")
    code, _, err = run(capsys, "--dir", str(directory), "index", str(SAMPLE), "--fresh")
    assert code == 1 and "refusing" in err
    assert (directory / "important.txt").exists()


def test_missing_file_is_an_error(tmp_path, capsys):
    code, _, err = run(capsys, "--dir", str(tmp_path / "idx"), "index", str(tmp_path / "nope.json"))
    assert code == 1 and "error:" in err

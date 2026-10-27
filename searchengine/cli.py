"""Command-line interface: `python -m searchengine ...`

searchengine index data/sample_docs.json --fresh
searchengine search '"inverted index" OR stemming' --filter category=concepts
searchengine suggest "inv"
"""

import argparse
import json
import shutil
import sys
import textwrap
from pathlib import Path

from searchengine import __version__
from searchengine.engine import Engine, SearchResults

DEFAULT_DIR = "index"
FIELDS = ["title", "body"]
BOOSTS = {"title": 2.0}
FACET_FIELDS = ["category", "tags"]


class CliError(Exception):
    pass


def open_engine(directory: str) -> Engine:
    try:
        return Engine(directory, fields=FIELDS, boosts=BOOSTS, facet_fields=FACET_FIELDS)
    except (KeyError, TypeError, ValueError) as error:
        raise CliError(
            f"the index in '{directory}' can't be read ({error!r}); "
            "rebuild it with: searchengine index FILE --fresh"
        ) from error


def load_documents(path: Path) -> list[dict]:
    """A JSON array of objects, or JSON Lines (one object per line). Any "id" key is dropped."""
    text = path.read_text(encoding="utf-8")
    try:
        records = (
            json.loads(text)
            if path.suffix == ".json"
            else [json.loads(line) for line in text.splitlines() if line.strip()]
        )
    except json.JSONDecodeError as error:
        raise CliError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise CliError(f"{path} must contain a list of JSON objects")
    return [{k: v for k, v in record.items() if k != "id"} for record in records]


def remove_index(directory: Path) -> None:
    """Delete an index directory, refusing if it holds anything an index wouldn't."""
    if not directory.exists():
        return
    unexpected = [
        p.name
        for p in directory.iterdir()
        if not (
            p.name == "manifest.json" or (p.name.startswith("segment_") and p.suffix in (".json", ".tmp"))
        )
    ]
    if unexpected:
        raise CliError(f"refusing to delete '{directory}': it contains non-index files {unexpected}")
    shutil.rmtree(directory)


def parse_filters(pairs: list[str]) -> dict[str, list[str]]:
    filters: dict[str, list[str]] = {}
    for pair in pairs:
        field, sep, value = pair.partition("=")
        if not sep or not field or not value:
            raise CliError(f"--filter expects field=value, got '{pair}'")
        filters.setdefault(field, []).append(value)
    return filters


def print_results(results: SearchResults) -> None:
    shown = len(results.hits)
    print(f"{results.total} result{'s' if results.total != 1 else ''} for {results.query or 'everything'}")
    if shown < results.total:
        print(f"(showing the top {shown})")
    for rank, hit in enumerate(results.hits, 1):
        fields = hit.doc.fields
        title = fields.get("title", "(untitled)")
        category = f"  [{fields['category']}]" if "category" in fields else ""
        print(f"\n{rank:>3}. {title}{category}  score={hit.score:.2f}  id={hit.doc.id}")
        body = str(fields.get("body", ""))
        if body:
            print(textwrap.indent(textwrap.shorten(body, 150, placeholder=" ..."), "     "))
    for field, counts in results.facets.items():
        if counts:
            print(f"\n{field}: " + ", ".join(f"{value} ({count})" for value, count in counts))


def cmd_index(args: argparse.Namespace) -> None:
    docs = load_documents(Path(args.file))
    if args.fresh:
        remove_index(Path(args.dir))
    with open_engine(args.dir) as engine:
        ids = engine.index_many(docs)
    print(f"indexed {len(ids)} documents into '{args.dir}' ({engine.doc_count} total)")


def cmd_search(args: argparse.Namespace) -> None:
    engine = open_engine(args.dir)
    operator = "OR" if args.any else "AND"
    print_results(engine.search(args.query, args.limit, parse_filters(args.filter), operator))


def cmd_suggest(args: argparse.Namespace) -> None:
    for suggestion in open_engine(args.dir).suggest(args.prefix, args.limit):
        print(suggestion)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="searchengine", description="A small search engine in pure Python.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--dir", default=DEFAULT_DIR, help=f"index directory (default: {DEFAULT_DIR})")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    index = commands.add_parser("index", help="add documents from a .json or .jsonl file")
    index.add_argument("file")
    index.add_argument("--fresh", action="store_true", help="delete the existing index first")
    index.set_defaults(run=cmd_index)

    search = commands.add_parser("search", help="search the index")
    search.add_argument("query", help="e.g. '\"inverted index\" OR stemming -lucene'")
    search.add_argument("-n", "--limit", type=int, default=10)
    search.add_argument(
        "-f", "--filter", action="append", default=[], metavar="FIELD=VALUE", help="facet filter (repeatable)"
    )
    search.add_argument("--any", action="store_true", help="join bare words with OR instead of AND")
    search.set_defaults(run=cmd_search)

    suggest = commands.add_parser("suggest", help="autocomplete a partial query")
    suggest.add_argument("prefix")
    suggest.add_argument("-n", "--limit", type=int, default=5)
    suggest.set_defaults(run=cmd_suggest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        args.run(args)
    except (CliError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0

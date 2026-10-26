"""Command-line interface: `python -m searchengine ...`"""

import argparse

from searchengine import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="searchengine", description="A small search engine in pure Python.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0

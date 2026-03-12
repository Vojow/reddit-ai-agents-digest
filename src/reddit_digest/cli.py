"""Command-line entrypoint for the Reddit digest project."""

from __future__ import annotations

import argparse
from typing import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reddit-digest")
    parser.add_argument(
        "--version",
        action="version",
        version="reddit-ai-agents-digest 0.1.0",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="help",
        help="Reserved for future pipeline commands.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

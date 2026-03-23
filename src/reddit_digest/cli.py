"""Command-line entrypoint for the Reddit digest project."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Sequence

from reddit_digest.pipeline import PipelineRunner
from reddit_digest.preflight import format_preflight_result
from reddit_digest.preflight import run_preflight
from reddit_digest.utils.logging import configure_logging

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reddit-digest")
    parser.add_argument(
        "--version",
        action="version",
        version="reddit-ai-agents-digest 0.1.0",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_daily = subparsers.add_parser("run-daily", help="Run the full daily digest pipeline.")
    run_daily.add_argument("--date", dest="run_date", default=date.today().isoformat(), help="Run date in YYYY-MM-DD format.")
    run_daily.add_argument("--base-path", default=".", help="Repository base path.")
    run_daily.add_argument("--skip-sheets", action="store_true", help="Skip Google Sheets export.")
    run_daily.add_argument(
        "--markdown-only",
        action="store_true",
        help="Skip OpenAI enrichments and only write the deterministic markdown digest.",
    )
    preflight = subparsers.add_parser("preflight", help="Check whether the daily digest can start successfully.")
    preflight.add_argument("--base-path", default=".", help="Repository base path.")
    preflight.add_argument("--skip-sheets", action="store_true", help="Skip Google Sheets export checks.")
    preflight.add_argument(
        "--markdown-only",
        action="store_true",
        help="Skip OpenAI enrichments and only validate the deterministic markdown run path.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run-daily":
        configure_logging()
        runner = PipelineRunner(base_path=Path(args.base_path))
        runner.run(
            run_date=args.run_date,
            skip_sheets=args.skip_sheets,
            skip_openai=args.markdown_only,
        )
        return 0
    if args.command == "preflight":
        result = run_preflight(
            base_path=Path(args.base_path),
            skip_sheets=args.skip_sheets,
            markdown_only=args.markdown_only,
        )
        print(format_preflight_result(result), end="")
        return 0 if result.ok else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

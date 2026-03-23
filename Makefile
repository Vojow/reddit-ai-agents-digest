.PHONY: install test lint run run-markdown

install:
	uv sync

test:
	uv run pytest

lint:
	uv run python -m compileall src tests

run:
	uv run reddit-digest --help

run-markdown:
	./scripts/run_markdown_with_env.sh

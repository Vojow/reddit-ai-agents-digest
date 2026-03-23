.PHONY: install test lint run preflight run-markdown

install:
	uv sync

test:
	uv run pytest

lint:
	uv run python -m compileall src tests

run:
	uv run reddit-digest --help

preflight:
	./scripts/run_markdown_with_env.sh --preflight-only

run-markdown:
	./scripts/run_markdown_with_env.sh

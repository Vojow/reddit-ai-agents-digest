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
	uv run reddit-digest preflight --base-path . --skip-sheets --markdown-only

run-markdown:
	uv run reddit-digest preflight --base-path . --skip-sheets --markdown-only
	uv run reddit-digest run-daily --base-path . --skip-sheets --markdown-only

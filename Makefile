.PHONY: install test lint run

install:
	uv sync

test:
	uv run pytest

lint:
	uv run python -m compileall src tests

run:
	uv run reddit-digest --help

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(relative_path: str) -> Any:
    fixture_path = FIXTURES_DIR / relative_path
    if fixture_path.suffix == ".json":
        return json.loads(fixture_path.read_text())
    return fixture_path.read_text()


@pytest.fixture
def sample_posts_payload() -> list[dict[str, Any]]:
    return load_fixture("raw/sample_posts.json")


@pytest.fixture
def sample_comments_payload() -> list[dict[str, Any]]:
    return load_fixture("raw/sample_comments.json")


@pytest.fixture
def sample_digest_markdown() -> str:
    return load_fixture("processed/sample_digest.md")

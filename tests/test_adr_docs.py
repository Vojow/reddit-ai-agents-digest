from __future__ import annotations

from pathlib import Path


def test_adr_index_and_seed_decisions_are_present() -> None:
    architecture = (Path.cwd() / "docs" / "architecture.md").read_text()
    index = (Path.cwd() / "docs" / "adr" / "README.md").read_text()

    assert "docs/adr/README.md" in architecture
    assert "ADR-0001" in index
    assert "ADR-0002" in index
    assert "ADR-0003" in index
    assert "ADR-0004" in index
    assert "ADR-0005" in index

    for filename in (
        "0001-deterministic-markdown-is-canonical.md",
        "0002-llm-output-is-advisory.md",
        "0003-public-reddit-json-ingestion.md",
        "0004-self-hosted-actions-for-live-collection.md",
        "0005-reruns-overwrite-and-upsert.md",
    ):
        content = (Path.cwd() / "docs" / "adr" / filename).read_text()
        assert "Status: Accepted" in content
        assert "## Context" in content
        assert "## Decision" in content
        assert "## Consequences" in content

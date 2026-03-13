from __future__ import annotations

from pathlib import Path


def test_docs_describe_dual_markdown_outputs() -> None:
    readme = (Path.cwd() / "README.md").read_text()
    operations = (Path.cwd() / "docs" / "operations.md").read_text()
    architecture = (Path.cwd() / "docs" / "architecture.md").read_text()
    digest_format = (Path.cwd() / "docs" / "digest-format.md").read_text()
    agents = (Path.cwd() / "AGENTS.md").read_text()

    assert "reports/daily/YYYY-MM-DD.llm.md" in readme
    assert "source of record" in readme
    assert "reports/latest.llm.md" in operations
    assert "data/processed/topic_rewrites/YYYY-MM-DD.json" in operations
    assert "same selected topics" in operations
    assert "reports/latest.llm.md" in architecture
    assert "does not create same-day Reddit findings or choose topics" in architecture
    assert "## Picked Topics" in digest_format
    assert "## Emerging Themes" in digest_format
    assert "## Watch Next" in digest_format
    assert "Top Tools Mentioned" not in digest_format
    assert "Optional LLM-enhanced digest" in agents
    assert "it may only rewrite topic prose" in agents

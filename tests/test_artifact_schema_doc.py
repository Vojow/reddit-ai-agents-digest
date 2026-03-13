from __future__ import annotations

from pathlib import Path


def test_artifact_schema_doc_covers_persisted_families_and_links() -> None:
    operations = (Path.cwd() / "docs" / "operations.md").read_text()
    architecture = (Path.cwd() / "docs" / "architecture.md").read_text()
    document = (Path.cwd() / "docs" / "artifact-schemas.md").read_text()

    assert "docs/artifact-schemas.md" in operations
    assert "docs/artifact-schemas.md" in architecture
    assert "data/raw/posts/YYYY-MM-DD.json" in document
    assert "data/raw/comments/YYYY-MM-DD.json" in document
    assert "data/processed/insights/YYYY-MM-DD.json" in document
    assert "data/processed/suggestions/YYYY-MM-DD.json" in document
    assert "data/processed/topic_rewrites/YYYY-MM-DD.json" in document
    assert "data/processed/executive_summary_rewrites/YYYY-MM-DD.json" in document
    assert "data/state/YYYY-MM-DD.json" in document
    assert "Raw_Posts" in document
    assert "Insights" in document
    assert "Daily_Digest" in document
    assert "Source-of-record local outputs" in document
    assert "Advisory outputs" in document

from __future__ import annotations

from pathlib import Path


def test_rerun_runbook_is_linked_from_operations_and_covers_main_scenarios() -> None:
    operations = (Path.cwd() / "docs" / "operations.md").read_text()
    document = (Path.cwd() / "docs" / "rerun-runbook.md").read_text()

    assert "docs/rerun-runbook.md" in operations
    assert "collection succeeded, later deterministic stage failed" in document
    assert "deterministic markdown succeeded, LLM rewrite failed" in document
    assert "Sheets export failed after local artifacts were written" in document
    assert "Teams delivery failed" in document
    assert "rerun a past date safely" in document
    assert "uv run reddit-digest run-daily --date YYYY-MM-DD --skip-sheets --markdown-only" in document
    assert "make preflight" in document
    assert "uv run reddit-digest preflight --base-path . --skip-sheets --markdown-only" in document
    assert "reports/daily/YYYY-MM-DD.md" in document
    assert "data/state/YYYY-MM-DD.json" in document

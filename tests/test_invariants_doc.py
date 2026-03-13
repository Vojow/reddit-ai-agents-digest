from __future__ import annotations

from pathlib import Path


def test_invariants_doc_is_linked_from_readme_and_agents() -> None:
    readme = (Path.cwd() / "README.md").read_text()
    agents = (Path.cwd() / "AGENTS.md").read_text()
    invariants = (Path.cwd() / "docs" / "invariants.md").read_text()

    assert "docs/invariants.md" in readme
    assert "docs/invariants.md" in agents
    assert "canonical report" in invariants
    assert "OpenAI output is advisory only" in invariants
    assert "Same-day reruns overwrite file outputs" in invariants
    assert "must not create duplicate rows" in invariants

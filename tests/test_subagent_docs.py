from __future__ import annotations

from pathlib import Path
import tomllib


def test_subagent_docs_are_linked_and_structured() -> None:
    agents = (Path.cwd() / "AGENTS.md").read_text()
    index = (Path.cwd() / "docs" / "subagents.md").read_text()
    config = (Path.cwd() / ".codex" / "config.toml").read_text()

    assert "docs/subagents.md" in agents
    assert ".codex/agents/" in agents
    assert "four-role Codex squad" in index
    assert ".codex/agents/" in index
    assert ".codex/config.toml" in index
    assert "Architect" in index
    assert "Doc reader/writer" in index
    assert "SDET" in index
    assert "Developer" in index
    assert "config/subreddits.yaml" in index
    assert "ClaudeAI" in index
    assert "Do not put these role definitions in `~/.codex/config.toml`." in index
    assert "[agents] max_threads = 4" in index
    assert "[agents] max_depth = 1" in index
    assert "[agents]" in config

    required_headings = (
        "## Role name",
        "## `agent_type`",
        "## Model",
        "## Default effort",
        "## Escalation triggers",
        "## Write scope",
        "## Must-read inputs",
        "## Required outputs",
        "## Stop conditions",
        "## Codex runtime file",
    )
    role_docs = (
        Path.cwd() / "docs" / "subagents" / "architect.md",
        Path.cwd() / "docs" / "subagents" / "doc-reader-writer.md",
        Path.cwd() / "docs" / "subagents" / "sdet.md",
        Path.cwd() / "docs" / "subagents" / "developer.md",
    )

    for path in role_docs:
        content = path.read_text()
        for heading in required_headings:
            assert heading in content


def test_project_local_subagent_toml_files_exist_and_have_required_fields() -> None:
    config_path = Path.cwd() / ".codex" / "config.toml"
    config = tomllib.loads(config_path.read_text())

    assert config["agents"]["max_threads"] == 4
    assert config["agents"]["max_depth"] == 1

    expected_agents = (
        ("architect.toml", "architect", "gpt-5.4", "high", "read-only"),
        ("doc-reader-writer.toml", "doc_reader_writer", "gpt-5.4-mini", "medium", "workspace-write"),
        ("sdet.toml", "sdet", "gpt-5.3-codex", "medium", "workspace-write"),
        ("developer.toml", "developer", "gpt-5.3-codex", "medium", "workspace-write"),
    )

    for filename, name, model, effort, sandbox in expected_agents:
        path = Path.cwd() / ".codex" / "agents" / filename
        payload = tomllib.loads(path.read_text())

        assert payload["name"] == name
        assert payload["description"]
        assert payload["developer_instructions"]
        assert payload["model"] == model
        assert payload["model_reasoning_effort"] == effort
        assert payload["sandbox_mode"] == sandbox
